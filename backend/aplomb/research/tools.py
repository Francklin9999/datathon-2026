"""Catalog-compatible model tool bindings with explicit missingness."""
import copy
import json
import math
import re
from collections import OrderedDict
from contextlib import nullcontext
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aplomb.contracts import models as m

from .adapters import AttentionAdapter, EdgarAdapter, ETFAdapter, GdeltAdapter
from .core import ResearchContext, ResearchError
from .numeric import document_ref, fact_input, fact_value, source_evidence


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


# The docstring of each Args model is the tool description the model reads in the JSON schema
# (contracts/tools.md §1): what the tool returns and when to use it.


class FindCompanyArgs(Args):
    """SEC EDGAR company lookup by exact ticker or exact registered name: returns CIK, official name and
    ticker. Use it first to get the CIK the other edgar tools need."""

    name_or_ticker: str = Field(min_length=1, max_length=200)


class ListFilingsArgs(Args):
    """SEC filings of one company (CIK) filed up to the run cutoff: form, filing date, accession and URL.
    Use it before edgar.filing_text, which only reads accessions listed in this run."""

    cik: str = Field(pattern=r"^\d{1,10}$")
    form_types: list[str] = Field(min_length=1, max_length=10)
    since: date | None = None
    limit: int = Field(default=10, ge=1, le=20)


class FilingTextArgs(Args):
    """Passage of one filing listed earlier in this run by edgar.list_filings, starting near the first match
    of query. Untrusted text: save a verbatim quote with research.save_evidence before citing it."""

    accession: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    query: str | None = Field(default=None, max_length=200)
    max_chars: int = Field(default=6000, ge=1, le=6000)


class CompanyFactsArgs(Args):
    """Reported SEC XBRL (us-gaap) values of one concept for one CIK, each registered as a fact with its
    period, filing date and form. Use it for reported figures such as Assets or Revenues."""

    cik: str = Field(pattern=r"^\d{1,10}$")
    concept: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]*$")


class GdeltSearchArgs(Args):
    """GDELT news article discovery in a window of at most 90 days ending no later than the run cutoff:
    title, publisher domain, first-seen date and URL. Discovery only, not verification; the country
    filter is not supported and returns nothing."""

    query: str = Field(min_length=1, max_length=300)
    start: date
    end: date
    country: str | None = Field(default=None, max_length=3)
    limit: int = Field(default=20, ge=1, le=20)


class WebFetchArgs(Args):
    """Text passages of one https page on the reviewed domain allow-list, starting near the first match of
    query. Untrusted text: save a verbatim quote with research.save_evidence before citing it."""

    url: str = Field(max_length=2000)
    query: str | None = Field(default=None, max_length=200)
    max_chars: int = Field(default=6000, ge=1, le=6000)


class PageviewsArgs(Args):
    """Wikipedia attention ratio of one asset: mean daily page views of the last 30 days over the previous
    365, registered as a fact, for a ticker with a reviewed article mapping. Informational only."""

    ticker: str = Field(min_length=1, max_length=20)


class HoldingsArgs(PageviewsArgs):
    """Top constituents and weights of one ETF from its configured, dated issuer holdings file, each weight
    registered as a fact. Partial coverage; identifiers are not resolved to the universe."""

    top_n: int = Field(default=25, ge=1, le=25)


class SaveEvidenceArgs(Args):
    """Save one verbatim quote from a page already fetched in this run (schemas.md Evidence)."""

    type: m.EvidenceType = Field(description="Kind of source document.")
    title: str = Field(max_length=300, description="Title of the source document.")
    publisher: str = Field(max_length=200, description="Publisher as named by the source; the stored publisher comes from the reviewed domain registry.")
    url: str = Field(max_length=2000, description="The url returned by web.fetch or edgar.filing_text earlier in this run.")
    published_at: date | None = Field(default=None, description="Publication date stated by the source (YYYY-MM-DD), if any.")
    quote: str = Field(min_length=1, max_length=400, description="Passage copied verbatim from that page, at most 400 characters.")
    claim: m.I18nText = Field(description="What the quote supports, in English (en) and in French (fr).")
    subject: m.EvidenceSubject = Field(description="What the evidence is about: id is the ticker for an asset, the ISO3 code for a country, "
                                                   "the event ID for an event, or the sector or theme name.")


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


