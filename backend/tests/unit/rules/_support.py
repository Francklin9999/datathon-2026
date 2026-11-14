"""Helpers shared by rule/profile/optimizer tests."""

from __future__ import annotations

from aplomb.contracts.models import PolicyRule
from aplomb.profiles.defaults import load_defaults
from aplomb.quant import LocalLedger, QuantEngine, apply_move
from aplomb.rules.engine import RuleEngine, RuleInputs, verdict_of

from tests.unit.datastore._support import starter_snapshot

NOW = "2026-11-14T23:00:00Z"
PROFILES = {p.profile_id: p for p in load_defaults()}


def weights_of(profile) -> dict[str, float]:
    return {p.ticker: p.weight_pct / 100 for p in profile.portfolio.positions}


def evaluate(pid: str, move: tuple | None = None, rules: list[PolicyRule] | None = None, evidence=(), as_of="2026-11-12",
             mode="current"):
    profile = PROFILES[pid]
    ledger = LocalLedger()
    eng = QuantEngine(starter_snapshot().gate(as_of, mode), ledger, currency="CAD", subject_id=pid, created_at=NOW)
    w, variant, moved = weights_of(profile), "before", ()
    if move:
        w, variant, moved = apply_move(w, *move).weights, "after", (move[0],)
    view = eng.view(w, variant, profile.portfolio.total_value)
    checks = RuleEngine(ledger, eng.ctx).check_rules(rules or profile.rules, RuleInputs(view, pid, moved, tuple(evidence)))
    verdict, counts = verdict_of(checks)
    return verdict, counts, {c.rule_id: c for c in checks}, ledger
