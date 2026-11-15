"""Pydantic v2 mirror of contracts/schemas.md, contract version 1.4.0.

Boundary types only: numerical calculations, temporal gates, workflow transitions,
and cross-resource checks remain with their owning services.
"""

from typing import Annotated, Literal

from pydantic import Field, create_model, field_validator, model_validator
from typing_extensions import TypeAliasType

from .base import (
    Boolean,
    Count,
    DataVersion,
    EventId,
    EvidenceId,
    FactId,
    FactKey,
    Integer,
    ISODate,
    ISODateTime,
    NonNegative,
    Number,
    Percent,
    ProfileId,
    RuleCode,
    RunId,
    ScenarioId,
    SessionId,
    String,
    Ticker,
    WireModel,
)
from .catalog import (
    AssetFlag,
    AuditCheckCode,
    DatasetId,
    ErrorCode,
    FeatureFlag,
    LimitationCode,
    MethodId,
    MetricCode,
    NeeReason,
    ThemeTag,
)

Currency = TypeAliasType("Currency", Annotated[String, Field(pattern=r"^[A-Z]{3}$")])
Lang = TypeAliasType("Lang", Literal["en", "fr"])
WindowCode = TypeAliasType("WindowCode", Literal["full", "1y", "3y", "5y", "ytd", "custom"])
AssetClass = TypeAliasType(
    "AssetClass", Literal["equity", "etf_equity", "etf_bond", "etf_commodity", "crypto", "cash"]
)
AssetGroup = TypeAliasType(
    "AssetGroup", Literal["equity", "fixed_income", "commodity", "crypto", "cash"]
)
RiskLevel = TypeAliasType(
    "RiskLevel", Literal["low", "low_moderate", "moderate", "moderate_high", "high"]
)
Objective = TypeAliasType("Objective", Literal["preserve", "balanced", "growth"])
Experience = TypeAliasType("Experience", Literal["beginner", "intermediate", "advanced"])
RuleType = TypeAliasType(
    "RuleType", Literal["cap", "floor", "limit", "exclude", "evidence", "flag", "sim"]
)
RuleOrigin = TypeAliasType("RuleOrigin", Literal["derived", "profile_preference", "user", "system", "imported"])
Comparator = TypeAliasType("Comparator", Literal["<=", ">=", "==", "none"])
Unit = TypeAliasType(
    "Unit", Literal["pct", "pts", "ratio", "count", "days", "cad", "usd", "currency", "date", "text", "bool"]
)
FundingMode = TypeAliasType(
    "FundingMode", Literal["auto", "pro_rata", "from_cash", "from_holdings", "new_money"]
)
RuleId = TypeAliasType(
    "RuleId",
    Annotated[
        String,
        Field(
            pattern=(
                r"^(cap\.(position|sector|asset_class\.crypto|growth_assets|country\.[A-Z]{3}|currency\.[A-Z]{3}|theme\.("
                + "|".join(tag.value for tag in ThemeTag)
                + r"))|floor\.(fixed_income|diversifiers)|limit\.(volatility|stress_2022|drawdown)"
                r"|exclude\.(sector\.[a-z]+(_[a-z]+)*|asset_class\.(equity|etf_equity|etf_bond|"
                r"etf_commodity|crypto|cash)|ticker\.[A-Z0-9][A-Z0-9.^=-]*)|evidence\.controversy"
                r"|flag\.(attention|rate_cycle|short_history)|sim\.only)$"
            )
        ),
    ],
)
FactKind = TypeAliasType(
    "FactKind",
    Literal["observed", "computed", "assumption", "input", "scenario", "rule_check", "evidence"],
)
EvidenceType = TypeAliasType(
    "EvidenceType",
    Literal[
        "filing",
        "company_report",
        "fund_document",
        "official_release",
        "news",
        "registry",
        "attention",
        "web_page",
    ],
)
RuleStatus = TypeAliasType("RuleStatus", Literal["pass", "tension", "conflict", "nee", "info"])
Verdict = TypeAliasType("Verdict", Literal["compatible", "tension", "conflict", "insufficient"])
ScenarioKind = TypeAliasType(
    "ScenarioKind",
    Literal["requested", "max_compatible", "alternative", "goal_candidate", "rebalance"],
)
BriefSectionId = TypeAliasType(
    "BriefSectionId",
    Literal["summary", "facts", "assumptions", "limits", "scenarios", "next_checks"],
)
RunKind = TypeAliasType(
    "RunKind",
    Literal["decision", "rebalance", "portfolio_brief", "event_brief", "replay", "profile_draft", "sabotage"],
)
RunStatus = TypeAliasType(
    "RunStatus", Literal["queued", "running", "waiting_input", "succeeded", "failed", "cancelled"]
)
StepType = TypeAliasType(
    "StepType",
    Literal["plan", "research", "quant", "risk_check", "revise", "write", "audit", "sign"],
)
AgentRole = TypeAliasType(
    "AgentRole", Literal["planner", "researcher", "quant", "risk_officer", "writer", "auditor"]
)
SabotageMode = TypeAliasType(
    "SabotageMode", Literal["invented_number", "false_comparison", "unsupported_interpretation"]
)
EventCategory = TypeAliasType(
    "EventCategory",
    Literal[
        "monetary_policy",
        "macro_release",
        "geopolitical",
        "trade_regulation",
        "corporate",
        "energy_commodities",
        "markets",
        "natural_disaster",
        "other",
    ],
)


