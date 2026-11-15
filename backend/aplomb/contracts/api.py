"""Named request/response envelopes for contracts/api.md (no HTTP handlers)."""

from typing import Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import TypeAliasType

from .base import (
    Boolean,
    Count,
    DataVersion,
    FactId,
    ISODate,
    ISODateTime,
    NonNegative,
    Number,
    Percent,
    ProfileId,
    RunId,
    String,
    Ticker,
    WireModel,
)
from .catalog import LimitationCode, MethodId
from .models import (
    ApiError,
    Asset,
    AssetClass,
    AttentionSignal,
    CheckResult,
    ConditionalPolicy,
    CountryExposure,
    Currency,
    DatasetPassport,
    DecisionRequest,
    EventId,
    Evidence,
    Experience,
    Facility,
    Fact,
    Hazard,
    HoldingExposure,
    HorizonYears,
    I18nText,
    InvestorContext,
    Lang,
    Objective,
    PartialProfile,
    PolicyRule,
    PortfolioSnapshot,
    Position,
    Preferences,
    ProposedMove,
    RiskLevel,
    RuleCheck,
    RuleId,
    Run,
    RunKind,
    RunStatus,
    SabotageMode,
    SeriesPoint,
    Verdict,
    VerdictCounts,
    WindowSpec,
    WorldEvent,
    WorldLayer,
    WorldPortfolioAssessment,
)


class HealthResponse(WireModel):
    status: Literal["ok"]
    time: ISODateTime


class AssetsResponse(WireModel):
    items: list[Asset]
    next_cursor: String | None
    total: Count


class EntityCandidate(WireModel):
    lei: String
    legal_name: String
    jurisdiction: String | None
    entity_status: String | None
    record_url: String
    match_status: Literal["candidate"]


class EntitySource(WireModel):
    provider: String
    url: String
    retrieved_at: ISODateTime
    available_at: ISODateTime
    published_at: ISODateTime | None
    content_sha256: String
    licence: String
    licence_url: String


class EntitySearchResponse(WireModel):
    query: String
    items: list[EntityCandidate]
    total: Count
    returned: Count
    rejected: Count
    truncated: Boolean
    source: EntitySource
    limitations: list[String]


class AssetMeasurement(WireModel):
    value: Number | None
    fact_id: FactId | None
    unavailable_reason: String | None


class AssetAnalyticsResponse(WireModel):
    asset: Asset
    currency: Currency
    data_version: DataVersion
    as_of: ISODate
    window: WindowSpec
    metrics: dict[str, AssetMeasurement]
    facts: dict[str, Fact]


class FetchAssetResponse(WireModel):
    asset: Asset
    accepted: Boolean
    rejected_reason: I18nText | None
    passport: DatasetPassport


class PageviewsPoint(WireModel):
    date: ISODate
    views: Count


class AttentionResponse(WireModel):
    signal: AttentionSignal
    fact: Fact | None
    evidence: Evidence | None
    series: list[PageviewsPoint]


class RiskDiagnosticsResponse(WireModel):
    profile_id: ProfileId
    currency: Currency
    data_version: DataVersion
    window: WindowSpec
    metrics: dict[str, AssetMeasurement]
    contributions: dict[str, AssetMeasurement]
    facts: dict[str, Fact]


class ProfilesResponse(WireModel):
    items: list["Profile"]


class InitialPortfolio(WireModel):
    total_value: NonNegative
    positions: list[Position]


class CreateProfileRequest(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=40)]
    age: Count | None
    risk_level: RiskLevel
    horizon_years: HorizonYears
    objective: Objective
    experience: Experience
    reporting_currency: Currency
    preferences: Preferences
    portfolio: InitialPortfolio | None
    rules: list[PolicyRule] | None
    from_draft_run_id: RunId | None
    investor_context: InvestorContext | None = None


class UpdateProfileRequest(CreateProfileRequest):
    version: Annotated[int, Field(strict=True, ge=1)]


