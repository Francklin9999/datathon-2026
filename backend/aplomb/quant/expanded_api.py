"""Session-bound portfolio comparisons, risk matrices and explicit-input models.

The router depends on the same session validation as the application and reads
profiles through its session-owned service. Cross-currency calculations always use
snapshot FX in target units per original currency unit; no rate is invented.
"""
import base64
import hashlib
import math
import time
from dataclasses import asdict
from datetime import date, datetime, timezone
from datetime import time as day_time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aplomb.api.errors import Conflict, ServiceError
from aplomb.api.repositories import timestamp
from aplomb.api.storage import canonical
from aplomb.intelligence.entities import Evidence
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.quant import metrics as mx

from .covariance import sample_covariance
from .exposures import FundConstituent, FundSnapshot
from .factors import FactorPeriod, ReturnPeriod, fit_factor_exposures
from .liquidity import SaleAssumption, sale_scenario
from .nested import nested_look_through


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


class CovarianceInput(BaseRequest):
    profile_id: Annotated[str, Field(alias='profileId', min_length=1, max_length=40)]
    version: int = Field(strict=True, ge=1)


class LiquidityAssumptionInput(InputModel):
    ticker: Annotated[str, Field(min_length=1, max_length=40)]
    sale_dates: Annotated[list[date], Field(alias='saleDates', max_length=3660)]
    daily_capacity: Annotated[float, Field(alias='dailyCapacity', ge=0)]
    half_spread_bps: Annotated[float, Field(alias='halfSpreadBps', ge=0, le=10_000)]
    impact_bps: Annotated[float, Field(alias='impactBps', ge=0, le=10_000)]
    source: Annotated[str, Field(min_length=1, max_length=1000)]
    as_of: date = Field(alias='asOf')


class LiquidityInput(InputModel):
    version: int = Field(strict=True, ge=1)
    as_of: date = Field(alias='asOf')
    through: date
    target_withdrawal: Annotated[float | None, Field(alias='targetWithdrawal', ge=0)] = None
    assumptions: Annotated[list[LiquidityAssumptionInput], Field(max_length=40)]


class ConstituentInput(InputModel):
    isin: str
    weight: float


class FundInput(InputModel):
    fund_isin: str = Field(alias='fundIsin')
    holdings_date: date = Field(alias='holdingsDate')
    evidence: Evidence
    constituents: Annotated[list[ConstituentInput], Field(max_length=5000)]


class NestedInput(InputModel):
    as_of: date = Field(alias='asOf')
    historical: bool = False
    positions: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    known_funds: Annotated[list[str], Field(alias='knownFunds', max_length=200)]
    snapshots: Annotated[list[FundInput], Field(max_length=50)]
    max_depth: Annotated[int, Field(alias='maxDepth', ge=1, le=8)] = 8


class FactorInputRow(InputModel):
    start: date
    end: date
    risk_free: float = Field(alias='riskFree')
    factors: Annotated[dict[str, float], Field(max_length=8)]


class FactorSource(InputModel):
    origin: Literal['user', 'imported', 'source']
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    available_at: date = Field(alias='availableAt')
    evidence: Evidence | None = None

    @model_validator(mode='after')
    def source_requires_evidence(self):
        if self.origin == 'source' and self.evidence is None:
            raise ValueError('source factor inputs require dated attributed evidence')
        return self


class ActiveFactorInput(BaseRequest):
    version: int = Field(strict=True, ge=1)
    names: Annotated[list[str], Field(min_length=1, max_length=8)]
    source: FactorSource | None = None
    factors: Annotated[list[FactorInputRow] | None, Field(max_length=5000)] = None
    capture_id: Annotated[str | None, Field(alias='captureId', pattern=r'^capture_[a-f0-9]{64}$')] = None

    @model_validator(mode='after')
    def exclusive_source(self):
        if self.capture_id and (self.source is not None or self.factors is not None):
            raise ValueError('captured factor ID cannot be combined with explicit factor rows')
        if not self.capture_id and (self.source is None or self.factors is None):
            raise ValueError('provide a captured factor ID or both explicit factor source and rows')
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


