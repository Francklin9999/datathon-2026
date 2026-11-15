"""Validate rights-cleared, dated issuer holdings without guessing security identity."""
from __future__ import annotations

import csv
import io
from datetime import date

from .entities import Evidence, valid_isin, valid_lei
from .overlap import Holding, HoldingsSnapshot


def issuer_holdings_csv(raw: bytes, *, fund_isin: str, effective_date: date,
                        evidence: Evidence) -> tuple[HoldingsSnapshot, list[dict]]:
    """Normalize a rights-cleared CSV with explicit ISIN and weight percentage columns.

    Rows without a valid ISIN are retained as unresolved, never resolved by names or
    ticker. The caller is responsible for acquisition rights, storage and provenance.
    """
    if not valid_isin(fund_isin):
        raise ValueError('fund ISIN checksum invalid')
    if len(raw) > 5_000_000:
        raise ValueError('holdings file exceeds size limit')
    import hashlib
    if hashlib.sha256(raw).hexdigest() != evidence.content_sha256:
        raise ValueError('source checksum mismatch')
    if effective_date > evidence.retrieved_at.date():
        raise ValueError('holdings date is after retrieval')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if not {'ISIN', 'Weight (%)'} <= set(reader.fieldnames or []):
            raise ValueError('source must provide ISIN and Weight (%) columns')
        resolved, unresolved = [], []
        for i, row in enumerate(reader):
            if i >= 20000:
                raise ValueError('too many holdings')
            isin = (row.get('ISIN') or '').strip().upper()
            value = float((row.get('Weight (%)') or '').replace(',', '').strip())
            if not 0 <= value <= 100:
                raise ValueError('invalid holding weight')
            if valid_isin(isin):
                resolved.append(Holding(security_id='isin:' + isin, weight_pct=value))
            else:
                unresolved.append({'row': i + 2, 'weight_pct': value, 'reason': 'missing_or_invalid_isin'})
        snap = HoldingsSnapshot(fund_id='isin:' + fund_isin, effective_date=effective_date,
                                holdings=tuple(resolved), evidence=evidence, complete=False)
        if sum(x.weight_pct for x in resolved) + sum(x['weight_pct'] for x in unresolved) > 100.01:
            raise ValueError('total holding weight exceeds 100 percent')
        return snap, unresolved
    except (UnicodeDecodeError, csv.Error, TypeError, OverflowError) as exc:
        raise ValueError('invalid holdings CSV') from exc


