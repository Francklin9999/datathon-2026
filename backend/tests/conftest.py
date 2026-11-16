"""Release discarded test applications between cases."""

import gc

import pytest
from fastapi.dependencies import models


@pytest.fixture(autouse=True)
def release_test_applications():
    yield
    # FastAPI 0.163.0's global caches retain route closures and their application
    # datasets. Clear these lookups so discarded test apps can be collected.
    # These private APIs are tied to the pinned FastAPI version; review them
    # when upgrading rather than silently skipping cleanup.
    for cache in (
        models._is_gen_callable_cached,
        models._is_async_gen_callable_cached,
        models._is_coroutine_callable_cached,
    ):
        cache.cache_clear()
    gc.collect()
