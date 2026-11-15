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
)


class HealthResponse(WireModel):
    status: Literal["ok"]
    time: ISODateTime


class AssetsResponse(WireModel):
    items: list[Asset]
    next_cursor: String | None
    total: Count


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


class CreateAccountRequest(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=80)]
    version: Annotated[int, Field(strict=True, ge=1)]
    portfolio: InitialPortfolio


class SelectAccountRequest(WireModel):
    version: Annotated[int, Field(strict=True, ge=1)]


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


class WorldEventResponse(WireModel):
    event: WorldEvent
    related: list[WorldEvent]
    exposures: list[HoldingExposure]


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


class FacilitiesResponse(WireModel):
    items: list[Facility]
    total: Count
    reporting_year: int
    limitations: list[LimitationCode]


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
