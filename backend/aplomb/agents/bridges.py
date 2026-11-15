"""Narrow, conservative ports for deterministic candidate and sourced event providers.

Providers are injected by composition after integration. Merely naming a company or geographic
location does not establish a listed-security relationship or a financial impact.
"""
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from aplomb.intelligence.entities import Relationship

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


def candidate_priorities(provider: CandidateProvider | None, profile, outcome, ledger) -> dict[str, int]:
    result = {}
    for finding in candidate_findings(provider, profile, outcome, ledger):
        result[finding.topic] = max(result.get(finding.topic, 0), finding.priority)
    return result


@dataclass(frozen=True)
class EventRelationship:
    event_reference: Relationship
    security_issuer: Relationship
    evidence_ids: tuple[str, ...]


class EventRelationshipProvider(Protocol):
    def __call__(self, event, profile, as_of: date, ledger) -> list[EventRelationship]: ...


def event_hypotheses(provider: EventRelationshipProvider | None, event, profile, as_of: date, ledger) -> list[dict]:
    """Accept only direct, same-issuer, dated relationships with same-run verified evidence.

    A hypothesis is an investigation lead, not a measured exposure or causal impact. Listing IDs
    must be reconciled to the session portfolio by the integrating provider before display.
    """
    if provider is None:
        return []
    result = []
    relationships = provider(event, profile, as_of, ledger)
    available = ledger.export().evidence
    if len(relationships) > 20:
        raise ValueError("Event relationship provider exceeded result budget")
    for item in relationships:
        if not isinstance(item, EventRelationship):
            raise ValueError("Invalid event relationship")
        event_edge, issuer_edge = item.event_reference, item.security_issuer
        if (event_edge.relation != "EVENT_REFERENCES_ENTITY" or event_edge.subject_id != event.event_id
                or issuer_edge.relation != "SECURITY_ISSUED_BY" or event_edge.object_id != issuer_edge.object_id
                or event_edge.evidence_class != "direct" or issuer_edge.evidence_class != "direct"):
            raise ValueError("Event hypothesis requires a directly documented event and issuer identity")
        for edge in (event_edge, issuer_edge):
            if (edge.valid_from > as_of or (edge.valid_to and edge.valid_to < as_of)
                    or not edge.evidence.visible(as_of, historical=True)):
                raise ValueError("Event relationship unavailable at cutoff")
        if not item.evidence_ids or any(eid not in available or available[eid].verification.status != "verified"
                                        for eid in item.evidence_ids):
            raise ValueError("Event relationship requires same-run verified evidence")
        sources = {available[eid].url for eid in item.evidence_ids}
        if not {event_edge.evidence.url, issuer_edge.evidence.url} <= sources:
            raise ValueError("Run evidence does not support both documented relationships")
        if any(date.fromisoformat(available[eid].retrieved_at[:10]) > as_of for eid in item.evidence_ids):
            raise ValueError("Run evidence was retrieved after cutoff")
        result.append({"security_id": issuer_edge.subject_id, "issuer_id": issuer_edge.object_id,
                       "evidence_ids": list(item.evidence_ids), "impact": "not_established",
                       "interpretation": "Documented relationship; financial impact is not established."})
    return result
