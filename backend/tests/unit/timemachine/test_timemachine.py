"""TM-01...TM-10 that do not need a model: eligibility, presets, gate, thresholds, reveal isolation."""

from __future__ import annotations

import copy
from datetime import date, timedelta

import pytest
from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.contracts import models as m
from aplomb.contracts.registry import adapter
from aplomb.datastore import LocalDataStore
from aplomb.datastore.ingest import ingest_bundle
from aplomb.profiles.defaults import load_defaults
from aplomb.quant import LocalLedger, QuantEngine
from aplomb.timemachine import (
    ReplayServiceImpl,
    build_presets,
    eligible_range,
    gate_report,
    replay_result,
    reveal,
    validate_asof,
)
from aplomb.timemachine.service import (
    MANDATORY_NOTICES,
    MIN_FORWARD_DAYS,
    MIN_HISTORY_OBS,
    UNCHANGED_SCENARIO,
)

from tests.unit.datastore._support import (
    encode_tables,
    fixed_clock,
    starter_snapshot,
    synthetic_tables,
    temp_root,
)

NOW = "2026-11-14T22:00:00Z"
SID = "s_6f1c2d3e-4a5b-4c6d-8e7f-0123456789ab"
MOVE = {"type": "move", "move": {"ticker": "TSLA", "sizePct": 5, "funding": {"mode": "pro_rata"}}}


def robert() -> m.Profile:
    return next(p for p in load_defaults() if p.profile_id == "robert")


def request(payload=MOVE):
    return adapter("DecisionRequest").validate_python(payload)


# TM-01 ---------------------------------------------------------------------------------------


def test_eligible_range_comes_from_the_master_calendar():
    snap = starter_snapshot()
    rng = eligible_range(snap)
    dates = snap.gate(snap.data_as_of).master_calendar().dates
    assert len(dates) == 1228
    assert rng.earliest == dates[MIN_HISTORY_OBS - 1] == "2022-11-22"
    assert rng.latest == dates[-1 - MIN_FORWARD_DAYS]
    assert len([d for d in dates if d <= rng.earliest]) == 252            # observations, not calendar days
    assert len([d for d in dates if d > rng.latest]) == 60


def test_presets_are_computed_and_validate_against_the_contract():
    snap = starter_snapshot()
    body = a.ReplayPresetsResponse.model_validate(build_presets(snap)).to_wire()
    rng = eligible_range(snap)
    assert (body["earliestAsOf"], body["latestAsOf"]) == (rng.earliest, rng.latest)
    days = [p["asOf"] for p in body["presets"]]
    assert len(days) == len(set(days)) and all(rng.earliest <= d <= rng.latest for d in days)
    assert all(d in rng.master_dates for d in days)
    # Year ends are the last master day of completed years; the demonstration date says it is hindsight.
    assert {"2022-12-30", "2023-12-29", "2024-12-31", "2025-12-31"} <= set(days)
    assert "hindsight" in body["presets"][0]["why"]["en"]
    assert set(MANDATORY_NOTICES) <= set(body["notices"])


def test_hindsight_preset_is_the_largest_forward_fall_of_the_reference_fund():
    snap = starter_snapshot()
    rng = eligible_range(snap)
    frame = snap.gate(snap.data_as_of).price_frame(["SPY"])
    index = {d: i for i, d in enumerate(frame.dates)}
    levels = frame.column("SPY")

    def fall(day):
        i = index[day]
        return 1 - min(levels[i + 1:i + 61]) / levels[i]

    chosen = build_presets(snap)["presets"][0]["asOf"]
    eligible = [d for d in rng.master_dates if rng.earliest <= d <= rng.latest]
    assert fall(chosen) == pytest.approx(max(fall(d) for d in eligible))


# TM-09 date validation -----------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["2022-11-21", "2026-11-12", "2030-01-01", "not-a-date", "2021-11-12"])
def test_dates_outside_the_eligible_range_are_rejected(bad):
    with pytest.raises(ServiceError) as exc:
        validate_asof(bad, robert(), starter_snapshot(), request(), NOW)
    assert exc.value.code == "validation_error"


def test_a_non_trading_day_inside_the_range_is_accepted():
    ctx = validate_asof("2023-07-01", robert(), starter_snapshot(), request(), NOW)   # a Saturday
    assert ctx.as_of == "2023-07-01" and ctx.reveal_available_until == "2026-11-12"


# TM-06 thresholds from pre-cutoff data ---------------------------------------------------------


