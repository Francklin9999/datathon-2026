"""Time Machine (track T12): historical eligibility, presets, gate report and isolated reveal.

A replay is the ordinary decision workflow run through a ``historical`` temporal gate. This
module decides which dates are eligible, pins a profile whose derived rules use only
pre-cutoff data, reports what the gate withheld and, separately, reveals what the pinned
scenario mixes did afterwards. The reveal uses its own ledger, makes no model call and never
touches the signed run.

Limits that stay true whatever the date: prices are a retrospectively adjusted 2026 snapshot,
the universe was selected in 2026 and the language model may know later events. The mandatory
notices say so; nothing here claims a leakage-free historical forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable

from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.datastore import Snapshot, UnknownTicker
from aplomb.datastore.constants import CASH_TICKERS
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.quant import metrics as mx

MIN_HISTORY_OBS = 252        # A-24: master price observations on or before the as-of date
MIN_FORWARD_DAYS = 60        # api.md §7.1: master days left after the latest offered date
PRESET_HORIZON = 60          # master days used to pick the hindsight-selected demonstration date
REFERENCE_TICKER = "SPY"
MANDATORY_NOTICES = ("LIM_LLM_KNOWLEDGE", "LIM_SAMPLE_WINDOW", "LIM_SURVIVORSHIP", "LIM_YAHOO_NOT_CERTIFIED")
MACRO_NOTICES = ("LIM_MACRO_REVISED", "LIM_MACRO_LAG_ASSUMED")
UNCHANGED_SCENARIO = "sc_unchanged"
GROWTH_RULES = ("cap.growth_assets", "floor.fixed_income")   # present only when the growth cap is below 100%
DIVERSIFIER_RULE = "floor.diversifiers"                      # takes their place when the growth cap is 100%
REVEAL_STATEMENT = {
    "en": "These outcomes describe what the hypothetical fixed mixes did in this dataset after the information cutoff. "
          "They do not establish that a prediction was made, or that one choice is generally superior.",
    "fr": "Ces résultats décrivent ce que les compositions hypothétiques fixes ont fait dans ce jeu de données après la date "
          "limite d'information. Ils n'établissent ni qu'une prévision a été faite, ni qu'un choix est supérieur en général.",
}


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


def _invalid(message: str, field: str, **details) -> ServiceError:
    return ServiceError("validation_error", message, {"fields": [{"path": field, "problem": message}], **details})


@dataclass(frozen=True)
class EligibleRange:
    """Dates a replay may use, derived from the loaded snapshot's master calendar."""

    earliest: str
    latest: str
    master_dates: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalContext:
    as_of: str
    data_version: str
    reveal_available_until: str
    profile: m.Profile            # derived thresholds recomputed from pre-cutoff data only


def eligible_range(snapshot: Snapshot) -> EligibleRange:
    """Earliest = 252nd master observation; latest = 60 master days before the snapshot end (TM-01)."""
    dates = snapshot.gate(snapshot.data_as_of, "current").master_calendar().dates
    if len(dates) < MIN_HISTORY_OBS + MIN_FORWARD_DAYS + 1:
        raise ServiceError("insufficient_data", "The snapshot is too short for a historical replay",
                           {"masterDays": len(dates), "required": MIN_HISTORY_OBS + MIN_FORWARD_DAYS + 1})
    return EligibleRange(dates[MIN_HISTORY_OBS - 1], dates[-1 - MIN_FORWARD_DAYS], dates)


def _largest_forward_decline(snapshot: Snapshot, rng: EligibleRange) -> tuple[str, float] | None:
    """Eligible master day followed by the largest fall of the reference fund within 60 master days.

    Chosen with hindsight for the demonstration only; it never enters a decision's inputs."""
    frame = snapshot.gate(snapshot.data_as_of, "current").price_frame([REFERENCE_TICKER])
    levels = frame.column(REFERENCE_TICKER)
    index = {d: i for i, d in enumerate(frame.dates)}
    best: tuple[float, str] | None = None
    for day in rng.master_dates:
        if not rng.earliest <= day <= rng.latest:
            continue
        i = index[day]
        window = levels[i:i + PRESET_HORIZON + 1]
        if len(window) < PRESET_HORIZON + 1 or any(v is None for v in window):
            continue
        decline = (1.0 - min(window[1:]) / window[0]) * 100.0
        if best is None or decline > best[0] + 1e-12:
            best = (decline, day)
    return (best[1], best[0]) if best and best[0] > 0 else None


