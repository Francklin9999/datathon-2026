"""Exact-CIK SEC company research. Reporting periods never imply publication dates.

Sections (overview/company, financial statements, filings, insider transactions,
institutional holdings) are captured independently: one unavailable or access-denied
source never hides the others, and nothing is inferred for a missing section.
"""

import hashlib
import math
import re
from datetime import date, datetime, timezone

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write
from aplomb.ledger import Ledger
from aplomb.ledger.sources import strict_json

from .core import ResearchContext, ResearchError
from .numeric import document_ref, fact_input

# (taxonomy, concept). Only us-gaap USD/CAD rows are independently re-verified by the ledger.
CONCEPTS = (
    ("us-gaap", "Revenues"), ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "GrossProfit"), ("us-gaap", "OperatingIncomeLoss"), ("us-gaap", "NetIncomeLoss"),
    ("us-gaap", "EarningsPerShareBasic"), ("us-gaap", "EarningsPerShareDiluted"),
    ("us-gaap", "Assets"), ("us-gaap", "Liabilities"), ("us-gaap", "StockholdersEquity"),
    ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"), ("us-gaap", "LongTermDebtNoncurrent"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
    ("dei", "EntityCommonStockSharesOutstanding"),
)
UNITS = ("USD", "CAD", "USD/shares", "CAD/shares", "shares")
LEDGER_UNITS = ("USD", "CAD")
ROWS_PER_CONCEPT_UNIT = 6
FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A", "20-F", "20-F/A", "40-F",
                   "6-K", "4", "4/A", "13F-HR", "13F-HR/A", "NPORT-P", "NPORT-P/A", "DEF 14A"})
INSIDER_FORMS = ("4", "4/A")
HOLDINGS_FORMS = ("13F-HR", "13F-HR/A")
MAX_INSIDER_FILINGS = 5
MAX_INFOTABLE_CANDIDATES = 2
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
# EDGAR lists Form 3/4/5 primary documents through an XSL rendering directory
# (e.g. "xslF345X05/form4.xml"); the raw XML sits at the bare file name.
PRIMARY = re.compile(r"(?:(xsl[A-Za-z0-9]{1,20})/)?([A-Za-z0-9_.-]{1,200})")
# Error codes are a closed vocabulary: provider messages never reach the client.
SAFE_CODES = frozenset({"rate_limited", "request_timeout", "response_too_large", "source_unavailable",
                        "unsupported_content_type", "domain_not_allowlisted", "dns_unavailable", "dns_timeout",
                        "unsafe_or_oversized_disclosure_xml", "invalid_disclosure_xml", "source_cik_mismatch",
                        "disclosure_issuer_cik_mismatch", "not_form_four", "not_form_13f_information_table",
                        "information_table_not_found", "redirect_or_retry_limit"})
SEC_LICENCE = "SEC public EDGAR records; third-party filing rights may apply"


def cik_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value) or int(value) == 0:
        raise ValueError("CIK must be a nonzero SEC numeric identifier")
    return value.zfill(10)


def _archive(cik, accession, name):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{name}"


