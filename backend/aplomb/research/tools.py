"""Catalog-compatible model tool bindings with explicit missingness."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from .adapters import AttentionAdapter, EdgarAdapter, ETFAdapter, GdeltAdapter
from .core import ResearchContext, ResearchError


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindCompanyArgs(Args):
    name_or_ticker: str = Field(min_length=1, max_length=200)


class ListFilingsArgs(Args):
    cik: str = Field(pattern=r"^\d{1,10}$")
    form_types: list[str] = Field(min_length=1, max_length=10)
    since: date | None = None
    limit: int = Field(default=10, ge=1, le=20)


class FilingTextArgs(Args):
    accession: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    query: str | None = Field(default=None, max_length=200)
    max_chars: int = Field(default=6000, ge=1, le=6000)


class CompanyFactsArgs(Args):
    cik: str = Field(pattern=r"^\d{1,10}$")
    concept: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]*$")


class GdeltSearchArgs(Args):
    query: str = Field(min_length=1, max_length=300)
    start: date
    end: date
    country: str | None = Field(default=None, max_length=3)
    limit: int = Field(default=20, ge=1, le=20)


class WebFetchArgs(Args):
    url: str = Field(max_length=2000)
    query: str | None = Field(default=None, max_length=200)
    max_chars: int = Field(default=6000, ge=1, le=6000)


class WebBrowseArgs(Args):
    task: str = Field(max_length=1000)
    start_url: str | None = None
    max_pages: int = Field(default=5, ge=1, le=5)


class PageviewsArgs(Args):
    ticker: str = Field(min_length=1, max_length=20)


class HoldingsArgs(PageviewsArgs):
    top_n: int = Field(default=25, ge=1, le=25)


class SaveEvidenceArgs(Args):
    type: str
    title: str = Field(max_length=300)
    publisher: str = Field(max_length=200)
    url: str = Field(max_length=2000)
    published_at: date | None = None
    quote: str = Field(min_length=1, max_length=400)
    claim: dict[str, str]
    subject: dict[str, str]


def passages(document, query=None, max_chars=6000):
    from .core import normalize
    text = normalize(document.text)
    start = text.casefold().find(query.casefold()) if query else 0
    if start < 0:
        return {"document_ref": document.document_id, "url": document.canonical_url,
                "passages": [], "reason": "no_matching_passage"}
    start = max(0, start - 100)
    excerpt = text[start:start + max_chars]
    # Offsets internal only: model numeric values must be facts; passage text remains untrusted.
    return {"document_ref": document.document_id, "url": document.canonical_url,
            "retrieved_at": document.retrieved_at.isoformat(), "from_cache": document.from_cache,
            "content_hash": document.content_hash, "published_at": None,
            "passages": [{"text": excerpt, "offset_ref": f"normalized:{start}:{start + len(excerpt)}"}],
            "source_warning": "Untrusted source text; claims require saved verified quotes"}


def research_tool_handlers(service, *, gdelt=None, attention=None, etf=None):
    from aplomb.agents.registry import ToolResult
    edgar = EdgarAdapter(service)
    gdelt, attention, etf = gdelt or GdeltAdapter(), attention or AttentionAdapter(service), etf or ETFAdapter(service)

    def context(ctx):
        if getattr(ctx, "historical", False):
            raise ResearchError("research_unavailable_in_replay")
        rc = getattr(ctx, "research_context", None)
        if rc is None:
            rc = ResearchContext(ctx.run_id, date.fromisoformat(str(ctx.as_of)))
        if rc.run_id != ctx.run_id or str(rc.as_of) != str(ctx.as_of):
            raise ResearchError("research_context_mismatch")
        rc.allow()
        return rc

    def search_result(result):
        return ToolResult(True, result.reason, data={"items": list(result.items), "reason": result.reason,
                          "coverage": result.coverage, "document_ref": result.document_ref,
                          "evidence_gap": True})

    def find(ctx, **kw):
        return search_result(edgar.search(kw["name_or_ticker"], context(ctx)))

    def filings(ctx, **kw):
        return search_result(edgar.list_filings(context=context(ctx), **kw))

    def filing(ctx, accession, query=None, max_chars=6000):
        return ToolResult(True, "Fetched filing; save a quote before citing", data=passages(edgar.filing_text(accession, context(ctx)), query, max_chars))

    def fetch(ctx, url, query=None, max_chars=6000):
        return ToolResult(True, "Fetched public page; save a quote before citing", data=passages(service.fetch(url, context(ctx)), query, max_chars))

    def gdelt_search(ctx, **kw):
        if kw["start"] > kw["end"] or kw["end"] > context(ctx).as_of:
            raise ResearchError("invalid_search_window")
        return search_result(gdelt.search(context=context(ctx), **kw))

    def save(ctx, **kw):
        rc = context(ctx)
        document = service.documents.get((rc.run_id, kw["url"]))
        if document is None:
            raise ResearchError("document_not_fetched_in_run")
        evidence_id = service.save_evidence(kw, document.document_id, rc, ctx.ledger)
        return ToolResult(True, "Verified same-run quote saved", evidence_ids=[evidence_id], data={"evidenceId": evidence_id})

    def unsupported_browser(ctx, **kw):
        context(ctx)
        return ToolResult(False, "Browser adapter disabled pending navigation capture", error="browser_disabled")

    def company_facts(ctx, **kw):
        units, document = edgar.company_facts(context=context(ctx), **kw)
        # The source is captured, but ambiguous XBRL unit semantics are never guessed.
        return ToolResult(True, "Captured company facts; explicit sourced unit verification required", data={
            "document_ref": document.document_id, "available_units": list(units),
            "figures": [], "reason": "numeric_quote_verification_required", "evidence_gap": True})

    def pageviews(ctx, **kw):
        result, document = attention.pageviews(context=context(ctx), **kw)
        # Until ledger has a verified series-derivation registration path, do not expose untagged ratio.
        ratio = result.pop("ratio", None)
        if ratio is not None:
            result["flag"] = "unknown"
            result["reason"] = "fact_registration_required"
        return ToolResult(True, result["reason"], data=result)

    def holdings(ctx, **kw):
        result, document = etf.holdings(context=context(ctx), **kw)
        for row in result["holdings"]:
            row.pop("weight_pct")
        result.update(document_ref=document.document_id, reason="weight_fact_registration_required")
        return ToolResult(True, "Issuer identities captured; weight facts unavailable", data=result)

    bindings = {
        "edgar.find_company": (FindCompanyArgs, find), "edgar.list_filings": (ListFilingsArgs, filings),
        "edgar.filing_text": (FilingTextArgs, filing), "edgar.company_facts": (CompanyFactsArgs, company_facts),
        "gdelt.search": (GdeltSearchArgs, gdelt_search), "web.fetch": (WebFetchArgs, fetch),
        "web.browse": (WebBrowseArgs, unsupported_browser), "attention.pageviews": (PageviewsArgs, pageviews),
        "etf.holdings": (HoldingsArgs, holdings), "research.save_evidence": (SaveEvidenceArgs, save),
    }

    def guarded(fn):
        def run(ctx, **kw):
            try:
                return fn(ctx, **kw)
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ResearchError) else "source_unavailable"
                return ToolResult(False, "Research unavailable; evidence gap remains", error=reason)
        return run
    return {name: (schema, guarded(fn)) for name, (schema, fn) in bindings.items()}