class I18nText(WireModel):
    en: String
    fr: String


class Period(WireModel):
    start: ISODate
    end: ISODate
    label: String = None  # optional key, null is rejected when explicitly supplied


class WindowSpec(WireModel):
    model_config = {
        "json_schema_extra": {
            "if": {"properties": {"code": {"const": "custom"}}},
            "then": {"required": ["start", "end"]},
        }
    }
    code: WindowCode
    start: ISODate = None
    end: ISODate = None

    @model_validator(mode="after")
    def custom_dates(self):
        if self.code == "custom" and not {"start", "end"} <= self.model_fields_set:
            raise ValueError("custom windows require start and end")
        return self


class ErrorDetail(WireModel):
    code: ErrorCode
    message: String
    details: dict[str, object] = None
    request_id: String


class ApiError(WireModel):
    error: ErrorDetail


class AssetHistory(WireModel):
    first_date: ISODate
    last_date: ISODate
    n_obs: Count
    n_obs_master: Count


class Asset(WireModel):
    ticker: Ticker
    name: String
    asset_class: AssetClass
    asset_group: AssetGroup
    market: String
    currency: Currency
    sector: String
    gics_sector: String | None
    is_single_name: Boolean
    country: String | None
    themes: list[ThemeTag]
    tier: Literal["starter", "extended", "on_demand"]
    history: AssetHistory
    flags: list[AssetFlag]
    data_version: DataVersion
    dataset_id: DatasetId


class Preferences(WireModel):
    themes_of_interest: list[ThemeTag]
    excluded_sectors: list[String]
    excluded_asset_classes: list[AssetClass]
    esg_focus: Boolean
    avoid_controversies: Boolean
    avoid_speculative: Boolean
    crypto_interest: Literal["none", "low", "open"]
    wants_diversification: Boolean
    notes: String


class Position(WireModel):
    ticker: Ticker
    weight_pct: Percent


class Portfolio(WireModel):
    is_fictional: Literal[True]
    total_value: NonNegative
    currency: Currency
    positions: list[Position]
    updated_at: ISODateTime

    @field_validator("is_fictional", mode="before")
    @classmethod
    def literal_true(cls, value):
        if value is not True:
            raise ValueError("isFictional must be true")
        return value


class HorizonYears(WireModel):
    min: NonNegative
    max: NonNegative | None


class InvestmentGoal(WireModel):
    """User-stated objective, never a promise of an achievable return."""

    name: Annotated[String, Field(min_length=1, max_length=120)]
    horizon_years: Annotated[Number, Field(gt=0, le=150)]
    priority: Annotated[Integer, Field(ge=1, le=100)]
    target_amount: NonNegative | None = None
    allocated_value: NonNegative | None = None
    annual_contribution: NonNegative | None = None
    assumed_return_pct: Annotated[Number, Field(gt=-100, le=100)] | None = None
    deadline: ISODate | None = None
    origin: Literal["user", "imported", "assumption"] = "user"


class InvestorContext(WireModel):
    """Optional global context. Jurisdiction is context, not a sourced tax policy."""

    country: Annotated[String, Field(pattern=r"^[A-Z]{2}$")] | None = None
    investor_type: Literal[
        "individual", "retirement", "income", "crypto", "institutional", "family_office",
        "endowment", "pension", "wealth_manager", "advisor", "custom"
    ] = "individual"
    language: Lang = "en"
    objectives: list[InvestmentGoal] = Field(default_factory=list, max_length=20,
        json_schema_extra={"tsType": "InvestmentGoal[]"})
    liquidity_notes: Annotated[String, Field(max_length=2000)] = ""
    risk_capacity_notes: Annotated[String, Field(max_length=2000)] = ""