class RulePatchRequest(WireModel):
    model_config = {
        "json_schema_extra": {"anyOf": [{"required": ["threshold"]}, {"required": ["enabled"]}]}
    }
    threshold: Number = None
    enabled: Boolean = None

    @model_validator(mode="after")
    def has_edit(self):
        if type(self) is RulePatchRequest and not self.model_fields_set:
            raise ValueError("supply threshold or enabled")
        return self


class RulePatchResponse(WireModel):
    rule: PolicyRule
    profile_version: Count


class DeriveRulesRequest(WireModel):
    reset: Boolean
    window: WindowSpec = None


class DeriveRulesResponse(WireModel):
    rules: list[PolicyRule]
    facts: dict[FactId, Fact]
    profile_version: Count


class GoalFundingScenario(WireModel):
    name: String
    state: Literal["missing_assumptions", "scenario_funded", "scenario_shortfall"]
    projected_value: NonNegative | None
    funding_gap: NonNegative | None
    fact_ids: dict[str, FactId]
    missing_inputs: list[String] = Field(default_factory=list)


class GoalFundingResponse(WireModel):
    profile_id: ProfileId
    currency: Currency
    overallocated: Boolean
    unallocated_value: NonNegative
    goals: list[GoalFundingScenario]
    facts: dict[str, Fact]


class DuplicateProfileRequest(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=40)] | None = None


class AddExposureLimitRequest(WireModel):
    dimension: Literal["country", "currency"]
    key: Annotated[String, Field(pattern=r"^[A-Z]{3}$")]
    threshold: Annotated[Number, Field(ge=0, le=100)]
    version: Annotated[int, Field(strict=True, ge=1)]


class AddCustomRuleRequest(WireModel):
    dimension: Literal["position", "sector", "asset_class", "country", "currency", "theme"]
    key: Annotated[String, Field(min_length=1, max_length=32)]
    operation: Literal["cap", "floor"]
    threshold: Annotated[Number, Field(ge=0, le=100)]
    version: Annotated[int, Field(strict=True, ge=1)]


class AddConditionalRuleRequest(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=120)]
    conditional: ConditionalPolicy
    origin: Literal["user", "imported", "system_default", "assumption"] = "user"
    version: Annotated[int, Field(strict=True, ge=1)]


class ArchiveProfileRequest(WireModel):
    archived: Boolean
    version: Annotated[int, Field(strict=True, ge=1)]


class CreateAccountRequest(WireModel):
    native_value_origin: Literal["user", "imported", "assumption"] = "user"
    native_value_source: Annotated[String, Field(min_length=1, max_length=1000)] | None = None
    currency: Currency | None = None
    name: Annotated[String, Field(min_length=1, max_length=80)]
    version: Annotated[int, Field(strict=True, ge=1)]
    portfolio: InitialPortfolio


class SelectAccountRequest(WireModel):
    version: Annotated[int, Field(strict=True, ge=1)]


class EditAccountRequest(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=80)] | None = None
    portfolio: InitialPortfolio | None = None
    version: Annotated[int, Field(strict=True, ge=1)]

    @model_validator(mode="after")
    def has_edit(self):
        if self.name is None and self.portfolio is None:
            raise ValueError("supply a name or portfolio")
        if self.name is not None and not self.name.strip():
            raise ValueError("account name must contain a visible character")
        return self


class RefreshAccountRequest(WireModel):
    version: Annotated[int, Field(strict=True, ge=1)]
    as_of: ISODate | None = None


class TransferAccountRequest(WireModel):
    version: Annotated[int, Field(strict=True, ge=1)]
    destination_account_id: String
    amount_reporting: Annotated[Number, Field(gt=0)]


class PrivateAssetRequest(WireModel):
    version: Annotated[int, Field(strict=True, ge=1)]
    asset_id: Annotated[String, Field(pattern=r"^priv_[0-9a-f]{12}$")] | None = None
    name: Annotated[String, Field(min_length=1, max_length=120)]
    asset_type: Annotated[String, Field(min_length=1, max_length=80)]
    liquidity_notes: Annotated[String, Field(max_length=1000)] = ""
    valuation_date: ISODate
    origin: Literal["user", "imported"]
    source_description: Annotated[String, Field(min_length=1, max_length=1000)]
    native_currency: Currency
    native_value: Annotated[Number, Field(gt=0)]


