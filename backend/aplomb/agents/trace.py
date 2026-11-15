"""Read-only execution trace and per-claim audit view of a persisted run.

Built only from what the worker recorded: steps, tool calls, the private agent state (model call
accounting, budgets, retries/fallbacks, checkpoint/resume events, limitations) and the frozen run
ledger. Error fields are already redacted where they are recorded; this module adds no provider
or model text and never re-executes anything. Source excerpts are untrusted data for display.
"""
from __future__ import annotations

from aplomb.ledger import Ledger

# Which independent check family each audit code belongs to (contracts/catalog.md, audit codes).
CHECK_FAMILY = {
    "A01": "reference", "A02": "numeric", "A03": "comparison", "A04": "reference", "A05": "structure",
    "A06": "policy", "A07": "policy", "A08": "source_quote", "A09": "source_interpretation",
    "A10": "guardrail", "A11": "temporal", "A12": "policy", "A13": "policy", "A14": "numeric",
}
MAX_SOURCE_CONTEXTS = 12
MAX_EXCERPT_CHARS = 1600


def _briefs(node, path="result", out=None, depth=0):
    """Every signed Brief inside a run result, with its JSON path (bounded walk)."""
    out = [] if out is None else out
    if depth > 6 or len(out) >= 8:
        return out
    if isinstance(node, dict):
        if {"sections", "audit", "disclaimer"} <= node.keys():
            out.append((path, node))
            return out
        for key, value in node.items():
            _briefs(value, f"{path}.{key}", out, depth + 1)
    elif isinstance(node, list):
        for index, value in enumerate(node[:20]):
            _briefs(value, f"{path}[{index}]", out, depth + 1)
    return out


def _budgets(run, agents, limits):
    usage = run["usage"]
    return [
        {"name": "llm_calls", "used": agents.get("llm_calls", usage.get("llmCalls", 0)), "limit": limits["max_llm_calls"]},
        {"name": "research_calls", "used": agents.get("research_calls", 0), "limit": limits["max_research_calls"]},
        {"name": "revisions", "used": agents.get("revisions", 0), "limit": limits["max_revisions"]},
        {"name": "rewrites", "used": agents.get("rewrites", 0), "limit": 1},
        {"name": "scenarios", "used": agents.get("scenarios", 0), "limit": 6},
        {"name": "wall_clock_ms", "used": round(usage.get("durationMs", 0)), "limit": round(limits["hard_seconds"] * 1000)},
    ]


def _model_call(item):
    return {
        "role": item.get("role"), "model": item.get("model"), "calls": item.get("calls", 0),
        "inputTokens": item.get("input_tokens"), "outputTokens": item.get("output_tokens"),
        "failed": bool(item.get("failed")), "errorType": item.get("error_type"),
        "attempts": [{k: a.get(k) for k in ("model", "outcome", "errorCode", "next") if a.get(k) is not None}
                     for a in (item.get("attempts") or [])][:6],
        "fallback": item.get("fallback"),
    }


def _timeline(run, agents):
    calls_by_step = {}
    for item in agents.get("model_calls", []):
        calls_by_step.setdefault(item.get("step"), []).append(_model_call(item))
    steps = []
    for step in run["steps"]:
        tools = step.get("toolCalls", [])
        steps.append({
            "seq": step["seq"], "type": step["type"], "iteration": step["iteration"], "agent": step["agent"],
            "actor": step["actor"], "status": step["status"], "startedAt": step["startedAt"],
            "endedAt": step.get("endedAt"), "durationMs": step.get("durationMs"), "summary": step["summary"],
            "model": step.get("model"), "usage": step.get("usage"),
            "modelCalls": calls_by_step.get(step["seq"], []),
            "toolCalls": [{
                "id": t["id"], "tool": t["tool"], "ok": t["ok"], "durationMs": t["durationMs"],
                "resultSummary": t["resultSummary"], "error": t.get("error"),
                "factCount": len(t.get("factIds", [])), "evidenceCount": len(t.get("evidenceIds", [])),
            } for t in tools],
            "factCount": len(step.get("factIds", [])), "evidenceCount": len(step.get("evidenceIds", [])),
        })
    return steps


def _restore_ledger(record):
    state = (record.private.get("agents") or {}).get("ledger")
    if not state:
        return None, "No ledger checkpoint was recorded for this run."
    try:
        return Ledger.restore(record.run.run_id, str(record.run.as_of), state), None
    except Exception:
        return None, "The recorded ledger checkpoint failed its integrity checks."


