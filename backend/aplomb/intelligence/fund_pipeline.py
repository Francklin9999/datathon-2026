"""SEC N-PORT fund holdings acquisition, session-owned persistence and look-through.

A fund is identified by its SEC series ID (``S`` + 9 digits). A fund ISIN is accepted
only through an explicitly documented series/ISIN mapping (``data/fund-isin-mappings.json``);
tickers and names never establish identity. Filing discovery results are not trusted
for identity either: the primary document's own ``genInfo/seriesId`` must match.

Every SEC request requires ``APLOMB_SEC_CONTACT`` (descriptive ``Organization email``
User-Agent, per SEC fair-access policy). A missing contact or an HTTP 403 is reported as
an explicit unavailable state; there is no retry with other headers, no redirect
following and no alternate host.

Availability: SEC acceptance time when the registrant's EDGAR submissions record lists
the accession; otherwise retrieval time. Report period date is never treated as
availability. Captures are immutable and content-addressed by source hash.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import socket
import time as _time
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .entities import Evidence, valid_isin
from .holdings_ingest import nport_positions
from .overlap import Holding, HoldingsSnapshot

SERIES_RE = re.compile(r'S\d{9}')
CIK_RE = re.compile(r'\d{1,10}')
ACCESSION_RE = re.compile(r'\d{10}-\d{2}-\d{6}')
CONTACT_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._-]{1,79} [^\s@]+@[^\s@]+\.[^\s@]+')
ALLOWED_HOSTS = frozenset({'www.sec.gov', 'data.sec.gov'})
NPORT_FORMS = ('NPORT-P', 'NPORT-P/A')
MAX_SCAN = 8
MAX_DOC_BYTES = 15_000_000
MAX_INDEX_BYTES = 12_000_000
MAPPINGS = Path(__file__).resolve().parent / 'data/fund-isin-mappings.json'
LICENCE = 'SEC EDGAR public filing (U.S. government work); SEC fair-access policy applies'


class FundPipelineError(RuntimeError):
    """``str(exc)`` is a stable reason code safe to return to clients."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _contact() -> str:
    contact = os.getenv('APLOMB_SEC_CONTACT', '')
    if not CONTACT_RE.fullmatch(contact):
        raise FundPipelineError('operator_contact_unconfigured')
    return contact


