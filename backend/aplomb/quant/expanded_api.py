"""Session-bound portfolio comparisons and documented position details.

The router depends on the same session validation as the application and reads
profiles through its session-owned service. Cross-currency calculations always use
snapshot FX in target units per original currency unit; no rate is invented.
"""
import math
import time
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aplomb.api.errors import Conflict, ServiceError
from aplomb.api.repositories import timestamp
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.quant import metrics as mx


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)


class WindowInput(InputModel):
    code: Literal['full', 'ytd', '1y', '3y', '5y', 'custom'] = 'full'
    start: date | None = None
    end: date | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.code == 'custom' and (not self.start or not self.end or self.start > self.end):
            raise ValueError('custom window requires ordered start and end dates')
        if self.code != 'custom' and (self.start or self.end):
            raise ValueError('start and end are only valid for custom windows')
        return self


class BaseRequest(InputModel):
    as_of: date | None = Field(default=None, alias='asOf')
    knowledge_mode: Literal['current', 'historical'] = Field(default='current', alias='knowledgeMode')
    window: WindowInput = Field(default_factory=WindowInput)


class ProfileVersion(InputModel):
    profile_id: str = Field(alias='profileId', min_length=1, max_length=40)
    version: int = Field(strict=True, ge=1)


class CompareInput(BaseRequest):
    profiles: Annotated[list[ProfileVersion], Field(min_length=2, max_length=5)]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]

    @model_validator(mode='after')
    def unique(self):
        if len({item.profile_id for item in self.profiles}) != len(self.profiles):
            raise ValueError('comparison profiles must be unique')
        return self


class QuantityInput(InputModel):
    ticker: Annotated[str, Field(min_length=1, max_length=40)]
    quantity: Annotated[float, Field(ge=0)]
    as_of: date = Field(alias='asOf')
    origin: Literal['user', 'imported']
    source: Annotated[str, Field(min_length=1, max_length=1000)]


class PositionDetailsInput(InputModel):
    version: int = Field(strict=True, ge=1)
    quantities: Annotated[list[QuantityInput], Field(max_length=40)] = Field(default_factory=list)


def _snapshot(request: Request, as_of: date | None, mode: str):
    provider = request.app.state.services.profiles
    if provider is None:
        raise ServiceError('upstream_unavailable', 'Profile service unavailable')
    snapshot = provider.snapshot()
    day = as_of or date.fromisoformat(snapshot.data_as_of)
    if day > date.fromisoformat(snapshot.data_as_of):
        raise ServiceError('validation_error', 'As-of date cannot be later than the snapshot observation cutoff')
    return provider, snapshot, snapshot.gate(day, mode), day


def _profile(provider, session_id: str, profile_id: str, version: int):
    profile = provider.get(session_id, profile_id)
    if profile.version != version:
        raise Conflict('Profile changed; reload before calculating')
    return profile


def _weights(profile):
    return {p.ticker: p.weight_pct / 100 for p in profile.portfolio.positions if p.weight_pct > 0}


def _engine(gate, profile, currency, window=None):
    return QuantEngine(gate, LocalLedger(), currency=currency, subject_id=profile.profile_id,
                       created_at=timestamp(time.time()), window=window, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())


def _conversion(engine, source: str, target: str, as_of: str):
    rate = engine.market.conversion_at(source, target, as_of)
    if rate is None:
        return None
    value, refs = rate
    if not math.isfinite(value) or value <= 0:
        raise ValueError('conversion rate must be positive and finite')
    source_rows = [{'datasetId': ref[0], 'currency': ref[1], 'observationDate': ref[2], 'availableAt': ref[3]}
                   for ref in refs]
    passports = [engine._source(dataset, sum(ref[0] == dataset for ref in refs))
                 for dataset in sorted({ref[0] for ref in refs})]
    return {'rate': value, 'direction': f'{target}/{source}', 'asOf': as_of,
            'sourceRows': source_rows, 'sources': passports}