def _accepted(value):
    """SEC acceptanceDateTime -> ISO UTC, or None when absent/unparseable (never guessed)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def submissions(data, cik, as_of):
    cik = cik_id(cik)
    if type(data.get("cik")) not in (str, int) or str(data["cik"]).zfill(10) != cik:
        raise ResearchError("source_cik_mismatch")
    recent = data.get("filings", {}).get("recent", {})
    fields = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if any(not isinstance(recent.get(k), list) for k in fields):
        raise ResearchError("invalid_submissions_arrays")
    size = len(recent["form"])
    if size > 20000 or any(len(recent[k]) != size for k in fields):
        raise ResearchError("inconsistent_submissions_arrays")
    optional = {k: recent[k] for k in ("acceptanceDateTime", "primaryDocDescription", "items")
                if isinstance(recent.get(k), list) and len(recent[k]) == size}
    rows, skipped = [], 0
    for i in range(size):
        form = recent["form"][i]
        if form not in FORMS:
            continue
        filed = str(date.fromisoformat(recent["filingDate"][i]))
        report = str(date.fromisoformat(recent["reportDate"][i])) if recent["reportDate"][i] else None
        if filed > as_of:
            continue
        accession, primary = recent["accessionNumber"][i], recent["primaryDocument"][i]
        if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
            raise ResearchError("unsafe_filing_identifier")
        match = PRIMARY.fullmatch(primary) if isinstance(primary, str) else None
        if match is None or match[2] in (".", ".."):
            skipped += 1  # counted, never silently repaired
            continue
        description = optional.get("primaryDocDescription", [None] * size)[i]
        rows.append({"form": form, "accession": accession, "filed": filed, "period_end": report,
                     "accepted_at": _accepted(optional.get("acceptanceDateTime", [None] * size)[i]),
                     "available_at": filed + "T23:59:59Z",
                     "description": description[:200] if isinstance(description, str) and description else None,
                     "items": optional.get("items", [None] * size)[i] or None,
                     "url": _archive(cik, accession, primary),
                     "raw_document_url": _archive(cik, accession, match[2]),
                     "index_url": _archive(cik, accession, accession + "-index.htm")})
    rows.sort(key=lambda r: (r["filed"], r["accepted_at"] or "", r["accession"]), reverse=True)
    tickers = data.get("tickers") if isinstance(data.get("tickers"), list) else []
    exchanges = data.get("exchanges") if isinstance(data.get("exchanges"), list) else []
    return {"cik": cik, "name": data.get("name"), "sic": data.get("sic"),
            "sic_description": data.get("sicDescription"), "entity_type": data.get("entityType"),
            "incorporation": data.get("stateOfIncorporation"),
            "fiscal_year_end": data.get("fiscalYearEnd") if isinstance(data.get("fiscalYearEnd"), str) else None,
            "filer_category": data.get("category") if isinstance(data.get("category"), str) else None,
            "reported_tickers": [t for t in tickers[:20] if isinstance(t, str)],
            "reported_exchanges": [e for e in exchanges[:20] if isinstance(e, str)],
            "ticker_identity_note": "SEC-reported tickers are labels; the CIK is the identity key.",
            "filings": rows[:40], "skipped_unrecognized_documents": skipped,
            "is_13f_filer": any(r["form"] in HOLDINGS_FORMS for r in rows),
            "disclosure_candidates": {
                "form4": [r for r in rows if r["form"] in INSIDER_FORMS
                          and r["raw_document_url"].endswith(".xml")][:MAX_INSIDER_FILINGS],
                "form13f": [r for r in rows if r["form"] in HOLDINGS_FORMS][:1]},
            "coverage": "Recent submissions only; older filing archives not requested."}


def statements(data, cik, as_of):
    if type(data.get("cik")) is not int or str(data["cik"]).zfill(10) != cik_id(cik):
        raise ResearchError("source_cik_mismatch")
    result = []
    for taxonomy, concept in CONCEPTS:
        source = data.get("facts", {}).get(taxonomy, {}).get(concept, {})
        for unit, rows in source.get("units", {}).items():
            if unit not in UNITS:
                continue
            if not isinstance(rows, list) or len(rows) > 50000:
                raise ResearchError("invalid_companyfacts_rows")
            candidates = []
            for index, row in enumerate(rows):
                filed, end = str(date.fromisoformat(row["filed"])), str(date.fromisoformat(row["end"]))
                start = str(date.fromisoformat(row["start"])) if "start" in row else None
                value = row["val"]
                if type(value) not in (float, int) or not math.isfinite(value) or (start and start > end) or end > filed:
                    raise ResearchError("invalid_statement_value_or_period")
                if filed > as_of or row.get("form") not in FORMS:
                    continue
                accession = row.get("accn")
                if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                    raise ResearchError("invalid_statement_accession")
                candidates.append({"taxonomy": taxonomy, "concept": concept, "label": source.get("label", concept),
                                   "value": value, "unit": unit, "period_start": start, "period_end": end,
                                   "filed": filed, "available_at": filed + "T23:59:59Z", "form": row["form"],
                                   "accession": accession, "fiscal_year": row.get("fy"), "fiscal_period": row.get("fp"),
                                   "frame": row.get("frame") if isinstance(row.get("frame"), str) else None,
                                   "source_row_index": index, "classification": "company-reported XBRL",
                                   "data_class": "official_reported", "estimate": False,
                                   "filing_url": _archive(cik_id(cik), accession, accession + "-index.htm")})
            candidates.sort(key=lambda r: (r["period_end"], r["filed"], r["accession"]), reverse=True)
            result.extend(candidates[:ROWS_PER_CONCEPT_UNIT])
    return result


def safe_code(exc):
    code = str(exc.args[0]) if isinstance(exc, ResearchError) and exc.args else ""
    return code if code in SAFE_CODES else "source_unavailable_or_invalid"


class CompanyResearch:
    def __init__(self, service, store, clock=None):
        self.service, self.store = service, store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # -- capture plumbing -------------------------------------------------
    def _status(self, url):
        statuses = getattr(getattr(self.service, "transport", None), "statuses", None)
        return statuses.get(url) if isinstance(statuses, dict) else None

    def _error(self, section, url, exc):
        status = self._status(url)
        code = "sec_access_denied" if status == 403 else safe_code(exc)
        return {"section": section, "code": code, "http_status": status if status in (403, 404, 429) else None}

    def _fetch(self, url, context):
        doc = self.service.fetch(url, context)
        if doc.canonical_url != url:
            raise ResearchError("exact_sec_endpoint_required")
        return doc

    def _store(self, owner, session_id, section, url, doc, normalized, published_at=None):
        source = {"url": doc.canonical_url, "sha256": doc.content_hash, "section": section,
                  "retrieved_at": doc.retrieved_at.isoformat(), "available_at": doc.retrieved_at.isoformat(),
                  "captured_text_sha256": hashlib.sha256(doc.text.encode()).hexdigest(),
                  "published_at": published_at, "provider": "SEC EDGAR", "version": "sha256:" + doc.content_hash,
                  "licence": SEC_LICENCE}
        item = {"revision": 1, "sessionId": session_id, "raw": doc.text, "source": source,
                "section": section, "normalized": normalized}
        sk = "CAPTURE#" + hashlib.sha256((url + doc.content_hash).encode()).hexdigest()
        try:
            self.store.transact([Write("cache", owner, sk, item, None)])
        except Conflict:
            existing = self.store.get("cache", owner, sk)
            if existing is None or existing["raw"] != item["raw"] or existing["sessionId"] != session_id:
                raise ResearchError("capture_integrity_failure")
            source = existing["source"]
        return source

    # -- sections ---------------------------------------------------------
    def _insiders(self, owner, session_id, cik, context, candidates, result):
        from .disclosures import insider_transactions
        section = {"status": "not_applicable" if not candidates else "available", "filings": [], "errors": []}
        for filing in candidates:
            url = filing["raw_document_url"]
            try:
                doc = self._fetch(url, context)
                parsed = insider_transactions(doc.text, issuer_cik=cik, filed=filing["filed"])
                parsed.update(accession=filing["accession"], form=filing["form"], accepted_at=filing["accepted_at"],
                              filing_url=filing["url"], index_url=filing["index_url"], source_url=url)
                parsed["source"] = self._store(owner, session_id, "insider_transactions", url, doc, parsed,
                                               filing["accepted_at"])
                result["sources"].append(parsed["source"])
                section["filings"].append(parsed)
            except (ResearchError, ValueError, TypeError, KeyError) as exc:
                error = self._error("insider_transactions", url, exc)
                section["errors"].append({**error, "accession": filing["accession"]})
        if candidates and not section["filings"]:
            section["status"] = "unavailable"
        elif section["errors"]:
            section["status"] = "partial"
        section["summary"] = insider_summary(section["filings"])
        section["coverage"] = (f"Most recent {MAX_INSIDER_FILINGS} Form 4 filings listed in recent submissions "
                               "for this CIK; earlier filings and Forms 3/5 not requested.")
        return section

    def _holdings(self, owner, session_id, cik, context, candidates, result):
        from .disclosures import institutional_holdings, summarize_holdings
        if not candidates:
            return {"status": "not_applicable", "filing": None, "errors": [],
                    "coverage": "No 13F-HR filing in recent submissions; this CIK is not shown as a 13F filer."}
        filing = candidates[0]
        index_url = _archive(cik, filing["accession"], "index.json")
        section = {"status": "unavailable", "filing": None, "errors": [],
                   "coverage": "Most recent 13F-HR information table only; earlier quarters not requested."}
        attempted = [index_url]
        try:
            index = self._fetch(index_url, context)
            listing = strict_json(index.text)
            items = listing.get("directory", {}).get("item", []) if isinstance(listing, dict) else []
            if not isinstance(items, list) or len(items) > 500:
                raise ResearchError("invalid_filing_index")
            names = [i.get("name") for i in items if isinstance(i, dict)]
            xml = [n for n in names if isinstance(n, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,200}\.xml", n)
                   and n.lower() != "primary_doc.xml"][:MAX_INFOTABLE_CANDIDATES]
            result["sources"].append(self._store(owner, session_id, "institutional_holdings_index", index_url,
                                                 index, {"xml_documents": xml}, filing["accepted_at"]))
            parsed, last_error = None, ResearchError("information_table_not_found")
            for name in xml:
                url = _archive(cik, filing["accession"], name)
                attempted.append(url)
                try:
                    doc = self._fetch(url, context)
                    parsed = institutional_holdings(doc.text, manager_cik=cik, filed=filing["filed"],
                                                    report_period=filing["period_end"] or filing["filed"])
                except (ResearchError, ValueError, TypeError, KeyError) as exc:
                    last_error = exc
                    if self._status(url) == 403:
                        raise
                    continue
                parsed = summarize_holdings(parsed)
                parsed.update(accession=filing["accession"], form=filing["form"], accepted_at=filing["accepted_at"],
                              filing_url=filing["url"], index_url=filing["index_url"], source_url=url,
                              report_period_source="submissions reportDate" if filing["period_end"] else
                              "unavailable; filing date shown instead")
                parsed["source"] = self._store(owner, session_id, "institutional_holdings", url, doc, parsed,
                                               filing["accepted_at"])
                result["sources"].append(parsed["source"])
                break
            if parsed is None:
                raise last_error
            section.update(status="available", filing=parsed)
        except (ResearchError, ValueError, TypeError, KeyError) as exc:
            denied = [u for u in attempted if self._status(u) == 403]
            error = self._error("institutional_holdings", denied[0] if denied else attempted[-1], exc)
            section["errors"].append({**error, "accession": filing["accession"]})
        return section

    def detail(self, session_id, cik):
        cik = cik_id(cik)
        retrieved = self.clock()
        stamp = retrieved.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        context = ResearchContext("company_" + hashlib.sha256(session_id.encode()).hexdigest(), retrieved.date())
        # Deterministic ledger clock: identical captures register identical facts (idempotent detail).
        ledger = Ledger(context.run_id, str(context.as_of), clock=lambda: stamp)
        owner = "COMPANY#" + hashlib.sha256(session_id.encode()).hexdigest()
        result = {"cik": cik, "as_of": str(retrieved.date()), "retrieved_at": retrieved.isoformat(),
                  "company": None, "statements": [], "facts": {}, "sources": [], "errors": [],
                  "insider_transactions": None, "institutional_holdings": None, "sections": {},
                  "limitations": ["CIK identifies a US disclosure registrant, not an exchange listing.",
                                  "Current captures include revisions; not original historical vintages.",
                                  "Filing-day availability uses conservative end of day, not period end; "
                                  "EDGAR acceptance time is shown separately when SEC reports it.",
                                  "SEC values are official company-reported figures; no estimates are shown.",
                                  "No complete beneficial ownership, realtime news or absence-of-controversy guarantee."]}
        for section, url in (("company", f"https://data.sec.gov/submissions/CIK{cik}.json"),
                             ("statements", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")):
            try:
                doc = self._fetch(url, context)
                data = strict_json(doc.text)
                if not isinstance(data, dict):
                    raise ResearchError("invalid_source_json")
                normalized = submissions(data, cik, str(context.as_of)) if section == "company" else statements(data, cik, str(context.as_of))
                if section == "statements":
                    with ledger.transaction():
                        for row in normalized:
                            if row["taxonomy"] != "us-gaap" or row["unit"] not in LEDGER_UNITS:
                                continue
                            fact = fact_input(doc, context, value=row["value"], unit=row["unit"].lower(),
                                              subject_id=cik, variant=f"{row['concept']}:{row['unit']}:{row['source_row_index']}",
                                              label=row["label"])
                            row["fact_id"] = ledger.add_source_fact(fact, document_ref(doc), {
                                "format": "sec_companyfacts", "concept": row["concept"],
                                "unit": row["unit"], "row_index": row["source_row_index"],
                            })
                source = self._store(owner, session_id, section, url, doc, normalized)
                result[section] = normalized
                result["sources"].append(source)
                result["sections"][section] = {"status": "available", "source": source}
            except (ResearchError, ValueError, TypeError, KeyError) as exc:
                error = self._error(section, url, exc)
                result["errors"].append(error)
                result["sections"][section] = {"status": "unavailable", "code": error["code"]}
        company = result["company"]
        result["sections"]["filings"] = result["sections"]["company"]
        if company is None:
            for name in ("insider_transactions", "institutional_holdings"):
                result["sections"][name] = {"status": "unavailable", "code": "submissions_required"}
                result["errors"].append({"section": name, "code": "submissions_required", "http_status": None})
        else:
            candidates = company["disclosure_candidates"]
            insiders = self._insiders(owner, session_id, cik, context, candidates["form4"], result)
            holdings = self._holdings(owner, session_id, cik, context, candidates["form13f"], result)
            result["insider_transactions"], result["institutional_holdings"] = insiders, holdings
            for name, section in (("insider_transactions", insiders), ("institutional_holdings", holdings)):
                result["sections"][name] = {"status": section["status"],
                                            "code": section["errors"][0]["code"] if section["errors"] else None}
                result["errors"].extend(section["errors"] if section["status"] == "unavailable" else [])
        statuses = {s["status"] for s in result["sections"].values()}
        result["status"] = ("unavailable" if not result["sources"] else
                            "available" if statuses <= {"available", "not_applicable"} else "partial")
        result["facts"] = {key: value.to_wire() for key, value in ledger.export().facts.items()}
        return result


def insider_summary(filings):
    """Code-computed counts of reported rows; quantities are not converted or valued."""
    counts = {}
    for filing in filings:
        for row in filing["transactions"]:
            key = f"{row['kind']}:{row['code']}:{row['acquired_or_disposed']}"
            counts[key] = counts.get(key, 0) + 1
    return {"filings": len(filings), "transactions": sum(counts.values()),
            "by_kind_code_direction": dict(sorted(counts.items())),
            "method": "Count of reported transaction rows; no valuation or netting."}
