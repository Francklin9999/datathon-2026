"""Exchange-aware, evidence-backed listing records and conservative provider routing."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .entities import Evidence, Model, valid_isin, valid_lei

MIC_LESS_KINDS = ('crypto', 'index', 'commodity')
AssetKind = Literal['stock', 'etf', 'bond', 'index', 'commodity', 'fund', 'crypto', 'other']


class ListingRecord(Model):
    """Record identity is anchored by a documented lifecycle, not ticker alone."""
    ticker: str = Field(pattern=r'^[A-Z0-9][A-Z0-9.=_-]{0,39}$')
    mic: str | None = Field(default=None, pattern=r'^[A-Z0-9]{4}$')
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    asset_class: AssetKind
    name: str = Field(min_length=1, max_length=200)
    isin: str | None = None
    series_lei: str | None = None
    registrant_cik: str | None = Field(default=None, pattern=r'^\d{10}$')
    provider: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    provider_asset_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$')
    valid_from: date | None = None
    valid_to: date | None = None
    # An explicit immutable record anchor, such as an exchange registration ID/date.
    lifecycle_anchor: str = Field(min_length=1, max_length=200)
    evidence: tuple[Evidence, ...] = Field(min_length=1)

    @field_validator('isin')
    @classmethod
    def check_isin(cls, value):
        if value is not None and not valid_isin(value):
            raise ValueError('invalid ISIN checksum')
        return value

    @field_validator('series_lei')
    @classmethod
    def check_lei(cls, value):
        if value is not None and not valid_lei(value):
            raise ValueError('invalid LEI checksum')
        return value

    @model_validator(mode='after')
    def check_dates(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('invalid listing lifecycle')
        if (self.provider is None) != (self.provider_asset_id is None):
            raise ValueError('provider and exact provider asset ID must be supplied together')
        if self.mic is None and (self.asset_class not in MIC_LESS_KINDS or not self.provider):
            raise ValueError('MIC-less assets must be crypto, index or commodity with an exact provider asset ID')
        if self.asset_class in MIC_LESS_KINDS and self.mic is None and self.registrant_cik:
            raise ValueError('provider-identified assets cannot carry an exchange registrant CIK')
        return self

    @property
    def isin_state(self):
        # Absence is reported as absence in this record, never as proof that no ISIN exists.
        return 'exact' if self.isin else 'not_in_source_record'

    @property
    def listing_id(self):
        if self.mic is None:
            key = '|'.join((self.provider, self.provider_asset_id, self.lifecycle_anchor))
            return 'asset_' + hashlib.sha256(key.encode()).hexdigest()[:24]
        key = '|'.join((self.mic, self.ticker, self.lifecycle_anchor))
        return 'listing_' + hashlib.sha256(key.encode()).hexdigest()[:24]

    def visible(self, as_of: date):
        return ((self.valid_from is None or self.valid_from <= as_of)
                and (self.valid_to is None or as_of <= self.valid_to)
                and all(e.visible(as_of, historical=True) for e in self.evidence))


IdentifierScheme = Literal['isin', 'lei', 'cik', 'mic_ticker', 'exchange_item_ticker', 'wikidata_qid',
                           'provider_asset_id', 'listing_id']
CrosswalkClass = Literal['direct', 'derived', 'unverified']
IdentifierRole = Literal['security', 'issuer_lei', 'fund_series_lei', 'registrant_cik', 'issuer_cik',
                         'listing', 'exchange_listing_candidate', 'community_item', 'provider_asset']


def check_identifier(scheme: str, value: str) -> str:
    """Syntax and checksum only; a valid identifier is not proof of the asserted relation."""
    ok = {
        'isin': lambda v: valid_isin(v),
        'lei': lambda v: valid_lei(v),
        'cik': lambda v: re.fullmatch(r'\d{10}', v),
        'mic_ticker': lambda v: re.fullmatch(r'[A-Z0-9]{4}:[A-Z0-9][A-Z0-9.=_-]{0,39}', v),
        'exchange_item_ticker': lambda v: re.fullmatch(r'Q[1-9]\d{0,11}(:[A-Z0-9][A-Z0-9.=_-]{0,39})?', v),
        'wikidata_qid': lambda v: re.fullmatch(r'Q[1-9]\d{0,11}', v),
        'provider_asset_id': lambda v: re.fullmatch(r'[a-z][a-z0-9_-]{0,39}:[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}', v),
        'listing_id': lambda v: re.fullmatch(r'(listing|asset)_[0-9a-f]{24}', v),
    }[scheme]
    if not isinstance(value, str) or not ok(value):
        raise ValueError(f'invalid {scheme} identifier')
    return value


class IdentifierAssertion(Model):
    """One source's statement that ``subject`` carries an identifier, with an explicit evidence class.

    ``unverified`` covers community assertions (for example Wikidata); they are never promoted to
    identity by themselves. ``derived`` requires a stated deterministic rule. Statement dates are
    the source's own claim and are kept apart from capture availability.
    """
    subject: str = Field(pattern=r'^(isin:[A-Z0-9]{12}|[a-z][a-z0-9_-]{0,39}:[a-zA-Z0-9][a-zA-Z0-9._-]{0,79})$')
    scheme: IdentifierScheme
    value: str = Field(min_length=1, max_length=140)
    role: IdentifierRole
    evidence_class: CrosswalkClass
    origin: str = Field(pattern=r'^[a-z][a-z0-9_]{0,59}$')
    stated_from: date | None = None
    stated_to: date | None = None
    derivation: str | None = Field(default=None, max_length=500)
    evidence: Evidence

    @model_validator(mode='after')
    def check(self):
        check_identifier(self.scheme, self.value)
        if self.subject.startswith('isin:') and not valid_isin(self.subject[5:]):
            raise ValueError('invalid subject ISIN checksum')
        if self.evidence_class == 'derived' and not self.derivation:
            raise ValueError('derived identifiers require an explicit rule')
        if self.stated_from and self.stated_to and self.stated_to < self.stated_from:
            raise ValueError('invalid stated interval')
        return self

    @property
    def assertion_id(self):
        key = '|'.join((self.subject, self.scheme, self.value, self.role, self.origin,
                        str(self.stated_from), str(self.stated_to), self.evidence.content_sha256))
        return 'idf_' + hashlib.sha256(key.encode()).hexdigest()[:24]


class InstrumentMaster:
    def __init__(self, listings: list[ListingRecord]):
        self.listings = tuple(listings)
        if len({item.listing_id for item in listings}) != len(listings):
            raise ValueError('duplicate listing lifecycle')

    def discover(self, *, as_of: date, ticker: str | None = None, mic: str | None = None,
                 isin: str | None = None, provider: str | None = None,
                 provider_asset_id: str | None = None):
        if (provider is None) != (provider_asset_id is None):
            raise ValueError('provider and exact provider asset ID must be supplied together')
        if not ticker and not isin and not provider:
            raise ValueError('ticker, exact ISIN, or exact provider asset ID required')
        if ticker and not mic and not isin and not provider:
            raise ValueError('ticker requires an exchange MIC, exact ISIN, or provider asset ID')
        if isin and not valid_isin(isin):
            raise ValueError('invalid ISIN checksum')
        return [item for item in self.listings if item.visible(as_of)
                and (not ticker or item.ticker == ticker)
                and (not mic or item.mic == mic)
                and (not isin or item.isin == isin)
                and (not provider or (item.provider, item.provider_asset_id) == (provider, provider_asset_id))]

    def detail(self, listing_id: str, *, as_of: date):
        return next((item for item in self.listings if item.listing_id == listing_id and item.visible(as_of)), None)


# Code-owned routing per ISO 10383 operating/segment MIC. The MIC-to-exchange labels were
# cross-checked on 2026-11-15 against Wikidata P7534 (community data), not the ISO file.
# Each adapter still needs its own exact provider identifier; a ticker is never converted.
US_MICS = {'XNAS': 'Nasdaq', 'XNYS': 'New York Stock Exchange', 'ARCX': 'NYSE Arca',
           'XASE': 'NYSE American', 'BATS': 'Cboe BZX U.S. Equities Exchange'}
MIC_ROUTES = {
    **{mic: {'region': 'US', 'exchange': name, 'filings': 'sec_edgar', 'financials': 'sec_companyfacts',
             'prices': 'tiingo_on_demand',
             'requirement': 'SEC EDGAR needs a descriptive APLOMB_SOURCE_USER_AGENT contact and live access '
                            '(prior SEC requests returned 403); Tiingo prices need APLOMB_TIINGO_TOKEN and cover '
                            'U.S. listed non-fund equities only.'}
       for mic, name in US_MICS.items()},
    'XTKS': {'region': 'JP', 'exchange': 'Tokyo Stock Exchange', 'filings': 'unavailable',
             'financials': 'jquants_statements', 'prices': 'jquants_tse_daily',
             'requirement': 'J-Quants needs an exact five-character issue code plus APLOMB_JQUANTS_KEY and '
                            'APLOMB_JQUANTS_RIGHTS_CONFIRMED=true; the exchange ticker is not converted.'},
    'XKRX': {'region': 'KR', 'exchange': 'Korea Exchange', 'filings': 'opendart', 'financials': 'opendart',
             'prices': 'unavailable',
             'requirement': 'OpenDART needs an exact eight-digit DART corporate code plus APLOMB_OPENDART_KEY and '
                            'APLOMB_OPENDART_RIGHTS_CONFIRMED=true; a stock code is not converted.'},
    'XKOS': {'region': 'KR', 'exchange': 'KOSDAQ', 'filings': 'opendart', 'financials': 'opendart',
             'prices': 'unavailable',
             'requirement': 'OpenDART needs an exact eight-digit DART corporate code plus APLOMB_OPENDART_KEY and '
                            'APLOMB_OPENDART_RIGHTS_CONFIRMED=true; a stock code is not converted.'},
    'XLIM': {'region': 'PE', 'exchange': 'Lima Stock Exchange', 'filings': 'bvl_captured_registration_only',
             'financials': 'unavailable', 'prices': 'unavailable',
             'requirement': 'Only captured BVL registration transcripts exist; no live BVL adapter.'},
}
PROVIDER_ROUTES = {
    'coinmetrics': {'region': None, 'exchange': None, 'filings': 'not_applicable', 'financials': 'not_applicable',
                    'prices': 'coinmetrics_community',
                    'requirement': 'Daily reference rate; requires APLOMB_COINMETRICS_NONCOMMERCIAL=1 (CC BY-NC).'},
}


def source_route(mic: str | None, kind: str):
    """Avoid silently routing a non-US listing to the US-specific SEC provider."""
    route = MIC_ROUTES.get(mic or '')
    if route is None or kind not in ('filings', 'prices', 'financials'):
        return 'unavailable'
    return route[kind]


def route_hint(mic: str | None, *, asset_class: str | None = None, provider: str | None = None):
    """Per-listing adapter hint; unknown markets get an explicit unavailable state."""
    if mic is None:
        base = PROVIDER_ROUTES.get(provider or '')
        if base is None:
            return {'mic': None, 'provider': provider, 'region': None, 'exchange': None, 'filings': 'unavailable',
                    'financials': 'unavailable', 'prices': 'unavailable', 'status': 'no_adapter',
                    'requirement': 'No adapter is implemented for this provider identifier.'}
        return {'mic': None, 'provider': provider, **base, 'status': 'routed'}
    route = MIC_ROUTES.get(mic)
    if route is None:
        return {'mic': mic, 'provider': provider, 'region': None, 'exchange': None, 'filings': 'unavailable',
                'financials': 'unavailable', 'prices': 'unavailable', 'status': 'no_adapter',
                'requirement': 'No adapter is implemented for this market; it is never routed to SEC by default.'}
    out = {'mic': mic, 'provider': provider, **route, 'status': 'routed'}
    if out['prices'] == 'tiingo_on_demand' and asset_class not in (None, 'stock'):
        out['prices'] = 'unavailable'
        out['requirement'] += ' This listing kind is outside Tiingo on-demand coverage.'
    return out


ASSET_COVERAGE = (
    {'kind': 'stock', 'identifier': 'exact ISIN or MIC + ticker', 'isin': 'expected',
     'adapters': ['captured_example', 'gleif_exact_pair', 'wikidata_assertions'],
     'status': 'partial', 'note': 'Listing records exist only where a trusted adapter published them.'},
    {'kind': 'etf', 'identifier': 'exact ISIN or MIC + ticker', 'isin': 'expected',
     'adapters': ['captured_example'], 'status': 'partial',
     'note': 'One captured example (AAPU on XNAS and XLIM); no live ETF listing acquisition.'},
    {'kind': 'crypto', 'identifier': 'provider + exact provider asset ID', 'isin': 'not_in_source_record',
     'adapters': ['coinmetrics'], 'status': 'gated',
     'note': 'Coin Metrics Community ids btc and eth only; requires APLOMB_COINMETRICS_NONCOMMERCIAL=1.'},
    {'kind': 'index', 'identifier': 'provider + exact provider asset ID', 'isin': 'not_in_source_record',
     'adapters': [], 'status': 'unavailable',
     'note': 'Model supported; no rights-cleared index provider adapter is implemented.'},
    {'kind': 'commodity', 'identifier': 'provider + exact provider asset ID', 'isin': 'not_in_source_record',
     'adapters': [], 'status': 'unavailable',
     'note': 'Model supported; no rights-cleared commodity provider adapter is implemented.'},
    {'kind': 'bond', 'identifier': 'exact ISIN', 'isin': 'expected', 'adapters': ['gleif_exact_pair'],
     'status': 'unavailable', 'note': 'Issuer LEI pairs only; no bond listing or terms source.'},
)


def captured_master():
    """Two exchange records from the same source; dates reflect verified knowledge."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / 'data/sec-nport-aapu-indexed-excerpt.json'
    raw = path.read_bytes()
    record = json.loads(raw)
    captured = datetime.fromisoformat(record['retrieved_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
    digest = hashlib.sha256(raw).hexdigest()
    sec = Evidence(source_id='fund_sec_class_mapping', url=record['fund_class_ticker_source'],
                   content_sha256=digest, available_at=captured, retrieved_at=captured,
                   licence='SEC filing indexed transcript; source must be independently reviewed',
                   limitations=('Hash identifies normalized transcript, not the source document.',))
    bvl = Evidence(source_id='security_bvl_registration', url=record['fund_ticker_isin_source'],
                   content_sha256=digest, available_at=captured, retrieved_at=captured,
                   licence='BVL indexed bulletin transcript; source rights require review',
                   limitations=('Hash identifies normalized transcript, not the source document.',))
    application = Evidence(source_id='security_bvl_application', url=record['fund_exchange_application_source'],
                           content_sha256=digest, available_at=captured, retrieved_at=captured,
                           licence='BVL indexed application transcript; source rights require review',
                           limitations=('Hash identifies normalized transcript, not the source document.',))
    common = dict(ticker='AAPU', currency='USD', asset_class='etf', name=record['fund_series_name'],
                  isin=record['fund_isin'], series_lei=record['fund_series_lei'],
                  registrant_cik=record['fund_registrant_cik'], evidence=(sec, bvl, application))
    # Nasdaq first-listing date is not evidenced by the source; the anchor identifies
    # the disclosure record, not a fabricated issuance or listing start date.
    return InstrumentMaster([
        ListingRecord(**common, mic='XNAS', lifecycle_anchor='sec-class-C000235743-observed-2025'),
        ListingRecord(**common, mic='XLIM', valid_from=date(2025, 12, 10),
                      lifecycle_anchor='bvl-registration-2025-12-10'),
    ])


def listing_wire(item: ListingRecord):
    hint = route_hint(item.mic, asset_class=item.asset_class, provider=item.provider)
    limitations = ['Historical visibility starts at evidence retrieval, not record effective date.',
                   'A null valid_from means the listing start is unverified.']
    if item.registrant_cik:
        limitations.insert(0, 'Registrant CIK is the fund trust, not automatically the security issuer.')
    if item.isin is None:
        limitations.append('No ISIN is present in the source record; absence is not proof that none exists.')
    if item.mic is None:
        limitations.append('Provider-identified asset: the ticker field is the provider symbol, not an exchange ticker.')
        limitations.append("Currency is the unit of the provider's reference metric, not a trading currency.")
    return {'listing_id': item.listing_id, **item.model_dump(mode='json'), 'isin_state': item.isin_state,
            'filings_provider': hint['filings'], 'prices_provider': hint['prices'], 'route': hint,
            'limitations': limitations}