class RuleTarget(WireModel):
    dimension: Literal[
        "position", "sector", "asset_class", "asset_group", "theme", "portfolio", "country", "currency", "none"
    ]
    key: String | None


class RuleBounds(WireModel):
    min: Number
    max: Number
    step: Annotated[Number, Field(gt=0)]


class RuleDerivation(WireModel):
    method_id: MethodId
    formula: String
    inputs: dict[str, Number | String]
    data_version: DataVersion
    window: WindowSpec


class PolicyRule(WireModel):
    rule_id: RuleId
    code: RuleCode
    type: RuleType
    enabled: Boolean
    label: I18nText
    rationale: I18nText
    metric: MetricCode | None
    target: RuleTarget
    comparator: Comparator
    threshold: Number | None
    unit: Unit
    editable: Boolean
    bounds: RuleBounds | None
    origin: RuleOrigin
    is_assumption: Boolean
    derivation: RuleDerivation | None
    counts_in_verdict: Boolean
    updated_at: ISODateTime


class AccountFXQuote(WireModel):
    currency: Currency
    cad_per_unit: Annotated[Number, Field(gt=0)]
    observed_on: ISODate
    available_at: ISODateTime
    source: "SourceRef"


class AccountValuation(WireModel):
    verified_checks: list[String] = Field(default_factory=list)
    native_currency: Currency
    native_value: Annotated[Number, Field(gt=0)]
    reporting_currency: Currency
    reporting_value: Annotated[Number, Field(gt=0)]
    conversion_rate: Annotated[Number, Field(gt=0)]
    valuation_date: ISODate
    captured_at: ISODateTime
    data_version: DataVersion
    quotes: list[AccountFXQuote]


class PortfolioAccount(WireModel):
    native_valuation: AccountValuation | None = None
    account_id: Annotated[String, Field(pattern=r"^acct_[0-9a-f]{12}$")]
    name: Annotated[String, Field(min_length=1, max_length=80)]
    portfolio: Portfolio


class Profile(WireModel):
    profile_id: ProfileId
    is_default: Boolean
    archived: Boolean = False
    origin: Literal["brief", "user", "agent_draft"]
    name: String
    initial: Annotated[String, Field(min_length=1, max_length=1)]
    age: Count | None
    occupation: String | None
    risk_level: RiskLevel
    horizon_years: HorizonYears
    objective: Objective
    objective_text: I18nText
    experience: Experience
    reporting_currency: Currency
    preferences: Preferences
    blurb: I18nText
    persona_test: I18nText | None
    investor_context: InvestorContext | None = None
    accounts: list[PortfolioAccount] = Field(default_factory=list)
    active_account_id: String | None = None
    portfolio: Portfolio
    rules: list[PolicyRule]
    version: Annotated[Integer, Field(ge=1)]
    created_at: ISODateTime
    updated_at: ISODateTime


# Partial<Profile> is shallow: omitted keys are allowed, explicit null only where
# Profile allows it. None defaults never cross the boundary via to_wire().
PartialProfile = create_model(
    "PartialProfile",
    __base__=WireModel,
    **{
        name: (
            Annotated[field.annotation, *field.metadata] if field.metadata else field.annotation,
            Field(default=None, alias=field.alias),
        )
        for name, field in Profile.model_fields.items()
    },
)


class Funding(WireModel):
    model_config = {
        "json_schema_extra": {
            "if": {"properties": {"mode": {"const": "from_holdings"}}},
            "then": {"required": ["fromTickers"], "properties": {"fromTickers": {"minItems": 1}}},
        }
    }
    mode: FundingMode
    from_tickers: list[Ticker] = None

    @model_validator(mode="after")
    def donors_required(self):
        if self.mode == "from_holdings" and not self.from_tickers:
            raise ValueError("from_holdings requires nonempty fromTickers")
        return self


class ProposedMove(WireModel):
    ticker: Ticker
    size_pct: Annotated[Number, Field(gt=0)]
    funding: Funding


class ExposureGoal(WireModel):
    model_config = {
        "json_schema_extra": {
            "anyOf": [
                {"properties": {name: {"minItems": 1}}}
                for name in ("themes", "assetClasses", "tickers")
            ]
        }
    }
    themes: list[ThemeTag]
    asset_classes: list[AssetClass]
    tickers: list[Ticker]
    target_exposure_pct: Percent | None
    max_loss_pct: NonNegative | None
    max_vol_pct: NonNegative | None
    notes: String

    @model_validator(mode="after")
    def has_target(self):
        if not (self.themes or self.asset_classes or self.tickers):
            raise ValueError("a goal requires a theme, asset class, or ticker")
        return self