def build_presets(snapshot: Snapshot) -> dict:
    rng = eligible_range(snapshot)
    presets = []
    hindsight = _largest_forward_decline(snapshot, rng)
    if hindsight:
        day, _ = hindsight
        presets.append({"asOf": day, "label": _t(f"{day}: before the largest later fall",
                                                 f"{day} : avant la plus forte baisse ultérieure"),
                        "why": _t(
                            f"Selected with hindsight for demonstration: the eligible day followed by the largest fall of {REFERENCE_TICKER} "
                            f"within the next {PRESET_HORIZON} trading days in this dataset. The selection never enters the decision.",
                            f"Choisie a posteriori pour la démonstration : le jour admissible suivi de la plus forte baisse de {REFERENCE_TICKER} "
                            f"dans les {PRESET_HORIZON} jours de bourse suivants de ce jeu de données. Ce choix n'entre jamais dans la décision.")})
    last_by_year: dict[str, str] = {}
    for day in rng.master_dates:
        if rng.earliest <= day <= rng.latest:
            last_by_year[day[:4]] = day
    final_year = rng.master_dates[-1][:4]
    for year, day in sorted(last_by_year.items()):
        # A year-end preset is the last master day of a completed calendar year.
        nxt = next((d for d in rng.master_dates if d > day), None)
        if year == final_year or nxt is None or nxt[:4] == year:
            continue
        presets.append({"asOf": day, "label": _t(f"{day}: end of {year}", f"{day} : fin de {year}"),
                        "why": _t(f"Last trading day of {year} common to the Canadian and U.S. markets.",
                                  f"Dernier jour de bourse de {year} commun aux marchés canadien et américain.")})
    presets.append({"asOf": rng.earliest, "label": _t(f"{rng.earliest}: earliest supported date",
                                                      f"{rng.earliest} : première date prise en charge"),
                    "why": _t(f"First date with {MIN_HISTORY_OBS} master-calendar price observations behind it (A-24).",
                              f"Première date précédée de {MIN_HISTORY_OBS} observations de prix du calendrier maître (A-24).")})
    seen: set[str] = set()
    unique = [p for p in presets if not (p["asOf"] in seen or seen.add(p["asOf"]))]
    return {"earliestAsOf": rng.earliest, "latestAsOf": rng.latest, "presets": unique,
            "notices": list(MANDATORY_NOTICES) + ["LIM_MACRO_REVISED"]}


def _underivable(as_of: str, what: str, detail: str | None = None) -> ServiceError:
    message = f"{what} cannot be derived from data visible at {as_of}"
    return ServiceError("insufficient_data", f"{message}: {detail}" if detail else message, {"asOf": as_of})


def rederive_at(profile: m.Profile, snapshot: Snapshot, as_of: str, created_at: str) -> m.Profile:
    """The profile with the derived rule set computed from rows visible at ``as_of`` (TM-06).

    Thresholds and the data-conditional rules both come from the derivation at that date: a growth
    cap and a fixed-income floor exist when the reference mix needs them then, and the
    diversification floor that takes their place otherwise is dropped or added with them. Rules
    the user edited and every other preference or system rule are kept as stored."""
    from aplomb.optimizer.derive import derive_thresholds
    from aplomb.profiles.rulebuilder import renumber

    if not any(r.origin == "derived" for r in profile.rules):
        return profile
    gate = snapshot.gate(as_of, "historical")
    engine = QuantEngine(gate, LocalLedger(), currency=profile.reporting_currency, subject_id=profile.profile_id,
                         created_at=created_at, custom_themes=profile.investor_context.custom_theme_definitions if profile.investor_context else ())
    try:
        derivation = derive_thresholds(profile, engine, created_at=created_at)
    except Unavailable as exc:
        raise _underivable(as_of, "Thresholds", exc.detail) from exc
    for issue in derivation.issues:
        if issue["code"] == "reference_mix_unavailable":
            raise _underivable(as_of, "The growth cap", issue["detail"])
    growth = derivation.values["growthCapPct"]   # None: no reference mix fits the budget at this date
    fresh = {r["ruleId"]: r for r in derivation.rules}

    def stamped(rule: dict) -> dict:
        if rule["origin"] != "derived":
            return rule
        return {**rule, "derivation": {**rule["derivation"], "inputs": {**rule["derivation"]["inputs"], "asOf": as_of}}}

    stored = profile.to_wire()["rules"]
    rules, wanted = [], set(GROWTH_RULES)
    for rule in stored:
        rule_id, new = rule["ruleId"], fresh.get(rule["ruleId"])
        if rule["origin"] == "derived":
            if new is None and rule_id in GROWTH_RULES and growth is not None:
                wanted.add(DIVERSIFIER_RULE)
                continue                     # the derivation at this date gives no such rule
            if new is None or new["origin"] != "derived":
                raise _underivable(as_of, f"Rule {rule_id}")
            rules.append({**stamped(new), "code": rule["code"], "enabled": rule["enabled"]})
        elif rule_id == DIVERSIFIER_RULE and rule["origin"] == "profile_preference" and growth is not None and growth < 100:
            continue                         # it stands in for a growth cap that does apply at this date
        else:
            rules.append(rule)
    held = {r["ruleId"] for r in stored}
    added = [stamped(r) for r in derivation.rules if r["ruleId"] in wanted and r["ruleId"] not in held]
    if added:
        slot = next((i for i, r in enumerate(rules) if r["ruleId"].startswith("limit.")),
                    next((i for i, r in enumerate(rules) if r["origin"] == "system"), len(rules)))
        rules[slot:slot] = added
    if [r["ruleId"] for r in rules] != [r["ruleId"] for r in stored]:
        rules = renumber(rules)              # codes follow display order; unchanged sets keep their stored codes
    data = profile.to_wire()
    data["rules"] = rules
    return m.Profile.model_validate(data)


