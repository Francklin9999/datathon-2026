"""HTTP boundary for user-supplied target-funding and cash-requirement scenarios."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from aplomb.api.errors import unavailable

from .cashflows import requirement_scenario
from .target_funding import compare_target_funding

router = APIRouter()


class ScenarioModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)


class TargetFundingInput(ScenarioModel):
    total_value: Annotated[float, Field(alias='totalValue')]
    before: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    target: Annotated[dict[str, float], Field(min_length=1, max_length=200)]
    external_flow: Annotated[float, Field(alias='externalFlow')]


class CashflowInput(ScenarioModel):
    date: date
    amount: float


class RequirementsInput(ScenarioModel):
    as_of: date = Field(alias='asOf')
    through: date
    liquid_capital: float = Field(alias='liquidCapital')
    annual_return_pct: float = Field(alias='annualReturnPct')
    cashflows: Annotated[list[CashflowInput], Field(max_length=1000)]


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
