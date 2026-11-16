"""Which research tools the registry offers and what the model is told about them (no network)."""
from datetime import datetime, timezone
from types import SimpleNamespace

from aplomb.agents.limits import Limits
from aplomb.agents.registry import RESEARCH, ToolContext
from aplomb.api.runtime import build_registry
from aplomb.api.settings import Settings
from aplomb.ledger import Ledger
from aplomb.research import (
    ArticleMapping,
    AttentionAdapter,
    ETFAdapter,
    HoldingsFile,
    ResearchService,
    research_tool_handlers,
)

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
AS_OF = "2026-11-14"
CONTACT = "Aplomb test (+https://example.org/contact)"
MAPPING = ("Apple_Inc.", "AAPL", "https://en.wikipedia.org/wiki/Apple_Inc.")


class NoTransport:
    def get(self, url, **kwargs):
        raise AssertionError("no network in this test")


def service():
    return ResearchService(NoTransport(), lambda: NOW)


def context(**kw):
    return ToolContext("RUN-registration", None, "en", AS_OF, SimpleNamespace(as_of=AS_OF), None, None, Limits(), None,
                       **kw)


def test_attention_and_holdings_are_offered_only_with_reviewed_configuration():
    svc = service()
    assert {"attention.pageviews", "etf.holdings"}.isdisjoint(research_tool_handlers(svc))
    unverified = AttentionAdapter(svc, {"AAPL": ArticleMapping(*MAPPING)})
    assert "attention.pageviews" not in research_tool_handlers(svc, attention=unverified)
    verified = AttentionAdapter(svc, {"AAPL": ArticleMapping(*MAPPING, verified=True)})
    holdings = ETFAdapter(svc, {"IVV": HoldingsFile("https://www.ishares.com/file", NOW.date())})
    assert {"attention.pageviews", "etf.holdings"} <= set(research_tool_handlers(svc, attention=verified, etf=holdings))


def test_application_registry_offers_no_unusable_research_tool_and_describes_each_one():
    registry = build_registry(Settings(source_user_agent=CONTACT), world=SimpleNamespace())
    schemas = registry.schemas(RESEARCH)
    names = {item["name"] for item in schemas}
    assert {"web.fetch", "research.save_evidence", "world.search_events"} <= names
    # SEC sources were removed by the owner (source_dispositions SRC-034..042); facilities need their flag.
    assert {"attention.pageviews", "etf.holdings", "emissions.facilities"}.isdisjoint(names)
    assert not {name for name in names if name.startswith("edgar.")}
    for item in schemas:
        assert item["schema"].get("description", "").strip(), f"{item['name']} has no description for the model"


def test_sec_tools_are_bound_only_on_request():
    assert not {name for name in research_tool_handlers(service()) if name.startswith("edgar.")}
    assert {"edgar.find_company", "edgar.list_filings", "edgar.filing_text", "edgar.company_facts"} <= set(
        research_tool_handlers(service(), sec=True))


def registry_world():
    """A world service whose facilities method is the real one over the packaged capture."""
    from aplomb.world.service import WorldServiceImpl

    class World:
        def search_events(self, **kwargs):
            return []

        def facilities(self, session_id, query):
            # The real service method; it reads only the packaged capture without a profileId.
            return WorldServiceImpl.facilities(self, session_id, query)

    return World()


def facility_registry(as_of):
    """The application registry with the facilities flag, over the packaged facility capture."""
    settings = Settings(features={"world_layer_facilities": True})
    registry = build_registry(settings, world=registry_world())
    ledger = Ledger("RUN-facilities", as_of, clock=lambda: NOW.isoformat().replace("+00:00", "Z"))
    ctx = ToolContext("RUN-facilities", None, "en", as_of, SimpleNamespace(as_of=as_of), ledger, None, Limits(), None)
    return registry, ctx, ledger


def test_facility_emissions_are_registered_facts_with_the_capture_as_availability():
    from aplomb.world.facilities import load_facilities

    _, meta = load_facilities()
    as_of = meta["capturedAt"][:10]
    registry, ctx, ledger = facility_registry(as_of)
    schema = registry.schemas(RESEARCH)
    assert "emissions.facilities" in {item["name"] for item in schema}
    result = registry.execute("researcher", "emissions.facilities", {"ticker_or_operator": "suncor"}, ctx)
    assert result.ok, result.error
    rows = result.data["facilities"]
    assert rows and len(rows) <= 10 and result.data["matched"] >= len(rows)
    assert all("suncor" in (row["name"] + " " + row["reportingCompany"]).casefold() for row in rows)
    assert result.fact_ids == [row["emissionsTco2e"]["factId"] for row in rows]
    for row in rows:
        fact = ledger.get_fact(row["emissionsTco2e"]["factId"])
        assert fact.metric == "emissions.facility_total" and fact.verification.status == "verified"
        assert fact.value == row["emissionsTco2e"]["value"] and fact.unit == "count"
        assert (fact.subject.type, fact.subject.id, fact.subject.variant) == ("country", "CAN", row["facilityId"])
        assert fact.available_at == meta["capturedAt"] and fact.sources[0].data_version == meta["dataVersion"]
    assert ctx.limits.research_calls == 1


def test_facility_capture_after_the_cutoff_is_not_offered_and_spends_no_research_call():
    # Review 2026-11-15: decision and brief runs (cutoff 2026-11-12, before the 2026-11-15 capture)
    # were offered the tool and charged a research call for a guaranteed evidence gap.
    from aplomb.api.runtime import facilities_tool

    registry, ctx, ledger = facility_registry("2026-11-12")
    assert "emissions.facilities" in {item["name"] for item in registry.schemas(RESEARCH)}
    assert "emissions.facilities" not in {item["name"] for item in registry.schemas(RESEARCH, ctx)}
    result = registry.execute("researcher", "emissions.facilities", {"ticker_or_operator": "suncor"}, ctx)
    assert not result.ok and ctx.limits.research_calls == 0
    assert ledger.export().facts == {}
    # The handler keeps its own cutoff check as a second safeguard.
    _, handler = facilities_tool(registry_world())
    gap = handler(ctx, "suncor")
    assert not gap.ok and gap.error == "facility_capture_after_cutoff"


def test_facility_arguments_are_validated_when_the_capture_is_known():
    from aplomb.world.facilities import load_facilities

    registry, ctx, _ = facility_registry(load_facilities()[1]["capturedAt"][:10])
    refused = registry.execute("researcher", "emissions.facilities", {"ticker_or_operator": "x", "country": "Canada"}, ctx)
    assert not refused.ok and "country" in refused.error


def test_every_research_binding_carries_a_description():
    svc = service()
    handlers = research_tool_handlers(
        svc, sec=True,
        attention=AttentionAdapter(svc, {"AAPL": ArticleMapping(*MAPPING, verified=True)}),
        etf=ETFAdapter(svc, {"IVV": HoldingsFile("https://www.ishares.com/file", NOW.date())}))
    for name, (schema, _) in handlers.items():
        assert (schema.model_json_schema().get("description") or "").strip(), name


def test_world_search_events_hands_the_historical_mode_to_the_service():
    calls = []

    class World:
        def search_events(self, **kwargs):
            calls.append(kwargs)
            return []

    registry = build_registry(Settings(), world=World())
    ctx = context()
    parsed, function = registry.validate("researcher", "world.search_events", {"q": "rate"}, ctx)
    assert function(ctx, **parsed.model_dump()).ok
    ctx.historical = True
    function(ctx, **parsed.model_dump())
    assert [(call["as_of"], call["historical"]) for call in calls] == [(AS_OF, False), (AS_OF, True)]