class MoveRequest(WireModel):
    type: Literal["move"]
    move: ProposedMove


class GoalRequest(WireModel):
    type: Literal["goal"]
    goal: ExposureGoal


DecisionRequest = TypeAliasType(
    "DecisionRequest", Annotated[MoveRequest | GoalRequest, Field(discriminator="type")]
)


class MissingField(WireModel):
    field: String
    question: I18nText


class Refusal(WireModel):
    reason: Literal["trade_execution", "advice_request", "off_topic"]
    message: I18nText


class ParsedRequest(WireModel):
    request: DecisionRequest | None
    interpretation: I18nText
    confidence: Literal["high", "medium", "low"]
    missing: list[MissingField]
    warnings: list[I18nText]
    refused: Refusal | None


class SourceRef(WireModel):
    dataset_id: DatasetId
    data_version: DataVersion
    source_name: String
    source_url: String | None
    retrieved_on: ISODate
    licence: String
    rows_read: Count | None


class FactSubject(WireModel):
    type: Literal[
        "asset",
        "portfolio",
        "sector",
        "asset_group",
        "asset_class",
        "theme",
        "country",
        "currency",
        "rule",
        "macro",
        "event",
        "request",
        "universe",
    ]
    id: String
    variant: String


class FactMethod(WireModel):
    id: MethodId
    description: I18nText
    params: dict[str, Number | String | Boolean]


class VerificationCheck(WireModel):
    code: String
    ok: Boolean
    detail: String


class Verification(WireModel):
    status: Literal["verified", "unverified", "failed"]
    checks: list[VerificationCheck]


class Fact(WireModel):
    id: FactId
    key: FactKey
    kind: FactKind
    metric: MetricCode
    label: I18nText
    value: Number | String | Boolean | None
    unit: Unit
    currency: Currency | None
    display: I18nText
    subject: FactSubject
    period: Period | None
    window: WindowSpec | None
    as_of: ISODate
    available_at: ISODateTime | None
    method: FactMethod
    inputs: list[FactId]
    n_obs: Count | None
    sources: list[SourceRef]
    limitations: list[LimitationCode]
    verification: Verification
    created_by: Literal[
        "quant", "rules", "optimizer", "research", "profile", "user", "world", "timemachine"
    ]
    created_at: ISODateTime


class EvidenceSubject(WireModel):
    type: Literal["asset", "sector", "country", "event", "theme"]
    id: String


class Evidence(WireModel):
    id: EvidenceId
    type: EvidenceType
    tier: Literal[1, 2, 3]
    title: String
    publisher: String
    url: String
    published_at: ISODate | None
    retrieved_at: ISODateTime
    lang: String
    quote: Annotated[String, Field(max_length=400)] | None
    claim: I18nText
    subject: EvidenceSubject
    tool: String
    document_ref: String | None
    licence: String
    verification: Verification

    @field_validator("tier", mode="before")
    @classmethod
    def numeric_tier(cls, value):
        if isinstance(value, bool):
            raise ValueError("tier must be 1, 2, or 3")
        return value


class WorstExposure(WireModel):
    type: Literal["asset", "sector", "asset_group", "theme"]
    id: String


class RuleCheck(WireModel):
    rule_id: RuleId
    code: RuleCode
    status: RuleStatus
    value: Number | None
    threshold: Number | None
    unit: Unit
    comparator: Comparator
    headroom: Number | None
    worst: WorstExposure | None
    value_fact_id: FactId | None
    threshold_fact_id: FactId | None
    detail: I18nText
    nee_reason: NeeReason | None
    evidence_ids: list[EvidenceId]


class VerdictCounts(WireModel):
    pass_: Count = Field(alias="pass")
    tension: Count
    conflict: Count
    nee: Count
    info: Count


class SnapshotPosition(Position):
    name: String
    asset_class: AssetClass
    asset_group: AssetGroup
    sector: String
    market_value: NonNegative


class GroupWeight(WireModel):
    key: AssetGroup
    weight_pct: Percent


class LabelWeight(WireModel):
    key: String
    weight_pct: Percent


class SnapshotMetrics(WireModel):
    volatility_pct: NonNegative | None
    max_drawdown_pct: NonNegative | None
    stress2022_pct: Number | None = Field(alias="stress2022Pct")
    fact_ids: dict[str, FactId]


class PortfolioSnapshot(WireModel):
    variant: String
    total_value: NonNegative
    currency: Currency
    positions: list[SnapshotPosition]
    by_asset_group: list[GroupWeight]
    by_sector: list[LabelWeight]
    by_country: list[LabelWeight]
    metrics: SnapshotMetrics