class UpdatePortfolioRequest(InitialPortfolio):
    version: Annotated[int, Field(strict=True, ge=1)]


class OverviewReturns(WireModel):
    ytd_pct: Number | None
    y1_pct: Number | None
    y3_pct: Number | None
    y5_pct: Number | None
    fact_ids: dict[str, FactId]


class OverviewRisk(WireModel):
    volatility_pct: NonNegative | None
    max_drawdown_pct: NonNegative | None
    worst12m_pct: Number | None = Field(alias="worst12mPct")
    stress2022_pct: Number | None = Field(alias="stress2022Pct")
    risk_category: RiskLevel
    fact_ids: dict[str, FactId]


class TopPosition(WireModel):
    ticker: Ticker
    name: String
    weight_pct: Number
    market_value: NonNegative
    return1y_pct: Number | None = Field(alias="return1yPct")
    asset_class: AssetClass


class Concentration(WireModel):
    hhi: NonNegative
    effective_n: NonNegative
    top_positions: list[TopPosition]


class Correlation(WireModel):
    tickers: list[Ticker]
    matrix: list[list[Number]]


class OverviewResponse(WireModel):
    profile_id: ProfileId
    as_of: ISODate
    data_version: DataVersion
    window: WindowSpec
    snapshot: PortfolioSnapshot
    returns: OverviewReturns
    risk: OverviewRisk
    concentration: Concentration
    correlation: Correlation | None
    rule_checks: list[RuleCheck]
    verdict: Verdict
    counts: VerdictCounts
    facts: dict[FactId, Fact]
    limitations: list[LimitationCode]


class Benchmark(WireModel):
    ticker: Ticker
    series: list[SeriesPoint]


class PerformanceResponse(WireModel):
    window: WindowSpec
    currency: Currency
    series: list[SeriesPoint]
    benchmark: Benchmark | None
    method: MethodId
    limitations: list[LimitationCode]


class FrontierMetrics(WireModel):
    vol_pct: NonNegative
    hist_return_pct: Number


class FrontierAsset(FrontierMetrics):
    ticker: Ticker


class FrontierPoint(FrontierMetrics):
    weights: list[Position]


class FrontierResponse(WireModel):
    window: WindowSpec
    currency: Currency
    assets: list[FrontierAsset]
    min_var_frontier: list[FrontierPoint]
    hist_mv_frontier: list[FrontierPoint]
    portfolio: FrontierMetrics
    portfolio_after: FrontierMetrics | None
    vol_budget_pct: NonNegative
    limitations: list[LimitationCode]
    facts: dict[FactId, Fact]


# ----- Strategies (api.md §3.13): standing rules simulated on history, never executed -----

StrategyFrequency = TypeAliasType("StrategyFrequency", Literal["monthly", "quarterly", "yearly"])
CostBps = Annotated[Number, Field(ge=0, le=100)]


class RebalanceStrategy(WireModel):
    """Bring weights back to today's target on a calendar or when one drifts past a band."""
    kind: Literal["rebalance"]
    trigger: Literal["calendar", "band"]
    frequency: StrategyFrequency = None
    band_pts: Annotated[Number, Field(ge=1, le=25)] = None
    cost_bps: CostBps = None


class ContributeStrategy(WireModel):
    """Add a fixed amount every period, split by target weights or into the most underweight."""
    kind: Literal["contribute"]
    amount: Annotated[Number, Field(gt=0, le=1_000_000)]
    frequency: Literal["monthly", "quarterly"]
    allocation: Literal["target", "underweight"]
    cost_bps: CostBps = None


