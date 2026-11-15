"""Session-bound HTTP port for the explicit joint planning calculation."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from aplomb.api.errors import Conflict, ServiceError, unavailable

from .joint_plan import PlanInputError, joint_plan

router = APIRouter()
Origin = Literal['user', 'imported', 'system_default', 'assumption']


class JointModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)


class CapitalSourceInput(JointModel):
    kind: Literal['account', 'private_asset', 'portfolio', 'outside']
    id: Annotated[str, Field(min_length=1, max_length=120)]
    amount: Annotated[float, Field(ge=0)]
    origin: Origin
    source_description: Annotated[str | None, Field(alias='sourceDescription', max_length=1000)] = None


class CashFlowInput(JointModel):
    date: date
    amount: float
    origin: Origin
    description: Annotated[str | None, Field(max_length=1000)] = None


class JointPlanInput(JointModel):
    profile_version: Annotated[int, Field(alias='profileVersion', strict=True, ge=1)]
    as_of: date = Field(alias='asOf')
    through: date
    annual_return_pct: Annotated[float, Field(alias='annualReturnPct', gt=-100, le=100)]
    annual_inflation_pct: Annotated[float, Field(alias='annualInflationPct', gt=-100, le=100)]
    amount_basis: Literal['nominal', 'as_of_real'] = Field(alias='amountBasis')
    capital_sources: Annotated[list[CapitalSourceInput], Field(alias='capitalSources', max_length=200)]
    outside_is_additional: bool = Field(alias='outsideIsAdditional', strict=True)
    cashflows: Annotated[list[CashFlowInput], Field(max_length=1000)]
    goal_indexes: Annotated[list[Annotated[int, Field(strict=True, ge=0)]], Field(alias='goalIndexes', max_length=20)]
    requirement_indexes: Annotated[list[Annotated[int, Field(strict=True, ge=0)]], Field(alias='requirementIndexes', max_length=100)]
    liquidity_aggregation: Literal['independent', 'overlapping'] = Field(alias='liquidityAggregation')
    allocation_treatment: Literal['shared_pool'] = Field(alias='allocationTreatment')


class JointPlanResult(JointModel):
    profile_id: str = Field(alias='profileId')
    profile_version: int = Field(alias='profileVersion')
    currency: str
    as_of: date = Field(alias='asOf')
    through: date
    capital: float
    capital_sources: list[dict[str, Any]] = Field(alias='capitalSources')
    annual_return_pct: float = Field(alias='annualReturnPct')
    annual_inflation_pct: float = Field(alias='annualInflationPct')
    amount_basis: Literal['nominal', 'as_of_real'] = Field(alias='amountBasis')
    liquidity_aggregation: Literal['independent', 'overlapping'] = Field(alias='liquidityAggregation')
    allocation_treatment: Literal['shared_pool'] = Field(alias='allocationTreatment')
    selected_goal_indexes: list[int] = Field(alias='selectedGoalIndexes')
    selected_requirement_indexes: list[int] = Field(alias='selectedRequirementIndexes')
    state: Literal['missing_inputs', 'scenario_shortfall', 'scenario_funded_through']
    missing_inputs: list[str] = Field(alias='missingInputs')
    goals: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    cashflows: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    events: list[dict[str, Any]]
    required_initial_capital: float | None = Field(alias='requiredInitialCapital')
    additional_initial_capital: float | None = Field(alias='additionalInitialCapital')
    first_shortfall_date: date | None = Field(alias='firstShortfallDate')
    ending_liquid_value: float | None = Field(alias='endingLiquidValue')
    assumptions: list[str]
    method: str
    claim_ids: list[str] = Field(alias='claimIds')
    fact_ids: list[str] = Field(alias='factIds')
    priority_plan: dict[str, Any] | None = Field(alias='priorityPlan')


@router.post('/v1/profiles/{profile_id}/joint-plan', response_model=JointPlanResult)
def profile_joint_plan(profile_id: str, body: JointPlanInput, request: Request,
                       x_aplomb_session: Annotated[str | None, Header()] = None):
    provider = request.app.state.services.profiles
    if provider is None:
        raise unavailable('Profile service')
    # The parent app registers this router with the existing session dependency.
    profile = provider.get(x_aplomb_session, profile_id)
    if profile.version != body.profile_version:
        raise Conflict('Profile changed since the planning inputs were selected')
    try:
        return joint_plan(profile, as_of=body.as_of, through=body.through,
            annual_return_pct=body.annual_return_pct, annual_inflation_pct=body.annual_inflation_pct,
            amount_basis=body.amount_basis,
            capital_sources=[item.model_dump(mode='json', by_alias=True) for item in body.capital_sources],
            outside_is_additional=body.outside_is_additional,
            cashflows=[item.model_dump(mode='json', by_alias=True) for item in body.cashflows],
            goal_indexes=body.goal_indexes, requirement_indexes=body.requirement_indexes,
            liquidity_aggregation=body.liquidity_aggregation, allocation_treatment=body.allocation_treatment)
    except PlanInputError as exc:
        raise ServiceError('validation_error', str(exc)) from exc
