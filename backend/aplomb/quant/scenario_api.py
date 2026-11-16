"""HTTP boundary for user-supplied, first-order sensitivity scenarios."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from aplomb.api.errors import unavailable
from aplomb.intelligence.entities import Evidence

from .cashflows import requirement_scenario
from .exposures import (
    FundConstituent,
    FundSnapshot,
    Sensitivity,
    Shock,
    disclosed_overlap,
    linear_shock,
    look_through,
)
from .factors import FactorPeriod, ReturnPeriod, fit_factor_exposures
from .target_funding import compare_target_funding

router = APIRouter()


class ScenarioModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)


class ShockInput(ScenarioModel):
    kind: Literal['interest_rate', 'credit_spread', 'currency', 'commodity', 'factor']
    key: Annotated[str, Field(min_length=1, max_length=120)]
    change: float
    assumption: Annotated[str, Field(min_length=1, max_length=1000)]


class SensitivityInput(ScenarioModel):
    value: float
    source: Annotated[str, Field(min_length=1, max_length=1000)]
    as_of: date = Field(alias='asOf')


class ScenarioInput(ScenarioModel):
    as_of: date = Field(alias='asOf')
    weights: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    shock: ShockInput
    sensitivities: Annotated[dict[str, SensitivityInput], Field(max_length=200)]


class TargetFundingInput(ScenarioModel):
    total_value: Annotated[float, Field(alias='totalValue')]
    before: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    target: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    external_flow: Annotated[float, Field(alias='externalFlow')]


class ConstituentInput(ScenarioModel):
    isin: str
    weight: float


class FundInput(ScenarioModel):
    fund_isin: str = Field(alias='fundIsin')
    holdings_date: date = Field(alias='holdingsDate')
    evidence: Evidence
    constituents: Annotated[list[ConstituentInput], Field(max_length=5000)]


class LookThroughInput(ScenarioModel):
    as_of: date = Field(alias='asOf')
    historical: bool = False
    positions: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    snapshots: Annotated[list[FundInput], Field(max_length=50)]


class CashflowInput(ScenarioModel):
    date: date
    amount: float


class RequirementsInput(ScenarioModel):
    as_of: date = Field(alias='asOf')
    through: date
    liquid_capital: float = Field(alias='liquidCapital')
    annual_return_pct: float = Field(alias='annualReturnPct')
    cashflows: Annotated[list[CashflowInput], Field(max_length=1000)]


class ReturnPeriodInput(ScenarioModel):
    start: date
    end: date
    value: float


class FactorPeriodInput(ScenarioModel):
    start: date
    end: date
    risk_free: float = Field(alias='riskFree')
    factors: Annotated[dict[str, float], Field(max_length=8)]
    source: Annotated[str, Field(min_length=1, max_length=1000)]


class FactorFitInput(ScenarioModel):
    names: Annotated[list[str], Field(min_length=1, max_length=8)]
    returns: Annotated[list[ReturnPeriodInput], Field(max_length=5000)]
    factors: Annotated[list[FactorPeriodInput], Field(max_length=5000)]


@router.post('/v1/risk/scenario')
def scenario(request: ScenarioInput) -> dict:
    try:
        shock = Shock(request.shock.kind, request.shock.key, request.shock.change, request.shock.assumption)
        sensitivities = {key: Sensitivity(value.value, value.source, value.as_of)
                         for key, value in request.sensitivities.items()}
        result = linear_shock(request.weights, shock, sensitivities, request.as_of)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'impactFraction': result.impact_fraction, 'knownImpactFraction': result.known_impact_fraction,
            'contributions': result.contributions, 'missing': result.missing, 'unit': 'fraction',
            'asOf': request.as_of.isoformat(), 'shock': request.shock.model_dump(),
            'sensitivities': {key: item.model_dump(by_alias=True, mode='json')
                              for key, item in request.sensitivities.items()},
            'model': 'First-order sum of weight × signed sensitivity × decimal shock; '
                     'rate/spread inputs are basis points. No convexity, interactions, costs or forecast.'}


@router.post('/v1/decision/target-funding')
def target_funding(request: TargetFundingInput) -> dict:
    try:
        result = compare_target_funding(request.total_value, request.before, request.target, request.external_flow)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'beforeValue': result.before_value, 'afterValue': result.after_value,
            'externalFlow': result.external_flow, 'purchases': result.purchases,
            'sales': result.sales, 'changes': result.changes,
            'assumptions': ['Positive flow is new capital; negative flow is a withdrawal.',
                            'Final weights use after-flow capital. Sales plus deposit fund purchases and withdrawals.',
                            'Simultaneous frictionless hypothetical changes; no orders, taxes or costs.']}


@router.post('/v1/risk/fund-look-through')
def fund_look_through(request: LookThroughInput) -> dict:
    try:
        snapshots = [FundSnapshot(s.fund_isin, s.holdings_date, s.evidence,
                                  tuple(FundConstituent(c.isin, c.weight) for c in s.constituents))
                     for s in request.snapshots]
        keyed = {snapshot.fund_isin: snapshot for snapshot in snapshots}
        if len(keyed) != len(snapshots):
            raise ValueError('duplicate fund snapshots')
        if any(key not in request.positions for key in keyed):
            raise ValueError('every fund snapshot must refer to a portfolio position')
        result = look_through(request.positions, keyed, request.as_of, historical=request.historical)
        overlap = [{'firstIsin': left.fund_isin, 'secondIsin': right.fund_isin,
                    'weight': disclosed_overlap(left, right, request.as_of, historical=request.historical)}
                   for index, left in enumerate(snapshots) for right in snapshots[index + 1:]]
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'direct': result.direct, 'indirect': result.indirect, 'unresolvedWeight': result.unresolved_weight,
            'snapshotDates': result.snapshot_dates, 'sourceIds': result.source_ids, 'overlap': overlap,
            'sources': {snapshot.fund_isin: snapshot.evidence.model_dump(mode='json') for snapshot in snapshots},
            'limitations': ['Inputs and provenance are supplied by the caller and not independently verified.',
                            'Exact ISINs only; partial disclosures are not scaled up and overlap is a lower bound.',
                            'One fund level; derivatives, issuer groups, hedges and nested funds are not inferred.']}


@router.post('/v1/profiles/{profile_id}/requirements-scenario')
def requirements_scenario(profile_id: str, body: RequirementsInput, request: Request,
                          x_aplomb_session: Annotated[str | None, Header()] = None) -> dict:
    provider = request.app.state.services.profiles
    if provider is None:
        raise unavailable('Profile service')
    # The router is registered with the existing session-validation dependency.
    profile = provider.get(x_aplomb_session, profile_id)
    requirements = profile.investor_context.requirements if profile.investor_context else []
    try:
        result = requirement_scenario(requirements, as_of=body.as_of, through=body.through,
            liquid_capital=body.liquid_capital, annual_return_pct=body.annual_return_pct,
            cashflows=[(flow.date, flow.amount) for flow in body.cashflows])
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**result, 'profileId': profile.profile_id, 'profileVersion': profile.version,
            'currency': profile.reporting_currency, 'inputs': body.model_dump(mode='json', by_alias=True),
            'requirements': [entry.to_wire() for entry in requirements],
            'assumptions': ['Only explicitly entered requirements and cash flows are considered.',
                            'Input liquid capital excludes assets unavailable for spending.',
                            'No tax, fees, inflation, borrowing or unentered income is inferred.',
                            'Return is an assumption and scenario results are not a forecast.']}


@router.post('/v1/risk/factor-fit')
def factor_fit(body: FactorFitInput) -> dict:
    try:
        result = fit_factor_exposures(
            [ReturnPeriod(row.start, row.end, row.value) for row in body.returns],
            [FactorPeriod(row.start, row.end, row.risk_free, row.factors, row.source) for row in body.factors],
            body.names)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'alphaPerPeriod': result.alpha_per_period, 'betas': result.betas,
            'residualStdev': result.residual_stdev, 'rSquared': result.r_squared,
            'observations': result.observations, 'firstStart': result.first_start,
            'lastEnd': result.last_end, 'sourceIds': result.source_ids,
            'excludedReturns': result.excluded_returns, 'excludedFactors': result.excluded_factors,
            'limitations': ['Inputs are supplied by the caller; source and currency are not independently verified.',
                            'Exact matching of return period start and end; no missing data is filled.',
                            'OLS exposure is descriptive of the supplied sample, not a causal estimate or forecast.']}
