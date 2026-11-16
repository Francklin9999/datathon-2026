"""The hashes the issuer relationship view shows resolve to raw captures for their own session only.

IssuerEvidence offers "Download raw capture" for GLEIF edge sources (entity_gleif_level2,
entity_gleif_isin_lei) through GET /v1/intelligence/relationships/captures/{sha256}, which
returns gleif_relations.stored_payload.
"""
import json

from aplomb.api.storage import MemoryStore
from aplomb.intelligence.gleif_relations import stored_payload
from aplomb.intelligence.relationship_graph import relationship_view

ISIN = 'US0378331005'
LEI = 'HWUPKR0MPOU8FGXBT394'


def pair_page(url: str) -> bytes:
    return json.dumps({'data': [{'type': 'isins', 'attributes': {'isin': ISIN, 'lei': LEI}}],
                       'meta': {'pagination': {'currentPage': 1, 'lastPage': 1}}}).encode()


def level2_down(url: str):
    return 503, b''


def test_exact_pair_hash_is_served_to_the_capturing_session_only():
    store = MemoryStore()
    view = relationship_view(store, 'session-a', lei=LEI, isin=ISIN, l2_fetch=level2_down, pair_fetch=pair_page)

    issued = [e for e in view['edges'] if e['relation'] == 'SECURITY_ISSUED_BY']
    assert len(issued) == 1
    source = issued[0]['source']
    assert source['source_id'] == 'entity_gleif_isin_lei'
    assert stored_payload(store, 'session-a', source['content_sha256']) == pair_page('')
    assert stored_payload(store, 'session-b', source['content_sha256']) is None
    # Level 2 failure is reported, not hidden; the verified pair is kept.
    assert view['corporate_tree'][LEI]['status'] == 'source_unavailable'

    # Non-GLEIF sources (the indexed N-PORT transcript) carry a hash the capture route does not serve.
    assert any(e['source'] and e['source']['source_id'] == 'fund_sec_nport_indexed_excerpt' for e in view['edges'])
    for edge in view['edges']:
        if edge['source'] and edge['source']['source_id'] not in ('entity_gleif_isin_lei', 'entity_gleif_level2'):
            assert stored_payload(store, 'session-a', edge['source']['content_sha256']) is None