def research_tool_handlers(service, *, gdelt=None, attention=None, etf=None, sec=False):
    """Tool bindings. ``attention.pageviews`` exists only with a verified article mapping and
    ``etf.holdings`` only with an issuer file.

    The four ``edgar.*`` tools exist only with ``sec=True``. The owner removed every SEC source from
    active coverage after HTTP 403 refusals (source catalogue rows SRC-034..SRC-042,
    "removed: owner excluded SEC access-refused sources"), so the application composition does not
    offer them and no research call is spent
    on a refused source. ``sec=True`` is for an accepted SEC access (docs/19-OWNER-ACTIONS.md item 1)
    and for tests."""
    from aplomb.agents.registry import ToolResult
    edgar = EdgarAdapter(service)
    gdelt, attention, etf = gdelt or GdeltAdapter(service=service), attention or AttentionAdapter(service), etf or ETFAdapter(service)

    def context(ctx):
        if getattr(ctx, "historical", False):
            raise ResearchError("research_unavailable_in_replay")
        rc = getattr(ctx, "research_context", None)
        if rc is None:
            # Research facts cite the snapshot the run is pinned to, as stated by its gate.
            pinned = getattr(getattr(ctx, "gate", None), "data_version", None)
            rc = ResearchContext(ctx.run_id, date.fromisoformat(str(ctx.as_of)), **({"data_version": pinned} if pinned else {}))
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

    def company_facts(ctx, **kw):
        rc = context(ctx)
        units, document = edgar.company_facts(context=rc, **kw)
        figures, fact_ids, unavailable = [], [], []
        # Bound output by selecting up to five latest filed records for each recognized currency.
        for source_unit, rows in units.items():
            unit = {"USD": "usd", "CAD": "cad"}.get(source_unit)
            if unit is None:
                unavailable.append({"source_unit": source_unit, "reason": "unsupported_explicit_unit"})
                continue
            selected = []
            if not isinstance(rows, list):
                unavailable.append({"source_unit": source_unit, "reason": "invalid_source_rows"})
                continue
            for index, row in enumerate(rows):
                try:
                    if not isinstance(row, dict):
                        continue
                    filed = date.fromisoformat(row["filed"])
                    end = date.fromisoformat(row["end"])
                    start = date.fromisoformat(row.get("start", row["end"]))
                    accession, form = row["accn"], row["form"]
                    if (not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
                            or not isinstance(form, str) or not re.fullmatch(r"[A-Za-z0-9/-]{1,20}", form)
                            or start > end or end > filed or filed > rc.as_of):
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                selected.append((index, row))
            selected.sort(key=lambda item: (item[1]["filed"], item[1]["end"]), reverse=True)
            for index, row in selected[:5]:
                value = row.get("val")
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    unavailable.append({"source_unit": source_unit, "reason": "invalid_source_value"})
                    continue
                fact = fact_input(document, rc, value=value, unit=unit, subject_id=kw["cik"].zfill(10),
                                  variant=f"{kw['concept']}:{source_unit}:{index}:{document.document_id}", label=kw["concept"])
                fact_id = ctx.ledger.add_source_fact(fact, document_ref(document), {
                    "format": "sec_companyfacts", "concept": kw["concept"], "unit": source_unit, "row_index": index})
                fact_ids.append(fact_id)
                figures.append({"concept": kw["concept"], "figure": fact_value(ctx.ledger, fact_id),
                                "source_unit": source_unit, "period_start": row.get("start"),
                                "period_end": row["end"], "filed": row["filed"], "form": row.get("form"),
                                "accession": row.get("accn")})
        evidence_ids = [source_evidence(service, document, rc, ctx.ledger, type="filing",
                         title="SEC company facts source", subject_id=kw["cik"].zfill(10))] if figures else []
        return ToolResult(True, "Verified structured SEC reported figures" if figures else "No supported visible figures",
                          fact_ids=fact_ids, evidence_ids=evidence_ids, data={
            "document_ref": document.document_id, "available_units": list(units), "figures": figures,
            "unavailable": unavailable, "reason": "verified_source_records" if figures else "no_supported_visible_figures",
            "evidence_gap": not bool(figures)})

    def pageviews(ctx, **kw):
        rc = context(ctx)
        result, document = attention.pageviews(context=rc, **kw)
        ratio = result.pop("ratio", None)
        if ratio is None:
            return ToolResult(True, result["reason"], data=result)
        fact = fact_input(document, rc, value=ratio, unit="ratio", subject_id=result["article"], subject_type="event",
                          variant=document.document_id, label="Wikipedia daily pageview attention ratio",
                          metric="attention.pageviews_ratio", limitations=["LIM_ATTENTION_PROXY"])
        fact_id = ctx.ledger.add_pageviews_ratio(fact, document_ref(document), article=result["article"])
        result["ratio"] = fact_value(ctx.ledger, fact_id)
        evidence_id = source_evidence(service, document, rc, ctx.ledger, type="attention",
                                      title="Wikimedia daily pageviews", subject_id=kw["ticker"])
        result.update(fact_id=fact_id, evidence_id=evidence_id, informational_only=True)
        return ToolResult(True, "Verified complete daily pageview ratio; informational only", fact_ids=[fact_id],
                          evidence_ids=[evidence_id], data=result)

    def holdings(ctx, **kw):
        rc = context(ctx)
        result, document = etf.holdings(context=rc, **kw)
        config = etf.files[kw["ticker"]]
        fact_ids = []
        for row in result["holdings"]:
            value = row.pop("weight_pct")
            fact = fact_input(document, rc, value=value, unit="pct", subject_id=row["identifier"],
                              variant=f"etf:{kw['ticker']}:{config.effective_date}:{document.document_id}",
                              label=f"{kw['ticker']} issuer weight of {row['identifier']}")
            fact_id = ctx.ledger.add_source_fact(fact, document_ref(document), {
                "format": "issuer_holdings_csv", "identifier": row["identifier"],
                "effective_date": str(config.effective_date), "identifier_column": config.identifier_column,
                "weight_column": "Weight (%)"})
            fact_ids.append(fact_id)
            row["weight_pct"] = fact_value(ctx.ledger, fact_id)
        evidence_id = source_evidence(service, document, rc, ctx.ledger, type="fund_document",
                                     title=f"{kw['ticker']} issuer holdings source", subject_id=kw["ticker"])
        result.update(document_ref=document.document_id, reason="verified_source_records")
        return ToolResult(True, "Verified dated issuer weights; partial coverage", fact_ids=fact_ids,
                          evidence_ids=[evidence_id], data=result)

    bindings = {
        "gdelt.search": (GdeltSearchArgs, gdelt_search), "web.fetch": (WebFetchArgs, fetch),
        "research.save_evidence": (SaveEvidenceArgs, save),
    }
    if sec:
        bindings.update({
            "edgar.find_company": (FindCompanyArgs, find), "edgar.list_filings": (ListFilingsArgs, filings),
            "edgar.filing_text": (FilingTextArgs, filing), "edgar.company_facts": (CompanyFactsArgs, company_facts),
        })
    # Without reviewed configuration (a verified ticker-to-article mapping, a dated issuer file) these
    # two tools can only answer an evidence gap; they are not offered, so no research call is spent on them.
    if any(mp.verified and mp.evidence_url and mp.entity_id for mp in getattr(attention, "mappings", {}).values()):
        bindings["attention.pageviews"] = (PageviewsArgs, pageviews)
    if getattr(etf, "files", None):
        bindings["etf.holdings"] = (HoldingsArgs, holdings)

    # Results per run ID: the workflow hands every tool call a copy of the run ledger, so the
    # ledger object cannot be the key. Each entry keeps the facts and evidence it registered; a
    # hit requires the ledger at hand to hold exactly those, which rejects an entry written by a
    # timed-out call whose ledger copy was discarded.
    completed: OrderedDict = OrderedDict()

    def guarded(name, fn):
        def run(ctx, **kw):
            try:
                rc = context(ctx)
                ledger = getattr(ctx, "ledger", None)
                cache_key = (name, rc.run_id, str(rc.as_of), rc.mode, rc.data_version,
                             str(service.clock().date()), json.dumps(kw, sort_keys=True, default=str))
                prior = completed.get(rc.run_id, {}) if ledger is not None else {}
                if cache_key in prior:
                    cached, facts, evidence = prior[cache_key]
                    view = ledger.export()
                    if all(view.facts.get(fid) == fact for fid, fact in facts.items()) and all(
                        view.evidence.get(eid) == item for eid, item in evidence.items()
                    ):
                        return copy.deepcopy(cached)
                # Source/document caches may survive failure; ledger facts/evidence are atomic.
                with ledger.transaction() if ledger is not None else nullcontext():
                    result = fn(ctx, **kw)
                if result.ok and ledger is not None:
                    view = ledger.export()
                    completed.setdefault(rc.run_id, {})[cache_key] = (
                        copy.deepcopy(result), {fid: view.facts[fid] for fid in result.fact_ids},
                        {eid: view.evidence[eid] for eid in result.evidence_ids})
                    completed.move_to_end(rc.run_id)
                    while len(completed) > 256:
                        completed.popitem(last=False)
                return result
            except ValidationError as exc:
                # A malformed shape is the caller's to correct; it is not a source outage.
                first = exc.errors()[0]
                where = ".".join(str(part) for part in first["loc"])
                return ToolResult(False, "Invalid research tool arguments; nothing was saved",
                                  error=f"validation_error: {where}: {first['msg']}"[:300])
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ResearchError) else "source_unavailable"
                return ToolResult(False, "Research unavailable; evidence gap remains", error=reason)
        return run
    return {name: (schema, guarded(name, fn)) for name, (schema, fn) in bindings.items()}
