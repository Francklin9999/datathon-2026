// Generated from contracts/generated/schema.json. Run npm run generate:contracts.
// Do not edit; see contracts/README.md.

/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Currency".
 */
export type Currency = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ISODate".
 */
export type ISODate = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ISODateTime".
 */
export type ISODateTime = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetId".
 */
export type DatasetId =
  | "assets_universe"
  | "prices_daily"
  | "corporate_actions"
  | "fx_boc_global"
  | "world_airports"
  | "world_bank_indicators"
  | "fx_usdcad_daily"
  | "macro_rates"
  | "asset_themes"
  | "default_profiles"
  | "macro_release_dates"
  | "etf_holdings"
  | "world_events"
  | "world_aviation_weather"
  | "world_noaa_alerts"
  | "world_gdacs_alerts"
  | "world_nasa_power"
  | "world_federal_register"
  | "energy_wri_plants"
  | "trade_portwatch_ports"
  | "attention_pageviews"
  | "emissions_facilities"
  | "natural_hazards"
  | "research_documents"
  | "filings_index";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DataVersion".
 */
export type DataVersion = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AgentRole".
 */
export type AgentRole = "planner" | "researcher" | "quant" | "risk_officer" | "writer" | "auditor";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Ticker".
 */
export type Ticker = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunId".
 */
export type RunId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ErrorCode".
 */
export type ErrorCode =
  | "validation_error"
  | "not_found"
  | "conflict"
  | "forbidden_action"
  | "insufficient_data"
  | "rate_limited"
  | "upstream_unavailable"
  | "feature_disabled"
  | "internal";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetClass".
 */
export type AssetClass = "equity" | "etf_equity" | "etf_bond" | "etf_commodity" | "crypto" | "cash";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetGroup".
 */
export type AssetGroup = "equity" | "fixed_income" | "commodity" | "crypto" | "cash";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ThemeTag".
 */
export type ThemeTag =
  | "ai"
  | "semiconductors"
  | "software"
  | "cloud"
  | "ecommerce"
  | "electric_vehicles"
  | "big_tech"
  | "banks"
  | "insurance"
  | "fossil_energy"
  | "pipelines"
  | "utilities"
  | "rail_transport"
  | "consumer_staples"
  | "healthcare"
  | "retail"
  | "broad_canada"
  | "broad_us"
  | "nasdaq_growth"
  | "esg_screened"
  | "bonds_canada"
  | "bonds_us"
  | "long_treasuries"
  | "cash_like"
  | "gold"
  | "crypto"
  | "dividend_payers";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetFlag".
 */
export type AssetFlag =
  | "short_history"
  | "zero_volume_rows"
  | "split_anomaly"
  | "on_demand"
  | "no_fx_needed"
  | "seven_day_calendar"
  | "sector_label_unsourced";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WindowCode".
 */
export type WindowCode = "full" | "1y" | "3y" | "5y" | "ytd" | "custom";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactId".
 */
export type FactId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactKey".
 */
export type FactKey = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactKind".
 */
export type FactKind = "observed" | "computed" | "assumption" | "input" | "scenario" | "rule_check" | "evidence";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "MetricCode".
 */
export type MetricCode =
  | "price.last"
  | "fx.usdcad"
  | "return.period"
  | "return.calendar_year"
  | "return.ytd"
  | "return.trailing"
  | "return.worst_12m"
  | "vol.annualized"
  | "input.goal_assumption"
  | "goal.projected_value"
  | "goal.funding_gap"
  | "risk.var95"
  | "risk.es95"
  | "risk.variance_share"
  | "drawdown.max"
  | "corr.pair"
  | "value.portfolio"
  | "value.position"
  | "weight.position"
  | "weight.position.max_single"
  | "weight.sector"
  | "weight.sector.max"
  | "weight.asset_class"
  | "weight.asset_group"
  | "weight.growth_assets"
  | "weight.fixed_income"
  | "weight.diversifiers"
  | "weight.theme"
  | "weight.currency"
  | "weight.country"
  | "concentration.hhi"
  | "concentration.effective_n"
  | "stress.replay_2022"
  | "stress.rate_cycle"
  | "size.requested"
  | "size.max_compatible"
  | "threshold.rule"
  | "budget.volatility"
  | "ref.sigma_single_stock_q3"
  | "ref.sigma_crypto_median"
  | "ref.mix_volatility"
  | "frontier.point"
  | "macro.level"
  | "macro.change"
  | "attention.pageviews_ratio"
  | "emissions.facility_total"
  | "count.rules"
  | "count.sources"
  | "gate.rows_withheld"
  | "quote.figure";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Unit".
 */
export type Unit = "pct" | "pts" | "ratio" | "count" | "days" | "cad" | "usd" | "currency" | "date" | "text" | "bool";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "MethodId".
 */
export type MethodId =
  | "M_PRICE_ADJ_CLOSE"
  | "M_FX_BOC_FFILL"
  | "M_CAL_INTERSECTION"
  | "M_RET_SIMPLE"
  | "M_RET_CALENDAR_YEAR"
  | "M_VOL_STDEV_252"
  | "M_GOAL_FUNDING_SCENARIO"
  | "M_HISTORICAL_TAIL"
  | "M_VARIANCE_SHARE"
  | "M_MDD_PEAK_TROUGH"
  | "M_WORST_ROLLING_252"
  | "M_CORR_PEARSON"
  | "M_PORT_CONST_WEIGHTS"
  | "M_WEIGHTS_AFTER_MOVE"
  | "M_STRESS_REPLAY"
  | "M_DERIVE_VOL_BUDGET"
  | "M_DERIVE_POSITION_CAP"
  | "M_DERIVE_SECTOR_CAP"
  | "M_DERIVE_CRYPTO_CAP"
  | "M_DERIVE_GROWTH_CAP"
  | "M_DERIVE_STRESS_LIMIT"
  | "M_DERIVE_DRAWDOWN_LIMIT"
  | "M_MAXSIZE_GRID"
  | "M_FRONTIER_MINVAR"
  | "M_FRONTIER_HIST_MV"
  | "M_RULE_COMPARE"
  | "M_USER_INPUT"
  | "M_PROFILE_ASSUMPTION"
  | "M_OBSERVED_ROW"
  | "M_ATTENTION_RATIO"
  | "M_QUOTE_VERBATIM"
  | "M_EVENT_IMPORTANCE"
  | "M_PRICE_MOVE_AFTER_EVENT"
  | "M_GATE_COUNT";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "LimitationCode".
 */
export type LimitationCode =
  | "LIM_PAST_NOT_FUTURE"
  | "LIM_SAMPLE_WINDOW"
  | "LIM_SURVIVORSHIP"
  | "LIM_CONSTANT_WEIGHTS"
  | "LIM_FX_FFILL"
  | "LIM_CALENDAR_INTERSECTION"
  | "LIM_YAHOO_NOT_CERTIFIED"
  | "LIM_CNQ_FACTOR"
  | "LIM_ETF_NO_LOOKTHROUGH"
  | "LIM_SECTOR_LABELS"
  | "LIM_THEME_TAGS"
  | "LIM_THRESHOLDS_ASSUMED"
  | "LIM_BONDS_SAMPLE"
  | "LIM_MACRO_REVISED"
  | "LIM_MACRO_LAG_ASSUMED"
  | "LIM_NO_CONTROVERSY_DATA"
  | "LIM_EVIDENCE_TIER"
  | "LIM_IMPACT_NOT_ESTABLISHED"
  | "LIM_PRICE_MOVE_NOT_CAUSAL"
  | "LIM_LLM_KNOWLEDGE"
  | "LIM_SHORT_HISTORY"
  | "LIM_CASH_NO_INTEREST"
  | "LIM_SIMULATION_ONLY"
  | "LIM_ATTENTION_PROXY"
  | "LIM_REGISTRY_MATCH"
  | "LIM_MV_ILLUSTRATION";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EvidenceId".
 */
export type EvidenceId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EvidenceType".
 */
export type EvidenceType =
  "filing" | "company_report" | "fund_document" | "official_release" | "news" | "registry" | "attention" | "web_page";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AuditCheckCode".
 */
export type AuditCheckCode =
  "A01" | "A02" | "A03" | "A04" | "A05" | "A06" | "A07" | "A08" | "A09" | "A10" | "A11" | "A12" | "A13" | "A14";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProfileId".
 */
export type ProfileId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FundingMode".
 */
export type FundingMode = "auto" | "pro_rata" | "from_cash" | "from_holdings" | "new_money";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleId".
 */
export type RuleId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Verdict".
 */
export type Verdict = "compatible" | "tension" | "conflict" | "insufficient";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleCode".
 */
export type RuleCode = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleStatus".
 */
