"""Security identity, temporal boundaries and GLEIF candidate search failures."""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from aplomb.intelligence import Evidence, GLEIFClient, GLEIFError, Relationship
from aplomb.intelligence.entities import valid_isin, valid_lei
from pydantic import ValidationError

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)
EVIDENCE = Evidence(source_id='issuer-file', url='https://example.org/holdings.csv', content_sha256='a' * 64,
                    available_at=NOW, retrieved_at=NOW, licence='test fixture')


def test_strong_identifiers_are_checksum_validated():
    assert valid_isin('US0378331005') and not valid_isin('US0378331004')
    assert valid_lei('HWUPKR0MPOU8FGXBT394') and not valid_lei('HWUPKR0MPOU8FGXBT395')


def test_relationships_require_a_rule_and_block_future_capture():
    relation = dict(subject_id='asset_1', relation='SECURITY_ISSUED_BY', object_id='LEI:HWUPKR0MPOU8FGXBT394',
                    valid_from=date(2025, 1, 1), evidence=EVIDENCE)
    direct = Relationship(evidence_class='direct', **relation)
    candidate = Relationship(evidence_class='candidate', **{**relation, 'object_id': 'LEI:OTHER'})
    # The identifier the world service serves is bound to the edge and its evidence.
    assert direct.relationship_id.startswith('rel_') and direct.relationship_id != candidate.relationship_id
    # Evidence captured on 2026-11-15 is invisible to a historical question about the day before.
    assert not direct.evidence.visible(date(2026, 11, 14), historical=True)
    assert direct.evidence.visible(date(2026, 11, 15), historical=True)
    with pytest.raises(ValidationError):
        Relationship(evidence_class='derived', **relation)
    with pytest.raises(ValidationError):
        Relationship(evidence_class='direct', **{**relation, 'valid_to': date(2024, 12, 31)})


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