class RiskGuardStrategy(WireModel):
    """Move part of the growth assets to a defensive asset after a fall; move back once it recovers."""
    kind: Literal["risk_guard"]
    trigger_drawdown_pct: Annotated[Number, Field(ge=2, le=50)]
    shift_pct: Annotated[Number, Field(ge=10, le=100)]
    reentry_drawdown_pct: Annotated[Number, Field(ge=0, le=50)]
    safe_ticker: Ticker | None = None
    cost_bps: CostBps = None

    @model_validator(mode="after")
    def _reentry_below_trigger(self):
        if self.reentry_drawdown_pct >= self.trigger_drawdown_pct:
            raise ValueError("reentryDrawdownPct must be below triggerDrawdownPct")
        return self


StrategyConfig = TypeAliasType(
    "StrategyConfig",
    Annotated[RebalanceStrategy | ContributeStrategy | RiskGuardStrategy, Field(discriminator="kind")],
)


class StrategySimulateRequest(WireModel):
    strategy: StrategyConfig
    window: WindowSpec = None


class StrategyTrade(WireModel):
    ticker: Ticker
    amount: Number          # signed, reporting currency: positive buys, negative sells
    weight_before_pct: Number
    weight_after_pct: Number


class StrategyAction(WireModel):
    date: ISODate
    kind: Literal["rebalance", "contribute", "de_risk", "re_risk"]
    reason: I18nText
    value_before: NonNegative
    trades: list[StrategyTrade]
    cost: NonNegative


class StrategyMetrics(WireModel):
    end_value: NonNegative
    invested: NonNegative           # starting value plus every contribution
    gain: Number                    # end value minus invested
    twr_pct: Number                 # time-weighted return over the window (contributions removed)
    vol_pct: NonNegative | None
    max_drawdown_pct: NonNegative | None
    turnover_pct: NonNegative       # sum of traded amounts ÷ average value × 100
    costs: NonNegative
    actions: Count


class StrategyRuleDays(WireModel):
    rule_id: RuleId
    code: String
    strategy_months: Count
    baseline_months: Count


class StrategyPlanCheck(WireModel):
    months_checked: Count
    strategy_months_in_conflict: Count
    baseline_months_in_conflict: Count
    by_rule: list[StrategyRuleDays]


class StrategyNextAction(WireModel):
    due: Boolean
    summary: I18nText
    trades: list[StrategyTrade]


class StrategySimulation(WireModel):
    window: WindowSpec
    currency: Currency
    strategy: StrategyConfig
    series: list[SeriesPoint]
    baseline: list[SeriesPoint]
    invested: list[SeriesPoint] | None
    metrics: StrategyMetrics
    baseline_metrics: StrategyMetrics
    actions: list[StrategyAction]
    actions_truncated: Boolean
    plan: StrategyPlanCheck
    next_action: StrategyNextAction
    method: MethodId
    limitations: list[LimitationCode]


class CachedBriefResponse(WireModel):
    run: Run | None
    stale: Boolean


class ParseRequest(WireModel):
    profile_id: ProfileId
    text: Annotated[String, Field(min_length=1, max_length=600)]
    lang: Lang


class RuleOverride(RulePatchRequest):
    # Rule overrides may carry just an ID: PATCH's nonempty-edit constraint does
    # not apply to the array element defined in API §4.2.
    model_config = {"json_schema_extra": {}}
    rule_id: RuleId


class CheckRequest(WireModel):
    profile_id: ProfileId
    move: ProposedMove | None
    rule_overrides: list[RuleOverride] = None
    window: WindowSpec = None
    as_of: ISODate = None
    compare_funding: Boolean = None
    knowledge_mode: Literal["current", "historical"] | None = None


class RebalanceRequest(WireModel):
    profile_id: ProfileId
    profile_version: Annotated[int, Field(strict=True, ge=1)]
    positions: Annotated[list[Position], Field(min_length=1, max_length=40, json_schema_extra={"tsType": "Position[]"})]
    window: WindowSpec | None = None


class AllocationChange(WireModel):
    ticker: Ticker
    before_pct: Percent
    target_pct: Percent
    change_pct: Number


