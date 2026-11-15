"""Instrument master: exact-ISIN crosswalk, coverage, and trusted adapter publication."""
from datetime import date

from fastapi import APIRouter, Depends, Query

from aplomb.api.errors import ServiceError, unavailable
from aplomb.api.limiter import SessionLimiter

from .coinmetrics import CoinMetricsError
from .gleif import GLEIFError
from .master import ASSET_COVERAGE, MIC_ROUTES, PROVIDER_ROUTES
from .master_adapters import publish_coinmetrics_asset, publish_gleif_pair, publish_wikidata
from .master_repository import crosswalk
from .wikidata import WikidataError, source_contact

DAY = r'^\d{4}-\d{2}-\d{2}$'


def _day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ServiceError('validation_error', 'Invalid as-of date') from exc


def master_router(settings, store, session_dependency):
    router = APIRouter()
    limiter = SessionLimiter(store)

    @router.get('/v1/intelligence/master/crosswalk')
    def identifier_crosswalk(isin: str = Query(min_length=12, max_length=12),
                             as_of: str = Query(pattern=DAY), sid: str = Depends(session_dependency)):
        try:
            return crosswalk(store, sid, isin, _day(as_of))
        except ValueError as exc:
            raise ServiceError('validation_error', str(exc)) from exc

    @router.get('/v1/intelligence/master/coverage')
    def coverage(sid: str = Depends(session_dependency)):
        return {'asset_kinds': list(ASSET_COVERAGE),
                'mic_routes': [{'mic': mic, **route} for mic, route in sorted(MIC_ROUTES.items())],
                'provider_routes': [{'provider': name, **route} for name, route in sorted(PROVIDER_ROUTES.items())],
                'wikidata_contact_configured': bool(source_contact(settings)),
                'limitations': ['Markets without a row have no adapter and are never routed to SEC by default.',
                                'Listing records exist only where a trusted adapter published them.']}

    @router.post('/v1/intelligence/master/adapters/gleif-pair')
    def gleif_pair(isin: str = Query(min_length=12, max_length=12), lei: str = Query(min_length=20, max_length=20),
                   sid: str = Depends(session_dependency)):
        limiter.take(sid, 'master-gleif', 4, 60)
        try:
            return publish_gleif_pair(store, sid, isin, lei)
        except GLEIFError as exc:
            raise unavailable('GLEIF exact security/issuer lookup') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', str(exc)) from exc

    @router.post('/v1/intelligence/master/adapters/wikidata')
    def wikidata_identifiers(isin: str = Query(min_length=12, max_length=12),
                             sid: str = Depends(session_dependency)):
        limiter.take(sid, 'master-wikidata', 4, 60)
        contact = source_contact(settings)
        if not contact:
            raise unavailable('Wikidata descriptive source contact configuration')
        try:
            return publish_wikidata(store, sid, isin, contact=contact)
        except WikidataError as exc:
            raise unavailable('Wikidata identifier assertions') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', str(exc)) from exc

    @router.post('/v1/intelligence/master/adapters/coinmetrics/{asset}')
    def coinmetrics_asset(asset: str, sid: str = Depends(session_dependency)):
        limiter.take(sid, 'master-coinmetrics', 4, 60)
        try:
            return publish_coinmetrics_asset(store, sid, asset)
        except CoinMetricsError as exc:
            raise unavailable('Coin Metrics Community or permitted noncommercial use') from exc
        except ValueError as exc:
            raise ServiceError('validation_error', str(exc)) from exc

    return router
