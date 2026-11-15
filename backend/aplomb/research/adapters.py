"""Source-specific parsers. Discovery never asserts absence of controversy."""
import csv
import io
import ipaddress
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlsplit

from .core import ResearchError


@dataclass(frozen=True)
class SearchResult:
    items: tuple[dict, ...]
    reason: str
    document_ref: str | None = None
    coverage: str = "partial; cannot establish absence of controversy"


class EdgarAdapter:
    def __init__(self, service):
        self.service, self.filings = service, {}

    def search(self, query, context):
        data, doc = self.service.json("https://www.sec.gov/files/company_tickers.json", context)
        query = query.strip().casefold()
        rows = [row for row in data.values() if query in (row["ticker"].casefold(), row["title"].casefold())]
        return SearchResult(tuple({"cik": str(r["cik_str"]).zfill(10), "name": r["title"], "ticker": r["ticker"]} for r in rows), "results" if rows else "no_results", doc.document_id)

    def list_filings(self, cik, form_types, context, since=None, limit=10):
        if not re.fullmatch(r"\d{1,10}", cik):
            raise ResearchError("invalid_cik")
        data, doc = self.service.json(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json", context)
        rows = data["filings"]["recent"]
        result = []
        for index, form in enumerate(rows["form"]):
            filed = rows["filingDate"][index]
            if form not in form_types or filed > str(context.as_of) or (since and filed < str(since)):
                continue
            accession = rows["accessionNumber"][index]
            primary = rows["primaryDocument"][index]
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(r"[A-Za-z0-9_.-]+", primary):
                continue
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary}"
            item = {"form": form, "filed": filed, "accession": accession, "url": url}
            self.filings[(context.run_id, accession)] = item
            result.append(item)
        return SearchResult(tuple(result[:limit]), "results" if result else "no_results", doc.document_id)

    def filing_text(self, accession, context):
        filing = self.filings.get((context.run_id, accession))
        if not filing:
            raise ResearchError("accession_requires_same_run_list_filings")
        return self.service.fetch(filing["url"], context)

    def company_facts(self, cik, concept, context):
        if not re.fullmatch(r"\d{1,10}", cik) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", concept):
            raise ResearchError("invalid_cik_or_concept")
        data, doc = self.service.json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json", context)
        if not isinstance(data, dict) or type(data.get("cik")) is not int or str(data["cik"]).zfill(10) != cik.zfill(10):
            raise ResearchError("source_cik_mismatch")
        units = data.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {})
        if not isinstance(units, dict):
            raise ResearchError("invalid_source_json")
        # Raw numbers are internal only; bindings require explicit quote.figure registration.
        return units, doc


class GdeltAdapter:
    """Cached batch only: no unverified live search quota or article claims."""
    def __init__(self, batches=None):
        self.batches = batches if batches is not None else {}

    def search(self, query, context, start, end, country=None, limit=20):
        context.allow()
        batch = self.batches.get((query.strip().casefold(), str(start), str(end), country))
        if batch is None:
            return SearchResult((), "cached_index_unavailable")
        # Cached indices are untrusted too: never expose future or undated rows, unsafe
        # links, or duplicates, even if the batch was stored under an incorrect key.
        try:
            first, last = date.fromisoformat(str(start)), date.fromisoformat(str(end))
        except ValueError as exc:
            raise ResearchError("invalid_search_window") from exc
        if first > last or last > context.as_of:
            raise ResearchError("invalid_search_window")
        articles, seen = [], set()
        for row in batch.get("articles", []):
            if not isinstance(row, dict):
                continue
            title, url, domain, stamp = (row.get(k) for k in ("title", "url", "domain", "seendate"))
            if not all(isinstance(v, str) and v.strip() for v in (title, url, domain, stamp)):
                continue
            try:
                if not re.fullmatch(r"\d{8}T\d{6}Z", stamp):
                    continue
                observed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").date()
                parsed = urlsplit(url)
                host = (parsed.hostname or "").lower().rstrip(".")
                if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                        or parsed.port not in (None, 443) or host == "localhost" or host.endswith(".localhost")):
                    continue
                try:
                    if not ipaddress.ip_address(host).is_global:
                        continue
                except ValueError:
                    pass  # DNS names are discovery links, never fetched by this adapter.
                from aplomb.world.ingest import canonical_url
                identity = canonical_url(url)
            except ValueError:
                continue
            if not first <= observed <= last or identity in seen:
                continue
            seen.add(identity)
            articles.append({"title": title, "url": url, "publisher": domain,
                             "published_at": None, "first_seen_at": stamp, "claim_verified": False})
            if len(articles) >= limit:
                break
        return SearchResult(tuple(articles), "results" if articles else "no_results", batch.get("document_ref"))