class FundingOption(WireModel):
    funding: Funding
    feasible: Boolean
    infeasible_reason: I18nText | None
    verdict: Verdict | None
    counts: VerdictCounts | None
    max_compatible_size_pct: NonNegative | None
    recommended: Boolean
    rank: Count | None
    note: I18nText


class ThemeExposure(WireModel):
    theme: ThemeTag
    before_pct: Percent
    after_pct: Percent


class Scenario(WireModel):
    scenario_id: ScenarioId
    kind: ScenarioKind
    label: I18nText
    moves: list[ProposedMove]
    verdict: Verdict
    counts: VerdictCounts
    rule_checks: list[RuleCheck]
    portfolio_after: PortfolioSnapshot
    exposure: list[ThemeExposure]
    rationale: I18nText
    is_best_fit: Boolean
    rank: Count
    key_fact_ids: list[FactId]


class CheckResult(WireModel):
    verdict: Verdict
    counts: VerdictCounts
    rule_checks: list[RuleCheck]
    portfolio_before: PortfolioSnapshot
    portfolio_after: PortfolioSnapshot
    funding_used: Funding
    funding_options: list[FundingOption]
    max_compatible_size_pct: NonNegative
    baseline_conflict: Boolean
    facts: dict[FactId, Fact]
    as_of: ISODate
    data_version: DataVersion
    window: WindowSpec
    compute_ms: NonNegative


class TextSegment(WireModel):
    t: Literal["text"]
    text: String


class FactSegment(WireModel):
    t: Literal["fact"]
    fact_id: FactId
    display: String


class RuleSegment(WireModel):
    t: Literal["rule"]
    rule_id: RuleId
    display: String


class StatusSegment(WireModel):
    t: Literal["status"]
    rule_id: RuleId
    display: String


class EvidenceSegment(WireModel):
    t: Literal["evidence"]
    evidence_id: EvidenceId
    display: String


Segment = TypeAliasType(
    "Segment",
    Annotated[
        TextSegment | FactSegment | RuleSegment | StatusSegment | EvidenceSegment,
        Field(discriminator="t"),
    ],
)


class SentenceAudit(WireModel):
    status: Literal["verified", "struck", "repaired"]
    failed_checks: list[AuditCheckCode]
    note: I18nText | None


class Sentence(WireModel):
    id: String
    segments: list[Segment]
    audit: SentenceAudit


class BriefSection(WireModel):
    id: BriefSectionId
    title: I18nText
    sentences: list[Sentence]


class AuditCheckResult(WireModel):
    code: AuditCheckCode
    ok: Boolean
    kind: Literal["code", "llm", "guardrail"]
    detail: String
    sentence_ids: list[String]


class GuardrailAudit(WireModel):
    applied: Boolean
    action: Literal["none", "blocked", "masked"]
    id: String | None


class ReviewFinding(WireModel):
    sentence_id: String
    issue: String
    code: AuditCheckCode


class LlmReview(WireModel):
    model: String | None
    findings: list[ReviewFinding]


class AuditReport(WireModel):
    status: Literal["passed", "passed_with_strikes", "failed"]
    checks: list[AuditCheckResult]
    sentences_checked: Count
    sentences_struck: Count
    rewrites: Annotated[Integer, Field(ge=0, le=1)]
    guardrail: GuardrailAudit
    llm_review: LlmReview
    ledger_hash: Annotated[String, Field(pattern=r"^[a-f0-9]{64}$")]
    signed_at: ISODateTime


class Brief(WireModel):
    lang: Lang
    sections: list[BriefSection]
    disclaimer: I18nText
    generated_at: ISODateTime
    model: String
    audit: AuditReport


class DatasetRead(WireModel):
    dataset_id: DatasetId
    data_version: DataVersion
    rows: Count
    rows_withheld: Count


class ToolCall(WireModel):
    id: String
    tool: String
    args: dict[str, object]
    started_at: ISODateTime
    duration_ms: NonNegative
    ok: Boolean
    result_summary: String
    datasets_read: list[DatasetRead]
    fact_ids: list[FactId]
    evidence_ids: list[EvidenceId]
    error: String | None


class TokenUsage(WireModel):
    input_tokens: Count
    output_tokens: Count


class Step(WireModel):
    seq: Annotated[Integer, Field(ge=1)]
    type: StepType
    iteration: Annotated[Integer, Field(ge=1)]
    agent: AgentRole
    actor: Literal["llm", "llm+tools", "code", "code+llm"]
    status: Literal["running", "done", "failed"]
    started_at: ISODateTime
    ended_at: ISODateTime | None
    duration_ms: NonNegative | None
    summary: I18nText
    model: String | None
    usage: TokenUsage | None
    tool_calls: list[ToolCall]
    fact_ids: list[FactId]
    evidence_ids: list[EvidenceId]