def fetch(url: str, *, accept: str, limit: int) -> bytes:
    """Single bounded HTTPS GET to an SEC host with the declared operator contact."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in ALLOWED_HOSTS or parts.username or parts.password:
        raise FundPipelineError('source_not_allowed')
    request = Request(url, headers={'User-Agent': _contact(), 'Accept': accept})
    try:
        with build_opener(_NoRedirect).open(request, timeout=15) as response:
            if response.status != 200:
                raise FundPipelineError('source_unavailable')
            body = response.read(limit + 1)
    except HTTPError as exc:
        if exc.code == 403:
            # Respect the access control: no header rotation or alternate route.
            raise FundPipelineError('source_forbidden') from None
        if exc.code == 404:
            raise FundPipelineError('source_not_found') from None
        if exc.code == 429:
            raise FundPipelineError('source_rate_limited') from None
        raise FundPipelineError('source_unavailable') from None
    except (URLError, OSError, socket.timeout):
        raise FundPipelineError('source_unavailable') from None
    finally:
        # Stay well under SEC's documented 10 requests/second ceiling.
        _time.sleep(0.15)
    if len(body) > limit:
        raise FundPipelineError('source_too_large')
    return body


# --------------------------------------------------------------------------- mappings

def documented_mappings() -> list[dict]:
    """Series/ISIN pairs backed by independently documented source records."""
    data = json.loads(MAPPINGS.read_bytes())
    rows = []
    for row in data['mappings']:
        if not SERIES_RE.fullmatch(row['series_id']) or not valid_isin(row['fund_isin']):
            raise ValueError('invalid documented mapping')
        rows.append(row)
    return rows


def mapping_for(*, series_id: str | None = None, fund_isin: str | None = None) -> dict | None:
    for row in documented_mappings():
        if (series_id and row['series_id'] == series_id) or (fund_isin and row['fund_isin'] == fund_isin):
            return row
    return None


def resolve_fund(fund_id: str) -> tuple[str, dict | None]:
    """Return (series_id, mapping). An ISIN resolves only through a documented mapping."""
    value = (fund_id or '').strip().upper().removeprefix('ISIN:')
    if SERIES_RE.fullmatch(value):
        return value, mapping_for(series_id=value)
    if valid_isin(value):
        mapping = mapping_for(fund_isin=value)
        if mapping is None:
            raise FundPipelineError('fund_isin_mapping_undocumented')
        return mapping['series_id'], mapping
    raise FundPipelineError('invalid_fund_identifier')


def _mapping_available_at(mapping: dict) -> datetime:
    return datetime.fromisoformat(mapping['available_at'].replace('Z', '+00:00')).astimezone(timezone.utc)


# --------------------------------------------------------------------------- discovery

def _safe_xml(payload: bytes) -> ET.Element:
    head = payload.upper()
    if b'<!DOCTYPE' in head or b'<!ENTITY' in head:
        raise FundPipelineError('invalid_response')
    try:
        return ET.fromstring(payload)
    except ET.ParseError:
        raise FundPipelineError('invalid_response') from None


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def browse_url(series_id: str) -> str:
    return 'https://www.sec.gov/cgi-bin/browse-edgar?' + urlencode({
        'action': 'getcompany', 'CIK': series_id, 'type': 'NPORT-P', 'dateb': '',
        'owner': 'include', 'count': '10', 'output': 'atom'})


def parse_browse(payload: bytes) -> list[dict]:
    """EDGAR company-browse Atom entries -> candidate filings (discovery only)."""
    root = _safe_xml(payload)
    rows = []
    for entry in (e for e in root.iter() if _local(e.tag) == 'entry'):
        fields = {_local(e.tag): (e.text or '').strip() for e in entry.iter()}
        accession = fields.get('accession-number') or fields.get('accession-nunber') or ''
        form = fields.get('filing-type') or next(
            (e.get('term', '') for e in entry if _local(e.tag) == 'category'), '')
        href = fields.get('filing-href') or ''
        match = re.search(r'/Archives/edgar/data/(\d{1,10})/(\d{18})/', urlsplit(href).path)
        if not ACCESSION_RE.fullmatch(accession) or form not in NPORT_FORMS or not match:
            continue
        if match.group(2) != accession.replace('-', ''):
            continue
        try:
            filing_date = date.fromisoformat(fields.get('filing-date', '')).isoformat()
        except ValueError:
            filing_date = None
        rows.append({'accession': accession, 'cik': match.group(1).zfill(10), 'form': form,
                     'filing_date': filing_date, 'primary_document': 'primary_doc.xml',
                     'acceptance_raw': None})
    return sorted(rows, key=lambda r: (r['filing_date'] or '', r['accession']), reverse=True)


def submissions_url(cik: str) -> str:
    return f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'


def parse_submissions(payload: bytes) -> list[dict]:
    """Registrant submissions JSON -> its recent N-PORT-P filings with acceptance times."""
    try:
        data = json.loads(payload)
        cik = str(int(data['cik'])).zfill(10)
        recent = data['filings']['recent']
        columns = ('accessionNumber', 'form', 'filingDate', 'acceptanceDateTime', 'primaryDocument')
        if len({len(recent[c]) for c in columns}) != 1:
            raise ValueError('ragged columns')
        rows = []
        for accession, form, filing_date, accepted, primary in zip(*(recent[c] for c in columns), strict=True):
            if form not in NPORT_FORMS or not ACCESSION_RE.fullmatch(str(accession)):
                continue
            name = str(primary).rsplit('/', 1)[-1]
            rows.append({'accession': accession, 'cik': cik, 'form': form,
                         'filing_date': date.fromisoformat(filing_date).isoformat(),
                         'primary_document': name if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}\.xml', name) else 'primary_doc.xml',
                         'acceptance_raw': str(accepted) if accepted else None})
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        raise FundPipelineError('invalid_response') from None
    return sorted(rows, key=lambda r: (r['filing_date'], r['accession']), reverse=True)


def acceptance_upper_bound(raw: str | None) -> datetime | None:
    """Latest UTC instant consistent with the EDGAR acceptance wall-clock value.

    The ``Z`` suffix on EDGAR ``acceptanceDateTime`` is not relied on: reading the
    wall clock as US Eastern (UTC-5 at most) is later than reading it as UTC, so +5h is
    a conservative upper bound that never makes a filing visible too early.
    """
    if not raw:
        return None
    try:
        wall = datetime.fromisoformat(raw.replace('Z', '').split('+')[0])
    except ValueError:
        return None
    return wall.replace(tzinfo=timezone.utc) + timedelta(hours=5)


def filing_urls(cik: str, accession: str, primary: str = 'primary_doc.xml') -> dict:
    base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}'
    return {'primary_doc_url': f'{base}/{primary}', 'index_url': f'{base}/{accession}-index.htm'}


# --------------------------------------------------------------------------- look-through

def _dec(value: str | None) -> Decimal:
    try:
        return Decimal(value) if value is not None else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


def compute_lookthrough(positions: list[dict]) -> dict:
    """Quantify resolved, derivative, short and unidentified parts of the report.

    Weights are N-PORT ``pctVal`` (percent of net assets). A derivative's pctVal is its
    fair value, not its notional, so derivative rows are flagged and excluded from
    constituent weights: direct holdings are not economic exposure.
    """
    constituents: dict[str, dict] = {}
    derivatives, shorts, unidentified, missing_weight = [], [], [], []
    for p in positions:
        pct = p['pct_of_net_assets']
        if p['derivative']:
            derivatives.append({k: p[k] for k in ('row', 'name', 'asset_category', 'derivative_kind',
                                                  'pct_of_net_assets', 'value_usd', 'payoff_profile')})
            continue
        if pct is None:
            missing_weight.append(p['row'])
            continue
        if p['payoff_profile'] == 'Short' or pct < 0:
            shorts.append({k: p[k] for k in ('row', 'name', 'isin', 'asset_category', 'pct_of_net_assets', 'value_usd')})
            continue
        if not p['isin']:
            unidentified.append({'row': p['row'], 'name': p['name'], 'asset_category': p['asset_category'],
                                 'pct_of_net_assets': pct, 'has_lei': bool(p['lei']), 'has_cusip': bool(p['cusip']),
                                 'reason': 'isin_reported_invalid' if p['isin_reported_invalid'] else 'no_isin_reported'})
            continue
        item = constituents.setdefault(p['isin'], {
            'security_id': 'isin:' + p['isin'], 'isin': p['isin'], 'weights': [], 'values': [],
            'names': [], 'leis': set(), 'asset_categories': set(), 'rows': []})
        item['weights'].append(pct)
        item['values'].append(_dec(p['value_usd']))
        if p['name'] and p['name'] not in item['names']:
            item['names'].append(p['name'])
        if p['lei']:
            item['leis'].add(p['lei'])
        if p['asset_category']:
            item['asset_categories'].add(p['asset_category'])
        item['rows'].append(p['row'])
    rows = []
    for item in constituents.values():
        rows.append({'security_id': item['security_id'], 'isin': item['isin'],
                     'weight_pct': math.fsum(item['weights']), 'value_usd': str(sum(item['values'], Decimal(0))),
                     'reported_names': item['names'][:3], 'leis': sorted(item['leis']),
                     'asset_categories': sorted(item['asset_categories']), 'source_rows': item['rows'][:20],
                     'direct_equity': item['asset_categories'] == {'EC'}})
    rows.sort(key=lambda r: (-r['weight_pct'], r['isin']))
    covered = math.fsum(r['weight_pct'] for r in rows)
    equity = math.fsum(r['weight_pct'] for r in rows if r['direct_equity'])
    derivative_pct = math.fsum(d['pct_of_net_assets'] or 0 for d in derivatives)
    short_pct = math.fsum(s['pct_of_net_assets'] or 0 for s in shorts)
    unidentified_pct = math.fsum(u['pct_of_net_assets'] for u in unidentified)
    warnings = []
    if derivatives:
        kinds = sorted({d['derivative_kind'] or d['asset_category'] or 'unspecified' for d in derivatives})
        warnings.append({'code': 'derivatives_present', 'kinds': kinds,
                         'message': 'Derivatives (e.g. swaps) are reported at fair value, not notional. '
                                    'Direct holdings are not the fund\'s economic exposure; leverage is not measured.'})
    if shorts:
        warnings.append({'code': 'short_positions_present', 'message': 'Short positions are excluded from constituent weights.'})
    if covered > 100.01:
        warnings.append({'code': 'covered_exceeds_net_assets',
                         'message': 'Resolved long positions exceed 100% of net assets (borrowing or liabilities); '
                                    'remainder is negative and cannot be read as cash.'})
    return {
        'constituents': rows,
        'constituent_count': len(rows),
        'covered_pct': covered,
        'direct_equity_pct': equity,
        'unknown_remainder_pct': 100 - covered,
        'unknown_remainder_breakdown': {
            'unidentified_long_pct': unidentified_pct,
            'derivatives_fair_value_pct': derivative_pct,
            'short_positions_pct': short_pct,
            'positions_without_weight': len(missing_weight),
            'unexplained_pct': 100 - covered - unidentified_pct - derivative_pct - short_pct,
        },
        'unidentified_positions': unidentified[:200],
        'unidentified_count': len(unidentified),
        'derivatives': derivatives[:200],
        'derivative_count': len(derivatives),
        'short_positions': shorts[:200],
        'warnings': warnings,
        'limitations': [
            'Constituent identity is the explicit ISIN reported in the filing; no name, ticker or CUSIP matching.',
            'The unknown remainder is unknown, not zero exposure. It includes cash, other assets/liabilities, '
            'unidentified positions and derivative effects.',
            'Weights are as of the report date, not current positions.',
        ],
    }


# --------------------------------------------------------------------------- persistence

def _owner(session_id: str) -> str:
    if not session_id:
        raise FundPipelineError('invalid_session')
    return hashlib.sha256(session_id.encode()).hexdigest()


def _keys(session_id: str) -> dict:
    owner = _owner(session_id)
    return {'index': 'FUND_NPORT_INDEX#' + owner, 'capture': 'FUND_NPORT#' + owner, 'raw': 'FUND_NPORT_RAW#' + owner}


def _persist(store, session_id: str, record: dict, raw: bytes) -> dict:
    from aplomb.api.errors import Conflict
    from aplomb.api.storage import Write

    keys = _keys(session_id)
    sha = record['source_sha256']
    try:
        raw_text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise FundPipelineError('invalid_response') from None
    try:
        store.transact([Write('cache', keys['raw'], 'RAW#' + sha,
                              {'revision': 1, 'sessionId': session_id, 'sha256': sha, 'raw': raw_text}, None)])
    except Conflict:
        old = store.get('cache', keys['raw'], 'RAW#' + sha)
        if not old or old.get('sessionId') != session_id or old.get('sha256') != sha:
            raise FundPipelineError('capture_conflict') from None
    summary = {k: record[k] for k in ('capture_id', 'dataset_version', 'series_id', 'fund_isin', 'series_name',
                                      'report_date', 'available_at', 'availability_basis', 'retrieved_at',
                                      'accession', 'form', 'source_sha256', 'position_count')}
    sk = 'CAPTURE#' + record['capture_id']
    try:
        store.transact([
            Write('cache', keys['capture'], sk, {'revision': 1, 'sessionId': session_id, 'record': record}, None),
            Write('cache', keys['index'], sk, {'revision': 1, 'sessionId': session_id, 'summary': summary}, None),
        ])
    except Conflict:
        old = store.get('cache', keys['capture'], sk)
        if not old or old.get('sessionId') != session_id or old['record']['source_sha256'] != sha:
            raise FundPipelineError('capture_conflict') from None
        # Immutable: an identical re-ingest keeps the first retrieval time.
        return old['record']
    return record


def list_funds(store, session_id: str) -> list[dict]:
    rows = [x['summary'] for x in store.query('cache', _keys(session_id)['index']) if x.get('sessionId') == session_id]
    return sorted(rows, key=lambda r: (r['series_id'], r['report_date'], r['available_at']), reverse=True)


def get_capture(store, session_id: str, capture_id: str) -> dict | None:
    if not re.fullmatch(r'[0-9a-f]{64}', capture_id or ''):
        return None
    item = store.get('cache', _keys(session_id)['capture'], 'CAPTURE#' + capture_id)
    return item['record'] if item and item.get('sessionId') == session_id else None


# --------------------------------------------------------------------------- ingestion

def ingest(store, session_id: str, series_id: str, *, cik: str | None = None, accession: str | None = None,
           get=fetch, now=None) -> dict:
    """Acquire and persist the latest N-PORT-P for a series (or an exact accession)."""
    series_id = (series_id or '').strip().upper()
    if not SERIES_RE.fullmatch(series_id):
        raise FundPipelineError('invalid_series_id')
    if cik is not None and not CIK_RE.fullmatch(cik):
        raise FundPipelineError('invalid_cik')
    if accession is not None and (not ACCESSION_RE.fullmatch(accession) or cik is None):
        raise FundPipelineError('invalid_accession')
    _owner(session_id)
    limitations: list[str] = []
    discovery_url: str | None = None
    if cik is not None:
        discovery_url = submissions_url(cik)
        filings = parse_submissions(get(discovery_url, accept='application/json', limit=MAX_INDEX_BYTES))
        if accession is not None:
            filings = [f for f in filings if f['accession'] == accession] or [
                {'accession': accession, 'cik': cik.zfill(10), 'form': None, 'filing_date': None,
                 'primary_document': 'primary_doc.xml', 'acceptance_raw': None}]
        discovery = 'registrant_submissions'
    else:
        discovery_url = browse_url(series_id)
        filings = parse_browse(get(discovery_url, accept='application/atom+xml, application/xml', limit=2_000_000))
        discovery = 'series_browse'
        if filings:
            try:
                accepted = {f['accession']: f for f in parse_submissions(
                    get(submissions_url(filings[0]['cik']), accept='application/json', limit=MAX_INDEX_BYTES))}
                for f in filings:
                    if f['accession'] in accepted:
                        f['acceptance_raw'] = accepted[f['accession']]['acceptance_raw']
                        f['primary_document'] = accepted[f['accession']]['primary_document']
            except FundPipelineError as exc:
                if str(exc) == 'operator_contact_unconfigured':
                    raise
                limitations.append('Registrant submissions index unavailable; acceptance time not established.')
    if not filings:
        raise FundPipelineError('no_filing_found')
    selected = parsed = raw = None
    scanned = 0
    for filing in filings[:MAX_SCAN]:
        urls = filing_urls(filing['cik'], filing['accession'], filing['primary_document'])
        body = get(urls['primary_doc_url'], accept='application/xml, text/xml', limit=MAX_DOC_BYTES)
        scanned += 1
        try:
            candidate = nport_positions(body, max_bytes=MAX_DOC_BYTES)
        except ValueError:
            raise FundPipelineError('invalid_response') from None
        # The document itself must name the requested series; discovery is not identity.
        if candidate['header']['series_id'] == series_id:
            selected, parsed, raw = {**filing, **urls}, candidate, body
            break
    if selected is None:
        raise FundPipelineError('no_filing_found')
    retrieved = (now or datetime.now(timezone.utc))
    if retrieved.tzinfo is None:
        raise ValueError('clock must be timezone-aware')
    retrieved = retrieved.astimezone(timezone.utc)
    accepted = acceptance_upper_bound(selected['acceptance_raw'])
    if accepted is not None:
        available, basis = min(accepted, retrieved), 'sec_acceptance_datetime'
    else:
        available, basis = retrieved, 'retrieval_time'
        limitations.append('SEC acceptance time not established; availability is the retrieval time.')
    header = parsed['header']
    report_day = date.fromisoformat(header['report_date'])
    if report_day > available.date():
        raise FundPipelineError('invalid_source_time')
    mapping = mapping_for(series_id=series_id)
    sha = hashlib.sha256(raw).hexdigest()
    identity = {'series_id': series_id, 'accession': selected['accession'], 'source_sha256': sha,
                'mapping': mapping['mapping_id'] if mapping else None}
    capture_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    record = {
        'capture_id': capture_id,
        'dataset_version': 'sec-nport-' + sha[:16],
        'storage': 'session-owned immutable capture',
        'series_id': series_id,
        'series_name': header['series_name'],
        'series_lei': header['series_lei'],
        'registrant_name': header['registrant_name'],
        'registrant_cik': selected['cik'],
        'fund_isin': mapping['fund_isin'] if mapping else None,
        'fund_isin_mapping': mapping,
        'accession': selected['accession'],
        'form': selected['form'] or header['submission_type'],
        'filing_date': selected['filing_date'],
        'acceptance_datetime_reported': selected['acceptance_raw'],
        'report_date': header['report_date'],
        'fiscal_period_end': header['fiscal_period_end'],
        'is_final_filing': header['is_final_filing'],
        'net_assets_usd': header['net_assets_usd'],
        'total_assets_usd': header['total_assets_usd'],
        'available_at': available.isoformat(),
        'availability_basis': basis,
        'retrieved_at': retrieved.isoformat(),
        'source_url': selected['primary_doc_url'],
        'filing_index_url': selected['index_url'],
        'discovery': discovery,
        'discovery_url': discovery_url,
        'filings_scanned': scanned,
        'source_sha256': sha,
        'licence': LICENCE,
        'position_count': len(parsed['positions']),
        'positions': parsed['positions'],
        'limitations': limitations,
    }
    return _persist(store, session_id, record, raw)


# --------------------------------------------------------------------------- consumption

def _visible(summary: dict, as_of: date, historical: bool) -> bool:
    cutoff = datetime.combine(as_of, time.max, timezone.utc)
    available = datetime.fromisoformat(summary['available_at'])
    retrieved = datetime.fromisoformat(summary['retrieved_at'])
    return (date.fromisoformat(summary['report_date']) <= as_of and available <= cutoff
            and (not historical or retrieved <= cutoff))


def _latest_visible(store, session_id: str, series_id: str, as_of: date, historical: bool) -> dict | None:
    rows = [r for r in list_funds(store, session_id) if r['series_id'] == series_id and _visible(r, as_of, historical)]
    if not rows:
        return None
    best = max(rows, key=lambda r: (r['report_date'], r['available_at'], r['retrieved_at']))
    return get_capture(store, session_id, best['capture_id'])


def look_through(store, session_id: str, fund_id: str, as_of: date, *, historical: bool = False,
                 limit: int | None = None) -> dict:
    """Latest visible captured report for a fund, with constituent look-through.

    Visibility: report date <= as_of and availability <= end of as_of (UTC); with
    ``historical`` the capture's retrieval must also precede the cutoff. A fund ISIN
    additionally requires its documented mapping to be available at the cutoff.
    """
    series_id, mapping = resolve_fund(fund_id)
    base = {'fund_id': fund_id, 'series_id': series_id, 'as_of': as_of.isoformat(), 'historical': historical,
            'fund_isin': mapping['fund_isin'] if mapping else None}
    cutoff = datetime.combine(as_of, time.max, timezone.utc)
    if fund_id.upper().removeprefix('ISIN:') != series_id and mapping and _mapping_available_at(mapping) > cutoff:
        return {**base, 'status': 'not_visible', 'reason': 'fund_isin_mapping_not_available_at_cutoff'}
    record = _latest_visible(store, session_id, series_id, as_of, historical)
    if record is None:
        captured = any(r['series_id'] == series_id for r in list_funds(store, session_id))
        return {**base, 'status': 'not_visible' if captured else 'not_ingested',
                'reason': 'no_capture_available_at_cutoff' if captured else 'fund_not_ingested_in_session'}
    result = compute_lookthrough(record['positions'])
    if limit is not None:
        result['constituents'] = result['constituents'][:limit]
    filing = {k: record[k] for k in record if k not in ('positions', 'limitations')}
    return {**base, 'status': 'available', 'filing': filing, **result,
            'limitations': [*result['limitations'], *record['limitations']]}


def holdings_snapshot(store, session_id: str, fund_id: str, as_of: date, *,
                      historical: bool = False) -> tuple[HoldingsSnapshot | None, dict]:
    """Bridge to ``overlap.portfolio_lookthrough``: a dated ISIN-keyed snapshot or a reason.

    Portfolio positions are ISIN/listing keyed, so a snapshot exists only for a fund
    with a documented ISIN mapping. Evidence availability is the later of the filing
    and the mapping, so a later mapping cannot leak into an earlier analysis.
    """
    view = look_through(store, session_id, fund_id, as_of, historical=historical)
    if view['status'] != 'available':
        return None, view
    mapping = mapping_for(series_id=view['series_id'])
    if mapping is None:
        return None, {**view, 'status': 'unmapped', 'reason': 'fund_isin_mapping_undocumented'}
    filing = view['filing']
    weights = [c for c in view['constituents'] if 0 <= c['weight_pct'] <= 100]
    if math.fsum(c['weight_pct'] for c in weights) > 100.01:
        return None, {**view, 'status': 'unrepresentable', 'reason': 'covered_exceeds_net_assets'}
    mapping_at = _mapping_available_at(mapping)
    filing_at = datetime.fromisoformat(filing['available_at'])
    retrieved = datetime.fromisoformat(filing['retrieved_at'])
    evidence = Evidence(
        source_id='fund_sec_nport_pipeline', url=filing['source_url'], content_sha256=filing['source_sha256'],
        available_at=max(filing_at, mapping_at), retrieved_at=max(retrieved, mapping_at), licence=LICENCE,
        limitations=(f"Fund mapping {mapping['mapping_id']}: " + '; '.join(mapping['sources']),
                     f"Availability basis: {filing['availability_basis']}",
                     'Derivatives, shorts and unidentified rows are not constituents; remainder is unknown.'))
    snapshot = HoldingsSnapshot(
        fund_id='isin:' + mapping['fund_isin'], effective_date=date.fromisoformat(filing['report_date']),
        holdings=tuple(Holding(security_id=c['security_id'], weight_pct=c['weight_pct']) for c in weights),
        evidence=evidence, complete=False)
    return snapshot, view