def _claims(run, ledger):
    claims, cited, briefs = [], [], []
    for path, brief in _briefs(run.get("result")):
        audit = brief["audit"]
        named = {}
        for check in audit["checks"]:
            for sid in check.get("sentenceIds", []):
                named.setdefault(sid, []).append(check)
        global_checks = [{"code": c["code"], "family": CHECK_FAMILY.get(c["code"], "other"), "ok": c["ok"],
                          "kind": c["kind"], "detail": c["detail"]}
                         for c in audit["checks"] if not c.get("sentenceIds")]
        ledger_match = None
        if ledger is not None:
            ledger_match = ledger.export().digest() == audit["ledgerHash"]
        briefs.append({"path": path, "status": audit["status"], "ledgerHash": audit["ledgerHash"],
                       "ledgerHashMatchesCheckpoint": ledger_match, "signedAt": audit["signedAt"],
                       "llmReviewModel": audit["llmReview"].get("model"), "globalChecks": global_checks})
        for section in brief["sections"]:
            for sentence in section["sentences"]:
                facts = [s["factId"] for s in sentence["segments"] if s["t"] == "fact"]
                evidence = [s["evidenceId"] for s in sentence["segments"] if s["t"] == "evidence"]
                rules = [s["ruleId"] for s in sentence["segments"] if s["t"] in ("rule", "status")]
                cited.extend(e for e in evidence if e not in cited)
                checks = [{"code": c["code"], "family": CHECK_FAMILY.get(c["code"], "other"), "ok": c["ok"],
                           "kind": c["kind"], "detail": c["detail"]} for c in named.get(sentence["id"], [])]
                failed = list(sentence["audit"].get("failedChecks", []))
                claims.append({
                    "briefPath": path, "sectionId": section["id"], "sentenceId": sentence["id"],
                    "status": sentence["audit"]["status"], "failedChecks": failed,
                    "failedFamilies": sorted({CHECK_FAMILY.get(code, "other") for code in failed}),
                    "checks": checks, "factIds": facts, "evidenceIds": evidence, "ruleIds": rules,
                })
    return claims, cited, briefs


def _source_contexts(run, ledger, cited):
    contexts = []
    wanted = list(cited)
    for evidence_id in run.get("evidence", {}):
        if evidence_id not in wanted:
            wanted.append(evidence_id)
    for evidence_id in wanted[:MAX_SOURCE_CONTEXTS]:
        entry = {"evidenceId": evidence_id, "cited": evidence_id in cited}
        if ledger is None:
            entry["unavailable"] = "ledger_unavailable"
        else:
            try:
                context = ledger.source_review_context(evidence_id)
                entry.update({
                    "sourceUrl": context["sourceUrl"], "documentRef": context["documentRef"],
                    "contentSha256": context["contentSha256"], "offsetUnit": context["offsetUnit"],
                    "sourceTextLength": context["sourceTextLength"], "moreMatches": context["moreMatches"],
                    "excerpts": [{**x, "text": x["text"][:MAX_EXCERPT_CHARS]} for x in context["excerpts"]],
                })
            except ValueError:
                # Unverified, foreign or missing captures fail closed; no excerpt is shown.
                entry["unavailable"] = "no_verified_same_run_source"
        contexts.append(entry)
    return contexts


def build_trace(record, limits: dict) -> dict:
    run = record.run.to_wire()
    agents = record.private.get("agents") or {}
    ledger, ledger_note = _restore_ledger(record)
    claims, cited, briefs = _claims(run, ledger)
    failed_audit = agents.get("failed_audit")
    return {
        "runId": run["runId"], "kind": run["kind"], "status": run["status"], "asOf": run["asOf"],
        "dataVersion": run["dataVersion"], "generation": record.generation,
        "claims": list(agents.get("claims", [])),
        "checkpoints": agents.get("checkpoints", 0),
        "budgets": _budgets(run, agents, limits),
        "usage": run["usage"],
        "steps": _timeline(run, agents),
        "events": list(agents.get("events", [])),
        "limitations": list(agents.get("execution_limitations", [])),
        "error": run.get("error"),
        "failedAudit": {"status": failed_audit.get("status"),
                        "failedChecks": sorted({c["code"] for c in failed_audit.get("checks", []) if not c.get("ok")})}
        if isinstance(failed_audit, dict) else None,
        "ledger": {"available": ledger is not None, "note": ledger_note,
                   "digest": ledger.export().digest() if ledger is not None else None},
        "briefs": briefs,
        "claimAudit": claims,
        "sources": _source_contexts(run, ledger, cited),
    }