class RebalanceResponse(WireModel):
    profile_id: ProfileId
    profile_version: Annotated[int, Field(strict=True, ge=1)]
    currency: Currency
    total_value: NonNegative
    as_of: ISODate
    data_version: DataVersion
    window: WindowSpec
    changes: list[AllocationChange]
    portfolio_before: PortfolioSnapshot
    portfolio_after: PortfolioSnapshot
    verdict_before: Verdict
    verdict_after: Verdict
    counts_before: VerdictCounts
    counts_after: VerdictCounts
    rule_checks_before: list[RuleCheck]
    rule_checks_after: list[RuleCheck]
    facts: dict[FactId, Fact]
    assumptions: list[I18nText]


class BatchCheckRequest(WireModel):
    items: Annotated[list[CheckRequest], Field(max_length=5)]


class BatchCheckResponse(WireModel):
    results: list[CheckResult | ApiError]


class CreateDecisionRunRequest(WireModel):
    kind: Literal["decision"]
    profile_id: ProfileId
    lang: Lang
    request: DecisionRequest
    original_text: String = None
    window: WindowSpec = None


class CreateRebalanceRunRequest(WireModel):
    kind: Literal["rebalance"]
    profile_id: ProfileId
    profile_version: Annotated[int, Field(strict=True, ge=1)]
    lang: Lang
    positions: Annotated[list[Position], Field(min_length=1, max_length=40)]
    window: WindowSpec = None


class CreatePortfolioBriefRunRequest(WireModel):
    kind: Literal["portfolio_brief"]
    profile_id: ProfileId
    lang: Lang
    window: WindowSpec = None
    force: Boolean = None


class CreateEventBriefRunRequest(WireModel):
    kind: Literal["event_brief"]
    profile_id: ProfileId
    lang: Lang
    event_id: EventId


class CreateReplayRunRequest(WireModel):
    kind: Literal["replay"]
    profile_id: ProfileId
    lang: Lang
    request: DecisionRequest
    as_of: ISODate
    window: WindowSpec = None


class CreateProfileDraftRunRequest(WireModel):
    kind: Literal["profile_draft"]
    lang: Lang
    text: String
    fields: PartialProfile = None


CreateRunRequest = TypeAliasType(
    "CreateRunRequest",
    Annotated[
        CreateDecisionRunRequest
        | CreateRebalanceRunRequest
        | CreatePortfolioBriefRunRequest
        | CreateEventBriefRunRequest
        | CreateReplayRunRequest
        | CreateProfileDraftRunRequest,
        Field(discriminator="kind"),
    ],
)


class QueuedRunResponse(WireModel):
    run_id: RunId
    status: Literal["queued"]
    poll_after_ms: Literal[1000]


class CachedRunResponse(WireModel):
    run_id: RunId
    status: Literal["succeeded"]


class RunSummary(WireModel):
    run_id: RunId
    kind: RunKind
    status: RunStatus
    profile_id: ProfileId | None
    created_at: ISODateTime
    title: I18nText
    verdict: Verdict | None
    duration_ms: NonNegative | None


class RunsResponse(WireModel):
    items: list[RunSummary]
    next_cursor: String | None


class AnswerRequest(WireModel):
    question_id: String
    value: String


class AnswerResponse(WireModel):
    run_id: RunId
    status: Literal["running"]


class CancelResponse(WireModel):
    run_id: RunId
    status: Literal["cancelled"]


class FactUsage(WireModel):
    sentence_ids: list[String]
    rule_ids: list[RuleId]


class FactResponse(WireModel):
    fact: Fact
    inputs: list[Fact]
    used_by: FactUsage


class SabotageRequest(WireModel):
    mode: SabotageMode = "invented_number"
    lang: Lang


class RevealRequest(WireModel):
    until: ISODate = None


class WorldLayersResponse(WireModel):
    items: list[WorldLayer]


class WorldEventItem(WorldEvent):
    portfolio_relevant: Boolean = None