def test_derived_thresholds_use_only_data_visible_at_the_cutoff():
    snap = starter_snapshot()
    current = {r.rule_id: r for r in robert().rules}
    ctx = validate_asof("2023-06-30", robert(), snap, request(), NOW)
    past = {r.rule_id: r for r in ctx.profile.rules}
    assert list(past) == list(current)                                     # same rules, same order and codes
    assert [r.code for r in ctx.profile.rules] == [r.code for r in robert().rules]
    derived = [r for r in ctx.profile.rules if r.origin == "derived"]
    assert derived
    for rule in derived:
        assert rule.derivation.data_version == snap.data_version
        assert rule.derivation.window.to_wire() == {"code": "full"}
    # The reference volatilities behind the caps come from the shorter, pre-cutoff sample.
    engine = QuantEngine(snap.gate("2023-06-30", "historical"), LocalLedger(), currency="CAD", subject_id="robert", created_at=NOW)
    assert engine.market.dates[-1] == "2023-06-30"
    assert past["cap.position"].derivation.inputs != current["cap.position"].derivation.inputs
    # Rules that are not derived are untouched.
    for rule_id, rule in current.items():
        if rule.origin != "derived":
            assert past[rule_id].to_wire() == rule.to_wire()


# TM-02 / TM-03 future rows cannot change historical outputs -------------------------------------


def _ingest(tables, version):
    root = temp_root()
    ingest_bundle(encode_tables(tables), root, version, clock=fixed_clock)
    return LocalDataStore(root).open(version)


def test_perturbing_future_prices_and_fx_leaves_historical_facts_unchanged():
    cutoff = "2025-01-10"
    base = synthetic_tables(with_releases=True)
    changed = copy.deepcopy(base)
    for row in changed["prices_daily.csv"]:
        if row[0] > cutoff:
            for i in (2, 3, 4, 5, 6):
                row[i] = str(float(row[i]) * 3.7)
    for row in changed["fx_usdcad_daily.csv"]:
        if row[0] > cutoff:
            row[1], row[2] = "2.0", "0.5"
    for row in changed["macro_rates.csv"]:
        if row[0] > cutoff:
            row[2] = "99.0"
    snaps = [_ingest(base, "snap-20240101-syn"), _ingest(changed, "snap-20240102-syn")]
    outputs = []
    for snap in snaps:
        gate = snap.gate(cutoff, "historical")
        engine = QuantEngine(gate, LocalLedger(), currency="CAD", subject_id="p", created_at=NOW)
        # The synthetic bundle has no FX rate on its first day, so the window starts after it.
        view = engine.view({"XIU.TO": 0.5, "SPY": 0.5}, "before", 1000.0, window={"code": "custom", "start": "2024-01-15", "end": cutoff})
        metrics = view.metrics()
        facts = {f.key: (f.value, f.period.to_wire() if f.period else None, f.available_at) for f in engine.ledger.facts().values()}
        report = [(d["datasetId"], d["rowsVisible"], d["lastVisibleDate"]) for d in gate_report(gate)["datasets"]]
        macro = [(r["date"], r["value"]) for r in gate.macro("DAILYX", None, None).rows]
        outputs.append((metrics.volatility_pct, metrics.max_drawdown_pct, facts, report, macro))
    assert outputs[0] == outputs[1]
    assert outputs[0][0] is not None
    # The current view of the two snapshots does differ, so the perturbation was real.
    current = [QuantEngine(s.gate(s.data_as_of), LocalLedger(), currency="CAD", subject_id="p", created_at=NOW)
               .view({"XIU.TO": 0.5, "SPY": 0.5}, "before", 1000.0, window={"code": "custom", "start": "2024-01-15", "end": s.data_as_of})
               .metrics().volatility_pct for s in snaps]
    assert current[0] != current[1]


def test_gate_report_counts_withheld_rows_and_never_invents_a_date():
    snap = starter_snapshot()
    report = m.GateReport.model_validate(gate_report(snap.gate("2023-06-30", "historical"))).to_wire()
    by_id = {d["datasetId"]: d for d in report["datasets"]}
    prices = by_id["prices_daily"]
    assert prices["rowsVisible"] + prices["rowsWithheld"] == 40049 and prices["rowsWithheld"] > 0
    assert prices["lastVisibleDate"] == "2023-06-30"
    assert all(d["lastVisibleDate"] <= "2023-06-30" for d in report["datasets"])
    # A dataset without a dated visible row (2026 theme assignments) is omitted, not given a date.
    assert "asset_themes" not in by_id


# Reveal (TM-07, TM-08, TM-09) ------------------------------------------------------------------


