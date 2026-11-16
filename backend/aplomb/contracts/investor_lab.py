"""Investor Lab: explicit circumstances, masked observations and confirmed changes."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ISODateTime, Number, Percent, ProfileId, String, Ticker, WireModel

LabRisk = Literal["low", "low_moderate", "moderate", "moderate_high", "high"]
LabAction = Literal["hold", "buy", "sell", "rebalance"]
LabReason = Literal[
    "cash_need", "company_evidence", "portfolio_balance", "loss_discomfort", "long_term", "other"
]
LabText = Annotated[String, Field(min_length=1, max_length=2000)]


class LabHolding(WireModel):
    ticker: Ticker
    weight_pct: Percent


class LabSituation(WireModel):
    name: Annotated[String, Field(min_length=1, max_length=40)]
    objective: Literal["preserve", "balanced", "growth"]
    horizon_years: Annotated[Number, Field(gt=0, le=100)]
    cash_need_pct: Percent
    cash_need_months: Annotated[int, Field(ge=1, le=120)] | None = None
    risk_capacity: LabRisk
    risk_willingness: LabRisk
    experience: Literal["beginner", "intermediate", "advanced"]
    interest: Annotated[String, Field(min_length=1, max_length=120)]
    reporting_currency: Annotated[String, Field(pattern=r"^[A-Z]{3}$")]
    capital: Annotated[Number, Field(gt=0)] = 100000
    holdings: list[LabHolding] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def valid_situation(self):
        if not self.name.strip() or not self.interest.strip():
            raise ValueError("Name and interest cannot be blank")
        if self.cash_need_pct > 0 and self.cash_need_months is None:
            raise ValueError("State when the cash will be needed")
        if self.holdings:
            if abs(sum(p.weight_pct for p in self.holdings) - 100) > 0.01:
                raise ValueError("Holding weights must total 100 percent")
            if len({p.ticker for p in self.holdings}) != len(self.holdings):
                raise ValueError("Holding tickers must be unique")
        return self


class LabStartRequest(WireModel):
    mode: Literal["new", "quick", "full"]
    profile_id: ProfileId | None = None
    profile_version: Annotated[int, Field(ge=1)] | None = None
    situation: LabSituation


class LabDecision(WireModel):
    action: LabAction
    target_pct: Percent
    reason: LabReason
    explanation: Annotated[String, Field(min_length=10, max_length=2000)]

    @model_validator(mode="after")
    def explained(self):
        if len(self.explanation.strip()) < 10:
            raise ValueError("Explain the choice in at least ten characters")
        return self


class LabInitialRequest(WireModel):
    version: Annotated[int, Field(ge=1)]
    decision: LabDecision


class LabConsultRequest(WireModel):
    version: Annotated[int, Field(ge=1)]
    evidence_id: String
    why: Annotated[String, Field(min_length=5, max_length=1000)]


class LabFinalRequest(LabInitialRequest):
    revisit_trigger: Annotated[String, Field(min_length=10, max_length=2000)]


class LabContrastRequest(LabInitialRequest):
    pass


class LabEvidence(WireModel):
    evidence_id: String
    category: Literal["exposures", "company", "macro", "disclosure"]
    title: String
    available: bool
    summary: String
    relative_date: String
    source_url: String | None = None


class LabConsultation(WireModel):
    evidence_id: String
    title: String
    why: String
    consulted_at: ISODateTime


class LabObservation(WireModel):
    checkpoint: int
    title: String
    starting_pct: Percent
    initial: LabDecision
    consultations: list[LabConsultation]
    final: LabDecision | None = None
    revisit_trigger: String = ""
    contrast: LabDecision | None = None
    contrast_prompt: String = ""
    interpretation: String = ""


class LabPoint(WireModel):
    step: int
    value: Number


class LabSleeve(WireModel):
    label: String
    weight_pct: Percent


class LabSetting(WireModel):
    key: String
    label: String
    current: String | None
    proposed: String
    value: Number | None = None
    minimum: Number | None = None
    maximum: Number | None = None
    basis: list[String]
    explanation: String
    required: bool = False


class LabAcceptedSetting(WireModel):
    key: String
    value: Number | None = None


class LabConfirmRequest(WireModel):
    version: Annotated[int, Field(ge=1)]
    accepted: list[LabAcceptedSetting] = Field(max_length=100)
    principle: Annotated[String, Field(min_length=10, max_length=2000)]
    revisit_trigger: Annotated[String, Field(min_length=10, max_length=2000)]
    explanation: Annotated[String, Field(min_length=10, max_length=2000)]


class LabSettingChange(WireModel):
    key: String
    label: String
    before: String | None
    after: String
    basis: list[String]


class LabReviewRecord(WireModel):
    lab_id: String
    confirmed_at: ISODateTime
    mode: Literal["new", "quick", "full"]
    explanation: String
    situation: LabSituation
    observations: list[LabObservation]
    changes: list[LabSettingChange]


class InvestmentPlaybook(WireModel):
    principle: String
    revisit_trigger: String
    interest: String
    updated_at: ISODateTime
    reviews: list[LabReviewRecord] = Field(default_factory=list, max_length=30)


class LabPlaybookRequest(WireModel):
    version: Annotated[int, Field(ge=1)]
    principle: Annotated[String, Field(min_length=10, max_length=2000)]
    revisit_trigger: Annotated[String, Field(min_length=10, max_length=2000)]
    explanation: Annotated[String, Field(min_length=10, max_length=2000)]


class LabSession(WireModel):
    lab_id: String
    version: int
    mode: Literal["new", "quick", "full"]
    stage: Literal["initial", "research", "contrast", "review", "saved"]
    profile_id: ProfileId | None
    saved_profile_id: ProfileId | None = None
    situation: LabSituation
    checkpoint: int
    checkpoint_count: int
    title: String
    prompt: String
    chart: list[LabPoint]
    sleeves: list[LabSleeve]
    focus_pct: Percent
    evidence: list[LabEvidence]
    observations: list[LabObservation]
    settings: list[LabSetting]
    proposed_principle: String
    proposed_revisit_trigger: String
    limitations: list[String]
    reveal: list[String]


class LabSessionsResponse(WireModel):
    items: list[LabSession]