def nport_holdings_xml(raw: bytes, *, fund_isin: str, fund_mapping: Evidence,
                       evidence: Evidence) -> tuple[HoldingsSnapshot, list[dict]]:
    """Parse a public N-PORT filing; caller supplies separately proven fund ISIN mapping.

    N-PORT series identifiers are not security identifiers. Only direct long equity
    positions with an explicit ISIN enter look-through; derivatives, missing identifiers,
    shorts, and other items remain unknown. Both source captures are required.
    """
    import hashlib
    import xml.etree.ElementTree as ET

    if not valid_isin(fund_isin):
        raise ValueError('fund ISIN checksum invalid')
    if len(raw) > 5_000_000 or hashlib.sha256(raw).hexdigest() != evidence.content_sha256:
        raise ValueError('source too large or checksum mismatch')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD and entities are forbidden')
    try:
        root = ET.fromstring(raw)
        ns = {'n': 'http://www.sec.gov/edgar/nport'}
        if root.tag != '{http://www.sec.gov/edgar/nport}edgarSubmission':
            raise ValueError('invalid N-PORT namespace')
        report_date = root.findtext('.//n:repPdDate', namespaces=ns)
        if not report_date:
            raise ValueError('missing reporting date')
        effective_date = date.fromisoformat(report_date)
        if effective_date > evidence.available_at.date():
            raise ValueError('filing availability predates reporting date')
        # Both documents are prerequisites: the filing's source date cannot make a
        # later fund-to-ISIN mapping visible in a historical analysis.
        combined_evidence = evidence.model_copy(update={
            'available_at': max(evidence.available_at, fund_mapping.available_at),
            'retrieved_at': max(evidence.retrieved_at, fund_mapping.retrieved_at),
            'limitations': (*evidence.limitations, f'Fund mapping: {fund_mapping.url}; SHA-256 {fund_mapping.content_sha256}; captured {fund_mapping.retrieved_at.isoformat()}'),
        })
        holdings, unresolved = [], []
        for i, node in enumerate(root.findall('.//n:invstOrSecs/n:invstOrSec', ns)):
            if i >= 20000:
                raise ValueError('too many holdings')
            weight = float(node.findtext('n:pctVal', '', ns))
            if not -1000 <= weight <= 1000:
                raise ValueError('invalid holding weight')
            isin_node = node.find('n:identifiers/n:isin', ns)
            isin = (isin_node.get('value', '') if isin_node is not None else '').upper()
            payoff = node.findtext('n:payoffProfile', '', ns)
            category = node.findtext('n:assetCat', '', ns)
            derivative = node.find('n:derivativeInfo', ns) is not None
            if 0 <= weight <= 100 and valid_isin(isin) and payoff == 'Long' and category == 'EC' and not derivative:
                holdings.append(Holding(security_id='isin:' + isin, weight_pct=weight))
            else:
                unresolved.append({'row': i + 1, 'weight_pct': weight,
                                   'reason': 'unsupported_position_or_missing_isin'})
        snapshot = HoldingsSnapshot(fund_id='isin:' + fund_isin, effective_date=effective_date,
                                    holdings=tuple(holdings), evidence=combined_evidence, complete=False)
        return snapshot, unresolved
    except (ET.ParseError, TypeError, OverflowError) as exc:
        raise ValueError('invalid N-PORT filing') from exc


NPORT_NS = 'http://www.sec.gov/edgar/nport'
# N-PORT Item C.4 derivative categories; these rows are fair values, not notionals.
DERIVATIVE_CATEGORIES = frozenset({'DCO', 'DCR', 'DE', 'DFE', 'DIR', 'DO'})


def _text(value: str | None, limit: int = 300) -> str | None:
    """Untrusted filing text: strip control characters, bound length, never interpret."""
    if value is None:
        return None
    cleaned = ''.join(c for c in value if c.isprintable()).strip()
    return cleaned[:limit] or None


def _decimal_text(value: str | None) -> str | None:
    from decimal import Decimal, InvalidOperation
    try:
        number = Decimal((value or '').strip())
    except InvalidOperation:
        return None
    return str(number) if number.is_finite() else None


def _float(value: str | None) -> float | None:
    import math
    try:
        number = float((value or '').strip())
    except ValueError:
        return None
    return number if math.isfinite(number) and -100_000 <= number <= 100_000 else None