def _captured_factor_rows(request: Request, sid: str, capture_id: str, day: date, mode: str,
                          currency: str, master_dates: list[str], names: list[str]):
    """Read session-owned, rights-allowed French factors without treating capture time as observation time."""
    from aplomb.datastore.errors import IngestionError
    from aplomb.datastore.fama_french import read_capture as read_french
    from aplomb.datastore.financial_connectors import PROVIDERS, provider_status

    if provider_status(PROVIDERS['fama-french'])['status'] != 'configured':
        raise ServiceError('upstream_unavailable', 'French factor data-use permission is not configured')
    if currency != 'USD':
        raise ServiceError('insufficient_data', 'Captured French US factors are in USD; use a USD-reporting profile or explicitly supply same-currency factors')
    if set(names) - {'market_excess', 'size', 'value'}:
        raise ServiceError('validation_error', 'Captured French factors support market_excess, size and value')
    store = getattr(request.app.state, 'financial_capture_store', None)
    if store is None:
        raise ServiceError('upstream_unavailable', 'Financial capture storage is not configured')
    owner = hashlib.sha256(sid.encode()).hexdigest()
    record = store.get('cache', f'FINANCIAL#{owner}#fama-french', capture_id)
    if not record or record.get('sessionId') != sid:
        raise ServiceError('not_found', 'Factor capture not found in this session')
    try:
        response = record['response']
        raw = base64.b64decode(record['rawBase64'], validate=True)
        if (response['provider'] != 'fama-french' or response['captureId'] != capture_id
                or hashlib.sha256(raw).hexdigest() != response['source']['rawSha256']
                or hashlib.sha256(canonical(response)).hexdigest() != record['responseSha256']):
            raise ValueError('capture integrity mismatch')
        captured = datetime.fromisoformat(response['availableAt'].replace('Z', '+00:00'))
        if captured.tzinfo is None or captured > datetime.now(timezone.utc):
            raise ValueError('invalid capture availability')
        if mode == 'historical' and captured > datetime.combine(day, day_time.max, timezone.utc):
            raise ServiceError('insufficient_data', 'French factor capture was not yet available at the historical cutoff')
        records = response['records']
        if not isinstance(records, list) or not records:
            raise ValueError('empty captured factors')
        query = response['query']
        limit = query['limit']
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise ValueError('invalid capture limit')
        parsed = read_french(raw, response['source'])
        expected = [asdict(row) for row in parsed.through(response['availableAt'], query['asOf'])][-limit:]
        if records != expected or response['unit'] != 'fractional daily factor return':
            raise ValueError('normalized factor rows do not match the captured source')
        rows = sorted(records, key=lambda row: row['date'])
        if len({row['date'] for row in rows}) != len(rows):
            raise ValueError('duplicate factor dates')
        previous = {rows[i]['date']: rows[i - 1]['date'] for i in range(1, len(rows))}
        matching = {master_dates[i + 1]: master_dates[i] for i in range(len(master_dates) - 1)}
        factor_rows = []
        for row in rows:
            end = row['date']
            start = previous.get(end)
            if start is None or matching.get(end) != start or date.fromisoformat(end) > day:
                continue
            factor_rows.append(FactorPeriod(date.fromisoformat(start), date.fromisoformat(end),
                float(row['risk_free']), {name: float(row[name]) for name in names}, capture_id))
        provenance = {'origin': 'source', 'description': 'French daily US three-factor captured data',
                      'currency': 'USD', 'captureId': capture_id,
                      'availableAt': response['availableAt'], 'source': response['source'],
                      'sourceVersion': response['version'], 'unit': response['unit'],
                      'limitations': response['limitations']}
        return factor_rows, provenance
    except (KeyError, ValueError, TypeError, OverflowError, IngestionError):
        raise ServiceError('upstream_unavailable', 'Stored factor capture failed validation') from None


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
                                'Private appraisals, actual transactions, tax and costs are excluded; values are modeled.',
                                'Local fact IDs are per portfolio; never combine their ledgers without remapping.']}

    @router.post('/v1/risk/covariance')
    def covariance(body: CovarianceInput, request: Request, sid: str = Depends(session_dependency)):
        provider, snapshot, gate, day = _snapshot(request, body.as_of, body.knowledge_mode)
        profile = _profile(provider, sid, body.profile_id, body.version)
        window = body.window.model_dump(mode='json', exclude_none=True)
        engine = _engine(gate, profile, profile.reporting_currency, window)
        tickers = sorted(_weights(profile))
        try:
            wr = engine.window(window)
            series = [engine.asset_returns(t, wr.i0, wr.i1) for t in tickers]
            matrix = sample_covariance(series)
            source_facts = engine.series_inputs(tickers, wr.i0, wr.i1)
            return {'profileId': profile.profile_id, 'profileVersion': profile.version, 'asOf': day.isoformat(),
                    'dataVersion': snapshot.data_version, 'currency': profile.reporting_currency,
                    'window': window, 'tickers': tickers, 'dailyCovariance': matrix,
                    'unit': 'fractional daily return squared', 'sample': {'start': wr.period['start'],
                    'end': wr.period['end'], 'returnObservations': wr.i1 - wr.i0, 'ddof': 1},
                    'sourceFactIds': source_facts, 'facts': engine.ledger.wire(),
                    'unavailable': 'short_history' if matrix is None else None,
                    'limitations': ['Exactly aligned master-calendar returns and adjusted close; no missing-price fill.',
                                    'Sample covariance is descriptive and not a future risk forecast.']}
        except Unavailable as exc:
            return {'profileId': profile.profile_id, 'profileVersion': profile.version, 'asOf': day.isoformat(),
                    'dataVersion': snapshot.data_version, 'currency': profile.reporting_currency,
                    'window': window, 'tickers': tickers, 'dailyCovariance': None, 'sample': None,
                    'unit': 'fractional daily return squared', 'sourceFactIds': [], 'facts': engine.ledger.wire(),
                    'unavailable': exc.reason, 'limitations': [exc.detail]}
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post('/v1/profiles/{profile_id}/liquidity-analysis')
    def liquidity(profile_id: str, body: LiquidityInput, request: Request, sid: str = Depends(session_dependency)):
        provider, snapshot, _, _ = _snapshot(request, None, 'current')
        profile = _profile(provider, sid, profile_id, body.version)
        tickers = [row.ticker for row in body.assumptions]
        if len(tickers) != len(set(tickers)):
            raise HTTPException(status_code=422, detail='duplicate liquidity inputs')
        try:
            values = {p.ticker: profile.portfolio.total_value * p.weight_pct / 100 for p in profile.portfolio.positions}
            supplied = {row.ticker: SaleAssumption(tuple(row.sale_dates), row.daily_capacity, row.half_spread_bps,
                        row.impact_bps, row.source, row.as_of) for row in body.assumptions}
            result = sale_scenario(values, supplied, body.as_of, body.through, body.target_withdrawal)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {**result, 'profileId': profile.profile_id, 'profileVersion': profile.version,
                'currency': profile.reporting_currency, 'dataVersion': snapshot.data_version,
                'limitations': [*result['limitations'], 'User-entered sale inputs are not independently verified.',
                                'Private/illiquid appraisals are excluded unless explicitly modeled separately.']}

    @router.post('/v1/risk/nested-fund-look-through')
    def nested(body: NestedInput, sid: str = Depends(session_dependency)):
        try:
            snapshots = [FundSnapshot(s.fund_isin, s.holdings_date, s.evidence,
                         tuple(FundConstituent(c.isin, c.weight) for c in s.constituents)) for s in body.snapshots]
            keyed = {snapshot.fund_isin: snapshot for snapshot in snapshots}
            if len(keyed) != len(snapshots) or len(set(body.known_funds)) != len(body.known_funds):
                raise ValueError('duplicate fund snapshots or identifiers')
            result = nested_look_through(body.positions, keyed, set(body.known_funds), body.as_of,
                                         historical=body.historical, max_depth=body.max_depth)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {'asOf': body.as_of.isoformat(), 'direct': result.direct, 'indirect': result.indirect,
                'unresolvedWeight': result.unresolved_weight, 'unresolvedByReason': result.unresolved_by_reason,
                'sourceIds': result.source_ids, 'snapshotDates': result.snapshot_dates, 'paths': result.paths,
                'omittedPaths': result.omitted_paths,
                'sources': {snapshot.fund_isin: snapshot.evidence.model_dump(mode='json') for snapshot in snapshots},
                'limitations': ['User-supplied captures and exact identifiers have not been independently verified.',
                                'Partial disclosures, unknown fund snapshots, cycles and depth limits remain unresolved.',
                                'No derivatives, issuer aggregation or implicit securities crosswalk is inferred.']}

    @router.post('/v1/profiles/{profile_id}/factor-exposure')
    def factor_exposure(profile_id: str, body: ActiveFactorInput, request: Request, sid: str = Depends(session_dependency)):
        provider, snapshot, gate, day = _snapshot(request, body.as_of, body.knowledge_mode)
        profile = _profile(provider, sid, profile_id, body.version)
        if body.source is not None:
            if body.source.currency != profile.reporting_currency:
                raise HTTPException(status_code=422, detail='factor currency must match portfolio reporting currency')
            known_day = day if body.knowledge_mode == 'historical' else datetime.now(timezone.utc).date()
            if body.source.available_at > known_day or (body.source.evidence and not body.source.evidence.visible(
                    known_day, historical=True)):
                raise HTTPException(status_code=422, detail='factor input not available at requested cutoff')
            if any(row.end > day for row in body.factors or []):
                raise HTTPException(status_code=422, detail='factor observations cannot follow analysis cutoff')
        window = body.window.model_dump(mode='json', exclude_none=True)
        engine = _engine(gate, profile, profile.reporting_currency, window)
        weights = _weights(profile)
        try:
            wr = engine.window(window)
            series = [engine.asset_returns(t, wr.i0, wr.i1) for t in weights]
            returns = mx.portfolio_returns(list(weights.values()), series)
            dates = engine.market.dates[wr.i0:wr.i1 + 1]
            portfolio = [ReturnPeriod(date.fromisoformat(dates[i]), date.fromisoformat(dates[i + 1]), ret)
                         for i, ret in enumerate(returns)]
            if body.capture_id:
                factors, provenance = _captured_factor_rows(request, sid, body.capture_id, day,
                    body.knowledge_mode, profile.reporting_currency, list(dates), body.names)
            else:
                factors = [FactorPeriod(row.start, row.end, row.risk_free, row.factors, body.source.description)
                           for row in body.factors or []]
                provenance = body.source.model_dump(mode='json', by_alias=True)
            fit = fit_factor_exposures(portfolio, factors, body.names)
            fact_ids = engine.series_inputs(list(weights), wr.i0, wr.i1)
        except Unavailable as exc:
            return {'profileId': profile.profile_id, 'profileVersion': profile.version, 'asOf': day.isoformat(),
                    'dataVersion': snapshot.data_version, 'currency': profile.reporting_currency,
                    'state': 'insufficient_data', 'reason': exc.reason, 'detail': exc.detail,
                    'sourceFactIds': [], 'facts': engine.ledger.wire(), 'limitations': [exc.detail]}
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {'profileId': profile.profile_id, 'profileVersion': profile.version, 'asOf': day.isoformat(),
                'dataVersion': snapshot.data_version, 'currency': profile.reporting_currency,
                'state': 'calculated', 'alphaPerPeriod': fit.alpha_per_period, 'betas': fit.betas,
                'residualStdev': fit.residual_stdev, 'rSquared': fit.r_squared,
                'observations': fit.observations, 'firstStart': fit.first_start.isoformat(),
                'lastEnd': fit.last_end.isoformat(), 'excludedReturns': fit.excluded_returns,
                'excludedFactors': fit.excluded_factors, 'source': provenance,
                'sourceFactIds': fact_ids, 'facts': engine.ledger.wire(),
                'limitations': ['Caller-supplied factors are unverified; captured factors are source-attributed but may be revised.',
                                'Portfolio uses adjusted closes and constant daily weights on the master calendar.',
                                'Exact start/end intersection only; OLS is descriptive and not a forecast.']}

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
