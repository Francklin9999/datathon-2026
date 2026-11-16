"""The planner's quant tasks select optional analyses from a closed list (agents SPEC §4.3): a
selected analysis registers facts the writer receives, an omitted one registers none, the
mandatory controls run whatever the plan says, and every other task is reported as skipped in the
run trace. A tool name outside the catalog never reaches the workflow: the plan schema rejects it
(test_agent_runtime.test_planner_cannot_smuggle_an_unknown_computation). Offline; scripted model."""

from __future__ import annotations

from tests.integration._scripted import ScriptedGateway
from tests.integration.test_fix_workflow import DECISION, client, session, wait


def run_with(plan: dict, body: dict = DECISION):
    gateway = ScriptedGateway(plan={"interpretation": "Test the confirmed hypothetical request.", **plan})
    c, headers = client(gateway), session()
    run_id = c.post("/v1/runs", json=body, headers=headers).json()["runId"]
    run = wait(c, headers, run_id, until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    trace = c.get(f"/v1/runs/{run_id}/trace", headers=headers).json()
    profile = c.get("/v1/profiles/robert", headers=headers).json()
    return run, trace, gateway, profile


def quant_step(run):
    return next(s for s in run["steps"] if s["type"] == "quant")


def metric_ids(run, metric):
    return {fid for fid, fact in run["facts"].items() if fact["metric"] == metric}


def skipped(trace):
    return [(x["task"], x["tool"], x["reason"]) for x in trace["events"] if x["type"] == "plan_task_skipped"]


def test_a_selected_optional_analysis_registers_facts_the_writer_receives():
    tasks = [{"tool": "quant.correlation"}, {"tool": "quant.calendar_year_return", "args": {"year": 2024}}]
    run, trace, gateway, _ = run_with({"quant_tasks": tasks})
    correlations = metric_ids(run, "corr.pair")
    assert correlations and all(run["facts"][f]["subject"]["id"].startswith("TSLA~") for f in correlations)
    years = {run["facts"][f]["subject"]["variant"] for f in metric_ids(run, "return.calendar_year")}
    assert years == {"before:year:2024", "after:year:2024"}
    step = quant_step(run)
    calls = step["toolCalls"]
    assert [c["tool"] for c in calls] == ["quant.correlation", "quant.calendar_year_return"]
    assert all(c["ok"] for c in calls) and set(calls[0]["factIds"]) == correlations
    assert set(calls[0]["factIds"]) | set(calls[1]["factIds"]) <= set(step["factIds"])
    assert run["usage"]["toolCalls"] == 2
    assert "2 run, 0 already mandatory, 0 skipped" in step["summary"]["en"]
    writer = next(p for role, p in gateway.prompts if role == "writer")
    assert correlations <= set(writer["facts"])
    planner = next(p for role, p in gateway.prompts if role == "planner")
    assert {"quant.correlation", "quant.calendar_year_return"} <= {a["tool"] for a in planner["optional_analyses"]}
    assert skipped(trace) == []


def test_an_omitted_analysis_registers_none_of_its_facts():
    run, trace, _, _ = run_with({})
    assert not metric_ids(run, "corr.pair") and not metric_ids(run, "return.calendar_year")
    assert quant_step(run)["toolCalls"] == [] and run["usage"]["toolCalls"] == 0
    assert skipped(trace) == []


def test_the_mandatory_controls_run_with_an_empty_plan_and_a_plan_cannot_change_them():
    empty, _, _, profile = run_with({})
    planned, _, _, _ = run_with({"quant_tasks": [{"tool": "quant.correlation"}, {"tool": "rules.check"}]})
    enabled = {r["ruleId"] for r in profile["rules"] if r["enabled"]}

    def governance(run):
        decision = run["result"]["decision"]
        scenarios = {s["scenarioId"]: s for s in decision["scenarios"]}
        return (decision["verdict"], decision["counts"], decision["maxCompatibleSizePct"],
                {sid: sorted((c["ruleId"], c["status"]) for c in s["ruleChecks"]) for sid, s in scenarios.items()})

    for run in (empty, planned):
        assert [s["type"] for s in run["steps"]] == ["plan", "quant", "risk_check", "write", "audit", "sign"]
        decision = run["result"]["decision"]
        requested = next(s for s in decision["scenarios"] if s["scenarioId"] == "sc_requested")
        assert {c["ruleId"] for c in requested["ruleChecks"]} >= enabled
        assert {"sc_requested", "sc_max_compatible"} <= {s["scenarioId"] for s in decision["scenarios"]}
        assert decision["maxCompatibleSizePct"] == 6.0
    assert governance(empty) == governance(planned)


def test_tasks_outside_the_closed_list_are_reported_as_skipped():
    tasks = [{"tool": "quant.price_move_after"}, {"tool": "quant.portfolio_metrics"},
             {"tool": "quant.calendar_year_return", "args": {"year": "last"}},
             {"tool": "quant.correlation"}, {"tool": "quant.correlation"},
             {"tool": "optimizer.rebalance", "args": {"target": "within_rules"}}]
    run, trace, gateway, _ = run_with({"quant_tasks": tasks})
    assert skipped(trace) == [(1, "quant.price_move_after", "not_optional"), (2, "quant.portfolio_metrics", "mandatory"),
                              (3, "quant.calendar_year_return", "invalid_args"), (5, "quant.correlation", "duplicate"),
                              (6, "optimizer.rebalance", "mandatory")]
    assert all(set(x) == {"type", "at", "step", "task", "tool", "reason"}
               for x in trace["events"] if x["type"] == "plan_task_skipped")   # no model-written args
    step = quant_step(run)
    assert [c["tool"] for c in step["toolCalls"]] == ["quant.correlation"]
    assert "1 run, 2 already mandatory, 3 skipped" in step["summary"]["en"]
    notes = " ".join(trace["limitations"])
    assert "quant.price_move_after" in notes and "quant.calendar_year_return" in notes
    assert "quant.portfolio_metrics" not in notes and "optimizer.rebalance" not in notes   # run by the controls
    writer = next(p for role, p in gateway.prompts if role == "writer")
    assert "quant.price_move_after" in " ".join(writer["execution_limitations"])


def test_alternatives_and_rebalance_tasks_are_left_to_the_risk_check_and_never_claimed_undone():
    # The risk check adds alternatives to a conflicting move (and a rebalance to a conflicting
    # portfolio) whatever the plan says, so the writer must not be told they were not computed. The
    # scripted planner repeats its plan as the revision, whose 3 scenarios exceed the budget (4 + 3).
    nvda = {**DECISION, "request": {"type": "move", "move": {"ticker": "NVDA", "sizePct": 20, "funding": {"mode": "pro_rata"}}}}
    tasks = [{"tool": "optimizer.alternatives"}, {"tool": "optimizer.rebalance"}, {"tool": "quant.correlation"}]
    run, trace, gateway, _ = run_with({"revise": True, "quant_tasks": tasks, "scenario_tasks": [{"kind": "alternative"}] * 3}, nvda)
    decision = run["result"]["decision"]
    assert decision["verdict"] == "conflict" and "alternative" in {s["kind"] for s in decision["scenarios"]}
    assert [s["type"] for s in run["steps"]] == ["plan", "quant", "risk_check", "revise", "write", "audit", "sign"]
    first = [(1, "optimizer.alternatives", "mandatory"), (2, "optimizer.rebalance", "mandatory")]
    assert skipped(trace) == first + first + [(3, "quant.correlation", "duplicate")]   # plan, then the stopped revision
    writer = next(p for role, p in gateway.prompts if role == "writer")
    for notes in (trace["limitations"], writer["execution_limitations"]):
        assert not [n for n in notes if "calculation" in n]


def test_an_analysis_without_visible_data_is_a_successful_call_with_no_fact():
    # A year before the visible history is a result (no fact), not a failed tool call.
    run, trace, _, _ = run_with({"quant_tasks": [{"tool": "quant.calendar_year_return", "args": {"year": 2020}}]})
    [call] = quant_step(run)["toolCalls"]
    assert call["ok"] and call["error"] is None and call["factIds"] == []
    assert call["resultSummary"].startswith("Optional analysis from the plan: no fact registered (")
    assert not metric_ids(run, "return.calendar_year") and skipped(trace) == []


def test_a_revision_that_selects_an_analysis_runs_it_in_the_next_quant_step():
    # Before, a revised plan without scenario tasks ended the loop and its calculations vanished.
    run, _, gateway, _ = run_with({"revise": True, "quant_tasks": [{"tool": "quant.asset_metrics"}]})
    quants = [s for s in run["steps"] if s["type"] == "quant"]
    assert [s["iteration"] for s in quants] == [1, 2]
    assert all([c["tool"] for c in s["toolCalls"]] == ["quant.asset_metrics"] for s in quants)
    revise = next(s for s in run["steps"] if s["type"] == "revise")
    assert revise["summary"]["en"].endswith("Its 1 calculation(s) are each run or reported as skipped.")
    assert gateway.roles.count("planner") == 2


def test_a_portfolio_brief_runs_no_optional_analysis_and_says_so():
    gateway = ScriptedGateway(plan={"interpretation": "Describe the portfolio.", "quant_tasks": [{"tool": "quant.correlation"}]})
    c, headers = client(gateway), session()
    run_id = c.post("/v1/runs", json={"kind": "portfolio_brief", "profileId": "robert", "lang": "en"}, headers=headers).json()["runId"]
    run = wait(c, headers, run_id, until=("succeeded", "failed"))
    assert run["status"] == "succeeded", run["error"]
    assert not metric_ids(run, "corr.pair") and quant_step(run)["toolCalls"] == []
    assert skipped(c.get(f"/v1/runs/{run_id}/trace", headers=headers).json()) == [(1, "quant.correlation", "move_only")]
    assert "optional_analyses" not in next(p for role, p in gateway.prompts if role == "planner")