export type RuleStatus = "pass" | "tension" | "conflict" | "nee" | "info";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Comparator".
 */
export type Comparator = "<=" | ">=" | "==" | "none";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "NeeReason".
 */
export type NeeReason =
  | "short_history"
  | "no_evidence_loaded"
  | "evidence_unverified"
  | "not_visible_at_asof"
  | "asset_unknown"
  | "dataset_missing";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Lang".
 */
export type Lang = "en" | "fr";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "BriefSectionId".
 */
export type BriefSectionId = "summary" | "facts" | "assumptions" | "limits" | "scenarios" | "next_checks";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Segment".
 */
export type Segment = TextSegment | FactSegment | RuleSegment | StatusSegment | EvidenceSegment;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunKind".
 */
export type RunKind = "decision" | "portfolio_brief" | "event_brief" | "replay" | "profile_draft" | "sabotage";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunStatus".
 */
export type RunStatus = "queued" | "running" | "waiting_input" | "succeeded" | "failed" | "cancelled";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SessionId".
 */
export type SessionId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunInput".
 */
export type RunInput =
  DecisionInput | PortfolioBriefInput | EventBriefInput | ReplayInput | ProfileDraftInput | SabotageInput;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DecisionRequest".
 */
export type DecisionRequest = MoveRequest | GoalRequest;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ExposureGoal".
 */
export type ExposureGoal = ExposureGoal1 & ExposureGoal2;
export type ExposureGoal1 =
  | {
      themes?: {
        [k: string]: unknown;
      };
    }
  | {
      assetClasses?: {
        [k: string]: unknown;
      };
    }
  | {
      tickers?: {
        [k: string]: unknown;
      };
    };
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventId".
 */
export type EventId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleType".
 */
export type RuleType = "cap" | "floor" | "limit" | "exclude" | "evidence" | "flag" | "sim";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleOrigin".
 */
export type RuleOrigin = "derived" | "profile_preference" | "user" | "system" | "imported";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SabotageMode".
 */
export type SabotageMode = "invented_number" | "false_comparison" | "unsupported_interpretation";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "StepType".
 */
export type StepType = "plan" | "research" | "quant" | "risk_check" | "revise" | "write" | "audit" | "sign";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunResult".
 */
export type RunResult =
  | DecisionRunResult
  | PortfolioBriefRunResult
  | EventBriefRunResult
  | ReplayRunResult
  | ProfileDraftRunResult
  | SabotageRunResult;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ScenarioId".
 */
export type ScenarioId = string;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ScenarioKind".
 */
export type ScenarioKind = "requested" | "max_compatible" | "alternative" | "goal_candidate" | "rebalance";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventCategory".
 */
export type EventCategory =
  | "monetary_policy"
  | "macro_release"
  | "geopolitical"
  | "trade_regulation"
  | "corporate"
  | "energy_commodities"
  | "markets"
  | "natural_disaster"
  | "other";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RiskLevel".
 */
export type RiskLevel = "low" | "low_moderate" | "moderate" | "moderate_high" | "high";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Objective".
 */
export type Objective = "preserve" | "balanced" | "growth";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Experience".
 */
export type Experience = "beginner" | "intermediate" | "advanced";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateRunRequest".
 */
export type CreateRunRequest =
  | CreateDecisionRunRequest
  | CreatePortfolioBriefRunRequest
  | CreateEventBriefRunRequest
  | CreateReplayRunRequest
  | CreateProfileDraftRunRequest;
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FeatureFlag".
 */
export type FeatureFlag =
  | "bilingual"
  | "world_explorer"
  | "world_layer_facilities"
  | "world_layer_hazards"
  | "time_machine"
  | "profile_creator"
  | "goal_requests"
  | "sabotage_demo"
  | "research_open_web"
  | "guardrails"
  | "on_demand_tickers"
  | "frontier_chart";
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RulePatchRequest".
 */
export type RulePatchRequest = RulePatchRequest1 & RulePatchRequest2;
export type RulePatchRequest1 = {
  [k: string]: unknown;
};

