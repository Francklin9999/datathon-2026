"""Public-source capture through the agent boundary and durable run checkpoint."""

import json
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from aplomb.agents import ToolContext, ToolRegistry
from aplomb.agents.limits import Limits
from aplomb.api.repositories import RunRepository
from aplomb.api.storage import FileStore
from aplomb.contracts.models import Run
from aplomb.ledger import Ledger
from aplomb.research import (
    ArticleMapping,
    AttentionAdapter,
    ResearchContext,
    ResearchService,
    Response,
    research_tool_handlers,
)

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


class Source:
    calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        return Response(200, {"content-type": "text/plain"}, b"Revenue reported as 42 USD.")


def test_registry_quote_is_saved_readable_and_historical_access_denied(tmp_path):
    payload = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    payload.update(status="queued", steps=[], facts={}, evidence={}, result=None, error=None,
                   question=None)
    repo = RunRepository(FileStore(tmp_path / "store.json"))
    created, _ = repo.create(Run.model_validate(payload), {}, None)
    claimed = repo.claim(created.run.run_id, created.generation)
    assert claimed is not None
    run = claimed.run
    ledger = Ledger(run.run_id, run.as_of, clock=lambda: NOW.isoformat().replace("+00:00", "Z"))
    source = Source()
    service = ResearchService(source, lambda: NOW, resolver=lambda *a, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    registry = ToolRegistry()
    for name, (schema, handler) in research_tool_handlers(service).items():
        registry.register(name, schema, handler)
    context = ToolContext(run.run_id, None, "en", run.as_of,
                          SimpleNamespace(as_of=run.as_of), ledger, None, Limits(), None,
                          research_context=ResearchContext(run.run_id, date.fromisoformat(run.as_of)))
    url = "https://www.sec.gov/Archives/example.txt"
    fetched = registry.execute("researcher", "web.fetch", {"url": url}, context)
    assert fetched.ok
    saved = registry.execute("researcher", "research.save_evidence", {
        "type": "filing", "title": "Revenue report", "publisher": "forged publisher",
        "url": url, "quote": "Revenue reported as 42 USD.",
        "claim": {"en": "Reported revenue", "fr": "Revenu déclaré"},
        "subject": {"type": "asset", "id": "AAPL"},
    }, context)
    assert saved.ok, saved.error
    eid = saved.evidence_ids[0]
    updated = run.model_copy(update={"evidence": ledger.export().evidence})
    repo.checkpoint(run.run_id, claimed.generation, claimed.owner, claimed.revision, updated,
                    {"ledger": ledger.checkpoint()})
    fresh = RunRepository(FileStore(tmp_path / "store.json")).get(run.session_id, run.run_id)
    assert fresh.run.evidence[eid].publisher == "SEC"
    assert fresh.run.evidence[eid].verification.status == "verified"
    restored = Ledger.restore(run.run_id, run.as_of, fresh.private["ledger"])
    assert restored.export().digest() == ledger.export().digest()
    context.historical = True
    denied = registry.execute("researcher", "web.fetch", {"url": url}, context)
    assert not denied.ok and "historical" in denied.error
    assert source.calls == 1
    assert context.limits.research_calls == 2


def test_captured_complete_series_survives_real_run_checkpoint(tmp_path):
    """A real captured series remains a tagged verified fact after durable reload."""
    raw = (ROOT / "backend/tests/research/fixtures/captured/wikimedia-395.json").read_bytes()

    class Captured:
        def get(self, url, **kwargs):
            return Response(200, {"content-type": "application/json"}, raw)

    payload = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    payload.update(status="queued", steps=[], facts={}, evidence={}, result=None, error=None,
                   question=None, asOf="2026-11-14")
    store_path = tmp_path / "series-store.json"
    repo = RunRepository(FileStore(store_path))
    created, _ = repo.create(Run.model_validate(payload), {}, None)
    claimed = repo.claim(created.run.run_id, created.generation)
    run = claimed.run
    ledger = Ledger(run.run_id, run.as_of, clock=lambda: NOW.isoformat().replace("+00:00", "Z"))
    service = ResearchService(Captured(), lambda: NOW, resolver=lambda *a, **kw: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    attention = AttentionAdapter(service, {"AAPL": ArticleMapping(
        "Apple_Inc.", "AAPL", "https://en.wikipedia.org/wiki/Apple_Inc.", True)})
    registry = ToolRegistry()
    for name, (schema, handler) in research_tool_handlers(service, attention=attention).items():
        registry.register(name, schema, handler)
    context = ToolContext(run.run_id, None, "en", run.as_of,
                          SimpleNamespace(as_of=run.as_of), ledger, None, Limits(), None)
    result = registry.execute("researcher", "attention.pageviews", {"ticker": "AAPL"}, context)
    assert result.ok, result.error
    ratio = next(ledger.get_fact(fid) for fid in result.fact_ids
                 if ledger.get_fact(fid).metric == "attention.pageviews_ratio")
    assert abs(ratio.value - 0.8359944473541175) < 1e-12
    assert ratio.verification.status == "verified"
    assert result.data["informational_only"] is True
    assert result.data["flag"] == "normal"
    view = ledger.export()
    updated = run.model_copy(update={"facts": view.facts, "evidence": view.evidence})
    repo.checkpoint(run.run_id, claimed.generation, claimed.owner, claimed.revision, updated,
                    {"ledger": ledger.checkpoint()})
    fresh = RunRepository(FileStore(store_path)).get(run.session_id, run.run_id)
    assert fresh.run.facts[ratio.id].verification.status == "verified"
    assert fresh.run.facts[ratio.id].value == ratio.value
    restored = Ledger.restore(run.run_id, run.as_of, fresh.private["ledger"])
    assert restored.export().digest() == view.digest()
    assert len(view.facts) < 97