@dataclass(frozen=True)
class ArticleMapping:
    article: str
    entity_id: str
    evidence_url: str
    verified: bool = False


class AttentionAdapter:
    def __init__(self, service, mappings=None):
        self.service, self.mappings = service, mappings or {}

    @staticmethod
    def calculate(items, as_of):
        first = as_of - timedelta(days=395)
        expected = {first + timedelta(days=i) for i in range(395)}
        values = {}
        for item in items:
            try:
                day = date.fromisoformat(item["timestamp"][:4] + "-" + item["timestamp"][4:6] + "-" + item["timestamp"][6:8])
                value = item["views"]
                if day in values or isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    return None, "invalid_daily_coverage"
                values[day] = value
            except (KeyError, ValueError, TypeError):
                return None, "invalid_daily_coverage"
        if set(values) != expected:
            return None, "incomplete_daily_coverage"
        split = as_of - timedelta(days=30)
        baseline = sum(value for day, value in values.items() if day < split) / 365
        if baseline <= 0:
            return None, "zero_baseline"
        return (sum(value for day, value in values.items() if day >= split) / 30) / baseline, "complete"

    def pageviews(self, ticker, context):
        context.allow()
        mapping = self.mappings.get(ticker)
        if not mapping or not mapping.verified or not mapping.evidence_url or not mapping.entity_id:
            return {"flag": "unknown", "reason": "unverified_article_mapping"}, None
        start, end = context.as_of - timedelta(days=395), context.as_of - timedelta(days=1)
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/"
               f"{quote(mapping.article, safe='')}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00")
        data, document = self.service.json(url, context)
        items = data.get("items", [])
        if any(row.get("project") != "en.wikipedia" or row.get("access") != "all-access" or row.get("agent") != "user" for row in items):
            ratio, reason = None, "unexpected_dimensions"
        else:
            ratio, reason = self.calculate(items, context.as_of)
        return {"ticker": ticker, "article": mapping.article, "ratio": ratio,
                "flag": "unknown" if ratio is None else "elevated" if ratio >= 2 else "normal",
                "reason": reason, "recent_start": str(context.as_of - timedelta(days=30)),
                "recent_end": str(end), "baseline_start": str(start),
                "baseline_end": str(context.as_of - timedelta(days=31)),
                "mapping_evidence": mapping.evidence_url, "project": "en.wikipedia.org",
                "access": "all-access", "agent": "user"}, document


@dataclass(frozen=True)
class HoldingsFile:
    url: str
    effective_date: date
    identifier_column: str = "Ticker"


class ETFAdapter:
    def __init__(self, service, files=None):
        self.service, self.files = service, files or {}

    def holdings(self, ticker, context, top_n=25):
        context.allow()
        config = self.files.get(ticker)
        if not config:
            raise ResearchError("issuer_file_not_configured")
        if config.effective_date > context.as_of:
            raise ResearchError("holdings_date_after_asof")
        document = self.service.fetch(config.url, context)
        lines = document.text.splitlines()
        header = next((i for i, line in enumerate(lines) if line.startswith("Ticker,") or line.startswith('"Ticker",')), None)
        if header is None or str(config.effective_date) not in document.text:
            raise ResearchError("holdings_date_or_header_unverified")
        holdings = []
        for row in csv.DictReader(io.StringIO("\n".join(lines[header:]))):
            identifier, weight = row.get(config.identifier_column), row.get("Weight (%)")
            if not identifier or weight is None:
                continue
            try:
                value = float(weight)
            except ValueError:
                continue
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ResearchError("invalid_weight")
            holdings.append({"identifier": identifier, "name": row.get("Name", ""), "weight_pct": value})
        if not holdings:
            raise ResearchError("no_holdings")
        return {"holdings": holdings[:top_n], "effective_date": str(config.effective_date),
                "partial_coverage": True, "coverage_note": "Top subset; identifiers not resolved to universe; no rule changes"}, document