def _common_full_window(profiles, gate, currency, window):
    """Align full histories to the longest continuous calendar where all assets are priced.

    Named/custom horizons are never shortened or relabeled. Missing intermediate
    observations are not filled; one common contiguous segment is selected for the
    full-history comparison and its actual bounds are reported explicitly.
    """
    if window['code'] != 'full':
        return window, 'requested_window'
    engine = _engine(gate, profiles[0], currency, window)
    try:
        wr = engine.window(window)
        tickers = sorted({ticker for profile in profiles for ticker in _weights(profile)})
        series = [engine.market.series(ticker) for ticker in tickers]
        if any(not item.synthetic and item.n_obs_master < 252 for item in series):
            return window, 'insufficient_history'
        best_start = best_end = run_start = None
        for index in range(wr.i0, wr.i1 + 1):
            if all(item.levels[index] is not None for item in series):
                if run_start is None:
                    run_start = index
                if best_start is None or index - run_start > best_end - best_start:
                    best_start, best_end = run_start, index
            else:
                run_start = None
        if best_start is None or best_end <= best_start:
            return window, 'no_common_contiguous_sample'
        if (best_start, best_end) == (wr.i0, wr.i1):
            return window, 'requested_window'
        return {'code': 'custom', 'start': engine.market.dates[best_start],
                'end': engine.market.dates[best_end]}, 'longest_common_contiguous_sample'
    except Unavailable:
        return window, 'insufficient_history'


def _comparison_row(profile, gate, currency, window):
    engine = _engine(gate, profile, currency, window)
    weights = _weights(profile)
    row = {'profileId': profile.profile_id, 'profileVersion': profile.version, 'name': profile.name,
           'sourceCurrency': profile.reporting_currency, 'currency': currency,
           'sourceCapital': profile.portfolio.total_value, 'capital': None, 'conversion': None,
           'positions': [], 'metrics': {}, 'facts': {}}
    try:
        conversion = _conversion(engine, profile.reporting_currency, currency, engine.ctx.as_of)
        if conversion is None:
            row['capitalUnavailable'] = f'no visible {currency}/{profile.reporting_currency} rate'
        else:
            capital = profile.portfolio.total_value * conversion['rate']
            if not math.isfinite(capital):
                raise ValueError('capital conversion overflows')
            row.update(capital=capital, conversion=conversion)
        wr = engine.window(window)
        view = engine.view(weights, f'comparison:{profile.profile_id}',
                           row['capital'] if row['capital'] is not None else profile.portfolio.total_value,
                           after_move=False, window=window)
        # A capital figure without visible FX must never be relabeled as target currency.
        if conversion is not None:
            snapshot = view.snapshot().to_wire()
            row['positions'] = snapshot['positions']
        portfolio_metrics = view.metrics()
        numbers = {'volatilityPct': portfolio_metrics.volatility_pct, 'maxDrawdownPct': portfolio_metrics.max_drawdown_pct,
                   'stress2022Pct': portfolio_metrics.stress2022_pct, 'hhi': portfolio_metrics.hhi,
                   'effectiveN': portfolio_metrics.effective_n}
        row['metrics'] = numbers
        row['factIds'] = portfolio_metrics.fact_ids
        row['missing'] = portfolio_metrics.missing
        try:
            levels = engine.portfolio_levels(weights, wr.i0, wr.i1)
            value = mx.period_return_pct(levels)
            row['metrics']['returnPct'] = value
            row['factIds']['return.period'] = engine.add_series_fact(
                metric='return.period', value=value, subject=view.subject, variant_key=view.variant,
                window_code=wr.code, tickers=list(weights), i0=wr.i0, i1=wr.i1,
                method_id='M_PORT_CONST_WEIGHTS', window_spec=wr.spec,
                inputs=view._weight_inputs(),
                label={'en': f'{profile.name}: common-currency portfolio return',
                       'fr': f'{profile.name} : rendement du portefeuille en devise commune'})
        except Unavailable as exc:
            row['metrics']['returnPct'] = None
            row['missing']['return.period'] = exc.reason
        row['sample'] = {'start': wr.period['start'], 'end': wr.period['end'], 'returnObservations': wr.i1 - wr.i0}
        row['facts'] = engine.ledger.wire()
    except Unavailable as exc:
        row['unavailable'] = {'reason': exc.reason, 'detail': exc.detail}
        row['facts'] = engine.ledger.wire()
    return row


