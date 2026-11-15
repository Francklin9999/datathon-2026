"""Trusted source adapters that publish into the session instrument repository.

Each adapter fetches one bounded, code-owned request from a real source, validates the
source-specific identity fields, and publishes records citing the exact captured bytes.
Callers never supply records, URLs, queries or evidence. Evidence classes are fixed per
adapter: GLEIF exact pairs are ``direct``; Wikidata statements are ``unverified`` community
assertions and are never promoted to identity; Coin Metrics provider asset ids are ``direct``
statements of the provider's own identifier only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from .coinmetrics import CoinMetricsError
from .coinmetrics import fetch as coinmetrics_fetch
from .coinmetrics import latest as coinmetrics_latest
from .entities import Evidence, valid_isin, valid_lei
from .exact import exact_pair
from .gleif import TERMS as GLEIF_TERMS
from .gleif import _fetch as gleif_fetch
from .master import IdentifierAssertion, ListingRecord
from .master_repository import InstrumentRepository
from .wikidata import ENDPOINT, MAX_BYTES, WikidataError
from .wikidata import TERMS as WIKIDATA_TERMS
from .wikidata import fetch as wikidata_fetch

WIKIDATA_ROW_LIMIT = 100
_ENTITY = r'http://www\.wikidata\.org/entity/(Q[1-9][0-9]{0,11})'
_TICKER = r'[A-Z0-9][A-Z0-9.=_-]{0,39}'


def _now(now):
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('clock must be timezone-aware')
    return stamp.astimezone(timezone.utc)


# --- GLEIF exact ISIN -> LEI (direct) -------------------------------------------------------

def publish_gleif_pair(store, session_id: str, isin: str, lei: str, *, fetch=gleif_fetch, now=None):
    """Reuse the bounded exact-pair proof; only an inspected matching row is published."""
    result, payload = exact_pair(isin, lei, fetch=fetch, now=now)
    if result['status'] != 'verified_pair':
        return {**result, 'published': []}
    rel = result['relationship']
    evidence = Evidence.model_validate(rel['evidence'])
    assertion = IdentifierAssertion(
        subject='isin:' + isin, scheme='lei', value=lei, role='issuer_lei', evidence_class='direct',
        origin='gleif_exact_pair', evidence=evidence)
    repository = InstrumentRepository(store, session_id)
    ids = repository.publish_assertions(
        [assertion], source_bytes=payload,
        # GLEIF LEI and ISIN-LEI mapping data are published as open data (see GLEIF_TERMS).
        rights_confirmed=True)
    recorded = repository.published_assertions(ids)[0].evidence
    return {'status': 'verified_pair', 'pages_inspected': result['pages_inspected'], 'published': ids,
            'source_sha256': recorded.content_sha256, 'retrieved_at': recorded.retrieved_at.isoformat(),
            'licence_url': GLEIF_TERMS}


# --- Wikidata identifiers and exchange statements (unverified) -----------------------------

def wikidata_identifier_query(isin: str) -> str:
    """Code-owned SPARQL: the exact ISIN item, its LEI/CIK, and P414 exchange statements.

    P946 ISIN, P1278 LEI, P5531 SEC CIK, P414 stock exchange with P249 ticker, P580/P582
    statement start/end qualifiers, and P7534 ISO 10383 MIC on the exchange item. Property
    meanings were checked against the live Wikidata property labels on 2026-11-15.
    """
    if not isinstance(isin, str) or not valid_isin(isin):
        raise ValueError('Valid exact ISIN with checksum required')
    wd, p, ps, pq = ('http://www.wikidata.org/prop/direct/', 'http://www.wikidata.org/prop/',
                     'http://www.wikidata.org/prop/statement/', 'http://www.wikidata.org/prop/qualifier/')
    return ('SELECT ?item ?isin ?lei ?cik ?exchange ?ticker ?mic ?start ?end WHERE { '
            f'?item <{wd}P946> ?isin . FILTER(?isin = "{isin}") '
            f'OPTIONAL {{ ?item <{wd}P1278> ?lei . }} '
            f'OPTIONAL {{ ?item <{wd}P5531> ?cik . }} '
            f'OPTIONAL {{ ?item <{p}P414> ?st . ?st <{ps}P414> ?exchange . '
            f'OPTIONAL {{ ?st <{pq}P249> ?ticker . }} OPTIONAL {{ ?st <{pq}P580> ?start . }} '
            f'OPTIONAL {{ ?st <{pq}P582> ?end . }} OPTIONAL {{ ?exchange <{wd}P7534> ?mic . }} }} '
            f'}} LIMIT {WIKIDATA_ROW_LIMIT + 1}')


def _literal(row, name):
    cell = row.get(name)
    if cell is None:
        return None
    if cell.get('type') != 'literal' or not isinstance(cell.get('value'), str):
        raise ValueError('unexpected binding type')
    return cell['value']


def _day(value):
    if value is None:
        return None
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T00:00:00Z', value):
        return None  # BCE, unknown or non-day values are not converted.
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_wikidata_identifiers(isin: str, payload: bytes):
    """Return validated (kind, value, extras) tuples and a count of rejected values."""
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise WikidataError('invalid_response')
    try:
        rows = json.loads(payload)['results']['bindings']
        if not isinstance(rows, list):
            raise ValueError('rows')
        found, rejected = [], 0
        for row in rows[:WIKIDATA_ROW_LIMIT]:
            item = row['item']
            match = re.fullmatch(_ENTITY, item.get('value', '')) if item.get('type') == 'uri' else None
            if match is None or _literal(row, 'isin') != isin:
                raise ValueError('mismatched item')
            qid = match.group(1)
            found.append(('wikidata_qid', qid, {}))
            lei, cik = _literal(row, 'lei'), _literal(row, 'cik')
            if lei is not None:
                found.append(('lei', lei, {'qid': qid}) if valid_lei(lei) else ('rejected', lei, {}))
            if cik is not None:
                found.append(('cik', cik, {'qid': qid}) if re.fullmatch(r'\d{10}', cik) else ('rejected', cik, {}))
            exchange = row.get('exchange')
            if exchange is not None:
                ex = re.fullmatch(_ENTITY, exchange.get('value', '')) if exchange.get('type') == 'uri' else None
                ticker, mic = _literal(row, 'ticker'), _literal(row, 'mic')
                if ex is None or (ticker is not None and not re.fullmatch(_TICKER, ticker)) or (
                        mic is not None and not re.fullmatch(r'[A-Z0-9]{4}', mic)):
                    found.append(('rejected', exchange.get('value'), {}))
                    continue
                extras = {'qid': qid, 'exchange_qid': ex.group(1), 'stated_from': _day(_literal(row, 'start')),
                          'stated_to': _day(_literal(row, 'end'))}
                if mic and ticker:
                    found.append(('mic_ticker', f'{mic}:{ticker}', extras))
                else:
                    # Without both an ISO MIC on the exchange item and a ticker, no MIC is asserted.
                    found.append(('exchange_item_ticker', ex.group(1) + (f':{ticker}' if ticker else ''), extras))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WikidataError('invalid_response') from exc
    rejected = sum(kind == 'rejected' for kind, _, _ in found)
    return [f for f in found if f[0] != 'rejected'], rejected, len(rows) > WIKIDATA_ROW_LIMIT


def publish_wikidata(store, session_id: str, isin: str, *, contact: str, get=wikidata_fetch, now=None):
    query = wikidata_identifier_query(isin)
    url = ENDPOINT + '?' + urlencode({'query': query, 'format': 'json'})
    if len(url) > 2048:
        raise ValueError('query URL exceeds evidence bound')
    payload = get(url, contact=contact)
    found, rejected, partial = parse_wikidata_identifiers(isin, payload)
    stamp = _now(now)
    evidence = Evidence(
        source_id='wikidata_sparql_identifiers', url=url, content_sha256=hashlib.sha256(payload).hexdigest(),
        available_at=stamp, retrieved_at=stamp, licence='CC0 1.0 Wikidata structured data',
        limitations=('Community-edited assertion; not proof of security, issuer or listing identity.',
                     'Availability before this capture is unknown; statement dates are the source\'s own claim.',
                     'Date precision qualifiers are not retrieved; a day may stand for a month or year.'))
    roles = {'wikidata_qid': 'community_item', 'lei': 'issuer_lei', 'cik': 'issuer_cik',
             'mic_ticker': 'exchange_listing_candidate', 'exchange_item_ticker': 'exchange_listing_candidate'}
    assertions, seen = [], set()
    for kind, value, extras in found:
        item = IdentifierAssertion(
            subject='isin:' + isin, scheme=kind, value=value, role=roles[kind], evidence_class='unverified',
            origin='wikidata_assertions', stated_from=extras.get('stated_from'), stated_to=extras.get('stated_to'),
            derivation=(f"Stated on Wikidata item {extras['qid']}, which also states this ISIN"
                        + (f"; exchange item {extras['exchange_qid']}" if extras.get('exchange_qid') else '')
                        if extras.get('qid') else None),
            evidence=evidence)
        if item.assertion_id not in seen:
            seen.add(item.assertion_id)
            assertions.append(item)
    repository = InstrumentRepository(store, session_id)
    ids = repository.publish_assertions(assertions, source_bytes=payload, rights_confirmed=True)
    assertions = repository.published_assertions(ids)
    return {'status': 'results' if assertions else 'no_results', 'isin': isin, 'published': ids,
            'assertions': [a.model_dump(mode='json') | {'assertion_id': a.assertion_id} for a in assertions],
            'rejected_values': rejected, 'partial': partial, 'source_url': url,
            'source_sha256': evidence.content_sha256,
            'retrieved_at': assertions[0].evidence.retrieved_at.isoformat() if assertions else stamp.isoformat(),
            'licence_url': WIKIDATA_TERMS, 'evidence_class': 'unverified',
            'limitations': list(evidence.limitations)
            + (['Row limit reached; further statements may exist.'] if partial else [])}


# --- Coin Metrics provider asset (crypto, no ISIN) ------------------------------------------

def publish_coinmetrics_asset(store, session_id: str, asset: str, *, get=coinmetrics_fetch,
                              permitted=None, now=None):
    """Publish a MIC-less crypto record keyed by Coin Metrics' own asset id.

    The record proves only that the provider served this asset id; the ticker field is the
    upper-cased provider id and USD is the unit of the PriceUSD reference metric.
    """
    if permitted is None:
        permitted = os.getenv('APLOMB_COINMETRICS_NONCOMMERCIAL') == '1'
    if not permitted:
        raise CoinMetricsError('licence_not_enabled')
    result, payload = coinmetrics_latest(asset, get=get, now=_now(now))
    stamp = datetime.fromisoformat(result['retrieved_at'])
    evidence = Evidence(
        source_id='coinmetrics_asset_metrics', url=result['source_url'], content_sha256=result['source_sha256'],
        observed_at=datetime.fromisoformat(result['observed_at']), available_at=stamp, retrieved_at=stamp,
        licence=result['licence'], limitations=tuple(result['limitations']))
    record = ListingRecord(
        ticker=asset.upper(), mic=None, currency='USD', asset_class='crypto', name=f'Coin Metrics asset {asset}',
        provider='coinmetrics', provider_asset_id=asset, lifecycle_anchor='coinmetrics-community-asset-id',
        evidence=(evidence,))
    listing_id = InstrumentRepository(store, session_id).publish(
        record, source_bytes={evidence.content_sha256: payload}, rights_confirmed=True)
    return {'status': 'published', 'listing_id': listing_id, 'provider': 'coinmetrics', 'provider_asset_id': asset,
            'isin_state': record.isin_state, 'source_sha256': evidence.content_sha256,
            'retrieved_at': stamp.isoformat(), 'licence': result['licence']}