def replay_run(snap, as_of="2023-06-30", session=SID, status="succeeded") -> m.Run:
    """A replay run whose result holds actual code-computed scenarios (no model text needed)."""
    from aplomb.optimizer.check import assess, prepare

    profile = validate_asof(as_of, robert(), snap, request(), NOW).profile
    engine = QuantEngine(snap.gate(as_of, "historical"), LocalLedger(), currency="CAD", subject_id="robert", created_at=NOW)
    move = m.ProposedMove.model_validate(MOVE["move"])
    check = assess(engine, profile, profile.rules, prepare(engine, profile, profile.rules, move, False), window={"code": "full"})
    scenario = {"scenarioId": "sc_requested", "kind": "requested", "label": {"en": "Requested", "fr": "Demandé"},
                "moves": [MOVE["move"]], "verdict": check.verdict, "counts": check.counts.to_wire(),
                "ruleChecks": [c.to_wire() for c in check.rule_checks], "portfolioAfter": check.portfolio_after.to_wire(),
                "exposure": [], "rationale": {"en": "-", "fr": "-"}, "isBestFit": True, "rank": 1, "keyFactIds": []}
    audit = {"status": "passed", "checks": [], "sentencesChecked": 0, "sentencesStruck": 0, "rewrites": 0,
             "guardrail": {"applied": False, "action": "none", "id": None}, "llmReview": {"model": None, "findings": []},
             "ledgerHash": "0" * 64, "signedAt": NOW}
    decision = {"request": MOVE, "verdict": check.verdict, "counts": check.counts.to_wire(), "selectedScenarioId": "sc_requested",
                "scenarios": [scenario], "portfolioBefore": check.portfolio_before.to_wire(),
                "maxCompatibleSizePct": check.max_compatible_size_pct, "fundingOptions": [], "attention": None, "macroContext": [],
                "brief": {"lang": "en", "sections": [], "disclaimer": {"en": "Simulation only.", "fr": "Simulation uniquement."},
                          "generatedAt": NOW, "model": "none", "audit": audit},
                "limitations": ["LIM_SIMULATION_ONLY"]}
    result = {"kind": "replay", "replay": {"asOf": as_of, "decision": decision, "gate": gate_report(engine.gate),
                                           "notices": list(MANDATORY_NOTICES), "revealAvailableUntil": snap.data_as_of}}
    return m.Run.model_validate({
        "runId": "run_01JCM9Z3QK8T5V7W9X2Y4A6B8C", "kind": "replay", "status": status, "sessionId": session, "profileId": "robert",
        "parentRunId": None, "lang": "en", "asOf": as_of, "dataVersion": snap.data_version,
        "input": {"kind": "replay", "request": MOVE, "asOf": as_of, "window": {"code": "full"}}, "steps": [],
        "facts": engine.ledger.wire(), "evidence": {}, "question": None, "result": result if status == "succeeded" else None,
        "error": None, "flags": {"sabotage": None, "fixture": False, "timeMachine": True},
        "usage": {"llmCalls": 0, "inputTokens": 0, "outputTokens": 0, "toolCalls": 0, "durationMs": 0},
        "createdAt": NOW, "updatedAt": NOW})


def test_reveal_uses_pinned_weights_in_a_separate_ledger_and_leaves_the_run_unchanged():
    snap = starter_snapshot()
    run = replay_run(snap)
    before = copy.deepcopy(run.to_wire())
    out = m.RevealResult.model_validate(reveal(run, snap, "2024-06-28", NOW)).to_wire()
    assert run.to_wire() == before                                         # TM-08: parent untouched
    assert (out["asOf"], out["until"]) == ("2023-06-30", "2024-06-28")
    assert [o["scenarioId"] for o in out["outcomes"]] == [UNCHANGED_SCENARIO, "sc_requested"]
    requested = out["outcomes"][1]
    assert requested["series"][0] == {"date": "2023-06-30", "value": 100.0}
    assert requested["series"][-1]["date"] == "2024-06-28"
    assert requested["returnPct"] == pytest.approx(requested["series"][-1]["value"] - 100.0)
    assert requested["maxDrawdownPct"] >= 0
    # Independent fact IDs: every outcome fact resolves in the reveal ledger, with its own provenance.
    for outcome in out["outcomes"]:
        for fid in outcome["factIds"]:
            fact = out["facts"][fid]
            assert fact["createdBy"] == "timemachine" and fact["asOf"] == "2024-06-28"
            assert fact["period"] == {"start": "2023-06-30", "end": "2024-06-28"}
            assert fact["subject"]["variant"] == f"scenario:{outcome['scenarioId']}"
            assert "LIM_CONSTANT_WEIGHTS" in fact["limitations"] and "LIM_PAST_NOT_FUTURE" in fact["limitations"]
    assert not set(k for k, f in out["facts"].items() if f["key"] in {x["key"] for x in before["facts"].values()})
    assert "do not establish" in out["statement"]["en"]