export interface AplombContracts {
  AccountFXQuote: AccountFXQuote;
  AccountValuation: AccountValuation;
  AddExposureLimitRequest: AddExposureLimitRequest;
  AgentRole: AgentRole;
  AirportReference: AirportReference;
  AirportsResponse: AirportsResponse;
  AllocationChange: AllocationChange;
  AnswerRequest: AnswerRequest;
  AnswerResponse: AnswerResponse;
  ApiError: ApiError;
  ArchiveProfileRequest: ArchiveProfileRequest;
  Asset: Asset;
  AssetAnalyticsResponse: AssetAnalyticsResponse;
  AssetClass: AssetClass;
  AssetFlag: AssetFlag;
  AssetGroup: AssetGroup;
  AssetHistory: AssetHistory;
  AssetMeasurement: AssetMeasurement;
  AssetsResponse: AssetsResponse;
  AttentionResponse: AttentionResponse;
  AttentionSignal: AttentionSignal;
  AuditCheckCode: AuditCheckCode;
  AuditCheckResult: AuditCheckResult;
  AuditReport: AuditReport;
  BatchCheckRequest: BatchCheckRequest;
  BatchCheckResponse: BatchCheckResponse;
  Benchmark: Benchmark;
  Brief: Brief;
  BriefSection: BriefSection;
  BriefSectionId: BriefSectionId;
  CachedBriefResponse: CachedBriefResponse;
  CachedRunResponse: CachedRunResponse;
  CancelResponse: CancelResponse;
  CheckRequest: CheckRequest;
  CheckResult: CheckResult;
  ClarifyingQuestion: ClarifyingQuestion;
  Comparator: Comparator;
  Concentration: Concentration;
  Correlation: Correlation;
  CountryExposure: CountryExposure;
  CreateAccountRequest: CreateAccountRequest;
  CreateDecisionRunRequest: CreateDecisionRunRequest;
  CreateEventBriefRunRequest: CreateEventBriefRunRequest;
  CreatePortfolioBriefRunRequest: CreatePortfolioBriefRunRequest;
  CreateProfileDraftRunRequest: CreateProfileDraftRunRequest;
  CreateProfileRequest: CreateProfileRequest;
  CreateReplayRunRequest: CreateReplayRunRequest;
  CreateRunRequest: CreateRunRequest;
  Currency: Currency;
  DataVersion: DataVersion;
  DatasetCheck: DatasetCheck;
  DatasetField: DatasetField;
  DatasetId: DatasetId;
  DatasetPassport: DatasetPassport;
  DatasetRead: DatasetRead;
  DatasetTrap: DatasetTrap;
  DatasetsResponse: DatasetsResponse;
  DecisionInput: DecisionInput;
  DecisionRequest: DecisionRequest;
  DecisionResult: DecisionResult;
  DecisionRunResult: DecisionRunResult;
  DeriveRulesRequest: DeriveRulesRequest;
  DeriveRulesResponse: DeriveRulesResponse;
  DuplicateProfileRequest: DuplicateProfileRequest;
  EmptyRequest: EmptyRequest;
  EntityCandidate: EntityCandidate;
  EntitySearchResponse: EntitySearchResponse;
  EntitySource: EntitySource;
  ErrorCode: ErrorCode;
  ErrorDetail: ErrorDetail;
  EventBriefInput: EventBriefInput;
  EventBriefResult: EventBriefResult;
  EventBriefRunResult: EventBriefRunResult;
  EventCategory: EventCategory;
  EventId: EventId;
  EventLocation: EventLocation;
  EventSource: EventSource;
  Evidence: Evidence;
  EvidenceId: EvidenceId;
  EvidenceSegment: EvidenceSegment;
  EvidenceSubject: EvidenceSubject;
  EvidenceType: EvidenceType;
  Experience: Experience;
  ExposureGoal: ExposureGoal;
  FacilitiesResponse: FacilitiesResponse;
  Facility: Facility;
  Fact: Fact;
  FactId: FactId;
  FactKey: FactKey;
  FactKind: FactKind;
  FactMethod: FactMethod;
  FactResponse: FactResponse;
  FactSegment: FactSegment;
  FactSubject: FactSubject;
  FactUsage: FactUsage;
  FeatureFlag: FeatureFlag;
  FetchAssetResponse: FetchAssetResponse;
  FieldExplanation: FieldExplanation;
  FocusCard: FocusCard;
  FrontierAsset: FrontierAsset;
  FrontierMetrics: FrontierMetrics;
  FrontierPoint: FrontierPoint;
  FrontierResponse: FrontierResponse;
  Funding: Funding;
  FundingMode: FundingMode;
  FundingOption: FundingOption;
  GateDataset: GateDataset;
  GateReport: GateReport;
  GoalFundingResponse: GoalFundingResponse;
  GoalFundingScenario: GoalFundingScenario;
  GoalRequest: GoalRequest;
  GroupWeight: GroupWeight;
  GuardrailAudit: GuardrailAudit;
  Hazard: Hazard;
  HazardsResponse: HazardsResponse;
  HealthResponse: HealthResponse;
  HoldingExposure: HoldingExposure;
  HoldingWeight: HoldingWeight;
  HorizonYears: HorizonYears1;
  I18nText: I18NText;
  ISODate: ISODate;
  ISODateTime: ISODateTime;
  InitialPortfolio: InitialPortfolio;
  InvestmentGoal: InvestmentGoal;
  InvestorContext: InvestorContext;
  LabelWeight: LabelWeight;
  Lang: Lang;
  LegendItem: LegendItem;
  LimitationCode: LimitationCode;
  LlmReview: LlmReview;
  Meta: Meta;
  MethodId: MethodId;
  MetricCode: MetricCode;
  MissingField: MissingField;
  ModelIds: ModelIds;
  MoveRequest: MoveRequest;
  NeeReason: NeeReason;
  Objective: Objective;
  OverviewResponse: OverviewResponse;
  OverviewReturns: OverviewReturns;
  OverviewRisk: OverviewRisk;
  PageviewsPoint: PageviewsPoint;
  ParseRequest: ParseRequest;
  ParsedRequest: ParsedRequest;
  PartialProfile: PartialProfile;
  PerformanceResponse: PerformanceResponse;
  Period: Period;
  PolicyRule: PolicyRule;
  Portfolio: Portfolio;
  PortfolioAccount: PortfolioAccount;
  PortfolioBriefInput: PortfolioBriefInput;
  PortfolioBriefResult: PortfolioBriefResult;
  PortfolioBriefRunResult: PortfolioBriefRunResult;
  PortfolioSnapshot: PortfolioSnapshot;
  Position: Position;
  Preferences: Preferences1;
  Profile: Profile;
  ProfileDraftInput: ProfileDraftInput;
  ProfileDraftResult: ProfileDraftResult;
  ProfileDraftRunResult: ProfileDraftRunResult;
  ProfileId: ProfileId;
  ProfilesResponse: ProfilesResponse;
  ProposedMove: ProposedMove;
  QuestionOption: QuestionOption;
  QueuedRunResponse: QueuedRunResponse;
  RebalanceRequest: RebalanceRequest;
  RebalanceResponse: RebalanceResponse;
  Refusal: Refusal;
  ReplayInput: ReplayInput;
  ReplayPreset: ReplayPreset;
  ReplayPresetsResponse: ReplayPresetsResponse;
  ReplayResult: ReplayResult;
  ReplayRunResult: ReplayRunResult;
  RevealOutcome: RevealOutcome;
  RevealRequest: RevealRequest;
  RevealResult: RevealResult;
  ReviewFinding: ReviewFinding;
  RiskDiagnosticsResponse: RiskDiagnosticsResponse;
  RiskLevel: RiskLevel;
  RuleBounds: RuleBounds;
  RuleCheck: RuleCheck;
  RuleCode: RuleCode;
  RuleDerivation: RuleDerivation;
  RuleId: RuleId;
  RuleOrigin: RuleOrigin;
  RuleOverride: RuleOverride;
  RulePatchRequest: RulePatchRequest;
  RulePatchResponse: RulePatchResponse;
  RuleSegment: RuleSegment;
  RuleStatus: RuleStatus;
  RuleTarget: RuleTarget;
  RuleType: RuleType;
  Run: Run;
  RunFlags: RunFlags;
  RunId: RunId;
  RunInput: RunInput;
  RunKind: RunKind;
  RunResult: RunResult;
  RunStatus: RunStatus;
  RunSummary: RunSummary;
  RunUsage: RunUsage;
  RunsResponse: RunsResponse;
  SabotageInput: SabotageInput;
  SabotageMode: SabotageMode;
  SabotageRequest: SabotageRequest;
  SabotageResult: SabotageResult;
  SabotageRunResult: SabotageRunResult;
  Scenario: Scenario;
  ScenarioId: ScenarioId;
  ScenarioKind: ScenarioKind;
  Segment: Segment;
  SelectAccountRequest: SelectAccountRequest;
  Sentence: Sentence;
  SentenceAudit: SentenceAudit;
  SeriesPoint: SeriesPoint;
  SessionId: SessionId;
  SnapshotMetrics: SnapshotMetrics;
  SnapshotPosition: SnapshotPosition;
  SourceRef: SourceRef;
  StatusSegment: StatusSegment;
  Step: Step;
  StepType: StepType;
  TextSegment: TextSegment;
  ThemeExposure: ThemeExposure;
  ThemeTag: ThemeTag;
  Ticker: Ticker;
  TokenUsage: TokenUsage;
  ToolCall: ToolCall;
  TopPosition: TopPosition;
  Unit: Unit;
  UniverseSummary: UniverseSummary;
  UnsignedDraft: UnsignedDraft;
  UnsignedDraftSection: UnsignedDraftSection;
  UnsignedDraftSentence: UnsignedDraftSentence;
  UpdatePortfolioRequest: UpdatePortfolioRequest;
  UpdateProfileRequest: UpdateProfileRequest;
  Verdict: Verdict;
  VerdictCounts: VerdictCounts;
  Verification: Verification;
  VerificationCheck: VerificationCheck;
  WindowCode: WindowCode;
  WindowSpec: WindowSpec;
  WorldCountryResponse: WorldCountryResponse;
  WorldEvent: WorldEvent;
  WorldEventItem: WorldEventItem;
  WorldEventResponse: WorldEventResponse;
  WorldEventsResponse: WorldEventsResponse;
  WorldExposureResponse: WorldExposureResponse;
  WorldGeographicRelationship: WorldGeographicRelationship;
  WorldLayer: WorldLayer;
  WorldLayersResponse: WorldLayersResponse;
  WorldModeStatus: WorldModeStatus;
  WorldObservation: WorldObservation;
  WorldObservationLocation: WorldObservationLocation;
  WorldObservationSource: WorldObservationSource;
  WorldObservationsResponse: WorldObservationsResponse;
  WorstExposure: WorstExposure;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AccountFXQuote".
 */
export interface AccountFXQuote {
  currency: Currency;
  cadPerUnit: number;
  observedOn: ISODate;
  availableAt: ISODateTime;
  source: SourceRef;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SourceRef".
 */
export interface SourceRef {
  datasetId: DatasetId;
  dataVersion: DataVersion;
  sourceName: string;
  sourceUrl: string | null;
  retrievedOn: ISODate;
  licence: string;
  rowsRead: number | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AccountValuation".
 */
export interface AccountValuation {
  verifiedChecks?: string[];
  nativeCurrency: Currency;
  nativeValue: number;
  reportingCurrency: Currency;
  reportingValue: number;
  conversionRate: number;
  valuationDate: ISODate;
  capturedAt: ISODateTime;
  dataVersion: DataVersion;
  quotes: AccountFXQuote[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AddExposureLimitRequest".
 */
export interface AddExposureLimitRequest {
  dimension: "country" | "currency";
  key: string;
  threshold: number;
  version: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AirportReference".
 */
export interface AirportReference {
  airportId: string;
  ident: string;
  name: string;
  lat: number;
  lon: number;
  countryIso2: string | null;
  countryIso3: string | null;
  sourceUrl: string;
  capturedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AirportsResponse".
 */
export interface AirportsResponse {
  items: AirportReference[];
  total: number;
  dataVersion: DataVersion;
  capturedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AllocationChange".
 */
export interface AllocationChange {
  ticker: Ticker;
  beforePct: number;
  targetPct: number;
  changePct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AnswerRequest".
 */
export interface AnswerRequest {
  questionId: string;
  value: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AnswerResponse".
 */
export interface AnswerResponse {
  runId: RunId;
  status: "running";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ApiError".
 */
export interface ApiError {
  error: ErrorDetail;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ErrorDetail".
 */
export interface ErrorDetail {
  code: ErrorCode;
  message: string;
  details?: {
    [k: string]: unknown;
  };
  requestId: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ArchiveProfileRequest".
 */
export interface ArchiveProfileRequest {
  archived: boolean;
  version: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Asset".
 */
export interface Asset {
  ticker: Ticker;
  name: string;
  assetClass: AssetClass;
  assetGroup: AssetGroup;
  market: string;
  currency: Currency;
  sector: string;
  gicsSector: string | null;
  isSingleName: boolean;
  country: string | null;
  themes: ThemeTag[];
  tier: "starter" | "extended" | "on_demand";
  history: AssetHistory;
  flags: AssetFlag[];
  dataVersion: DataVersion;
  datasetId: DatasetId;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetHistory".
 */
export interface AssetHistory {
  firstDate: ISODate;
  lastDate: ISODate;
  nObs: number;
  nObsMaster: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetAnalyticsResponse".
 */
export interface AssetAnalyticsResponse {
  asset: Asset;
  currency: Currency;
  dataVersion: DataVersion;
  asOf: ISODate;
  window: WindowSpec;
  metrics: {
    [k: string]: AssetMeasurement;
  };
  facts: {
    [k: string]: Fact;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WindowSpec".
 */
export interface WindowSpec {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetMeasurement".
 */
export interface AssetMeasurement {
  value: number | null;
  factId: FactId | null;
  unavailableReason: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Fact".
 */
export interface Fact {
  id: FactId;
  key: FactKey;
  kind: FactKind;
  metric: MetricCode;
  label: I18NText;
  value: number | string | boolean | null;
  unit: Unit;
  currency: Currency | null;
  display: I18NText;
  subject: FactSubject;
  period: Period | null;
  window: WindowSpec | null;
  asOf: ISODate;
  availableAt: ISODateTime | null;
  method: FactMethod;
  inputs: FactId[];
  nObs: number | null;
  sources: SourceRef[];
  limitations: LimitationCode[];
  verification: Verification;
  createdBy: "quant" | "rules" | "optimizer" | "research" | "profile" | "user" | "world" | "timemachine";
  createdAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "I18nText".
 */
export interface I18NText {
  en: string;
  fr: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactSubject".
 */
export interface FactSubject {
  type:
    | "asset"
    | "portfolio"
    | "sector"
    | "asset_group"
    | "asset_class"
    | "theme"
    | "country"
    | "currency"
    | "rule"
    | "macro"
    | "event"
    | "request"
    | "universe";
  id: string;
  variant: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Period".
 */
export interface Period {
  start: ISODate;
  end: ISODate;
  label?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactMethod".
 */
export interface FactMethod {
  id: MethodId;
  description: I18NText;
  params: {
    [k: string]: number | string | boolean;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Verification".
 */
export interface Verification {
  status: "verified" | "unverified" | "failed";
  checks: VerificationCheck[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "VerificationCheck".
 */
export interface VerificationCheck {
  code: string;
  ok: boolean;
  detail: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AssetsResponse".
 */
export interface AssetsResponse {
  items: Asset[];
  nextCursor: string | null;
  total: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AttentionResponse".
 */
export interface AttentionResponse {
  signal: AttentionSignal;
  fact: Fact | null;
  evidence: Evidence | null;
  series: PageviewsPoint[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AttentionSignal".
 */
export interface AttentionSignal {
  ticker: Ticker;
  article: string;
  ratio: number | null;
  recentPeriod: Period;
  baselinePeriod: Period;
  flag: "elevated" | "normal" | "unknown";
  factId: FactId | null;
  evidenceId: EvidenceId | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Evidence".
 */
export interface Evidence {
  id: EvidenceId;
  type: EvidenceType;
  tier: 1 | 2 | 3;
  title: string;
  publisher: string;
  url: string;
  publishedAt: ISODate | null;
  retrievedAt: ISODateTime;
  lang: string;
  quote: string | null;
  claim: I18NText;
  subject: EvidenceSubject;
  tool: string;
  documentRef: string | null;
  licence: string;
  verification: Verification;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EvidenceSubject".
 */
export interface EvidenceSubject {
  type: "asset" | "sector" | "country" | "event" | "theme";
  id: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PageviewsPoint".
 */
export interface PageviewsPoint {
  date: ISODate;
  views: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AuditCheckResult".
 */
export interface AuditCheckResult {
  code: AuditCheckCode;
  ok: boolean;
  kind: "code" | "llm" | "guardrail";
  detail: string;
  sentenceIds: string[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "AuditReport".
 */
export interface AuditReport {
  status: "passed" | "passed_with_strikes" | "failed";
  checks: AuditCheckResult[];
  sentencesChecked: number;
  sentencesStruck: number;
  rewrites: number;
  guardrail: GuardrailAudit;
  llmReview: LlmReview;
  ledgerHash: string;
  signedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GuardrailAudit".
 */
export interface GuardrailAudit {
  applied: boolean;
  action: "none" | "blocked" | "masked";
  id: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "LlmReview".
 */
export interface LlmReview {
  model: string | null;
  findings: ReviewFinding[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReviewFinding".
 */
export interface ReviewFinding {
  sentenceId: string;
  issue: string;
  code: AuditCheckCode;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "BatchCheckRequest".
 */
export interface BatchCheckRequest {
  /**
   * @maxItems 5
   */
  items:
    | []
    | [CheckRequest]
    | [CheckRequest, CheckRequest]
    | [CheckRequest, CheckRequest, CheckRequest]
    | [CheckRequest, CheckRequest, CheckRequest, CheckRequest]
    | [CheckRequest, CheckRequest, CheckRequest, CheckRequest, CheckRequest];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CheckRequest".
 */
export interface CheckRequest {
  profileId: ProfileId;
  move: ProposedMove | null;
  ruleOverrides?: RuleOverride[];
  window?: WindowSpec1;
  asOf?: string;
  compareFunding?: boolean;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProposedMove".
 */
export interface ProposedMove {
  ticker: Ticker;
  sizePct: number;
  funding: Funding;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Funding".
 */
export interface Funding {
  mode: FundingMode;
  fromTickers?: Ticker[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleOverride".
 */
export interface RuleOverride {
  threshold?: number;
  enabled?: boolean;
  ruleId: RuleId;
}
export interface WindowSpec1 {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "BatchCheckResponse".
 */
export interface BatchCheckResponse {
  results: (CheckResult | ApiError)[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CheckResult".
 */
export interface CheckResult {
  verdict: Verdict;
  counts: VerdictCounts;
  ruleChecks: RuleCheck[];
  portfolioBefore: PortfolioSnapshot;
  portfolioAfter: PortfolioSnapshot;
  fundingUsed: Funding;
  fundingOptions: FundingOption[];
  maxCompatibleSizePct: number;
  baselineConflict: boolean;
  facts: {
    [k: string]: Fact;
  };
  asOf: ISODate;
  dataVersion: DataVersion;
  window: WindowSpec;
  computeMs: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "VerdictCounts".
 */
export interface VerdictCounts {
  pass: number;
  tension: number;
  conflict: number;
  nee: number;
  info: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleCheck".
 */
export interface RuleCheck {
  ruleId: RuleId;
  code: RuleCode;
  status: RuleStatus;
  value: number | null;
  threshold: number | null;
  unit: Unit;
  comparator: Comparator;
  headroom: number | null;
  worst: WorstExposure | null;
  valueFactId: FactId | null;
  thresholdFactId: FactId | null;
  detail: I18NText;
  neeReason: NeeReason | null;
  evidenceIds: EvidenceId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorstExposure".
 */
export interface WorstExposure {
  type: "asset" | "sector" | "asset_group" | "theme";
  id: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PortfolioSnapshot".
 */
export interface PortfolioSnapshot {
  variant: string;
  totalValue: number;
  currency: Currency;
  positions: SnapshotPosition[];
  byAssetGroup: GroupWeight[];
  bySector: LabelWeight[];
  byCountry: LabelWeight[];
  metrics: SnapshotMetrics;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SnapshotPosition".
 */
export interface SnapshotPosition {
  ticker: Ticker;
  weightPct: number;
  name: string;
  assetClass: AssetClass;
  assetGroup: AssetGroup;
  sector: string;
  marketValue: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GroupWeight".
 */
export interface GroupWeight {
  key: AssetGroup;
  weightPct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "LabelWeight".
 */
export interface LabelWeight {
  key: string;
  weightPct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SnapshotMetrics".
 */
export interface SnapshotMetrics {
  volatilityPct: number | null;
  maxDrawdownPct: number | null;
  stress2022Pct: number | null;
  factIds: {
    [k: string]: FactId;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FundingOption".
 */
export interface FundingOption {
  funding: Funding;
  feasible: boolean;
  infeasibleReason: I18NText | null;
  verdict: Verdict | null;
  counts: VerdictCounts | null;
  maxCompatibleSizePct: number | null;
  recommended: boolean;
  rank: number | null;
  note: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Benchmark".
 */
export interface Benchmark {
  ticker: Ticker;
  series: SeriesPoint[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SeriesPoint".
 */
export interface SeriesPoint {
  date: ISODate;
  value: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Brief".
 */
export interface Brief {
  lang: Lang;
  sections: BriefSection[];
  disclaimer: I18NText;
  generatedAt: ISODateTime;
  model: string;
  audit: AuditReport;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "BriefSection".
 */
export interface BriefSection {
  id: BriefSectionId;
  title: I18NText;
  sentences: Sentence[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Sentence".
 */
export interface Sentence {
  id: string;
  segments: Segment[];
  audit: SentenceAudit;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "TextSegment".
 */
export interface TextSegment {
  t: "text";
  text: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactSegment".
 */
export interface FactSegment {
  t: "fact";
  factId: FactId;
  display: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleSegment".
 */
export interface RuleSegment {
  t: "rule";
  ruleId: RuleId;
  display: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "StatusSegment".
 */
export interface StatusSegment {
  t: "status";
  ruleId: RuleId;
  display: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EvidenceSegment".
 */
export interface EvidenceSegment {
  t: "evidence";
  evidenceId: EvidenceId;
  display: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SentenceAudit".
 */
export interface SentenceAudit {
  status: "verified" | "struck" | "repaired";
  failedChecks: AuditCheckCode[];
  note: I18NText | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CachedBriefResponse".
 */
export interface CachedBriefResponse {
  run: Run | null;
  stale: boolean;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Run".
 */
export interface Run {
  runId: RunId;
  kind: RunKind;
  status: RunStatus;
  sessionId: SessionId;
  profileId: ProfileId | null;
  parentRunId: RunId | null;
  lang: Lang;
  asOf: ISODate;
  dataVersion: DataVersion;
  input: RunInput;
  steps: Step[];
  facts: {
    [k: string]: Fact;
  };
  evidence: {
    [k: string]: Evidence;
  };
  question: ClarifyingQuestion | null;
  result: RunResult | null;
  error: ErrorDetail | null;
  flags: RunFlags;
  usage: RunUsage;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DecisionInput".
 */
export interface DecisionInput {
  kind: "decision";
  request: DecisionRequest;
  originalText: string | null;
  window: WindowSpec;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "MoveRequest".
 */
export interface MoveRequest {
  type: "move";
  move: ProposedMove;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GoalRequest".
 */
export interface GoalRequest {
  type: "goal";
  goal: ExposureGoal;
}
export interface ExposureGoal2 {
  themes: ThemeTag[];
  assetClasses: AssetClass[];
  tickers: Ticker[];
  targetExposurePct: number | null;
  maxLossPct: number | null;
  maxVolPct: number | null;
  notes: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PortfolioBriefInput".
 */
export interface PortfolioBriefInput {
  kind: "portfolio_brief";
  window: WindowSpec;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventBriefInput".
 */
export interface EventBriefInput {
  kind: "event_brief";
  eventId: EventId;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReplayInput".
 */
export interface ReplayInput {
  kind: "replay";
  request: DecisionRequest;
  asOf: ISODate;
  window: WindowSpec;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProfileDraftInput".
 */
export interface ProfileDraftInput {
  kind: "profile_draft";
  text: string;
  fields: PartialProfile;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PartialProfile".
 */
export interface PartialProfile {
  profileId?: string;
  isDefault?: boolean;
  archived?: boolean;
  origin?: "brief" | "user" | "agent_draft";
  name?: string;
  initial?: string;
  age?: number | null;
  occupation?: string | null;
  riskLevel?: "low" | "low_moderate" | "moderate" | "moderate_high" | "high";
  horizonYears?: HorizonYears;
  objective?: "preserve" | "balanced" | "growth";
  objectiveText?: I18NText1;
  experience?: "beginner" | "intermediate" | "advanced";
  reportingCurrency?: string;
  preferences?: Preferences;
  blurb?: I18NText2;
  personaTest?: I18NText | null;
  investorContext?: InvestorContext | null;
  accounts?: PortfolioAccount[];
  activeAccountId?: string | null;
  portfolio?: Portfolio1;
  rules?: PolicyRule[];
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}
export interface HorizonYears {
  min: number;
  max: number | null;
}
export interface I18NText1 {
  en: string;
  fr: string;
}
export interface Preferences {
  themesOfInterest: ThemeTag[];
  excludedSectors: string[];
  excludedAssetClasses: AssetClass[];
  esgFocus: boolean;
  avoidControversies: boolean;
  avoidSpeculative: boolean;
  cryptoInterest: "none" | "low" | "open";
  wantsDiversification: boolean;
  notes: string;
}
export interface I18NText2 {
  en: string;
  fr: string;
}
/**
 * Optional global context. Jurisdiction is context, not a sourced tax policy.
 *
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "InvestorContext".
 */
export interface InvestorContext {
  country?: string | null;
  investorType?:
    | "individual"
    | "retirement"
    | "income"
    | "crypto"
    | "institutional"
    | "family_office"
    | "endowment"
    | "pension"
    | "wealth_manager"
    | "advisor"
    | "custom";
  language?: "en" | "fr";
  /**
   * @maxItems 20
   */
  objectives?: InvestmentGoal[];
  liquidityNotes?: string;
  riskCapacityNotes?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PortfolioAccount".
 */
export interface PortfolioAccount {
  nativeValuation?: AccountValuation | null;
  accountId: string;
  name: string;
  portfolio: Portfolio;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Portfolio".
 */
export interface Portfolio {
  isFictional: true;
  totalValue: number;
  currency: Currency;
  positions: Position[];
  updatedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Position".
 */
export interface Position {
  ticker: Ticker;
  weightPct: number;
}
export interface Portfolio1 {
  isFictional: true;
  totalValue: number;
  currency: Currency;
  positions: Position[];
  updatedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PolicyRule".
 */
export interface PolicyRule {
  ruleId: RuleId;
  code: RuleCode;
  type: RuleType;
  enabled: boolean;
  label: I18NText;
  rationale: I18NText;
  metric: MetricCode | null;
  target: RuleTarget;
  comparator: Comparator;
  threshold: number | null;
  unit: Unit;
  editable: boolean;
  bounds: RuleBounds | null;
  origin: RuleOrigin;
  isAssumption: boolean;
  derivation: RuleDerivation | null;
  countsInVerdict: boolean;
  updatedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleTarget".
 */
export interface RuleTarget {
  dimension:
    "position" | "sector" | "asset_class" | "asset_group" | "theme" | "portfolio" | "country" | "currency" | "none";
  key: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleBounds".
 */
export interface RuleBounds {
  min: number;
  max: number;
  step: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RuleDerivation".
 */
export interface RuleDerivation {
  methodId: MethodId;
  formula: string;
  inputs: {
    [k: string]: number | string;
  };
  dataVersion: DataVersion;
  window: WindowSpec;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SabotageInput".
 */
export interface SabotageInput {
  kind: "sabotage";
  mode: SabotageMode;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Step".
 */
export interface Step {
  seq: number;
  type: StepType;
  iteration: number;
  agent: AgentRole;
  actor: "llm" | "llm+tools" | "code" | "code+llm";
  status: "running" | "done" | "failed";
  startedAt: ISODateTime;
  endedAt: ISODateTime | null;
  durationMs: number | null;
  summary: I18NText;
  model: string | null;
  usage: TokenUsage | null;
  toolCalls: ToolCall[];
  factIds: FactId[];
  evidenceIds: EvidenceId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "TokenUsage".
 */
export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ToolCall".
 */
export interface ToolCall {
  id: string;
  tool: string;
  args: {
    [k: string]: unknown;
  };
  startedAt: ISODateTime;
  durationMs: number;
  ok: boolean;
  resultSummary: string;
  datasetsRead: DatasetRead[];
  factIds: FactId[];
  evidenceIds: EvidenceId[];
  error: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetRead".
 */
export interface DatasetRead {
  datasetId: DatasetId;
  dataVersion: DataVersion;
  rows: number;
  rowsWithheld: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ClarifyingQuestion".
 */
export interface ClarifyingQuestion {
  questionId: string;
  text: I18NText;
  field: string;
  options: QuestionOption[] | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "QuestionOption".
 */
export interface QuestionOption {
  value: string;
  label: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DecisionRunResult".
 */
export interface DecisionRunResult {
  kind: "decision";
  decision: DecisionResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DecisionResult".
 */
export interface DecisionResult {
  request: DecisionRequest;
  verdict: Verdict;
  counts: VerdictCounts;
  selectedScenarioId: ScenarioId;
  scenarios: Scenario[];
  portfolioBefore: PortfolioSnapshot;
  maxCompatibleSizePct: number | null;
  fundingOptions: FundingOption[];
  attention: AttentionSignal | null;
  macroContext: FactId[];
  brief: Brief;
  limitations: LimitationCode[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Scenario".
 */
export interface Scenario {
  scenarioId: ScenarioId;
  kind: ScenarioKind;
  label: I18NText;
  moves: ProposedMove[];
  verdict: Verdict;
  counts: VerdictCounts;
  ruleChecks: RuleCheck[];
  portfolioAfter: PortfolioSnapshot;
  exposure: ThemeExposure[];
  rationale: I18NText;
  isBestFit: boolean;
  rank: number;
  keyFactIds: FactId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ThemeExposure".
 */
export interface ThemeExposure {
  theme: ThemeTag;
  beforePct: number;
  afterPct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PortfolioBriefRunResult".
 */
export interface PortfolioBriefRunResult {
  kind: "portfolio_brief";
  portfolioBrief: PortfolioBriefResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PortfolioBriefResult".
 */
export interface PortfolioBriefResult {
  snapshot: PortfolioSnapshot;
  ruleChecks: RuleCheck[];
  verdict: Verdict;
  counts: VerdictCounts;
  /**
   * @minItems 3
   * @maxItems 3
   */
  focusCards: [FocusCard, FocusCard, FocusCard];
  brief: Brief;
  horizonBand: "short" | "medium" | "long";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FocusCard".
 */
export interface FocusCard {
  title: I18NText;
  body: Sentence[];
  factIds: FactId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventBriefRunResult".
 */
export interface EventBriefRunResult {
  kind: "event_brief";
  eventBrief: EventBriefResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventBriefResult".
 */
export interface EventBriefResult {
  event: WorldEvent;
  exposures: HoldingExposure[];
  brief: Brief;
  impactStatement: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldEvent".
 */
export interface WorldEvent {
  eventId: EventId;
  title: string;
  category: EventCategory;
  occurredAt: ISODate;
  publishedAt: ISODateTime | null;
  location: EventLocation;
  origin: "gdelt" | "official" | "curated" | "usgs" | "firms" | "live" | "eonet";
  /**
   * @minItems 1
   */
  sources: [EventSource, ...EventSource[]];
  sourceCount: number;
  importance: number;
  relatedTickers: Ticker[];
  relatedThemes: ThemeTag[];
  relatedCountries: string[];
  datasetId: DatasetId;
  dataVersion: DataVersion;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventLocation".
 */
export interface EventLocation {
  lat: number;
  lon: number;
  countryIso3: string | null;
  placeName: string | null;
  precision: "point" | "city" | "country";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EventSource".
 */
export interface EventSource {
  publisher: string;
  title: string;
  url: string;
  publishedAt: ISODateTime | null;
  sourceType: "news" | "official" | "filing" | "data";
  lang: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "HoldingExposure".
 */
export interface HoldingExposure {
  ticker: Ticker;
  weightPct: number;
  linkType: "named_in_source" | "listing_country" | "sector" | "theme" | "documented_exposure" | "etf_lookthrough";
  evidenceIds: EvidenceId[];
  impact: "not_established" | "measured_price_move";
  impactFactId: FactId | null;
  note: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReplayRunResult".
 */
export interface ReplayRunResult {
  kind: "replay";
  replay: ReplayResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReplayResult".
 */
export interface ReplayResult {
  asOf: ISODate;
  decision: DecisionResult;
  gate: GateReport;
  notices: LimitationCode[];
  revealAvailableUntil: ISODate;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GateReport".
 */
export interface GateReport {
  datasets: GateDataset[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GateDataset".
 */
export interface GateDataset {
  datasetId: DatasetId;
  rowsVisible: number;
  rowsWithheld: number;
  lastVisibleDate: ISODate;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProfileDraftRunResult".
 */
export interface ProfileDraftRunResult {
  kind: "profile_draft";
  draft: ProfileDraftResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProfileDraftResult".
 */
export interface ProfileDraftResult {
  profile: PartialProfile;
  explanations: FieldExplanation[];
  unresolved: MissingField[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FieldExplanation".
 */
export interface FieldExplanation {
  field: string;
  text: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "MissingField".
 */
export interface MissingField {
  field: string;
  question: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SabotageRunResult".
 */
export interface SabotageRunResult {
  kind: "sabotage";
  sabotage: SabotageResult;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SabotageResult".
 */
export interface SabotageResult {
  mode: SabotageMode;
  injectedInstruction: string;
  briefBeforeAudit: UnsignedDraft;
  briefAfterAudit: Brief;
  caught: boolean;
  failedChecks: AuditCheckResult[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UnsignedDraft".
 */
export interface UnsignedDraft {
  status: "unaudited";
  model: string;
  sections: UnsignedDraftSection[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UnsignedDraftSection".
 */
export interface UnsignedDraftSection {
  id: BriefSectionId;
  sentences: UnsignedDraftSentence[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UnsignedDraftSentence".
 */
export interface UnsignedDraftSentence {
  id: string;
  template: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunFlags".
 */
export interface RunFlags {
  sabotage: SabotageMode | null;
  fixture: boolean;
  timeMachine: boolean;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunUsage".
 */
export interface RunUsage {
  inputTokens: number;
  outputTokens: number;
  llmCalls: number;
  toolCalls: number;
  durationMs: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CachedRunResponse".
 */
export interface CachedRunResponse {
  runId: RunId;
  status: "succeeded";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CancelResponse".
 */
export interface CancelResponse {
  runId: RunId;
  status: "cancelled";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Concentration".
 */
export interface Concentration {
  hhi: number;
  effectiveN: number;
  topPositions: TopPosition[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "TopPosition".
 */
export interface TopPosition {
  ticker: Ticker;
  name: string;
  weightPct: number;
  marketValue: number;
  return1yPct: number | null;
  assetClass: AssetClass;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Correlation".
 */
export interface Correlation {
  tickers: Ticker[];
  matrix: number[][];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CountryExposure".
 */
export interface CountryExposure {
  countryIso3: string;
  weightPct: number;
  basis: "listing_country" | "etf_lookthrough" | "mixed";
  holdings: HoldingWeight[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "HoldingWeight".
 */
export interface HoldingWeight {
  ticker: Ticker;
  weightPct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateAccountRequest".
 */
export interface CreateAccountRequest {
  currency?: Currency | null;
  name: string;
  version: number;
  portfolio: InitialPortfolio;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "InitialPortfolio".
 */
export interface InitialPortfolio {
  totalValue: number;
  positions: Position[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateDecisionRunRequest".
 */
export interface CreateDecisionRunRequest {
  kind: "decision";
  profileId: ProfileId;
  lang: Lang;
  request: DecisionRequest;
  originalText?: string;
  window?: WindowSpec2;
}
export interface WindowSpec2 {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateEventBriefRunRequest".
 */
export interface CreateEventBriefRunRequest {
  kind: "event_brief";
  profileId: ProfileId;
  lang: Lang;
  eventId: EventId;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreatePortfolioBriefRunRequest".
 */
export interface CreatePortfolioBriefRunRequest {
  kind: "portfolio_brief";
  profileId: ProfileId;
  lang: Lang;
  window?: WindowSpec3;
  force?: boolean;
}
export interface WindowSpec3 {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateProfileDraftRunRequest".
 */
export interface CreateProfileDraftRunRequest {
  kind: "profile_draft";
  lang: Lang;
  text: string;
  fields?: PartialProfile1;
}
export interface PartialProfile1 {
  profileId?: string;
  isDefault?: boolean;
  archived?: boolean;
  origin?: "brief" | "user" | "agent_draft";
  name?: string;
  initial?: string;
  age?: number | null;
  occupation?: string | null;
  riskLevel?: "low" | "low_moderate" | "moderate" | "moderate_high" | "high";
  horizonYears?: HorizonYears;
  objective?: "preserve" | "balanced" | "growth";
  objectiveText?: I18NText1;
  experience?: "beginner" | "intermediate" | "advanced";
  reportingCurrency?: string;
  preferences?: Preferences;
  blurb?: I18NText2;
  personaTest?: I18NText | null;
  investorContext?: InvestorContext | null;
  accounts?: PortfolioAccount[];
  activeAccountId?: string | null;
  portfolio?: Portfolio1;
  rules?: PolicyRule[];
  version?: number;
  createdAt?: string;
  updatedAt?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateProfileRequest".
 */
export interface CreateProfileRequest {
  name: string;
  age: number | null;
  riskLevel: RiskLevel;
  horizonYears: HorizonYears1;
  objective: Objective;
  experience: Experience;
  reportingCurrency: Currency;
  preferences: Preferences1;
  portfolio: InitialPortfolio | null;
  rules: PolicyRule[] | null;
  fromDraftRunId: RunId | null;
  investorContext?: InvestorContext | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "HorizonYears".
 */
export interface HorizonYears1 {
  min: number;
  max: number | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Preferences".
 */
export interface Preferences1 {
  themesOfInterest: ThemeTag[];
  excludedSectors: string[];
  excludedAssetClasses: AssetClass[];
  esgFocus: boolean;
  avoidControversies: boolean;
  avoidSpeculative: boolean;
  cryptoInterest: "none" | "low" | "open";
  wantsDiversification: boolean;
  notes: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "CreateReplayRunRequest".
 */
export interface CreateReplayRunRequest {
  kind: "replay";
  profileId: ProfileId;
  lang: Lang;
  request: DecisionRequest;
  asOf: ISODate;
  window?: WindowSpec4;
}
export interface WindowSpec4 {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetCheck".
 */
export interface DatasetCheck {
  name: string;
  ok: boolean;
  detail: string;
  checkedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetField".
 */
export interface DatasetField {
  name: string;
  type: string;
  description: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetPassport".
 */
export interface DatasetPassport {
  datasetId: DatasetId;
  name: I18NText;
  role: I18NText;
  status: "in_use" | "planned" | "rejected";
  source: string;
  sourceUrl: string | null;
  accessMethod: string;
  licence: string;
  licenceUrl: string | null;
  retrievedOn: ISODate | null;
  coverage: Period | null;
  frequency: string;
  rowCount: number | null;
  dataVersion: DataVersion | null;
  schema: DatasetField[];
  processing: I18NText[];
  limitations: LimitationCode[];
  availabilityRule: I18NText;
  checks: DatasetCheck[];
  rejectedReason: I18NText | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetTrap".
 */
export interface DatasetTrap {
  code: LimitationCode;
  handledBy: string;
  status: "handled" | "disclosed" | "open";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DatasetsResponse".
 */
export interface DatasetsResponse {
  items: DatasetPassport[];
  traps: DatasetTrap[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DeriveRulesRequest".
 */
export interface DeriveRulesRequest {
  reset: boolean;
  window?: WindowSpec5;
}
export interface WindowSpec5 {
  code: WindowCode;
  start?: string;
  end?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DeriveRulesResponse".
 */
export interface DeriveRulesResponse {
  rules: PolicyRule[];
  facts: {
    [k: string]: Fact;
  };
  profileVersion: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "DuplicateProfileRequest".
 */
export interface DuplicateProfileRequest {
  name?: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EmptyRequest".
 */
export interface EmptyRequest {}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EntityCandidate".
 */
export interface EntityCandidate {
  lei: string;
  legalName: string;
  jurisdiction: string | null;
  entityStatus: string | null;
  recordUrl: string;
  matchStatus: "candidate";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EntitySearchResponse".
 */
export interface EntitySearchResponse {
  query: string;
  items: EntityCandidate[];
  total: number;
  returned: number;
  rejected: number;
  truncated: boolean;
  source: EntitySource;
  limitations: string[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "EntitySource".
 */
export interface EntitySource {
  provider: string;
  url: string;
  retrievedAt: ISODateTime;
  availableAt: ISODateTime;
  publishedAt: ISODateTime | null;
  contentSha256: string;
  licence: string;
  licenceUrl: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FacilitiesResponse".
 */
export interface FacilitiesResponse {
  capturedAt?: ISODateTime | null;
  dataVersion?: DataVersion | null;
  items: Facility[];
  total: number;
  reportingYear: number;
  limitations: LimitationCode[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Facility".
 */
export interface Facility {
  facilityId: string;
  name: string;
  operator: string;
  ticker: Ticker | null;
  matchConfidence: "exact" | "probable" | "none";
  lat: number;
  lon: number;
  countryIso3: string;
  reportingYear: number;
  emissionsTco2e: number;
  registry: "eccc_ghgrp" | "epa_ghgrp";
  sourceUrl: string;
  dataVersion: DataVersion;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactResponse".
 */
export interface FactResponse {
  fact: Fact;
  inputs: Fact[];
  usedBy: FactUsage;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FactUsage".
 */
export interface FactUsage {
  sentenceIds: string[];
  ruleIds: RuleId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FetchAssetResponse".
 */
export interface FetchAssetResponse {
  asset: Asset;
  accepted: boolean;
  rejectedReason: I18NText | null;
  passport: DatasetPassport;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FrontierAsset".
 */
export interface FrontierAsset {
  volPct: number;
  histReturnPct: number;
  ticker: Ticker;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FrontierMetrics".
 */
export interface FrontierMetrics {
  volPct: number;
  histReturnPct: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FrontierPoint".
 */
export interface FrontierPoint {
  volPct: number;
  histReturnPct: number;
  weights: Position[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "FrontierResponse".
 */
export interface FrontierResponse {
  window: WindowSpec;
  currency: Currency;
  assets: FrontierAsset[];
  minVarFrontier: FrontierPoint[];
  histMvFrontier: FrontierPoint[];
  portfolio: FrontierMetrics;
  portfolioAfter: FrontierMetrics | null;
  volBudgetPct: number;
  limitations: LimitationCode[];
  facts: {
    [k: string]: Fact;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GoalFundingResponse".
 */
export interface GoalFundingResponse {
  profileId: ProfileId;
  currency: Currency;
  overallocated: boolean;
  unallocatedValue: number;
  goals: GoalFundingScenario[];
  facts: {
    [k: string]: Fact;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "GoalFundingScenario".
 */
export interface GoalFundingScenario {
  name: string;
  state: "missing_assumptions" | "scenario_funded" | "scenario_shortfall";
  projectedValue: number | null;
  fundingGap: number | null;
  factIds: {
    [k: string]: FactId;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Hazard".
 */
export interface Hazard {
  hazardId: string;
  type: "earthquake" | "wildfire";
  occurredAt: ISODateTime;
  lat: number;
  lon: number;
  magnitude: number | null;
  title: string;
  origin: "usgs" | "firms";
  sourceUrl: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "HazardsResponse".
 */
export interface HazardsResponse {
  items: Hazard[];
  total: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "HealthResponse".
 */
export interface HealthResponse {
  status: "ok";
  time: ISODateTime;
}
/**
 * User-stated objective, never a promise of an achievable return.
 *
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "InvestmentGoal".
 */
export interface InvestmentGoal {
  name: string;
  horizonYears: number;
  priority: number;
  targetAmount?: number | null;
  allocatedValue?: number | null;
  annualContribution?: number | null;
  assumedReturnPct?: number | null;
  deadline?: ISODate | null;
  origin?: "user" | "imported" | "assumption";
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "LegendItem".
 */
export interface LegendItem {
  label: I18NText;
  color: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Meta".
 */
export interface Meta {
  reportingCurrencies?: Currency[];
  contractVersion: string;
  dataVersion: DataVersion;
  dataAsOf: ISODate;
  environment: "local" | "aws";
  languages: Lang[];
  features: {
    bilingual: boolean;
    world_explorer: boolean;
    world_layer_facilities: boolean;
    world_layer_hazards: boolean;
    time_machine: boolean;
    profile_creator: boolean;
    goal_requests: boolean;
    sabotage_demo: boolean;
    research_open_web: boolean;
    guardrails: boolean;
    on_demand_tickers: boolean;
    frontier_chart: boolean;
    [k: string]: boolean;
  };
  models: ModelIds;
  universe: UniverseSummary;
  disclaimer: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ModelIds".
 */
export interface ModelIds {
  strong: string | null;
  fast: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UniverseSummary".
 */
export interface UniverseSummary {
  total: number;
  byTier: {
    [k: string]: number;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "OverviewResponse".
 */
export interface OverviewResponse {
  profileId: ProfileId;
  asOf: ISODate;
  dataVersion: DataVersion;
  window: WindowSpec;
  snapshot: PortfolioSnapshot;
  returns: OverviewReturns;
  risk: OverviewRisk;
  concentration: Concentration;
  correlation: Correlation | null;
  ruleChecks: RuleCheck[];
  verdict: Verdict;
  counts: VerdictCounts;
  facts: {
    [k: string]: Fact;
  };
  limitations: LimitationCode[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "OverviewReturns".
 */
export interface OverviewReturns {
  ytdPct: number | null;
  y1Pct: number | null;
  y3Pct: number | null;
  y5Pct: number | null;
  factIds: {
    [k: string]: FactId;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "OverviewRisk".
 */
export interface OverviewRisk {
  volatilityPct: number | null;
  maxDrawdownPct: number | null;
  worst12mPct: number | null;
  stress2022Pct: number | null;
  riskCategory: RiskLevel;
  factIds: {
    [k: string]: FactId;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ParseRequest".
 */
export interface ParseRequest {
  profileId: ProfileId;
  text: string;
  lang: Lang;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ParsedRequest".
 */
export interface ParsedRequest {
  request: DecisionRequest | null;
  interpretation: I18NText;
  confidence: "high" | "medium" | "low";
  missing: MissingField[];
  warnings: I18NText[];
  refused: Refusal | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Refusal".
 */
export interface Refusal {
  reason: "trade_execution" | "advice_request" | "off_topic";
  message: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "PerformanceResponse".
 */
export interface PerformanceResponse {
  window: WindowSpec;
  currency: Currency;
  series: SeriesPoint[];
  benchmark: Benchmark | null;
  method: MethodId;
  limitations: LimitationCode[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "Profile".
 */
export interface Profile {
  profileId: ProfileId;
  isDefault: boolean;
  archived?: boolean;
  origin: "brief" | "user" | "agent_draft";
  name: string;
  initial: string;
  age: number | null;
  occupation: string | null;
  riskLevel: RiskLevel;
  horizonYears: HorizonYears1;
  objective: Objective;
  objectiveText: I18NText;
  experience: Experience;
  reportingCurrency: Currency;
  preferences: Preferences1;
  blurb: I18NText;
  personaTest: I18NText | null;
  investorContext?: InvestorContext | null;
  accounts?: PortfolioAccount[];
  activeAccountId?: string | null;
  portfolio: Portfolio;
  rules: PolicyRule[];
  version: number;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ProfilesResponse".
 */
export interface ProfilesResponse {
  items: Profile[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "QueuedRunResponse".
 */
export interface QueuedRunResponse {
  runId: RunId;
  status: "queued";
  pollAfterMs: 1000;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RebalanceRequest".
 */
export interface RebalanceRequest {
  profileId: ProfileId;
  profileVersion: number;
  /**
   * @minItems 1
   * @maxItems 40
   */
  positions: Position[];
  window?: WindowSpec | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RebalanceResponse".
 */
export interface RebalanceResponse {
  profileId: ProfileId;
  profileVersion: number;
  currency: Currency;
  totalValue: number;
  asOf: ISODate;
  dataVersion: DataVersion;
  window: WindowSpec;
  changes: AllocationChange[];
  portfolioBefore: PortfolioSnapshot;
  portfolioAfter: PortfolioSnapshot;
  verdictBefore: Verdict;
  verdictAfter: Verdict;
  countsBefore: VerdictCounts;
  countsAfter: VerdictCounts;
  ruleChecksBefore: RuleCheck[];
  ruleChecksAfter: RuleCheck[];
  facts: {
    [k: string]: Fact;
  };
  assumptions: I18NText[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReplayPreset".
 */
export interface ReplayPreset {
  asOf: ISODate;
  label: I18NText;
  why: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "ReplayPresetsResponse".
 */
export interface ReplayPresetsResponse {
  earliestAsOf: ISODate;
  latestAsOf: ISODate;
  presets: ReplayPreset[];
  notices: LimitationCode[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RevealOutcome".
 */
export interface RevealOutcome {
  scenarioId: ScenarioId;
  label: I18NText;
  returnPct: number;
  maxDrawdownPct: number;
  series: SeriesPoint[];
  factIds: FactId[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RevealRequest".
 */
export interface RevealRequest {
  until?: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RevealResult".
 */
export interface RevealResult {
  asOf: ISODate;
  until: ISODate;
  outcomes: RevealOutcome[];
  facts: {
    [k: string]: Fact;
  };
  statement: I18NText;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RiskDiagnosticsResponse".
 */
export interface RiskDiagnosticsResponse {
  profileId: ProfileId;
  currency: Currency;
  dataVersion: DataVersion;
  window: WindowSpec;
  metrics: {
    [k: string]: AssetMeasurement;
  };
  contributions: {
    [k: string]: AssetMeasurement;
  };
  facts: {
    [k: string]: Fact;
  };
}
export interface RulePatchRequest2 {
  threshold?: number;
  enabled?: boolean;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RulePatchResponse".
 */
export interface RulePatchResponse {
  rule: PolicyRule;
  profileVersion: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunSummary".
 */
export interface RunSummary {
  runId: RunId;
  kind: RunKind;
  status: RunStatus;
  profileId: ProfileId | null;
  createdAt: ISODateTime;
  title: I18NText;
  verdict: Verdict | null;
  durationMs: number | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "RunsResponse".
 */
export interface RunsResponse {
  items: RunSummary[];
  nextCursor: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SabotageRequest".
 */
export interface SabotageRequest {
  mode?: "invented_number" | "false_comparison" | "unsupported_interpretation";
  lang: Lang;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "SelectAccountRequest".
 */
export interface SelectAccountRequest {
  version: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UpdatePortfolioRequest".
 */
export interface UpdatePortfolioRequest {
  totalValue: number;
  positions: Position[];
  version: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "UpdateProfileRequest".
 */
export interface UpdateProfileRequest {
  name: string;
  age: number | null;
  riskLevel: RiskLevel;
  horizonYears: HorizonYears1;
  objective: Objective;
  experience: Experience;
  reportingCurrency: Currency;
  preferences: Preferences1;
  portfolio: InitialPortfolio | null;
  rules: PolicyRule[] | null;
  fromDraftRunId: RunId | null;
  investorContext?: InvestorContext | null;
  version: number;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldCountryResponse".
 */
export interface WorldCountryResponse {
  countryIso3: string;
  name: I18NText;
  exposure: CountryExposure | null;
  events: WorldEvent[];
  macro: Fact[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldEventItem".
 */
export interface WorldEventItem {
  eventId: EventId;
  title: string;
  category: EventCategory;
  occurredAt: ISODate;
  publishedAt: ISODateTime | null;
  location: EventLocation;
  origin: "gdelt" | "official" | "curated" | "usgs" | "firms" | "live" | "eonet";
  /**
   * @minItems 1
   */
  sources: [EventSource, ...EventSource[]];
  sourceCount: number;
  importance: number;
  relatedTickers: Ticker[];
  relatedThemes: ThemeTag[];
  relatedCountries: string[];
  datasetId: DatasetId;
  dataVersion: DataVersion;
  portfolioRelevant?: boolean;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldEventResponse".
 */
export interface WorldEventResponse {
  event: WorldEvent;
  related: WorldEvent[];
  exposures: HoldingExposure[];
  geographicRelationships?: WorldGeographicRelationship[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldGeographicRelationship".
 */
export interface WorldGeographicRelationship {
  relationshipId: string;
  relation: "EVENT_OCCURRED_AT" | "FACILITY_LOCATED_IN";
  subjectId: string;
  objectId: string;
  evidenceClass: "direct" | "derived" | "candidate" | "model_inferred";
  sourceId: string;
  sourceUrl: string;
  normalizedRecordSha256: string;
  retrievedAt: ISODateTime;
  limitations: string[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldEventsResponse".
 */
export interface WorldEventsResponse {
  items: WorldEventItem[];
  nextCursor: string | null;
  total: number;
  coverage: Period;
  dataVersion: DataVersion;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldExposureResponse".
 */
export interface WorldExposureResponse {
  items: CountryExposure[];
  basisNote: I18NText;
  limitations: LimitationCode[];
  facts: {
    [k: string]: Fact;
  };
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldLayer".
 */
export interface WorldLayer {
  layerId: "events" | "exposure" | "facilities" | "hazards" | "airports";
  title: I18NText;
  tier: "P1" | "P2";
  available: boolean;
  datasetIds: DatasetId[];
  legend: LegendItem[];
  count: number | null;
  coverage: Period | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldLayersResponse".
 */
export interface WorldLayersResponse {
  items: WorldLayer[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldModeStatus".
 */
export interface WorldModeStatus {
  mode: string;
  available: boolean;
  count: number;
  reason: string | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldObservation".
 */
export interface WorldObservation {
  id: string;
  mode: "news" | "macro" | "trade" | "energy" | "hazards" | "conflicts" | "aviation" | "environment" | "infrastructure";
  title: string;
  summary: string;
  occurredAt: ISODateTime;
  timeBasis: "source_observation" | "event_date" | "capture_only";
  publishedAt: ISODateTime | null;
  retrievedAt: ISODateTime;
  location: WorldObservationLocation | null;
  source: WorldObservationSource;
  datasetId: string;
  limitations: string[];
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldObservationLocation".
 */
export interface WorldObservationLocation {
  lat: number;
  lon: number;
  countryIso3: string | null;
  precision: "point" | "city" | "country" | "polygon_anchor";
  geometry?: {
    [k: string]: unknown;
  } | null;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldObservationSource".
 */
export interface WorldObservationSource {
  name: string;
  url: string;
}
/**
 * This interface was referenced by `AplombContracts`'s JSON-Schema
 * via the `definition` "WorldObservationsResponse".
 */
export interface WorldObservationsResponse {
  items: WorldObservation[];
  total: number;
  nextCursor: string | null;
  dataVersion: string | null;
  capturedAt: ISODateTime | null;
  modes: WorldModeStatus[];
}

export type I18nText = AplombContracts["I18nText"];