def validate_asof(as_of: str, profile: m.Profile, snapshot: Snapshot, request: m.DecisionRequest | None = None,
                  created_at: str | None = None) -> HistoricalContext:
    """Eligibility of a replay date for a profile (timemachine SPEC §2); raises ``validation_error``."""
    try:
        date.fromisoformat(as_of)
    except (TypeError, ValueError) as exc:
        raise _invalid("asOf must be an ISO date", "asOf") from exc
    rng = eligible_range(snapshot)
    if not rng.earliest <= as_of <= rng.latest:
        raise _invalid(f"asOf must be between {rng.earliest} and {rng.latest}", "asOf",
                       earliestAsOf=rng.earliest, latestAsOf=rng.latest)
    universe = snapshot.gate(as_of, "historical").universe()
    wanted = [p.ticker for p in profile.portfolio.positions if p.weight_pct > 0]
    if request is not None and request.type == "move":
        wanted.append(request.move.ticker)
        wanted.extend(request.move.funding.from_tickers or [])
    if request is not None and request.type == "goal":
        wanted.extend(request.goal.tickers)
        if request.goal.themes and not any(asset.themes for asset in universe.all()):
            # Theme tags are 2026 team assignments: none is visible at a historical cutoff, so a
            # theme goal could only fail later with an empty candidate list.
            raise _invalid("Theme tags were assigned in 2026 and are not visible at a historical date; "
                           "name tickers or asset classes instead", "request.goal.themes", themesVisibleAtAsOf=False)
    unknown = sorted({t for t in wanted if t not in CASH_TICKERS and t not in universe})
    if unknown:
        raise _invalid(f"No price is visible on or before {as_of} for: {', '.join(unknown)}", "asOf", unknownAtAsOf=unknown)
    stamp = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return HistoricalContext(as_of, snapshot.data_version, snapshot.data_as_of, rederive_at(profile, snapshot, as_of, stamp))


def gate_report(gate) -> dict:
    """``M_GATE_COUNT`` per loaded dataset. A dataset with no visible dated row is omitted rather
    than given an invented ``lastVisibleDate`` (timemachine SPEC §2)."""
    datasets = [{"datasetId": row["datasetId"], "rowsVisible": row["rowsVisible"], "rowsWithheld": row["rowsWithheld"],
                 "lastVisibleDate": row["lastVisibleDate"]}
                for row in gate.availability_summary() if row["lastVisibleDate"]]
    return {"datasets": datasets}


def replay_result(decision: m.DecisionResult, ctx, private: dict) -> dict:
    """``AgentServices.replay_result_factory``: the actual gate metadata of a signed replay."""
    if getattr(ctx.gate, "mode", None) != "historical":
        raise RuntimeError("A replay must run through a historical temporal gate")
    notices = list(MANDATORY_NOTICES)
    notices += [code for code in MACRO_NOTICES if code in decision.limitations]
    if "LIM_MACRO_REVISED" not in notices:
        notices.append("LIM_MACRO_REVISED")  # revised U.S. macro series are withheld, and that is disclosed
    return {"asOf": str(ctx.as_of), "decision": decision.to_wire(), "gate": gate_report(ctx.gate),
            "notices": notices, "revealAvailableUntil": private["revealAvailableUntil"]}