class QuestionOption(WireModel):
    value: String
    label: I18nText


class ClarifyingQuestion(WireModel):
    question_id: String
    text: I18nText
    field: String
    options: list[QuestionOption] | None


class DecisionInput(WireModel):
    kind: Literal["decision"]
    request: DecisionRequest
    original_text: String | None
    window: WindowSpec


class RebalanceInput(WireModel):
    kind: Literal["rebalance"]
    profile_version: Annotated[int, Field(strict=True, ge=1)]
    positions: Annotated[list[Position], Field(min_length=1, max_length=40)]
    window: WindowSpec


class PortfolioBriefInput(WireModel):
    kind: Literal["portfolio_brief"]
    window: WindowSpec


class EventBriefInput(WireModel):
    kind: Literal["event_brief"]
    event_id: EventId


class ReplayInput(WireModel):
    kind: Literal["replay"]
    request: DecisionRequest
    as_of: ISODate
    window: WindowSpec


class ProfileDraftInput(WireModel):
    kind: Literal["profile_draft"]
    text: String
    fields: PartialProfile


class SabotageInput(WireModel):
    kind: Literal["sabotage"]
    mode: SabotageMode


RunInput = TypeAliasType(
    "RunInput",
    Annotated[
        DecisionInput
        | RebalanceInput
        | PortfolioBriefInput
        | EventBriefInput
        | ReplayInput
        | ProfileDraftInput
        | SabotageInput,
        Field(discriminator="kind"),
    ],
)


class AttentionSignal(WireModel):
    ticker: Ticker
    article: String
    ratio: NonNegative | None
    recent_period: Period
    baseline_period: Period
    flag: Literal["elevated", "normal", "unknown"]
    fact_id: FactId | None
    evidence_id: EvidenceId | None


class DecisionResult(WireModel):
    request: DecisionRequest
    verdict: Verdict
    counts: VerdictCounts
    selected_scenario_id: ScenarioId
    scenarios: list[Scenario]
    portfolio_before: PortfolioSnapshot
    max_compatible_size_pct: NonNegative | None
    funding_options: list[FundingOption]
    attention: AttentionSignal | None
    macro_context: list[FactId]
    brief: Brief
    limitations: list[LimitationCode]


class FocusDetail(WireModel):
    """Code-owned focus metadata. ``score`` is an inspectable heuristic, never a forecast."""

    priority: Annotated[Integer, Field(ge=1, le=3)]
    topic: Literal["risk", "concentration", "plan", "fixed_income", "objective"]
    score: Annotated[Integer, Field(ge=0, le=100)]
    basis: Literal["built_in", "candidate_provider"]
    time_horizon: Literal["short", "medium", "long"]
    horizon_years: Annotated[Number, Field(ge=0, le=150)]
    objective: String | None = None
    holdings: list[Ticker]
    evidence_ids: list[EvidenceId]
    rule_ids: list[RuleId]
    uncertainty: Literal["low", "medium", "high"]
    uncertainty_reasons: list[I18nText]
    investigation: I18nText
    href: Annotated[String, Field(pattern=r"^/[A-Za-z0-9/_?=&%.-]*$")]


class FocusCard(WireModel):
    title: I18nText
    body: list[Sentence]
    fact_ids: list[FactId]
    detail: FocusDetail | None = None


class PortfolioBriefResult(WireModel):
    snapshot: PortfolioSnapshot
    rule_checks: list[RuleCheck]
    verdict: Verdict
    counts: VerdictCounts
    focus_cards: Annotated[list[FocusCard], Field(min_length=3, max_length=3)]
    brief: Brief
    horizon_band: Literal["short", "medium", "long"]


class FieldExplanation(WireModel):
    field: String
    text: I18nText


class ProfileDraftResult(WireModel):
    profile: PartialProfile
    explanations: list[FieldExplanation]
    unresolved: list[MissingField]


class UnsignedDraftSentence(WireModel):
    id: String
    template: String


class UnsignedDraftSection(WireModel):
    id: BriefSectionId
    sentences: list[UnsignedDraftSentence]


class UnsignedDraft(WireModel):
    status: Literal["unaudited"]
    model: String
    sections: list[UnsignedDraftSection]


class SabotageResult(WireModel):
    mode: SabotageMode
    injected_instruction: String
    brief_before_audit: UnsignedDraft
    brief_after_audit: Brief
    caught: Boolean
    failed_checks: list[AuditCheckResult]


