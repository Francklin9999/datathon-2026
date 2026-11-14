"""Rule engine (track T06, rules SPEC). Pure comparison code: values come from quant through
``PortfolioView.measure``; this module never computes market figures, calls a model or does I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aplomb.contracts.models import Evidence, PolicyRule, RuleCheck, VerdictCounts
from aplomb.quant.engine import Measurement, PortfolioView
from aplomb.quant.facts import FactContext, FactSink, display, fact_key, make_fact

from .definitions import SECTOR_FR, rule_def
from .templates import WHAT, family, render

TENSION_BAND = 0.10  # A-09
TOL = 1e-9
STATUSES = ("pass", "tension", "conflict", "nee", "info")


@dataclass(frozen=True)
class RuleInputs:
    view: PortfolioView                    # snapshot weights + metrics through quant
    profile_id: str
    moved_tickers: tuple[str, ...] = ()    # assets added or increased; empty for a baseline check
    evidence: tuple[Evidence, ...] = ()    # controversy evidence produced by the researcher
    attention: dict | None = None          # AttentionSignal wire dict, when available
    attention_ticker: str | None = None


@dataclass
class RuleOutcome:
    checks: list[RuleCheck]
    fact_ids: list[str] = field(default_factory=list)


def compare(rule_type: str, value: float, threshold: float) -> str:
    """``M_RULE_COMPARE`` (rules SPEC §3, A-09)."""
    if rule_type in ("cap", "limit"):
        if value > threshold + TOL:
            return "conflict"
        return "tension" if value > (1 - TENSION_BAND) * threshold + TOL else "pass"
    if rule_type == "floor":
        if value < threshold - TOL:
            return "conflict"
        return "tension" if value < (1 + TENSION_BAND) * threshold - TOL else "pass"
    if rule_type == "exclude":
        return "conflict" if value > TOL else "pass"
    raise ValueError(rule_type)


def _what(rule: PolicyRule) -> dict:
    if rule.rule_id in WHAT:
        return WHAT[rule.rule_id]
    d = rule_def(rule.rule_id)
    if rule.rule_id.startswith("exclude.sector."):
        return {"en": f"{d.target_key} sector", "fr": f"secteur {SECTOR_FR.get(d.target_key, d.target_key)}"}
    if rule.rule_id.startswith("exclude.asset_class."):
        return {"en": f"asset class {d.target_key}", "fr": f"classe d'actifs {d.target_key}"}
    if rule.rule_id.startswith("cap.theme."):
        return {"en": f"Positions tagged {d.target_key}", "fr": f"Les positions étiquetées {d.target_key}"}
    return {"en": rule.label.en, "fr": rule.label.fr}


def _plain(text: str) -> dict:
    return {"en": text, "fr": text}


class RuleEngine:
    def __init__(self, ledger: FactSink, ctx: FactContext) -> None:
        self.ledger = ledger
        self.ctx = ctx
        self.last_status_facts: list[str] = []  # rule_check fact IDs produced, in order

    def check_rules(self, rules: list[PolicyRule], inputs: RuleInputs) -> list[RuleCheck]:
        return [self._check(rule, inputs) for rule in rules if rule.enabled]

    # Facts ------------------------------------------------------------------------------------

    def _threshold_fact(self, rule: PolicyRule, profile_id: str) -> str | None:
        if rule.threshold is None:
            return None
        derived = rule.origin == "derived" and rule.derivation is not None
        params = {"origin": rule.origin}
        if derived:
            params.update({k: v for k, v in rule.derivation.inputs.items()})
        fact = make_fact(
            self.ctx, key=fact_key("threshold.rule", "rule", rule.rule_id, f"profile:{profile_id}", "na"),
            kind="assumption", metric="threshold.rule",
            label={"en": f"Threshold of rule {rule.code} ({rule.rule_id}), {profile_id}",
                   "fr": f"Seuil de la règle {rule.code} ({rule.rule_id}), {profile_id}"},
            value=float(rule.threshold), unit=rule.unit, currency=None,
            subject={"type": "rule", "id": rule.rule_id, "variant": "na"},
            method_id=rule.derivation.method_id if derived else ("M_USER_INPUT" if rule.origin == "user" else "M_PROFILE_ASSUMPTION"),
            created_by="profile", params=params, limitations=["LIM_THRESHOLDS_ASSUMED"],
            checks=[{"code": "rule_definition", "ok": True, "detail": f"Threshold read from the profile rule {rule.rule_id}."}],
        )
        return self.ledger.add_fact(fact)

    def _status_fact(self, rule: PolicyRule, variant: str, status: str, inputs: list[str]) -> str:
        fact = make_fact(
            self.ctx, key=fact_key("count.rules", "rule", rule.rule_id, f"{variant}:status:{status}", "na"),
            kind="rule_check", metric="count.rules",
            label={"en": f"Rule {rule.code} ({rule.rule_id}) status: {status}", "fr": f"Règle {rule.code} ({rule.rule_id}), statut : {status}"},
            value=1, unit="count", currency=None, subject={"type": "rule", "id": rule.rule_id, "variant": f"{variant}:status:{status}"},
            method_id="M_RULE_COMPARE", created_by="rules", params={"status": status, "tensionBand": TENSION_BAND},
            inputs=[i for i in inputs if i], limitations=["LIM_THRESHOLDS_ASSUMED"],
            checks=[{"code": "comparison", "ok": True, "detail": "Status computed by code from the value and threshold facts."}],
        )
        return self.ledger.add_fact(fact)

    def _loss_fact(self, view: PortfolioView, stress: Measurement) -> tuple[float, str]:
        loss = max(0.0, -stress.value)
        src = self.ledger.get_fact(stress.fact_id)
        fact = make_fact(
            self.ctx, key=fact_key("stress.replay_2022", "portfolio", view.engine.subject_id, f"{view.variant}:loss", "replay_2022"),
            kind="scenario", metric="stress.replay_2022",
            label={"en": f"Loss in a repeat of calendar 2022 (positive), {view.engine.subject_id} ({view.variant})",
                   "fr": f"Perte lors d'une répétition de 2022 (positive), {view.engine.subject_id} ({view.variant})"},
            value=loss, unit="pct", currency=None, subject={"type": "portfolio", "id": view.engine.subject_id, "variant": f"{view.variant}:loss"},
            method_id="M_STRESS_REPLAY", created_by="rules", period=src.period.to_wire() if src.period else None,
            available_at=src.available_at, params={"definition": "max(0, -stress.replay_2022)"}, inputs=[stress.fact_id],
            n_obs=src.n_obs, sources=[s.to_wire() for s in src.sources], limitations=list(src.limitations),
            checks=[{"code": "derived_from_fact", "ok": True, "detail": f"Loss = max(0, -{stress.fact_id})."}],
        )
        return loss, self.ledger.add_fact(fact)

    # One rule ---------------------------------------------------------------------------------

    def _check(self, rule: PolicyRule, inputs: RuleInputs) -> RuleCheck:
        view = inputs.view
        d = rule_def(rule.rule_id)
        fam = family(rule.rule_id, rule.type)
        base = {"ruleId": rule.rule_id, "code": rule.code, "unit": rule.unit, "comparator": rule.comparator,
                "threshold": float(rule.threshold) if rule.threshold is not None else None, "evidenceIds": []}

        if rule.type == "sim":
            fid = self._status_fact(rule, view.variant, "info", [])
            return self._result(base, "info", None, None, None, fid, render(("sim", "info"), {}), None, view, rule)

        if rule.type == "evidence":
            return self._evidence(rule, inputs, base)

        if rule.type == "flag":
            return self._flag(rule, inputs, base)

        m = view.measure(d.metric, d.key)
        threshold_id = self._threshold_fact(rule, inputs.profile_id)
        worst_name = self._worst_name(m.worst)
        if m.value is None:
            reason = m.nee_reason or "short_history"
            fid = self._status_fact(rule, view.variant, "nee", [threshold_id])
            detail = render(("any", f"nee:{reason}"), {"worst": _plain(worst_name or "An asset in the portfolio")})
            return self._result(base, "nee", None, None, threshold_id, fid, detail, reason, view, rule)

        value, value_id = m.value, m.fact_id
        if rule.rule_id == "limit.stress_2022":
            value, value_id = self._loss_fact(view, m)
        threshold = float(rule.threshold)
        status = compare(rule.type, value, threshold)
        fid = self._status_fact(rule, view.variant, status, [value_id, threshold_id])
        values = {"value": self.ledger.get_fact(value_id).display.to_wire() if value_id else display(value, "pct"),
                  "threshold": self.ledger.get_fact(threshold_id).display.to_wire(),
                  "worst": self._worst_text(m.worst), "what": _what(rule)}
        key = (fam, status)
        if rule.type == "exclude" and status == "pass":
            key = ("exclude", "pass")
        detail = render(key, values)
        headroom = None
        if rule.type in ("cap", "limit"):
            headroom = threshold - value
        elif rule.type == "floor":
            headroom = value - threshold
        return self._result(base, status, value, value_id, threshold_id, fid, detail, None, view, rule,
                            worst=m.worst, headroom=headroom)

    def _evidence(self, rule: PolicyRule, inputs: RuleInputs, base: dict) -> RuleCheck:
        view = inputs.view
        scope = _evidence_scope(view, inputs.moved_tickers)
        relevant = [e for e in inputs.evidence if e.subject.type == "asset" and e.subject.id in scope]
        strong = [e for e in relevant if e.verification.status == "verified" and e.tier in (1, 2)]
        label = ", ".join(scope) if scope else "the moved assets"
        if strong:
            status, reason = "tension", None
            detail = render(("evidence", "tension"), {"worst": _plain(", ".join(sorted({e.subject.id for e in strong})))})
            ev_ids = [e.id for e in strong]
        else:
            status = "nee"
            reason = "evidence_unverified" if relevant else "no_evidence_loaded"
            detail = render(("evidence", "nee"), {"worst": _plain(label)})
            ev_ids = []
        fid = self._status_fact(rule, view.variant, status, [])
        base = {**base, "evidenceIds": ev_ids}
        worst = {"type": "asset", "id": scope[0]} if len(scope) == 1 else None
        return self._result(base, status, None, None, None, fid, detail, reason, view, rule, worst=worst)

    def _flag(self, rule: PolicyRule, inputs: RuleInputs, base: dict) -> RuleCheck:
        view = inputs.view
        if rule.rule_id == "flag.rate_cycle":
            m = view.measure("stress.rate_cycle")
            fid = self._status_fact(rule, view.variant, "info", [m.fact_id])
            if m.value is None:
                detail = render(("flag.rate_cycle", "info_missing"), {})
                return self._result(base, "info", None, None, None, fid, detail, None, view, rule)
            detail = render(("flag.rate_cycle", "info"), {"value": self.ledger.get_fact(m.fact_id).display.to_wire()})
            return self._result(base, "info", m.value, m.fact_id, None, fid, detail, None, view, rule)
        if rule.rule_id == "flag.attention":
            ticker = inputs.attention_ticker or (inputs.moved_tickers[0] if inputs.moved_tickers else None)
            sig = inputs.attention
            fid_in = sig.get("factId") if sig else None
            fid = self._status_fact(rule, view.variant, "info", [fid_in] if fid_in else [])
            worst = {"type": "asset", "id": ticker} if ticker else None
            if sig and sig.get("ratio") is not None and fid_in:
                value_display = self.ledger.get_fact(fid_in).display.to_wire()
                detail = render(("flag.attention", "info"), {"worst": _plain(ticker or ""), "value": value_display})
                return self._result(base, "info", float(sig["ratio"]), fid_in, None, fid, detail, None, view, rule, worst=worst)
            detail = render(("flag.attention", "info_missing"), {"worst": _plain(ticker or "the requested asset")})
            return self._result(base, "info", None, None, None, fid, detail, None, view, rule, worst=worst)
        fid = self._status_fact(rule, view.variant, "info", [])
        return self._result(base, "info", None, None, None, fid, render(("sim", "info"), {}), None, view, rule)

    # Helpers ----------------------------------------------------------------------------------

    def _worst_name(self, worst: dict | None) -> str | None:
        return worst["id"] if worst else None

    def _worst_text(self, worst: dict | None) -> dict:
        if not worst:
            return _plain("—")
        if worst["type"] == "sector":
            return {"en": worst["id"], "fr": SECTOR_FR.get(worst["id"], worst["id"])}
        return _plain(worst["id"])

    def _result(self, base: dict, status: str, value, value_id, threshold_id, status_fact_id, detail: dict,
                nee_reason, view, rule, worst: dict | None = None, headroom=None) -> RuleCheck:
        self.last_status_facts.append(status_fact_id)
        return RuleCheck.model_validate({
            **base, "status": status, "value": float(value) if value is not None else None, "headroom": headroom,
            "worst": worst, "valueFactId": value_id, "thresholdFactId": threshold_id, "detail": detail, "neeReason": nee_reason,
        })


def _evidence_scope(view: PortfolioView, moved: tuple[str, ...]) -> list[str]:
    if moved:
        return [t for t in moved if t in view.assets and view.assets[t].is_single_name]
    return [t for t, a in view.assets.items() if a.is_single_name]


def quick_statuses(rules: list[PolicyRule], inputs: RuleInputs) -> dict[str, str]:
    """Statuses only, no facts (optimizer grid scans). Same comparisons as ``check_rules``."""
    view = inputs.view
    out: dict[str, str] = {}
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.type in ("sim", "flag"):
            out[rule.rule_id] = "info"
            continue
        if rule.type == "evidence":
            scope = _evidence_scope(view, inputs.moved_tickers)
            strong = [e for e in inputs.evidence if e.subject.type == "asset" and e.subject.id in scope
                      and e.verification.status == "verified" and e.tier in (1, 2)]
            out[rule.rule_id] = "tension" if strong else "nee"
            continue
        d = rule_def(rule.rule_id)
        m = view.measure(d.metric, d.key)
        if m.value is None:
            out[rule.rule_id] = "nee"
            continue
        value = max(0.0, -m.value) if rule.rule_id == "limit.stress_2022" else m.value
        out[rule.rule_id] = compare(rule.type, value, float(rule.threshold))
    return out


def verdict_of_statuses(statuses) -> str:
    st = set(statuses)
    if "conflict" in st:
        return "conflict"
    if "tension" in st:
        return "tension"
    return "insufficient" if "nee" in st else "compatible"


def verdict_of(checks: list[RuleCheck]) -> tuple[str, VerdictCounts]:
    """rules SPEC §3.2. Counts include every returned status, including ``info``."""
    counts = {s: 0 for s in STATUSES}
    for c in checks:
        counts[c.status] += 1
    if counts["conflict"]:
        verdict = "conflict"
    elif counts["tension"]:
        verdict = "tension"
    elif counts["nee"]:
        verdict = "insufficient"
    else:
        verdict = "compatible"
    return verdict, VerdictCounts.model_validate(counts)


def explain_difference(a: list[RuleCheck], b: list[RuleCheck]) -> list[dict]:
    """Align two profiles' checks by ruleId for the compare view (rules SPEC §6)."""
    ia = {c.rule_id: c for c in a}
    ib = {c.rule_id: c for c in b}
    out = []
    for rid in list(ia) + [r for r in ib if r not in ia]:
        ca, cb = ia.get(rid), ib.get(rid)
        if ca is None or cb is None:
            reason = "rule_only_in_b" if ca is None else "rule_only_in_a"
        elif ca.status == cb.status and ca.threshold == cb.threshold and ca.value == cb.value:
            reason = "same"
        elif ca.threshold != cb.threshold:
            reason = "threshold_differs"
        else:
            reason = "portfolio_differs"
        out.append({
            "ruleId": rid, "reason": reason,
            "statusA": ca.status if ca else None, "statusB": cb.status if cb else None,
            "thresholdA": ca.threshold if ca else None, "thresholdB": cb.threshold if cb else None,
            "valueA": ca.value if ca else None, "valueB": cb.value if cb else None,
        })
    return out