def reveal(run: m.Run, snapshot: Snapshot, until: str | None, created_at: str) -> dict:
    """What the pinned scenario mixes did between the cutoff and ``until`` (deterministic, TM-07).

    Uses the weights stored in the signed result and a fresh ledger; the run is only read."""
    if run.kind != "replay" or run.status != "succeeded" or run.result is None:
        raise Conflict("Reveal requires a succeeded replay")
    if run.data_version != snapshot.data_version:
        raise ServiceError("upstream_unavailable", f"The run is pinned to {run.data_version}, which is not the loaded snapshot")
    replay = run.result.replay
    as_of = replay.as_of
    until = until or snapshot.data_as_of
    try:
        date.fromisoformat(until)
    except (TypeError, ValueError) as exc:
        raise _invalid("until must be an ISO date", "until") from exc
    if not as_of < until <= snapshot.data_as_of:
        raise _invalid(f"until must be after {as_of} and no later than {snapshot.data_as_of}", "until")
    decision = replay.decision
    currency = decision.portfolio_before.currency
    engine = QuantEngine(snapshot.gate(until, "historical"), LocalLedger(), currency=currency,
                         subject_id=run.profile_id or "portfolio", created_at=created_at)
    i0 = engine.market.last_index_on_or_before(as_of)
    i1 = engine.market.last_index_on_or_before(until)
    if i0 is None or i1 is None or i1 <= i0:
        raise ServiceError("insufficient_data", f"No trading day lies between {as_of} and {until} in this dataset",
                           {"asOf": as_of, "until": until})
    d0, d1 = engine.market.dates[i0], engine.market.dates[i1]
    mixes = [(UNCHANGED_SCENARIO, _t("Portfolio without the change", "Portefeuille sans le changement"), decision.portfolio_before)]
    mixes += [(s.scenario_id, s.label.to_wire(), s.portfolio_after) for s in decision.scenarios]
    outcomes = []
    for scenario_id, label, snapshot_after in mixes:
        weights = {p.ticker: p.weight_pct / 100.0 for p in snapshot_after.positions if p.weight_pct > 0}
        total = sum(weights.values())
        weights = {t: w / total for t, w in weights.items()}
        try:
            levels = engine.portfolio_levels(weights, i0, i1)
        except (Unavailable, UnknownTicker) as exc:
            raise ServiceError("insufficient_data", f"Scenario {scenario_id} cannot be valued until {until}: {exc}",
                               {"scenarioId": scenario_id}) from exc
        value = mx.period_return_pct(levels)
        drawdown = mx.max_drawdown_pct(levels)
        common = dict(subject={"type": "portfolio", "id": run.profile_id or "portfolio", "variant": f"scenario:{scenario_id}"},
                      variant_key=f"reveal:{scenario_id}:currency:{currency}", window_code=f"custom:{d0}..{d1}",
                      tickers=sorted(weights), i0=i0, i1=i1, kind="scenario", created_by="timemachine",
                      window_spec={"code": "custom", "start": d0, "end": d1},
                      params={"scenarioId": scenario_id, "asOf": as_of, "until": until, "indexBase": 100},
                      extra_lims=("LIM_PAST_NOT_FUTURE",))
        fact_ids = [
            engine.add_series_fact(metric="return.period", value=value, method_id="M_PORT_CONST_WEIGHTS",
                                   label=_t(f"{label['en']}: return from {d0} to {d1}", f"{label['fr']} : rendement du {d0} au {d1}"),
                                   **common),
            engine.add_series_fact(metric="drawdown.max", value=drawdown, method_id="M_MDD_PEAK_TROUGH",
                                   label=_t(f"{label['en']}: largest fall from {d0} to {d1}",
                                            f"{label['fr']} : plus forte baisse du {d0} au {d1}"), **common),
        ]
        outcomes.append({"scenarioId": scenario_id, "label": label, "returnPct": value, "maxDrawdownPct": drawdown,
                         "series": [{"date": d, "value": v * 100.0} for d, v in zip(engine.market.dates[i0:i1 + 1], levels)],
                         "factIds": fact_ids})
    return {"asOf": as_of, "until": until, "outcomes": outcomes, "facts": engine.ledger.wire(), "statement": REVEAL_STATEMENT}


class ReplayServiceImpl:
    """``ReplayService`` for the HTTP API (api.md §5.8 and §7.1)."""

    def __init__(self, snapshot: Callable[[], Snapshot], clock: Callable[[], datetime] | None = None) -> None:
        self.snapshot = snapshot
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def presets(self, session_id: str) -> a.ReplayPresetsResponse:
        return a.ReplayPresetsResponse.model_validate(build_presets(self.snapshot()))

    def reveal(self, session_id: str, run: m.Run, request: a.RevealRequest) -> m.RevealResult:
        if run.session_id != session_id:
            raise NotFound()
        stamp = self.clock().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return m.RevealResult.model_validate(reveal(run, self.snapshot(), request.until, stamp))