class WorldEventsResponse(WireModel):
    items: list[WorldEventItem]
    next_cursor: String | None
    total: Count
    coverage: "Period"
    data_version: DataVersion


class WorldGeographicRelationship(WireModel):
    relationship_id: String
    relation: Literal["EVENT_OCCURRED_AT", "FACILITY_LOCATED_IN"]
    subject_id: String
    object_id: String
    evidence_class: Literal["direct", "derived", "candidate", "model_inferred"]
    source_id: String
    source_url: String
    normalized_record_sha256: String
    retrieved_at: ISODateTime
    limitations: list[String]


class WorldEventResponse(WireModel):
    event: WorldEvent
    related: list[WorldEvent]
    exposures: list[HoldingExposure]
    geographic_relationships: list[WorldGeographicRelationship] = []
    assessment: WorldPortfolioAssessment | None = None


class WorldExposureResponse(WireModel):
    items: list[CountryExposure]
    basis_note: I18nText
    limitations: list[LimitationCode]
    facts: dict[FactId, Fact]


class WorldCountryResponse(WireModel):
    country_iso3: String
    name: I18nText
    exposure: CountryExposure | None
    events: list[WorldEvent]
    macro: list[Fact]


class WorldObservationLocation(WireModel):
    lat: Annotated[Number, Field(ge=-90, le=90)]
    lon: Annotated[Number, Field(ge=-180, le=180)]
    country_iso3: String | None
    precision: Literal["point", "city", "country", "polygon_anchor"]
    geometry: dict | None = None


class WorldObservationSource(WireModel):
    name: String
    url: String


class WorldObservation(WireModel):
    id: String
    mode: Literal["news", "macro", "trade", "energy", "hazards", "conflicts",
                  "aviation", "environment", "infrastructure"]
    title: String
    summary: String
    occurred_at: ISODateTime
    time_basis: Literal["source_observation", "reference_period", "event_date", "capture_only"]
    published_at: ISODateTime | None
    retrieved_at: ISODateTime
    location: WorldObservationLocation | None
    geometry: dict | None = None
    country_iso3: String | None = None
    source: WorldObservationSource
    dataset_id: String
    limitations: list[String]
    assessment: WorldPortfolioAssessment | None = None


class WorldModeStatus(WireModel):
    mode: String
    available: Boolean
    count: Count
    reason: String | None


class WorldObservationsResponse(WireModel):
    items: list[WorldObservation]
    total: Count
    next_cursor: String | None
    data_version: String | None
    captured_at: ISODateTime | None
    modes: list[WorldModeStatus]


class FacilitiesResponse(WireModel):
    captured_at: ISODateTime | None = None
    data_version: DataVersion | None = None
    items: list[Facility]
    total: Count
    reporting_year: int
    limitations: list[LimitationCode]


class AirportReference(WireModel):
    airport_id: String
    ident: String
    name: String
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    country_iso2: String | None
    country_iso3: String | None
    source_url: String
    captured_at: ISODateTime
    assessment: WorldPortfolioAssessment | None = None


class AirportsResponse(WireModel):
    items: list[AirportReference]
    total: Count
    data_version: DataVersion
    captured_at: ISODateTime


class HazardsResponse(WireModel):
    items: list[Hazard]
    total: Count


class ReplayPreset(WireModel):
    as_of: ISODate
    label: I18nText
    why: I18nText


class ReplayPresetsResponse(WireModel):
    earliest_as_of: ISODate
    latest_as_of: ISODate
    presets: list[ReplayPreset]
    notices: list[LimitationCode]


class DatasetTrap(WireModel):
    code: LimitationCode
    handled_by: String
    status: Literal["handled", "disclosed", "open"]


class DatasetsResponse(WireModel):
    items: list[DatasetPassport]
    traps: list[DatasetTrap]


class EmptyRequest(WireModel):
    pass


# Resolve named forward references without importing application modules.
from .models import Period, Profile  # noqa: E402

ProfilesResponse.model_rebuild()
WorldEventsResponse.model_rebuild()
