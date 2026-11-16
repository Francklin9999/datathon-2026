"""Deterministic strategic focus candidates for a separately audited writer.

Candidate identifiers are local to this evaluation. Fact IDs refer only to the
returned ledger. A claim ID is never invented: the orchestration/auditor owns
claim creation and must remap fact references into its canonical run ledger.
"""
from __future__ import annotations

from dataclasses import dataclass

from aplomb.profiles.goals import assess_goals
from aplomb.quant import LocalLedger, QuantEngine
from aplomb.rules.engine import RuleEngine, RuleInputs


@dataclass(frozen=True)
class FocusCandidate:
    candidate_id: str
    kind: str
    severity: str
    label: str
    fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    affected_holdings: tuple[str, ...]
    investigation: str
    navigation_target: str
    missing_inputs: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()

    def to_wire(self):
        return {'candidateId': self.candidate_id, 'kind': self.kind, 'severity': self.severity,
                'label': self.label, 'factIds': list(self.fact_ids), 'evidenceIds': list(self.evidence_ids),
                'affectedHoldings': list(self.affected_holdings), 'investigation': self.investigation,
                'navigationTarget': self.navigation_target, 'missingInputs': list(self.missing_inputs),
                'claimIds': list(self.claim_ids)}


def strategic_brief(profile, snapshot, now: str, limit: int = 3) -> dict:
    """Evaluate the actual portfolio, rules and explicitly entered goal assumptions.

    The response contains the local fact ledger needed to inspect every quantitative
    reference. Ranking: policy conflict, goal shortfall, policy tension, and missing
    evidence or goal inputs. Ties are deterministic and goal ties use stated priority.
    A nominal goal scenario isn't an investment forecast or a feasibility guarantee.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 3:
        raise ValueError('limit must be between zero and three')
    ledger = LocalLedger()
    gate = snapshot.gate(snapshot.data_as_of, 'current')
    engine = QuantEngine(gate, ledger, currency=profile.reporting_currency,
                         subject_id=profile.profile_id, created_at=now, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())
    weights = {p.ticker: p.weight_pct / 100 for p in profile.portfolio.positions if p.weight_pct > 0}
    view = engine.view(weights, 'strategic-focus', profile.portfolio.total_value)
    rule_engine = RuleEngine(ledger, engine.ctx)
    checks = rule_engine.check_rules(profile.rules, RuleInputs(view, profile.profile_id))
    ranked = []
    ranks = {'conflict': 0, 'tension': 2, 'nee': 3}
    for check, status_fact in zip(checks, rule_engine.last_status_facts, strict=True):
        if check.status not in ranks:
            continue
        holdings = (check.worst.id,) if check.worst and check.worst.type == 'asset' else ()
        facts = tuple(dict.fromkeys(x for x in (status_fact, check.value_fact_id, check.threshold_fact_id) if x))
        candidate = FocusCandidate('policy:' + check.rule_id, 'policy', check.status, check.detail.en,
                                   facts, tuple(check.evidence_ids), holdings,
                                   'Inspect the rule, its measured value and missing evidence.', '/risk-intelligence/')
        ranked.append(((ranks[check.status], 0, candidate.candidate_id), candidate))
    goals = assess_goals(profile, snapshot.data_version, now, snapshot.data_as_of)
    remap = {}
    for original, fact in goals.facts.items():
        body = fact.to_wire()
        body.pop('id', None)
        body['inputs'] = [remap[key] for key in fact.inputs]
        remap[original] = ledger.add_fact(body)
    objectives = profile.investor_context.objectives if profile.investor_context else []
    for index, (goal, outcome) in enumerate(zip(objectives, goals.goals, strict=True)):
        missing = tuple(name for name, value in (
            ('targetAmount', goal.target_amount), ('allocatedValue', goal.allocated_value),
            ('annualContribution', goal.annual_contribution), ('assumedReturnPct', goal.assumed_return_pct),
        ) if value is None)
        if goals.overallocated:
            missing += ('nonOverlappingGoalAllocations',)
        facts = tuple(remap[x] for x in outcome.fact_ids.values())
        if outcome.state == 'scenario_shortfall':
            candidate = FocusCandidate(f'goal:{index}', 'goal', 'scenario_shortfall',
                                       f'{goal.name}: nominal scenario falls short of its target.', facts, (), (),
                                       'Review the stated allocation, contribution, return assumption and deadline.',
                                       '/profiles')
            ranked.append(((1, goal.priority, candidate.candidate_id), candidate))
        elif outcome.state == 'missing_assumptions':
            if not missing:
                missing = ('validFiniteScenario',)
            candidate = FocusCandidate(f'goal:{index}', 'goal', 'missing_assumptions',
                                       f'{goal.name}: goal scenario needs additional inputs.', facts, (), (),
                                       'Provide the missing inputs to calculate a nominal scenario.', '/profiles', missing)
            ranked.append(((3, goal.priority, candidate.candidate_id), candidate))
    ranked.sort(key=lambda item: item[0])
    return {'profileId': profile.profile_id, 'profileVersion': profile.version,
            'asOf': snapshot.data_as_of, 'dataVersion': snapshot.data_version,
            'candidates': [candidate.to_wire() for _, candidate in ranked[:limit]], 'facts': ledger.wire(),
            # The fact IDs above are local to this response: a run that cites them must remap them into
            # its own ledger first (as the goal facts are remapped into this one). A code note, not a
            # user-facing limitation (QA 4.5b).
            'limitations': ['Goal figures are nominal scenarios from user assumptions, not forecasts.',
                            'No model, independent review or recommendation has run.']}
