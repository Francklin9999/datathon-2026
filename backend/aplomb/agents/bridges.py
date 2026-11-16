"""Narrow, conservative port for a deterministic candidate provider.

Providers are injected by composition after integration. Merely naming a company or geographic
location does not establish a listed-security relationship or a financial impact.
"""
from dataclasses import dataclass
from typing import Literal, Protocol

CANDIDATE_TOPICS = frozenset({"risk", "concentration", "plan", "fixed_income", "objective"})


@dataclass(frozen=True)
class CandidateFinding:
    """A deterministic finding from Agent 1's candidate service.

    ``tickers`` must be held in the session portfolio; ``objective`` must name one of the
    profile's own objectives exactly. Neither may introduce prose, a new figure or a new policy.
    """

    topic: Literal["risk", "concentration", "plan", "fixed_income", "objective"]
    priority: int
    fact_ids: tuple[str, ...]
    tickers: tuple[str, ...] = ()
    objective: str | None = None


class CandidateProvider(Protocol):
    def __call__(self, profile, outcome, ledger) -> list[CandidateFinding]: ...


def candidate_findings(provider: CandidateProvider | None, profile, outcome, ledger) -> list[CandidateFinding]:
    """Validated provider findings; any invalid finding rejects the whole batch (fail closed)."""
    if provider is None:
        return []
    facts = ledger.export().facts
    findings = provider(profile, outcome, ledger)
    if len(findings) > 12:
        raise ValueError("Candidate provider exceeded finding budget")
    held = {p.ticker for p in profile.portfolio.positions} if profile is not None else set()
    objectives = ({g.name for g in profile.investor_context.objectives}
                  if profile is not None and profile.investor_context else set())
    for finding in findings:
        if not isinstance(finding, CandidateFinding) or finding.topic not in CANDIDATE_TOPICS:
            raise ValueError("Unsupported candidate finding")
        if type(finding.priority) is not int or not 0 <= finding.priority <= 100 or not finding.fact_ids:
            raise ValueError("Candidate requires bounded priority and actual facts")
        if any(fid not in facts or facts[fid].verification.status != "verified" for fid in finding.fact_ids):
            raise ValueError("Candidate references missing, foreign or unverified facts")
        if len(finding.tickers) > 10 or any(t not in held for t in finding.tickers):
            raise ValueError("Candidate names a holding outside the session portfolio")
        if finding.objective is not None and finding.objective not in objectives:
            raise ValueError("Candidate names an objective absent from the profile")
        if (finding.topic == "objective") != (finding.objective is not None):
            raise ValueError("Objective findings require exactly one profile objective")
    return list(findings)