def test_reveal_matches_an_independent_constant_weight_calculation():
    snap = starter_snapshot()
    run = replay_run(snap)
    out = reveal(run, snap, "2024-06-28", NOW)
    weights = {p.ticker: p.weight_pct / 100 for p in run.result.replay.decision.scenarios[0].portfolio_after.positions}
    engine = QuantEngine(snap.gate("2024-06-28", "historical"), LocalLedger(), currency="CAD", subject_id="x", created_at=NOW)
    i0, i1 = engine.market.index_of("2023-06-30"), engine.market.index_of("2024-06-28")
    level = 1.0
    for step in range(i0 + 1, i1 + 1):
        r = sum(w * (engine.market.series(t).levels[step] / engine.market.series(t).levels[step - 1] - 1) for t, w in weights.items())
        level *= 1 + r
    assert out["outcomes"][1]["returnPct"] == pytest.approx((level - 1) * 100, abs=1e-9)


def test_reveal_never_reads_rows_after_until():
    snap = starter_snapshot()
    run = replay_run(snap)
    short = reveal(run, snap, "2024-06-28", NOW)
    long = reveal(run, snap, None, NOW)
    assert long["until"] == snap.data_as_of
    n = len(short["outcomes"][1]["series"])
    assert long["outcomes"][1]["series"][:n] == short["outcomes"][1]["series"]


@pytest.mark.parametrize("until,code", [("2023-06-30", "validation_error"), ("2023-01-01", "validation_error"),
                                         ("2030-01-01", "validation_error"), ("nope", "validation_error"),
                                         ("2023-07-01", "insufficient_data")])
def test_reveal_rejects_unsupported_windows(until, code):
    snap = starter_snapshot()
    with pytest.raises(ServiceError) as exc:
        reveal(replay_run(snap), snap, until, NOW)        # 2023-07-01 is a Saturday: no trading day after the cutoff
    assert exc.value.code == code


def test_reveal_requires_a_succeeded_replay_owned_by_the_session():
    snap = starter_snapshot()
    service = ReplayServiceImpl(lambda: snap)
    with pytest.raises(NotFound):
        service.reveal("s_" + "0" * 8 + "-0000-4000-8000-000000000000", replay_run(snap), a.RevealRequest())
    with pytest.raises(Conflict):
        reveal(replay_run(snap, status="failed"), snap, None, NOW)
    ok = service.reveal(SID, replay_run(snap), a.RevealRequest(until="2023-12-29"))
    assert ok.until == "2023-12-29"


def test_replay_result_reports_the_actual_gate_and_mandatory_notices():
    snap = starter_snapshot()
    run = replay_run(snap)

    class Ctx:
        as_of = "2023-06-30"
        gate = snap.gate("2023-06-30", "historical")

    body = m.ReplayResult.model_validate(replay_result(run.result.replay.decision, Ctx, {"revealAvailableUntil": snap.data_as_of})).to_wire()
    assert body["asOf"] == "2023-06-30" and body["revealAvailableUntil"] == "2026-11-12"
    assert set(MANDATORY_NOTICES) <= set(body["notices"]) and "LIM_MACRO_REVISED" in body["notices"]
    assert body["gate"] == gate_report(Ctx.gate)
    Ctx.gate = snap.gate("2023-06-30", "current")
    with pytest.raises(RuntimeError):
        replay_result(run.result.replay.decision, Ctx, {"revealAvailableUntil": snap.data_as_of})


# TM-05 -----------------------------------------------------------------------------------------


def test_stress_2022_is_not_enough_evidence_before_the_window_ends():
    snap = starter_snapshot()
    as_of = "2022-12-01"
    assert (date.fromisoformat("2022-12-31") - date.fromisoformat(as_of)) > timedelta(days=0)
    run = replay_run(snap, as_of)
    checks = {c.rule_id: c for c in run.result.replay.decision.scenarios[0].rule_checks}
    assert (checks["limit.stress_2022"].status, checks["limit.stress_2022"].nee_reason) == ("nee", "not_visible_at_asof")
    later = {c.rule_id: c for c in replay_run(snap, "2023-06-30").result.replay.decision.scenarios[0].rule_checks}
    assert later["limit.stress_2022"].status != "nee"
