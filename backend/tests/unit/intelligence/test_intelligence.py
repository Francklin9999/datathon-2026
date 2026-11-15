"""Security identity, temporal boundaries, documented exposure and provider failures."""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from aplomb.intelligence import (
    Evidence,
    GLEIFClient,
    GLEIFError,
    Holding,
    HoldingsSnapshot,
    Instrument,
    Relationship,
    RelationshipStore,
    portfolio_lookthrough,
)
from aplomb.intelligence.entities import valid_isin, valid_lei
from pydantic import ValidationError

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
EVIDENCE = Evidence(source_id='issuer-file', url='https://example.org/holdings.csv', content_sha256='a' * 64,
                    available_at=NOW, retrieved_at=NOW, licence='test fixture')
AAPL = 'isin:US0378331005'
MSFT = 'isin:US5949181045'
IVV = 'isin:US4642872000'
SPY = 'isin:US78462F1030'


def test_strong_identifiers_and_listings_are_exchange_and_lifecycle_aware():
    assert valid_isin('US0378331005') and not valid_isin('US0378331004')
    assert valid_lei('HWUPKR0MPOU8FGXBT394') and not valid_lei('HWUPKR0MPOU8FGXBT395')
    data = {'ticker': 'XYZ', 'currency': 'USD', 'valid_from': '2020-01-01', 'name': 'Example', 'evidence': EVIDENCE}
    first = Instrument(exchange_mic='XNAS', **data)
    assert first.listing_id == Instrument(exchange_mic='XNAS', **data).listing_id
    assert first.listing_id != Instrument(exchange_mic='XNYS', **data).listing_id
    assert first.listing_id != Instrument(exchange_mic='XNAS', **{**data, 'valid_from': '2023-01-01'}).listing_id
    with pytest.raises(ValidationError):
        Instrument(exchange_mic='XNAS', isin='US0378331004', **data)
    with pytest.raises(ValidationError):
        Holding(security_id='AAPL', weight_pct=2)


def test_relationships_distinguish_unverified_and_block_future_capture():
    relation = dict(subject_id='asset_1', relation='SECURITY_ISSUED_BY', object_id='LEI:HWUPKR0MPOU8FGXBT394',
                    valid_from=date(2025, 1, 1), evidence=EVIDENCE)
    direct = Relationship(evidence_class='direct', **relation)
    candidate = Relationship(evidence_class='candidate', **{**relation, 'object_id': 'LEI:OTHER'})
    store = RelationshipStore([direct, candidate])
    assert store.find('asset_1', date(2026, 11, 14), historical=True) == []
    assert store.find('asset_1', date(2026, 11, 15)) == [direct]
    assert store.find('asset_1', date(2026, 11, 15), include_unverified=True) == [direct, candidate]
    with pytest.raises(ValidationError):
        Relationship(evidence_class='derived', **relation)
    with pytest.raises(ValueError):
        RelationshipStore([direct, direct])


def test_lookthrough_combines_only_exact_ids_and_exposes_missing_data():
    pos = [Holding(security_id=IVV, weight_pct=40), Holding(security_id=SPY, weight_pct=40),
           Holding(security_id=AAPL, weight_pct=20)]
    snapshots = [
        HoldingsSnapshot(fund_id=IVV, effective_date=date(2026, 11, 12), evidence=EVIDENCE,
                         holdings=[Holding(security_id=AAPL, weight_pct=10), Holding(security_id=MSFT, weight_pct=5)]),
        HoldingsSnapshot(fund_id=SPY, effective_date=date(2026, 11, 12), evidence=EVIDENCE,
                         holdings=[Holding(security_id=AAPL, weight_pct=5)]),
    ]
    out = portfolio_lookthrough(pos, snapshots, date(2026, 11, 15), fund_ids={IVV, SPY})
    assert out['overlap'] == [AAPL]
    assert next(x['weight_pct'] for x in out['exposures'] if x['security_id'] == AAPL) == pytest.approx(26)
    assert out['unresolved_portfolio_weight_pct'] == pytest.approx(72)
    historical = portfolio_lookthrough(pos, snapshots, date(2026, 11, 14), fund_ids={IVV, SPY}, historical=True)
    assert len(historical['unavailable_funds']) == 2
    assert historical['unresolved_portfolio_weight_pct'] == 80
    assert historical['exposures'] == [{'security_id': AAPL, 'weight_pct': 20, 'contributing_funds': []}]


def test_no_holdings_snapshot_never_becomes_zero_underlying_exposure():
    out = portfolio_lookthrough([Holding(security_id=IVV, weight_pct=100)], [], NOW.date(), fund_ids={IVV})
    assert out['exposures'] == []
    assert out['unresolved_portfolio_weight_pct'] == 100
    with pytest.raises(ValidationError):
        HoldingsSnapshot(fund_id=IVV, effective_date=NOW.date(), evidence=EVIDENCE,
                         holdings=[Holding(security_id=AAPL, weight_pct=10)], complete=True)


def test_gleif_captured_search_keeps_candidates_and_source_hash():
    raw_path = Path('docs/evidence/global-platform/gleif-apple-capture.raw.json')
    payload = raw_path.read_bytes()
    captured = []
    client = GLEIFClient(fetch=lambda url: payload, clock=lambda: NOW, capture=captured.append)
    result = client.search('Apple Inc.')
    assert captured == [payload]
    assert result['source']['content_sha256'] == hashlib.sha256(payload).hexdigest()
    assert result['total'] >= result['returned'] > 0
    assert all(x['match_status'] == 'candidate' and valid_lei(x['lei']) for x in result['items'])
    assert result['source']['published_at'] is None
    assert json.loads(payload)['data']


def test_gleif_rejects_invalid_content_and_query():
    with pytest.raises(ValueError):
        GLEIFClient(fetch=lambda _: b'').search('x')
    with pytest.raises(GLEIFError):
        GLEIFClient(fetch=lambda _: b'{invalid').search('Apple')
    with pytest.raises(GLEIFError):
        GLEIFClient(fetch=lambda _: b'x' * 2_000_001).search('Apple')
