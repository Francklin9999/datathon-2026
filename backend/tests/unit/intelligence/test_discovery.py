from datetime import datetime, timezone
from pathlib import Path

import pytest
from aplomb.api.storage import MemoryStore, Write
from aplomb.intelligence.discovery import DiscoveryStorageError, EntityDiscovery
from aplomb.intelligence.gleif import GLEIFClient, GLEIFError

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


def test_source_capture_is_immutable_cached_and_session_isolated():
    raw = Path('docs/evidence/global-platform/gleif-apple-capture.raw.json').read_bytes()
    store, calls = MemoryStore(), []
    def factory(**kwargs):
        calls.append(1)
        return GLEIFClient(fetch=lambda _: raw, clock=lambda: NOW, **kwargs)
    service = EntityDiscovery(store, factory, clock=lambda: NOW.timestamp())
    first = service.search('session-a', 'Apple')
    assert service.search('session-a', 'Apple') == first and len(calls) == 1
    service.search('session-b', 'Apple')
    assert len(calls) == 2
    captures = [i for i in store._items.values() if i['sk'].startswith('CAPTURE#')]
    assert len(captures) == 2 and all(i['value']['raw'].encode() == raw for i in captures)
    capture = captures[0]
    item = capture['value']
    store.transact([Write('cache', capture['pk'], capture['sk'], {**item, 'revision': 2, 'raw': '{}'}, 1)])
    with pytest.raises(DiscoveryStorageError, match='read validated'):
        service.search('session-a', 'Apple')
    assert len(calls) == 2  # corruption is not silently replaced by a new provider response


def test_expired_entity_cache_does_not_hide_provider_failure():
    raw = Path('docs/evidence/global-platform/gleif-apple-capture.raw.json').read_bytes()
    store, now = MemoryStore(), [NOW.timestamp()]
    service = EntityDiscovery(store, lambda **kwargs: GLEIFClient(fetch=lambda _: raw, clock=lambda: NOW, **kwargs), clock=lambda: now[0])
    service.search('session-a', 'Apple')
    now[0] += 3601
    def unavailable(**kwargs):
        raise GLEIFError('source_unavailable')
    service.client_factory = unavailable
    with pytest.raises(GLEIFError):
        service.search('session-a', 'Apple')
    assert len([i for i in store._items.values() if i['sk'].startswith('CAPTURE#')]) == 1
