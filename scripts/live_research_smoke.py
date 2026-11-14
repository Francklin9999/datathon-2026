"""Opt-in public-source -> registry -> ledger -> audit smoke (no AWS or model calls).

The demonstration mapping was reviewed against the Apple Inc. article on
2026-11-14. It is confined to this probe; runtime mappings remain injected.
Run with a real contact user-agent and an output directory outside the repo.
"""

import argparse
import json
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from aplomb.agents import ToolContext, ToolRegistry
from aplomb.agents.limits import Limits
from aplomb.ledger import Ledger, ReviewResult, audit_and_sign
from aplomb.research import (
    ArticleMapping,
    AttentionAdapter,
    PublicHTTP,
    ResearchContext,
    ResearchService,
    research_tool_handlers,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-agent", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=datetime.now(UTC).date())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run_id = "research-smoke-" + uuid.uuid4().hex
    rc = ResearchContext(run_id, args.as_of)
    ledger = Ledger(run_id, str(args.as_of))
    service = ResearchService(PublicHTTP(args.user_agent), lambda: datetime.now(UTC))
    attention = AttentionAdapter(service, {"AAPL": ArticleMapping(
        "Apple_Inc.", "AAPL", "https://en.wikipedia.org/wiki/Apple_Inc.", verified=True,
    )})
    registry = ToolRegistry()
    for name, (schema, handler) in research_tool_handlers(service, attention=attention).items():
        registry.register(name, schema, handler)
    ctx = ToolContext(run_id, None, "en", str(args.as_of),
                      SimpleNamespace(as_of=args.as_of), ledger, None, Limits(), None,
                      research_context=rc)
    result = registry.execute("researcher", "attention.pageviews", {"ticker": "AAPL"}, ctx)
    report = {"run_id": run_id, "as_of": str(args.as_of), "tool": asdict(result),
              "llm_calls": 0, "scope": "public research tool boundary; no portfolio workflow"}
    if not result.ok or not result.fact_ids:
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        raise SystemExit("Live source did not yield registered facts; see report.json")
    ratio_id = next(fid for fid in result.fact_ids
                    if ledger.get_fact(fid).metric == "attention.pageviews_ratio")
    draft = {"sections": [
        {"id": "facts", "title": {"en": "Facts", "fr": "Faits"}, "sentences": [
            {"id": "S-ratio", "template": f"The pageview ratio is {{{{fact:{ratio_id}}}}}."}]},
        {"id": "assumptions", "title": {"en": "Assumptions", "fr": "Hypothèses"},
         "sentences": [{"id": "S-assumption", "template":
                        "The article mapping is reviewed configuration."}]},
        {"id": "limits", "title": {"en": "Limits", "fr": "Limites"}, "sentences": [
            {"id": "S-limit", "template": "Attention does not determine an investment verdict."}]},
    ]}
    brief = audit_and_sign(ledger, draft, lang="en", model="code-smoke-template",
                           review=lambda sections, view: ReviewResult(model="code-smoke-review"))
    if brief.audit.status != "passed":
        raise RuntimeError("Smoke brief failed clean audit; numeric support needs investigation")
    report["audit"] = brief.audit.to_wire()
    report["facts"] = {fid: fact.to_wire() for fid, fact in ledger.export().facts.items()}
    report["evidence"] = {eid: item.to_wire() for eid, item in ledger.export().evidence.items()}
    report["research_calls"] = ctx.limits.research_calls
    checkpoint = ledger.checkpoint()
    restored = Ledger.restore(run_id, str(args.as_of), checkpoint)
    assert restored.export().digest() == ledger.export().digest()
    report["checkpoint_roundtrip"] = True
    (args.output / "ledger.json").write_text(json.dumps(checkpoint, indent=2) + "\n")
    (args.output / "brief.json").write_text(json.dumps(brief.to_wire(), indent=2) + "\n")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "audit": brief.audit.status,
                      "facts": len(ledger.export().facts), "checkpoint_roundtrip": True}))


if __name__ == "__main__":
    main()
