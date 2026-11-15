"""Point-in-time SEC fundamentals and filings for Time Machine calibration.

What this reconstructs: from a *current* capture of SEC EDGAR ``submissions`` and XBRL
``companyfacts`` (or ``companyconcept`` per concept when companyfacts is too large), it
rebuilds which company-reported values and filings were already public at a replay cutoff.
Availability of a reported value is the EDGAR acceptance timestamp of the filing that
carried it (``acceptanceDateTime`` from submissions, matched by accession number). When the
accession is outside the fetched submission pages, availability falls back to the filing
date at end of day UTC and the row says so. Rows without either are withheld as unknown.

What it does not do: it never feeds a replay run, never rewrites a frozen run and never claims
the capture itself existed at the cutoff (it was retrieved later). SEC companyfacts is SEC's
current processing of filed XBRL; values a later filing restated appear as separate rows
under the later accession and are selected only once that accession was accepted.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from aplomb.datastore.timeutil import boundary_for, normalize_ts, parse_date
from aplomb.ledger.sources import strict_json
from aplomb.research.company_detail import CONCEPTS, FORMS, cik_id
from aplomb.research.core import PublicHTTP, ResearchContext, ResearchError, ResearchService

from .records import PointInTimeRecord, PointInTimeRecords

SEC_CONTACT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{1,79} [^\s@]+@[^\s@]+\.[^\s@]+")
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
PRIMARY = re.compile(r"[A-Za-z0-9_.-]{1,200}")
PAGE_NAME = re.compile(r"CIK[0-9]{10}-submissions-[0-9]{3}\.json")
UNITS = ("USD", "CAD", "USD/shares", "CAD/shares")
MAX_ROWS = 50_000
MAX_EXTRA_PAGES = 3
PERIODS_SHOWN = 8
SAMPLE = 60

LIMITATIONS = (
    "Reconstructed from SEC EDGAR captures retrieved after the cutoff; the capture itself did not exist at the cutoff.",
    "Availability is the EDGAR acceptance timestamp exactly as the submissions JSON states it; it was not cross-checked "
    "against each filing header. Where the accession is outside the fetched submission pages, the filing date at end "
    "of day UTC is used and labelled date-level.",
    "SEC companyfacts is SEC's current processing of filed XBRL. A value restated by a later filing is selected only "
    "after that filing's availability; companyfacts may not retain every historical presentation.",
    "Only a fixed list of us-gaap concepts in USD/CAD is reconstructed; no estimates, prices or news.",
    "This calibration does not feed or alter any replay run. Restricting tools does not erase what a language model "
    "learned in pretraining: a deterministic point-in-time selection is not evidence that a model predicted history.",
)


class PointInTimeUnavailable(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sec_contact(environ=None) -> str | None:
    """Operator SEC contact (``APLOMB_SEC_CONTACT``: "Name email"). Never invented."""
    value = (os.environ if environ is None else environ).get("APLOMB_SEC_CONTACT", "").strip()
    return value if SEC_CONTACT_PATTERN.fullmatch(value) else None


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("retrieval clock must be timezone-aware")
    moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- filings


@dataclass(frozen=True)
class Filing:
    accession: str
    form: str
    filing_date: str
    report_date: str | None
    acceptance: str | None
    url: str


def parse_filing_columns(block: dict, cik: str) -> tuple[list[Filing], int]:
    """Columnar EDGAR submissions block -> filings; returns (filings, rejected row count)."""
    fields = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if not isinstance(block, dict) or any(not isinstance(block.get(k), list) for k in fields):
        raise ResearchError("invalid_submissions_arrays")
    size = len(block["form"])
    accepted = block.get("acceptanceDateTime")
    if size > 20_000 or any(len(block[k]) != size for k in fields) or (
            accepted is not None and (not isinstance(accepted, list) or len(accepted) != size)):
        raise ResearchError("inconsistent_submissions_arrays")
    out, rejected = [], 0
    for i in range(size):
        try:
            form, accession = block["form"][i], block["accessionNumber"][i]
            if not isinstance(form, str) or not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                raise ValueError("identifier")
            filed = parse_date(block["filingDate"][i]).isoformat()
            report_raw = block["reportDate"][i]
            report = parse_date(report_raw).isoformat() if report_raw else None
        except (ValueError, TypeError):
            rejected += 1
            continue
        acceptance = None
        if accepted is not None and isinstance(accepted[i], str):
            try:
                acceptance = normalize_ts(accepted[i])
            except ValueError:
                acceptance = None
        primary = block["primaryDocument"][i]
        folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
        url = folder + primary if isinstance(primary, str) and PRIMARY.fullmatch(primary) else folder
        out.append(Filing(accession, form, filed, report, acceptance, url))
    return out, rejected


def extra_pages(data: dict, cutoff: date, today: date) -> list[str]:
    """Older submission page names overlapping [cutoff - 2 years, today], newest first."""
    files = data.get("filings", {}).get("files", [])
    if not isinstance(files, list):
        return []
    lower = (cutoff - timedelta(days=730)).isoformat()
    names = []
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not PAGE_NAME.fullmatch(entry["name"]):
            continue
        start, end = entry.get("filingFrom"), entry.get("filingTo")
        try:
            if parse_date(end).isoformat() < lower or parse_date(start) > today:
                continue
        except (ValueError, TypeError):
            continue
        names.append((end, entry["name"]))
    return [name for _, name in sorted(names, reverse=True)[:MAX_EXTRA_PAGES]]


def availability(filing_date: str | None, acceptance: str | None, retrieved_at: str) -> tuple[str | None, str | None, str]:
    """(available_at, published_at, basis). Never later than the capture that observed it."""
    if acceptance and acceptance <= retrieved_at:
        return acceptance, acceptance, "edgar_acceptance"
    if filing_date:
        end_of_day = f"{filing_date}T23:59:59.999Z"
        return min(end_of_day, retrieved_at), None, "filing_date_end_of_day"
    return None, None, "unknown"


# --------------------------------------------------------------------------- XBRL facts


def concept_units(data: dict, concept: str, *, single: bool) -> tuple[str, dict]:
    """Label and units of one us-gaap concept from companyfacts or a companyconcept document."""
    source = data if single else data.get("facts", {}).get("us-gaap", {}).get(concept, {})
    if not isinstance(source, dict):
        raise ResearchError("invalid_companyfacts_shape")
    if single and (source.get("taxonomy") != "us-gaap" or source.get("tag") != concept):
        raise ResearchError("companyconcept_mismatch")
    units = source.get("units", {})
    if not isinstance(units, dict):
        raise ResearchError("invalid_companyfacts_shape")
    label = source.get("label") if isinstance(source.get("label"), str) else concept
    return label[:200], units


def fact_rows(concept: str, label: str, units: dict) -> tuple[list[dict], int]:
    rows, rejected = [], 0
    for unit, items in units.items():
        if unit not in UNITS:
            continue
        if not isinstance(items, list) or len(items) > MAX_ROWS:
            raise ResearchError("invalid_companyfacts_rows")
        for index, item in enumerate(items):
            try:
                value = item["val"]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError("value")
                end = parse_date(item["end"]).isoformat()
                start = parse_date(item["start"]).isoformat() if item.get("start") else None
                filed = parse_date(item["filed"]).isoformat()
                accession = item.get("accn")
                if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                    raise ValueError("accession")
                if (start and start > end) or end > filed:
                    raise ValueError("period")
            except (KeyError, TypeError, ValueError):
                rejected += 1
                continue
            form = item.get("form") if isinstance(item.get("form"), str) else None
            rows.append({"concept": concept, "label": label, "unit": unit, "period_start": start, "period_end": end,
                         "value": value, "filed": filed, "form": form, "accession": accession,
                         "fiscal_year": item.get("fy") if type(item.get("fy")) is int else None,
                         "fiscal_period": item.get("fp") if isinstance(item.get("fp"), str) else None,
                         "source_row_index": index})
    return rows, rejected


# --------------------------------------------------------------------------- capture


@dataclass
class Capture:
    cik: str
    name: str | None
    retrieved_at: str
    filings: list[Filing]
    facts: list[dict]
    sources: list[dict]
    errors: list[dict]
    rejected_rows: int
    filings_cover_from: str | None
    fact_source: str | None
    facts_version: str = "sec-companyfacts:none"
    filings_version: str = "sec-submissions:none"
    notes: list[str] = field(default_factory=list)


class SecPointInTimeSource:
    """Fetch EDGAR documents through the shared bounded ResearchService (read-only reuse)."""

    def __init__(self, contact: str, clock=None, service: ResearchService | None = None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.service = service or ResearchService(PublicHTTP(contact), self.clock)

    def _json(self, url: str, context: ResearchContext):
        document = self.service.fetch(url, context)
        if document.canonical_url != url:
            raise ResearchError("exact_sec_endpoint_required")
        data = strict_json(document.text)
        if not isinstance(data, dict):
            raise ResearchError("invalid_source_json")
        return data, document

    def _source(self, document, kind: str) -> dict:
        return {"kind": kind, "url": document.canonical_url, "sha256": document.content_hash,
                "retrieved_at": _stamp(document.retrieved_at), "provider": "SEC EDGAR",
                "licence": "SEC public EDGAR records; third-party filing rights may apply"}

    def capture(self, session_id: str, cik: str, cutoff: date) -> Capture:
        cik = cik_id(cik)
        retrieved = self.clock()
        today = retrieved.astimezone(timezone.utc).date()
        context = ResearchContext("pit_" + _sha(session_id)[:32], today, mode="point_in_time")
        capture = Capture(cik, None, _stamp(retrieved), [], [], [], [], 0, None, None)

        # 1) Submissions: filing identities and EDGAR acceptance timestamps.
        try:
            data, document = self._json(f"https://data.sec.gov/submissions/CIK{cik}.json", context)
            if type(data.get("cik")) not in (str, int) or str(data["cik"]).zfill(10) != cik:
                raise ResearchError("source_cik_mismatch")
            capture.name = data["name"][:200] if isinstance(data.get("name"), str) else None
            filings, rejected = parse_filing_columns(data.get("filings", {}).get("recent", {}), cik)
            capture.rejected_rows += rejected
            capture.sources.append(self._source(document, "submissions"))
            hashes = [document.content_hash]
            for name in extra_pages(data, cutoff, today):
                try:
                    page, page_doc = self._json(f"https://data.sec.gov/submissions/{name}", context)
                    block = page if "accessionNumber" in page else page.get("filings", {}).get("recent", {})
                    more, rejected = parse_filing_columns(block, cik)
                    filings.extend(more)
                    capture.rejected_rows += rejected
                    capture.sources.append(self._source(page_doc, "submissions_page"))
                    hashes.append(page_doc.content_hash)
                except (ResearchError, ValueError, TypeError, KeyError):
                    capture.errors.append({"section": "submissions_page", "code": "source_unavailable_or_invalid"})
            unique = {}
            for filing in filings:
                unique.setdefault(filing.accession, filing)
            capture.filings = sorted(unique.values(), key=lambda f: (f.filing_date, f.accession))
            capture.filings_cover_from = capture.filings[0].filing_date if capture.filings else None
            capture.filings_version = "sec-submissions:" + _sha("|".join(hashes))[:40]
        except (ResearchError, ValueError, TypeError, KeyError):
            capture.errors.append({"section": "submissions", "code": "source_unavailable_or_invalid"})

        # 2) XBRL facts: companyfacts, or one companyconcept per concept if the document is too large.
        try:
            data, document = self._json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", context)
            if type(data.get("cik")) is not int or str(data["cik"]).zfill(10) != cik:
                raise ResearchError("source_cik_mismatch")
            capture.name = capture.name or (data["entityName"][:200] if isinstance(data.get("entityName"), str) else None)
            for concept in CONCEPTS:
                label, units = concept_units(data, concept, single=False)
                rows, rejected = fact_rows(concept, label, units)
                capture.facts.extend(rows)
                capture.rejected_rows += rejected
            capture.sources.append(self._source(document, "companyfacts"))
            capture.fact_source = "companyfacts"
            capture.facts_version = "sec-companyfacts:" + document.content_hash[:40]
        except ResearchError as exc:
            if str(exc) != "response_too_large":
                capture.errors.append({"section": "companyfacts", "code": "source_unavailable_or_invalid"})
            else:
                capture.notes.append("companyfacts exceeded the capture size limit; per-concept companyconcept documents were used.")
                self._concepts(capture, cik, context)
        except (ValueError, TypeError, KeyError):
            capture.errors.append({"section": "companyfacts", "code": "source_unavailable_or_invalid"})
        return capture

    def _concepts(self, capture: Capture, cik: str, context: ResearchContext) -> None:
        hashes = []
        for concept in CONCEPTS:
            url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
            try:
                data, document = self._json(url, context)
                if type(data.get("cik")) is not int or str(data["cik"]).zfill(10) != cik:
                    raise ResearchError("source_cik_mismatch")
                label, units = concept_units(data, concept, single=True)
                rows, rejected = fact_rows(concept, label, units)
                capture.facts.extend(rows)
                capture.rejected_rows += rejected
                capture.sources.append(self._source(document, "companyconcept"))
                hashes.append(document.content_hash)
            except (ResearchError, ValueError, TypeError, KeyError):
                # A concept the registrant never reported answers 404: it is absent, not zero.
                capture.errors.append({"section": f"companyconcept:{concept}", "code": "source_unavailable_or_absent"})
        if hashes:
            capture.fact_source = "companyconcept"
            capture.facts_version = "sec-companyconcept:" + _sha("|".join(hashes))[:40]


# --------------------------------------------------------------------------- records


def _record(kind, record_id, revision_id, observation, published, available, retrieved, version, url, payload):
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return PointInTimeRecord(record_id, revision_id, kind, observation, published, available, retrieved,
                             version, url, _sha(text), text)


def fundamental_records(capture: Capture) -> tuple[list[PointInTimeRecord], list[dict]]:
    """One record revision per (concept, unit, period) x accession. Returns (records, excluded rows)."""
    acceptance = {f.accession: f.acceptance for f in capture.filings}
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in capture.facts:
        key = f"{row['concept']}|{row['unit']}|{row['period_start'] or ''}|{row['period_end']}"
        grouped.setdefault((key, row["accession"]), []).append(row)
    staged: dict[str, list[tuple[str | None, str | None, str, dict]]] = {}
    excluded = []
    for (key, accession), rows in grouped.items():
        if len({row["value"] for row in rows}) > 1:
            excluded.extend(dict(row, reason="conflicting_values_in_one_filing") for row in rows)
            continue
        row = rows[0]
        available, published, basis = availability(row["filed"], acceptance.get(accession), capture.retrieved_at)
        staged.setdefault(key, []).append((available, published, basis, row))
    records = []
    for key, revisions in staged.items():
        by_time: dict[str | None, list] = {}
        for item in revisions:
            by_time.setdefault(item[0], []).append(item)
        for available, items in by_time.items():
            if available is not None and len(items) > 1:
                if len({item[3]["value"] for item in items}) > 1:
                    excluded.extend(dict(item[3], reason="ambiguous_same_time_revisions") for item in items)
                    continue
                items = [min(items, key=lambda item: item[3]["accession"])]
            for _, published, basis, row in items:
                payload = {k: row[k] for k in ("concept", "label", "unit", "period_start", "period_end", "value", "filed",
                                               "form", "accession", "fiscal_year", "fiscal_period")}
                payload["availability_basis"] = basis
                records.append(_record("fundamental", key, row["accession"], row["period_end"], published, available,
                                       capture.retrieved_at, capture.facts_version,
                                       f"https://data.sec.gov/api/xbrl/companyfacts/CIK{capture.cik}.json", payload))
    return records, excluded


def filing_records(capture: Capture) -> list[PointInTimeRecord]:
    out = []
    for f in capture.filings:
        available, published, basis = availability(f.filing_date, f.acceptance, capture.retrieved_at)
        observation = f.report_date if f.report_date and f.report_date <= f.filing_date else f.filing_date
        payload = {"accession": f.accession, "form": f.form, "filing_date": f.filing_date, "report_date": f.report_date,
                   "acceptance": f.acceptance, "availability_basis": basis}
        out.append(_record("filing", f.accession, "1", observation, published, available, capture.retrieved_at,
                           capture.filings_version, f.url, payload))
    return out


def classify(records: list[PointInTimeRecord], version: str, cutoff: str) -> dict:
    """Split records into selected-at-cutoff, withheld (with reason) and superseded-before-cutoff."""
    selected = PointInTimeRecords(version, tuple(records)).select(cutoff) if records else ()
    chosen = {(r.kind, r.record_id): r for r in selected}
    boundary = boundary_for(parse_date(cutoff, "cutoff"))
    withheld, superseded = [], []
    for row in records:
        current = chosen.get((row.kind, row.record_id))
        if current is row:
            continue
        if row.available_at is None:
            withheld.append((row, "unknown_availability"))
        elif normalize_ts(row.available_at) >= boundary:
            withheld.append((row, "revision_after_cutoff" if current else "published_after_cutoff"))
        elif row.observation_date > cutoff:
            withheld.append((row, "observation_after_cutoff"))
        else:
            superseded.append(row)
    return {"selected": list(selected), "chosen": chosen, "withheld": withheld, "superseded": superseded}


def _payload(row: PointInTimeRecord) -> dict:
    return json.loads(row.payload)


def _fact_view(row: PointInTimeRecord) -> dict:
    data = _payload(row)
    return {**data, "record_id": row.record_id, "available_at": row.available_at, "published_at": row.published_at,
            "content_sha256": row.content_hash}


def _filing_view(row: PointInTimeRecord, url: str) -> dict:
    data = _payload(row)
    return {**data, "available_at": row.available_at, "url": url}


def _latest_periods(rows: list[PointInTimeRecord]) -> list[PointInTimeRecord]:
    groups: dict[tuple[str, str], list[PointInTimeRecord]] = {}
    for row in rows:
        concept, unit, _, _ = row.record_id.split("|")
        groups.setdefault((concept, unit), []).append(row)
    out = []
    for key in sorted(groups):
        ordered = sorted(groups[key], key=lambda r: (r.observation_date, r.record_id), reverse=True)
        out.extend(ordered[:PERIODS_SHOWN])
    return out


def _count(items, key) -> dict:
    counts: dict[str, int] = {}
    for item in items:
        name = key(item)
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _base(capture: Capture, cutoff: str) -> dict:
    return {"cik": capture.cik, "name": capture.name, "cutoff": cutoff, "boundary": boundary_for(parse_date(cutoff)),
            "retrieved_at": capture.retrieved_at, "fact_source": capture.fact_source,
            "dataset_versions": {"facts": capture.facts_version, "filings": capture.filings_version},
            "sources": capture.sources, "errors": capture.errors, "notes": capture.notes,
            "rejected_source_rows": capture.rejected_rows, "filings_cover_from": capture.filings_cover_from,
            "limitations": list(LIMITATIONS),
            "status": "available" if not capture.errors else "partial" if capture.sources else "unavailable"}


def point_in_time(capture: Capture, cutoff: str) -> dict:
    """Available-at-cutoff fundamentals and filings, plus the withheld set with reasons."""
    facts, excluded = fundamental_records(capture)
    fc = classify(facts, capture.facts_version, cutoff)
    filings = filing_records(capture)
    urls = {f.accession: f.url for f in capture.filings}
    lc = classify(filings, capture.filings_version, cutoff)

    shown = _latest_periods(fc["selected"])
    withheld_facts = sorted(fc["withheld"], key=lambda item: (item[0].available_at or "9", item[0].record_id))
    def withheld_view(row, reason):
        view = _fact_view(row)
        prior = fc["chosen"].get((row.kind, row.record_id))
        view["reason"] = reason
        if prior is not None:
            view["value_at_cutoff"] = _payload(prior)["value"]
            view["value_changed"] = _payload(prior)["value"] != view["value"]
        return view
    changed = [item for item in withheld_facts if item[1] == "revision_after_cutoff"
               and _payload(fc["chosen"][(item[0].kind, item[0].record_id)])["value"] != _payload(item[0])["value"]]
    changed_ids = {id(item[0]) for item in changed}
    sample = changed[:SAMPLE // 2] + [item for item in withheld_facts if id(item[0]) not in changed_ids][:SAMPLE // 2]

    filings_available = sorted(lc["selected"], key=lambda r: (r.available_at or "", r.record_id), reverse=True)
    filings_withheld = sorted(lc["withheld"], key=lambda item: (item[0].available_at or "9", item[0].record_id))
    result = _base(capture, cutoff)
    result["fundamentals"] = {
        "available": [_fact_view(row) for row in shown],
        "available_total": len(fc["selected"]),
        "available_by_basis": _count(fc["selected"], lambda r: _payload(r)["availability_basis"]),
        "withheld_total": len(fc["withheld"]),
        "withheld_by_reason": _count(fc["withheld"], lambda item: item[1]),
        "withheld_revised_values": len(changed),
        "withheld": [withheld_view(row, reason) for row, reason in sample],
        "superseded_before_cutoff": len(fc["superseded"]),
        "excluded_source_rows": _count(excluded, lambda row: row["reason"]),
        "shown_periods_per_concept": PERIODS_SHOWN,
    }
    result["filings"] = {
        "available_total": len(lc["selected"]),
        "available_by_form": _count(lc["selected"], lambda r: _payload(r)["form"]),
        "available": [_filing_view(r, urls.get(r.record_id, r.source_url)) for r in filings_available
                      if _payload(r)["form"] in FORMS][:40],
        "withheld_total": len(lc["withheld"]),
        "withheld_by_reason": _count(lc["withheld"], lambda item: item[1]),
        "withheld_by_form": _count(lc["withheld"], lambda item: _payload(item[0])["form"]),
        "withheld": [dict(_filing_view(r, urls.get(r.record_id, r.source_url)), reason=reason)
                     for r, reason in filings_withheld if _payload(r)["form"] in FORMS][:25],
        "list_forms": sorted(FORMS),
    }
    return result


def published_later(capture: Capture, cutoff: str, until: str) -> dict:
    """What became public in (cutoff, until]: new values, revised values and filings. Reveal-only."""
    if parse_date(until, "until") <= parse_date(cutoff, "cutoff"):
        raise ValueError("until must be after cutoff")
    facts, _ = fundamental_records(capture)
    at_cutoff = classify(facts, capture.facts_version, cutoff)["chosen"]
    at_until = classify(facts, capture.facts_version, until)["chosen"]
    revised, new = [], []
    for key, row in at_until.items():
        prior = at_cutoff.get(key)
        if prior is None:
            new.append(row)
        elif prior is not row and _payload(prior)["value"] != _payload(row)["value"]:
            view = _fact_view(row)
            view.update(value_at_cutoff=_payload(prior)["value"], accession_at_cutoff=_payload(prior)["accession"],
                        available_at_cutoff=prior.available_at)
            revised.append(view)
    new_shown = _latest_periods(new)
    filings = filing_records(capture)
    before = classify(filings, capture.filings_version, cutoff)["chosen"]
    window = [r for key, r in classify(filings, capture.filings_version, until)["chosen"].items() if key not in before]
    urls = {f.accession: f.url for f in capture.filings}
    result = _base(capture, cutoff)
    result.update({
        "until": until,
        "separate_from_run": True,
        "statement": "Published after the cutoff; shown only for comparison in the reveal. Nothing here was available "
                     "to the replay and nothing is added to the signed run.",
        "new_values_total": len(new), "new_values": [_fact_view(r) for r in new_shown],
        "revised_values_total": len(revised),
        "revised_values": sorted(revised, key=lambda v: (v["available_at"] or "", v["record_id"]))[:SAMPLE],
        "filings_total": len(window), "filings_by_form": _count(window, lambda r: _payload(r)["form"]),
        "filings": [_filing_view(r, urls.get(r.record_id, r.source_url))
                    for r in sorted(window, key=lambda r: (r.available_at or "", r.record_id))
                    if _payload(r)["form"] in FORMS][:40],
    })
    return result


# --------------------------------------------------------------------------- session cache


class CaptureCache:
    """Small per-session, per-day cache of parsed captures; no raw documents are retained."""

    def __init__(self, size: int = 32):
        self.size, self._items, self._lock = size, OrderedDict(), threading.Lock()

    def get(self, key):
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key, value):
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)
