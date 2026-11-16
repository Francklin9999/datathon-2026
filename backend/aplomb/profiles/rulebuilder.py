"""Build ``PolicyRule`` wire dicts from a rule ID, a threshold and its provenance."""

from __future__ import annotations

from aplomb.contracts.models import PolicyRule
from aplomb.rules.definitions import rule_def

RISK_FR = {"low": "faible", "low_moderate": "faible à modéré", "moderate": "modéré", "moderate_high": "modéré à élevé", "high": "élevé"}
RISK_EN = {"low": "low", "low_moderate": "low-to-moderate", "moderate": "moderate", "moderate_high": "moderate-to-high", "high": "high"}


def make_rule(rule_id: str, code: str, *, threshold: float | None, origin: str, rationale: dict,
              derivation: dict | None, updated_at: str, enabled: bool = True) -> dict:
    d = rule_def(rule_id)
    if d.type in ("cap", "floor", "limit") and threshold is None:
        raise ValueError(f"{rule_id} needs a threshold")
    if d.type == "exclude":
        threshold = 0.0
    if d.type in ("evidence", "flag", "sim"):
        threshold = None
    rule = {
        "ruleId": rule_id, "code": code, "type": d.type, "enabled": enabled, "label": dict(d.label),
        "rationale": rationale, "metric": d.metric if d.metric in _METRICS else None,
        "target": {"dimension": d.dimension, "key": d.target_key}, "comparator": d.comparator,
        "threshold": float(threshold) if threshold is not None else None, "unit": d.unit,
        "editable": d.editable, "bounds": dict(d.bounds) if d.bounds else None, "origin": origin,
        "isAssumption": d.type != "sim", "derivation": derivation, "countsInVerdict": d.counts,
        "updatedAt": updated_at,
    }
    PolicyRule.model_validate(rule)
    return rule


_METRICS = {
    "weight.country", "weight.currency", "weight.position.max_single", "weight.sector.max", "weight.growth_assets", "weight.fixed_income", "weight.diversifiers",
    "weight.asset_group", "weight.asset_class", "weight.sector", "weight.position", "weight.theme", "vol.annualized",
    "stress.replay_2022", "drawdown.max", "attention.pageviews_ratio", "stress.rate_cycle",
}


def renumber(rules: list[dict]) -> list[dict]:
    """R codes follow display order (schemas.md §1 RuleCode)."""
    return [{**r, "code": f"R{i}"} for i, r in enumerate(rules, start=1)]