def make_router(session_dependency) -> APIRouter:
    router = APIRouter()

    @router.post('/v1/portfolios/compare')
    def compare(body: CompareInput, request: Request, sid: str = Depends(session_dependency)):
        provider, snapshot, gate, day = _snapshot(request, body.as_of, body.knowledge_mode)
        profiles = [_profile(provider, sid, entry.profile_id, entry.version) for entry in body.profiles]
        window = body.window.model_dump(mode='json', exclude_none=True)
        try:
            applied_window, sample_rule = _common_full_window(profiles, gate, body.currency, window)
            rows = [_comparison_row(p, gate, body.currency, applied_window) for p in profiles]
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        valid_samples = [row.get('sample') for row in rows if row.get('sample')]
        same_sample = bool(valid_samples) and len(valid_samples) == len(rows) and all(
            sample == valid_samples[0] for sample in valid_samples) and all(
            row['metrics'].get('returnPct') is not None for row in rows)
        return {'asOf': day.isoformat(), 'dataVersion': snapshot.data_version, 'knowledgeMode': body.knowledge_mode,
                'currency': body.currency, 'window': window, 'windowApplied': applied_window,
                'sampleRule': sample_rule, 'sameSample': same_sample, 'portfolios': rows,
                'limitations': ['Constant weights rebalanced each master return period; adjusted closes already include source corporate actions.',
                                'FX is target units per source unit via CAD, last visible quote on or before each date; no backward fill.',
                                # Each portfolio row has its own local fact IDs; code combining rows must remap
                                # them. A code note, not a user-facing limitation (QA 4.5b).
                                'Private appraisals, actual transactions, tax and costs are excluded; values are modeled.']}

    @router.post('/v1/profiles/{profile_id}/position-details')
    def position_details(profile_id: str, body: PositionDetailsInput, request: Request, sid: str = Depends(session_dependency)):
        provider, snapshot, _, day = _snapshot(request, None, 'current')
        profile = _profile(provider, sid, profile_id, body.version)
        tickers = [q.ticker for q in body.quantities]
        if len(tickers) != len(set(tickers)) or set(tickers) - {p.ticker for p in profile.portfolio.positions}:
            raise HTTPException(status_code=422, detail='quantities must have unique owned tickers')
        if any(item.as_of > datetime.now(timezone.utc).date() for item in body.quantities):
            raise HTTPException(status_code=422, detail='quantity observations cannot be dated in the future')
        supplied = {item.ticker: item for item in body.quantities}
        rows = []
        for position in profile.portfolio.positions:
            q = supplied.get(position.ticker)
            saved_quantity = getattr(position, 'quantity', None)
            provenance = ({'quantity': q.quantity, 'asOf': q.as_of.isoformat(), 'origin': q.origin,
                           'source': q.source, 'inputScope': 'request'} if q is not None else
                          {'quantity': saved_quantity, 'asOf': getattr(position, 'quantity_as_of', None),
                           'origin': getattr(position, 'quantity_origin', None),
                           'source': getattr(position, 'quantity_source', None), 'inputScope': 'saved_profile'}
                          if saved_quantity is not None else None)
            rows.append({'ticker': position.ticker, 'weightPct': position.weight_pct,
                         'modeledPositionValue': profile.portfolio.total_value * position.weight_pct / 100,
                         'currency': profile.reporting_currency, 'quantity': provenance,
                         'valueBasis': 'modeled weight × reported portfolio capital'})
        return {'profileId': profile.profile_id, 'profileVersion': profile.version, 'asOf': day.isoformat(),
                'dataVersion': snapshot.data_version, 'currency': profile.reporting_currency, 'positions': rows,
                'limitations': ['Quantity is explicitly entered/imported and not independently verified.',
                                'Modeled position value uses profile weights and capital, not quantity times an executable price.',
                                'Quantity overrides apply only to this read-only request.']}

    return router