class EventSource(WireModel):
    publisher: String
    title: String
    url: String
    published_at: ISODateTime | None
    source_type: Literal["news", "official", "filing", "data"]
    lang: String


class EventLocation(WireModel):
    lat: Annotated[Number, Field(ge=-90, le=90)]
    lon: Annotated[Number, Field(ge=-180, le=180)]
    country_iso3: String | None
    place_name: String | None
    precision: Literal["point", "city", "country"]


class WorldEvent(WireModel):
    event_id: EventId
    title: String
    category: EventCategory
    occurred_at: ISODate
    published_at: ISODateTime | None
    location: EventLocation
    origin: Literal["gdelt", "official", "curated", "usgs", "firms", "live", "eonet"]
    sources: Annotated[list[EventSource], Field(min_length=1)]
    source_count: Annotated[Integer, Field(ge=1)]
    importance: Annotated[Number, Field(ge=0, le=1)]
    related_tickers: list[Ticker]
    related_themes: list[ThemeTag]
    related_countries: list[String]
    dataset_id: DatasetId
    data_version: DataVersion


class HoldingExposure(WireModel):
    ticker: Ticker
    weight_pct: Percent
    link_type: Literal[
        "named_in_source",
        "listing_country",
        "sector",
        "theme",
        "documented_exposure",
        "etf_lookthrough",
    ]
    evidence_ids: list[EvidenceId]
    impact: Literal["not_established", "measured_price_move"]
    impact_fact_id: FactId | None
    note: I18nText


class EventHypothesis(WireModel):
    """A documented event→issuer→security lead; never a measured or causal impact."""

    security_id: String
    issuer_id: String
    evidence_ids: list[EvidenceId]
    impact: Literal["not_established"]
    interpretation: I18nText


class EventRelationshipReview(WireModel):
    status: Literal["not_configured", "none_found", "documented", "failed"]
    hypotheses: list[EventHypothesis]
    limitations: list[I18nText]


class EventBriefResult(WireModel):
    event: WorldEvent
    exposures: list[HoldingExposure]
    brief: Brief
    impact_statement: I18nText
    relationship_review: EventRelationshipReview | None = None


class HoldingWeight(WireModel):
    ticker: Ticker
    weight_pct: Percent


class CountryExposure(WireModel):
    country_iso3: String
    weight_pct: Percent
    basis: Literal["listing_country", "etf_lookthrough", "mixed"]
    holdings: list[HoldingWeight]


class Facility(WireModel):
    facility_id: String
    name: String
    operator: String
    ticker: Ticker | None
    match_confidence: Literal["exact", "probable", "none"]
    lat: Annotated[Number, Field(ge=-90, le=90)]
    lon: Annotated[Number, Field(ge=-180, le=180)]
    country_iso3: String
    reporting_year: Integer
    emissions_tco2e: NonNegative = Field(alias="emissionsTco2e")
    registry: Literal["eccc_ghgrp", "epa_ghgrp"]
    source_url: String
    data_version: DataVersion


class Hazard(WireModel):
    hazard_id: String
    type: Literal["earthquake", "wildfire"]
    occurred_at: ISODateTime
    lat: Annotated[Number, Field(ge=-90, le=90)]
    lon: Annotated[Number, Field(ge=-180, le=180)]
    magnitude: Number | None
    title: String
    origin: Literal["usgs", "firms"]
    source_url: String


class LegendItem(WireModel):
    label: I18nText
    color: String


class WorldLayer(WireModel):
    layer_id: Literal["events", "exposure", "facilities", "hazards", "airports"]
    title: I18nText
    tier: Literal["P1", "P2"]
    available: Boolean
    dataset_ids: list[DatasetId]
    legend: list[LegendItem]
    count: Count | None
    coverage: Period | None


class GateDataset(WireModel):
    dataset_id: DatasetId
    rows_visible: Count
    rows_withheld: Count
    last_visible_date: ISODate


class GateReport(WireModel):
    datasets: list[GateDataset]


class ReplayResult(WireModel):
    as_of: ISODate
    decision: DecisionResult
    gate: GateReport
    notices: list[LimitationCode]
    reveal_available_until: ISODate


class SeriesPoint(WireModel):
    date: ISODate
    value: Number


class RevealOutcome(WireModel):
    scenario_id: ScenarioId
    label: I18nText
    return_pct: Number
    max_drawdown_pct: NonNegative
    series: list[SeriesPoint]
    fact_ids: list[FactId]


class RevealResult(WireModel):
    as_of: ISODate
    until: ISODate
    outcomes: list[RevealOutcome]
    facts: dict[FactId, Fact]
    statement: I18nText