def nport_positions(raw: bytes, *, max_bytes: int = 15_000_000) -> dict:
    """Parse every reported position of a public N-PORT primary document.

    Returns header facts and one record per ``invstOrSec`` without filtering, so a
    caller can quantify what is resolved, what is a derivative and what is unknown.
    Identity is only the explicit ISIN element; names, tickers and CUSIPs are retained
    for display and audit, never to resolve a security. DTDs and entities are rejected.
    """
    import xml.etree.ElementTree as ET

    if len(raw) > max_bytes:
        raise ValueError('N-PORT document exceeds size limit')
    head = raw.upper()
    if b'<!DOCTYPE' in head or b'<!ENTITY' in head:
        raise ValueError('DTD and entities are forbidden')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('invalid N-PORT filing') from exc
    if root.tag != '{%s}edgarSubmission' % NPORT_NS:
        raise ValueError('invalid N-PORT namespace')
    ns = {'n': NPORT_NS}
    gen = root.find('.//n:formData/n:genInfo', ns)
    if gen is None:
        raise ValueError('missing general information')
    series_id = (gen.findtext('n:seriesId', '', ns) or root.findtext('.//n:seriesClassInfo/n:seriesId', '', ns)).strip()
    report_date = (gen.findtext('n:repPdDate', '', ns) or '').strip()
    try:
        report_day = date.fromisoformat(report_date)
    except ValueError as exc:
        raise ValueError('missing reporting date') from exc
    period_end = (gen.findtext('n:repPdEnd', '', ns) or '').strip()
    try:
        period_end = date.fromisoformat(period_end).isoformat()
    except ValueError:
        period_end = None
    fund_info = root.find('.//n:formData/n:fundInfo', ns)
    header = {
        'submission_type': _text(root.findtext('.//n:headerData/n:submissionType', '', ns), 20),
        'series_id': series_id or None,
        'series_name': _text(gen.findtext('n:seriesName', None, ns)),
        'series_lei': _text(gen.findtext('n:seriesLei', None, ns), 20),
        'registrant_name': _text(gen.findtext('n:regName', None, ns)),
        'registrant_cik': _text(gen.findtext('n:regCik', None, ns), 10),
        'registrant_lei': _text(gen.findtext('n:regLei', None, ns), 20),
        'fiscal_period_end': period_end,
        'report_date': report_day.isoformat(),
        'is_final_filing': (gen.findtext('n:isFinalFiling', '', ns) or '').strip() == 'Y',
        'total_assets_usd': _decimal_text(fund_info.findtext('n:totAssets', None, ns)) if fund_info is not None else None,
        'net_assets_usd': _decimal_text(fund_info.findtext('n:netAssets', None, ns)) if fund_info is not None else None,
    }
    positions = []
    for i, node in enumerate(root.findall('.//n:invstOrSecs/n:invstOrSec', ns)):
        if i >= 20000:
            raise ValueError('too many holdings')
        isin_node = node.find('n:identifiers/n:isin', ns)
        isin = (isin_node.get('value', '') if isin_node is not None else '').strip().upper()
        ticker_node = node.find('n:identifiers/n:ticker', ns)
        category = (node.findtext('n:assetCat', '', ns) or '').strip()
        if not category:
            conditional = node.find('n:assetConditional', ns)
            category = (conditional.get('assetCat', '') if conditional is not None else '').strip()
        derivative_node = node.find('n:derivativeInfo', ns)
        derivative_kind = None
        if derivative_node is not None and len(derivative_node):
            derivative_kind = derivative_node[0].tag.rsplit('}', 1)[-1]
        lei = (node.findtext('n:lei', '', ns) or '').strip().upper()
        positions.append({
            'row': i + 1,
            'name': _text(node.findtext('n:name', None, ns)),
            'title': _text(node.findtext('n:title', None, ns)),
            'lei': lei if valid_lei(lei) else None,
            'isin': isin if valid_isin(isin) else None,
            'isin_reported_invalid': bool(isin) and not valid_isin(isin),
            'cusip': _text(node.findtext('n:cusip', None, ns), 9),
            'ticker_display_only': _text(ticker_node.get('value') if ticker_node is not None else None, 20),
            'balance': _decimal_text(node.findtext('n:balance', None, ns)),
            'units': _text(node.findtext('n:units', None, ns), 10),
            'currency': _text(node.findtext('n:curCd', None, ns), 3),
            'value_usd': _decimal_text(node.findtext('n:valUSD', None, ns)),
            'pct_of_net_assets': _float(node.findtext('n:pctVal', None, ns)),
            'payoff_profile': _text(node.findtext('n:payoffProfile', None, ns), 20),
            'asset_category': _text(category, 10),
            'issuer_category': _text(node.findtext('n:issuerCat', None, ns), 10),
            'investment_country': _text(node.findtext('n:invCountry', None, ns), 2),
            'derivative': derivative_node is not None or category in DERIVATIVE_CATEGORIES,
            'derivative_kind': derivative_kind,
        })
    return {'header': header, 'positions': positions}