class DecisionRunResult(WireModel):
    kind: Literal["decision"]
    decision: DecisionResult


class RebalanceChange(WireModel):
    ticker: Ticker
    before_pct: Percent
    target_pct: Percent
    change_pct: Number


class ReviewedRebalance(WireModel):
    profile_id: ProfileId
    profile_version: Annotated[int, Field(strict=True, ge=1)]
    currency: Currency
    total_value: NonNegative
    as_of: ISODate
    data_version: DataVersion
    window: WindowSpec
    changes: list[RebalanceChange]
    portfolio_before: PortfolioSnapshot
    portfolio_after: PortfolioSnapshot
    verdict_before: Verdict
    verdict_after: Verdict
    counts_before: VerdictCounts
    counts_after: VerdictCounts
    rule_checks_before: list[RuleCheck]
    rule_checks_after: list[RuleCheck]
    assumptions: list[I18nText]
    brief: Brief


class RebalanceRunResult(WireModel):
    kind: Literal["rebalance"]
    rebalance: ReviewedRebalance


class PortfolioBriefRunResult(WireModel):
    kind: Literal["portfolio_brief"]
    portfolio_brief: PortfolioBriefResult


class EventBriefRunResult(WireModel):
    kind: Literal["event_brief"]
    event_brief: EventBriefResult


class ReplayRunResult(WireModel):
    kind: Literal["replay"]
    replay: ReplayResult


class ProfileDraftRunResult(WireModel):
    kind: Literal["profile_draft"]
    draft: ProfileDraftResult


class SabotageRunResult(WireModel):
    kind: Literal["sabotage"]
    sabotage: SabotageResult


RunResult = TypeAliasType(
    "RunResult",
    Annotated[
        DecisionRunResult
        | RebalanceRunResult
        | PortfolioBriefRunResult
        | EventBriefRunResult
        | ReplayRunResult
        | ProfileDraftRunResult
        | SabotageRunResult,
        Field(discriminator="kind"),
    ],
)


class RunFlags(WireModel):
    sabotage: SabotageMode | None
    fixture: Boolean
    time_machine: Boolean


class RunUsage(TokenUsage):
    llm_calls: Count
    tool_calls: Count
    duration_ms: NonNegative


class Run(WireModel):
    run_id: RunId
    kind: RunKind
    status: RunStatus
    session_id: SessionId
    profile_id: ProfileId | None
    parent_run_id: RunId | None
    lang: Lang
    as_of: ISODate
    data_version: DataVersion
    input: RunInput
    steps: list[Step]
    facts: dict[FactId, Fact]
    evidence: dict[EvidenceId, Evidence]
    question: ClarifyingQuestion | None
    result: RunResult | None
    error: ErrorDetail | None
    flags: RunFlags
    usage: RunUsage
    created_at: ISODateTime
    updated_at: ISODateTime


class DatasetField(WireModel):
    name: String
    type: String
    description: String


class DatasetCheck(WireModel):
    name: String
    ok: Boolean
    detail: String
    checked_at: ISODateTime


class DatasetPassport(WireModel):
    dataset_id: DatasetId
    name: I18nText
    role: I18nText
    status: Literal["in_use", "planned", "rejected"]
    source: String
    source_url: String | None
    access_method: String
    licence: String
    licence_url: String | None
    retrieved_on: ISODate | None
    coverage: Period | None
    frequency: String
    row_count: Count | None
    data_version: DataVersion | None
    schema_: list[DatasetField] = Field(alias="schema")
    processing: list[I18nText]
    limitations: list[LimitationCode]
    availability_rule: I18nText
    checks: list[DatasetCheck]
    rejected_reason: I18nText | None


class ModelIds(WireModel):
    strong: String | None
    fast: String | None


class UniverseSummary(WireModel):
    total: Count
    by_tier: dict[str, Count]


class Meta(WireModel):
    reporting_currencies: list[Currency] = Field(default_factory=lambda: ["CAD", "USD"])
    contract_version: String
    data_version: DataVersion
    data_as_of: ISODate
    environment: Literal["local", "aws"]
    languages: list[Lang]
    features: dict[FeatureFlag, Boolean] = Field(
        json_schema_extra={
            "properties": {flag.value: {"type": "boolean"} for flag in FeatureFlag},
            "required": [flag.value for flag in FeatureFlag],
        }
    )
    models: ModelIds
    universe: UniverseSummary
    disclaimer: I18nText

    @field_validator("features")
    @classmethod
    def all_features(cls, value):
        if set(value) != set(FeatureFlag):
            raise ValueError("every feature flag must be present")
        return value
