"""Additional SEC EDGAR research surfaces: XBRL company concepts, XBRL frames, EDGAR Atom
filing feeds and Form N-CEN fund census filings.

Rules applied throughout:
- Exact SEC endpoints only, through the bounded public transport (size cap, deadline, no
  redirect substitution). A descriptive operator contact is required; none is ever invented.
- An HTTP 403 is reported as ``sec_access_denied`` and is never retried or bypassed.
- Every captured payload is stored once per session (immutable, sha256-keyed); a second
  capture with the same key must be byte-identical and owned by the same session.
- Numbers are parsed as Decimal straight from the source JSON (never through float) and are
  returned as strings with their unit stated explicitly.
- Filing date is the availability date. Amended or re-reported values are kept as separate
  revisions, never merged or overwritten.
- Entity names and feed titles are labels only; the CIK is the identity key. External text is
  data, never instructions.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlsplit

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

from .company_detail import ACCESSION, PRIMARY, SEC_LICENCE, _accepted, _archive, cik_id
from .core import ResearchContext, ResearchError

TAXONOMIES = ("us-gaap", "ifrs-full", "dei", "srt")
TAG = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,150}")
# SEC frames encode a ratio unit with "-per-" (e.g. USD-per-shares).
FRAME_UNIT = re.compile(r"[A-Za-z0-9]{1,20}(?:-per-[A-Za-z0-9]{1,20})?")
FRAME_PERIOD = re.compile(r"CY(19|20)[0-9]{2}(?:Q[1-4])?I?")
FORM_FILTER = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ./-]{0,19}")
SERIES = re.compile(r"S[0-9]{9}")
NCEN_FORMS = ("N-CEN", "N-CEN/A")
MAX_CONCEPT_ROWS_PER_UNIT = 3000
MAX_UNITS = 10
MAX_FRAME_ROWS_IN = 20000
MAX_XML_BYTES = 4_000_000
MAX_FEED_ENTRIES = 100
MAX_NCEN_LEAVES = 400
MAX_SERIES_BLOCKS = 5
ATOM = "{http://www.w3.org/2005/Atom}"
SAFE_CODES = frozenset({
    "rate_limited", "request_timeout", "response_too_large", "source_unavailable",
    "unsupported_content_type", "domain_not_allowlisted", "dns_unavailable", "dns_timeout",
    "redirect_or_retry_limit", "exact_sec_endpoint_required", "source_cik_mismatch",
    "source_concept_mismatch", "source_frame_mismatch", "invalid_source_json", "invalid_concept_rows",
    "invalid_frame_rows", "unsafe_or_oversized_xml", "invalid_xml", "not_atom_feed",
    "invalid_submissions_arrays", "no_ncen_filing_in_recent_submissions", "unsafe_filing_identifier",
    "not_ncen_document", "capture_integrity_failure",
})


# -- parsing helpers --------------------------------------------------------------------------

def _no_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ResearchError("invalid_source_json")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ResearchError("invalid_source_json")


def decimal_json(text):
    """Strict JSON with every number as Decimal (no float rounding, no NaN/Infinity, no dupes)."""
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates, parse_float=Decimal,
                          parse_int=Decimal, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ResearchError("invalid_source_json") from exc
    if not isinstance(data, dict):
        raise ResearchError("invalid_source_json")
    return data


def _decimal(value):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ResearchError("invalid_concept_rows")
    return value


def _iso_date(value, code):
    try:
        return str(date.fromisoformat(value))
    except (TypeError, ValueError) as exc:
        raise ResearchError(code) from exc


def _int_or_none(value):
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    return None


def _label(value, limit=300):
    return value[:limit] if isinstance(value, str) and value else None


def safe_xml(text: str):
    """Hardened XML parse: no DTDs or entity declarations, bounded size."""
    raw = text.encode("utf-8")
    upper = raw.upper()
    if len(raw) > MAX_XML_BYTES or b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ResearchError("unsafe_or_oversized_xml")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ResearchError("invalid_xml") from exc


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


# -- company concept (SRC-036) ----------------------------------------------------------------

def concept_url(cik, taxonomy, tag):
    return f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik_id(cik)}/{taxonomy}/{tag}.json"


def concept_series(data, cik, taxonomy, tag, as_of=None):
    """Every reported observation per unit, grouped into revisions of the same period.

    A period is (start, end); instant concepts have no start. Observations of one period are
    ordered by filing date then accession; revision 1 is the first filing that reported it.
    ``as_of`` (ISO date) adds a point-in-time view using only rows filed on or before it.
    """
    cik = cik_id(cik)
    if _int_or_none(data.get("cik")) is None or str(_int_or_none(data.get("cik"))).zfill(10) != cik:
        raise ResearchError("source_cik_mismatch")
    if data.get("taxonomy") != taxonomy or data.get("tag") != tag:
        raise ResearchError("source_concept_mismatch")
    units = data.get("units")
    if not isinstance(units, dict):
        raise ResearchError("invalid_concept_rows")
    out_units = []
    for unit, rows in list(units.items())[:MAX_UNITS]:
        if not isinstance(unit, str) or len(unit) > 40 or not isinstance(rows, list) or len(rows) > 100000:
            raise ResearchError("invalid_concept_rows")
        observations = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ResearchError("invalid_concept_rows")
            end = _iso_date(row.get("end"), "invalid_concept_rows")
            start = _iso_date(row["start"], "invalid_concept_rows") if row.get("start") is not None else None
            filed = _iso_date(row.get("filed"), "invalid_concept_rows")
            accession = row.get("accn")
            if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
                raise ResearchError("invalid_concept_rows")
            if start and start > end:
                raise ResearchError("invalid_concept_rows")
            value = _decimal(row.get("val"))
            form = row.get("form") if isinstance(row.get("form"), str) and len(row["form"]) <= 20 else None
            observations.append({
                "value": str(value), "unit": unit, "period_start": start, "period_end": end,
                "duration_days": (date.fromisoformat(end) - date.fromisoformat(start)).days if start else None,
                "fiscal_year": _int_or_none(row.get("fy")),
                "fiscal_period": row.get("fp") if isinstance(row.get("fp"), str) and len(row["fp"]) <= 4 else None,
                "form": form, "is_amendment_form": bool(form and form.endswith("/A")),
                "filed": filed, "available_at": filed + "T23:59:59Z", "accession": accession,
                "frame": row.get("frame") if isinstance(row.get("frame"), str) and len(row["frame"]) <= 20 else None,
                "filing_index_url": _archive(cik, accession, accession + "-index.htm"),
                "source_row_index": index, "_decimal": value,
            })
        total = len(observations)
        observations.sort(key=lambda r: (r["period_end"], r["period_start"] or "", r["filed"], r["accession"]))
        groups = {}
        for row in observations:
            groups.setdefault((row["period_start"], row["period_end"]), []).append(row)
        for group in groups.values():
            prior = None
            for number, row in enumerate(group, start=1):
                row["revision"] = number
                row["revisions_in_period"] = len(group)
                row["value_changed_from_prior_revision"] = None if prior is None else row["_decimal"] != prior
                prior = row["_decimal"]
        point_in_time = None
        if as_of is not None:
            point_in_time = []
            for (start, end), group in groups.items():
                known = [r for r in group if r["filed"] <= as_of]
                if known:
                    latest = known[-1]
                    point_in_time.append({"period_start": start, "period_end": end, "value": latest["value"],
                                          "unit": unit, "filed": latest["filed"], "accession": latest["accession"],
                                          "form": latest["form"], "revision": latest["revision"],
                                          "revisions_known_as_of": len(known)})
            point_in_time.sort(key=lambda r: (r["period_end"], r["period_start"] or ""), reverse=True)
        observations.reverse()  # newest period first for display
        kept = observations[:MAX_CONCEPT_ROWS_PER_UNIT]
        for row in kept:
            del row["_decimal"]
        revised = sum(1 for g in groups.values() if len(g) > 1)
        out_units.append({"unit": unit, "observations": kept, "observation_count": total,
                          "truncated": total > len(kept), "period_count": len(groups),
                          "periods_with_multiple_revisions": revised,
                          "point_in_time": point_in_time})
    return {"cik": cik, "taxonomy": taxonomy, "tag": tag, "label": _label(data.get("label")),
            "description": _label(data.get("description"), 2000),
            "entity_name_label": _label(data.get("entityName")),
            "units": out_units, "units_truncated": len(units) > MAX_UNITS, "as_of": as_of}


# -- frames (SRC-037) -------------------------------------------------------------------------

def frames_url(taxonomy, tag, unit, period):
    return f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json"


def _median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def frame_table(data, taxonomy, tag, unit, period, limit=100, order="desc"):
    """One value per reporting entity for one concept/unit/calendar frame, as SEC aggregates it."""
    if data.get("taxonomy") != taxonomy or data.get("tag") != tag or data.get("ccp") != period:
        raise ResearchError("source_frame_mismatch")
    if not isinstance(data.get("uom"), str):
        raise ResearchError("source_frame_mismatch")
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) > MAX_FRAME_ROWS_IN:
        raise ResearchError("invalid_frame_rows")
    parsed = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ResearchError("invalid_frame_rows")
        cik = _int_or_none(row.get("cik"))
        accession = row.get("accn")
        if cik is None or cik <= 0 or not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
            raise ResearchError("invalid_frame_rows")
        value = row.get("val")
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ResearchError("invalid_frame_rows")
        end = _iso_date(row.get("end"), "invalid_frame_rows")
        start = _iso_date(row["start"], "invalid_frame_rows") if row.get("start") is not None else None
        cik10 = str(cik).zfill(10)
        parsed.append({"cik": cik10, "entity_name_label": _label(row.get("entityName")),
                       "location_label": _label(row.get("loc"), 20), "value": value, "unit": data["uom"],
                       "period_start": start, "period_end": end, "accession": accession,
                       "filing_index_url": _archive(cik10, accession, accession + "-index.htm"),
                       "source_row_index": index})
    parsed.sort(key=lambda r: (r["value"], r["cik"]), reverse=(order == "desc"))
    values = [r["value"] for r in parsed]
    stats = {"count": len(values), "min": str(min(values)) if values else None,
             "max": str(max(values)) if values else None,
             "median": str(_median(values)) if values else None,
             "method": "Computed by code from all rows in the captured frame, using exact decimals."}
    shown = parsed[:limit]
    for rank, row in enumerate(shown, start=1):
        row["rank"] = rank
        row["value"] = str(row["value"])
    return {"taxonomy": taxonomy, "tag": tag, "unit": data["uom"], "requested_unit": unit, "period": period,
            "label": _label(data.get("label")), "description": _label(data.get("description"), 2000),
            "reported_point_count": _int_or_none(data.get("pts")), "statistics": stats,
            "order": order, "rows": shown, "truncated": len(parsed) > len(shown)}


# -- EDGAR Atom feeds (SRC-038 / MASTER-045) ---------------------------------------------------

def feed_url(form="", cik=None, count=40):
    form_q = quote(form, safe="")
    if cik:
        return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                f"&CIK={cik_id(cik)}&type={form_q}&dateb=&owner=include&start=0&count={count}&output=atom")
    return ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
            f"&type={form_q}&company=&dateb=&owner=include&start=0&count={count}&output=atom")


def _feed_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_feed(text, form_filter=""):
    root = safe_xml(text)
    if root.tag != ATOM + "feed":
        raise ResearchError("not_atom_feed")
    entries, skipped = [], 0
    for entry in root.findall(ATOM + "entry")[:MAX_FEED_ENTRIES]:
        title = (entry.findtext(ATOM + "title") or "").strip()
        link = entry.find(ATOM + "link")
        href = (link.get("href") if link is not None else "") or ""
        parsed = urlsplit(href)
        if (not title or len(title) > 500 or parsed.scheme != "https" or parsed.hostname != "www.sec.gov"
                or parsed.username or parsed.password or not parsed.path.startswith("/Archives/edgar/data/")):
            skipped += 1
            continue
        category = entry.find(ATOM + "category")
        form = category.get("term") if category is not None else None
        content = entry.find(ATOM + "content")
        details = {}
        if content is not None:
            for child in content:
                name = _local(child.tag)
                if name in ("accession-number", "filing-date", "filing-type", "form-name", "size", "act",
                            "file-number", "film-number"):
                    details[name] = (child.text or "").strip()[:200]
        if not form and details.get("filing-type"):
            form = details["filing-type"]
        form = form if isinstance(form, str) and FORM_FILTER.fullmatch(form) else None
        ident = entry.findtext(ATOM + "id") or ""
        summary = entry.findtext(ATOM + "summary") or ""
        accession = None
        for candidate in (details.get("accession-number", ""), ident, summary):
            match = re.search(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", candidate)
            if match:
                accession = match.group(0)
                break
        filed = None
        for candidate in (details.get("filing-date", ""),
                          (re.search(r"Filed:\s*(?:<[^>]{0,10}>\s*)?([0-9]{4}-[0-9]{2}-[0-9]{2})", summary) or [None, ""])[1]):
            try:
                filed = str(date.fromisoformat(candidate.strip()))
                break
            except ValueError:
                continue
        path_cik = re.match(r"/Archives/edgar/data/([0-9]{1,10})/", parsed.path)
        role = re.search(r"\((Filer|Reporting|Subject|Filed by|Issuer)\)\s*$", title)
        entries.append({"title_label": title, "url": href, "form": form, "accession": accession,
                        "filed": filed, "available_at": filed + "T23:59:59Z" if filed else None,
                        "feed_updated_at": _feed_time(entry.findtext(ATOM + "updated")),
                        "cik_from_link": path_cik.group(1).zfill(10) if path_cik else None,
                        "role_label": role.group(1) if role else None,
                        "form_name_label": _label(details.get("form-name"), 200),
                        "size_label": _label(details.get("size"), 40)})
    filtered_out = 0
    if form_filter:
        # Local re-check of the server-side type filter: entries whose form does not start with the
        # requested type are dropped and counted (e.g. "10-K" keeps "10-K" and "10-K/A").
        wanted = form_filter.upper()
        kept = [e for e in entries if e["form"] and e["form"].upper().startswith(wanted)]
        filtered_out, entries = len(entries) - len(kept), kept
    return {"feed_title_label": _label(root.findtext(ATOM + "title")),
            "feed_updated_at": _feed_time(root.findtext(ATOM + "updated")),
            "form_filter": form_filter or None, "entries": entries, "skipped_entries": skipped,
            "filtered_out_entries": filtered_out}


# -- N-CEN (SRC-041) ---------------------------------------------------------------------------

def ncen_candidates(data, cik):
    cik = cik_id(cik)
    raw_cik = data.get("cik")  # submissions JSON reports the CIK as a zero-padded string
    numeric = _int_or_none(raw_cik) if isinstance(raw_cik, Decimal) else (
        int(raw_cik) if isinstance(raw_cik, str) and re.fullmatch(r"[0-9]{1,10}", raw_cik) else None)
    if numeric is None or str(numeric).zfill(10) != cik:
        raise ResearchError("source_cik_mismatch")
    recent = data.get("filings", {}).get("recent", {}) if isinstance(data.get("filings"), dict) else {}
    fields = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if any(not isinstance(recent.get(k), list) for k in fields):
        raise ResearchError("invalid_submissions_arrays")
    size = len(recent["form"])
    if size > 20000 or any(len(recent[k]) != size for k in fields):
        raise ResearchError("invalid_submissions_arrays")
    accepted = recent.get("acceptanceDateTime") if isinstance(recent.get("acceptanceDateTime"), list) \
        and len(recent["acceptanceDateTime"]) == size else [None] * size
    rows = []
    for i in range(size):
        if recent["form"][i] not in NCEN_FORMS:
            continue
        accession, primary = recent["accessionNumber"][i], recent["primaryDocument"][i]
        if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
            raise ResearchError("unsafe_filing_identifier")
        match = PRIMARY.fullmatch(primary) if isinstance(primary, str) else None
        if match is None or match[2] in (".", ".."):
            continue
        filed = _iso_date(recent["filingDate"][i], "invalid_submissions_arrays")
        report = recent["reportDate"][i]
        rows.append({"form": recent["form"][i], "accession": accession, "filed": filed,
                     "available_at": filed + "T23:59:59Z",
                     "period_end": str(date.fromisoformat(report)) if isinstance(report, str) and report else None,
                     "accepted_at": _accepted(accepted[i]),
                     "url": _archive(cik, accession, primary),
                     "raw_document_url": _archive(cik, accession, match[2]),
                     "index_url": _archive(cik, accession, accession + "-index.htm")})
    rows.sort(key=lambda r: (r["filed"], r["accepted_at"] or "", r["accession"]), reverse=True)
    return {"cik": cik, "registrant_name_label": _label(data.get("name")),
            "entity_type_label": _label(data.get("entityType"), 60), "filings": rows[:10]}


def _leaves(element, prefix=""):
    """Yield (path, text) for leaf elements in document order, namespaces stripped."""
    path = f"{prefix}/{_local(element.tag)}" if prefix else _local(element.tag)
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        if text:
            yield path, text[:300]
        for key, value in element.attrib.items():
            if value.strip():
                yield f"{path}@{_local(key)}", value.strip()[:300]
        return
    for child in children:
        yield from _leaves(child, path)


def parse_ncen(text, cik, series=None):
    """Structured N-CEN fields exactly as tagged in the filing (no field semantics are assumed).

    With ``series``, returns the smallest enclosing element blocks that carry that exact series
    identifier as a direct child value.
    """
    root = safe_xml(text)
    if _local(root.tag) != "edgarSubmission":
        raise ResearchError("not_ncen_document")
    leaves = []
    total = 0
    cik_values = {cik_id(cik), str(int(cik_id(cik)))}
    filer_cik_present = False
    for path, value in _leaves(root):
        total += 1
        if value in cik_values:
            filer_cik_present = True
        if len(leaves) < MAX_NCEN_LEAVES:
            leaves.append({"path": path, "value": value})
    submission_type = None
    for element in root.iter():
        if _local(element.tag) == "submissionType" and element.text:
            submission_type = element.text.strip()[:20]
            break
    if submission_type not in (None, *NCEN_FORMS):
        raise ResearchError("not_ncen_document")
    blocks = None
    if series:
        blocks = []
        parents = {child: parent for parent in root.iter() for child in parent}
        for element in root.iter():
            if len(blocks) >= MAX_SERIES_BLOCKS:
                break
            if list(element) or (element.text or "").strip() != series:
                continue
            container = parents.get(element)
            if container is None:
                continue
            fields = []
            for path, value in _leaves(container):
                if len(fields) >= MAX_NCEN_LEAVES:
                    break
                fields.append({"path": path, "value": value})
            blocks.append({"container": _local(container.tag), "matched_field": _local(element.tag),
                           "fields": fields})
    return {"submission_type": submission_type, "filer_cik_present_in_document": filer_cik_present,
            "leaf_count": total, "leaves": leaves, "leaves_truncated": total > len(leaves),
            "series_id": series, "series_blocks": blocks}


# -- capture service ----------------------------------------------------------------------------

def safe_code(exc):
    code = str(exc.args[0]) if isinstance(exc, ResearchError) and exc.args else ""
    return code if code in SAFE_CODES else "source_unavailable_or_invalid"


class SecExtra:
    """Session-owned, immutable captures of the extra SEC surfaces."""

    def __init__(self, service, store, clock=None):
        self.service, self.store = service, store
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _context(self, session_id):
        return ResearchContext("secx_" + hashlib.sha256(session_id.encode()).hexdigest()[:32], self.clock().date())

    def _status(self, url):
        statuses = getattr(getattr(self.service, "transport", None), "statuses", None)
        return statuses.get(url) if isinstance(statuses, dict) else None

    def _unavailable(self, kind, url, exc):
        status = self._status(url)
        code = "sec_access_denied" if status == 403 else safe_code(exc)
        return {"kind": kind, "status": "unavailable", "code": code,
                "http_status": status if status in (403, 404, 429) else None, "source_url": url}

    def _fetch(self, url, context):
        doc = self.service.fetch(url, context)
        if doc.canonical_url != url or doc.redirects:
            raise ResearchError("exact_sec_endpoint_required")
        return doc

    def _store(self, session_id, kind, url, doc, normalized):
        owner = "SEC_EXTRA#" + hashlib.sha256(session_id.encode()).hexdigest()
        source = {"url": doc.canonical_url, "sha256": doc.content_hash, "kind": kind,
                  "content_type": doc.content_type, "retrieved_at": doc.retrieved_at.isoformat(),
                  "captured_text_sha256": hashlib.sha256(doc.text.encode()).hexdigest(),
                  "provider": "SEC EDGAR", "version": "sha256:" + doc.content_hash, "licence": SEC_LICENCE}
        item = {"revision": 1, "sessionId": session_id, "raw": doc.text, "source": source,
                "kind": kind, "normalized": normalized}
        sk = "CAPTURE#" + hashlib.sha256((url + doc.content_hash).encode()).hexdigest()
        try:
            self.store.transact([Write("cache", owner, sk, item, None)])
        except Conflict:
            existing = self.store.get("cache", owner, sk)
            if existing is None or existing.get("raw") != item["raw"] or existing.get("sessionId") != session_id:
                raise ResearchError("capture_integrity_failure")
            source = existing["source"]
        return source

    def _run(self, session_id, kind, url, build, limitations):
        context = self._context(session_id)
        try:
            doc = self._fetch(url, context)
            normalized = build(doc)
            source = self._store(session_id, kind, url, doc, normalized)
        except (ResearchError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
            return {**self._unavailable(kind, url, exc), "limitations": limitations}
        return {"kind": kind, "status": "available", "source": source, "result": normalized,
                "limitations": limitations}

    def concept(self, session_id, cik, taxonomy, tag, as_of=None):
        url = concept_url(cik, taxonomy, tag)
        return self._run(session_id, "company_concept", url,
                         lambda doc: concept_series(decimal_json(doc.text), cik, taxonomy, tag, as_of), [
                             "Current SEC capture: includes every revision SEC still serves, not original vintages.",
                             "Availability is the filing date (conservative end of day UTC), never the period end.",
                             "Amended and re-reported values are separate revisions; none is overwritten.",
                             "Entity name is a label; the CIK is the identity key.",
                             "Values are company-reported XBRL facts, exact decimals, in the stated unit."])

    def frame(self, session_id, taxonomy, tag, unit, period, limit=100, order="desc"):
        url = frames_url(taxonomy, tag, unit, period)
        return self._run(session_id, "xbrl_frame", url,
                         lambda doc: frame_table(decimal_json(doc.text), taxonomy, tag, unit, period, limit, order), [
                             "SEC frames keep one fact per entity that best matches the calendar period; "
                             "fiscal periods may not align exactly with the calendar frame.",
                             "Rows are not comparable across different units; no conversion is applied.",
                             "Entity names and locations are labels only; the CIK is the identity key.",
                             "Statistics describe this captured frame only, not a market or index."])

    def feed(self, session_id, form="", cik=None, count=40):
        url = feed_url(form, cik, count)
        return self._run(session_id, "edgar_feed", url, lambda doc: parse_feed(doc.text, form), [
            "Discovery feed of recent filings only, not a complete filing history.",
            "feed_updated_at is the Atom <updated> value as published; it is not independently "
            "verified as the EDGAR acceptance time.",
            "Titles and form names are labels; the CIK in the archive link is the identity key.",
            "No filing content is fetched or inferred from a feed entry."])

    def ncen(self, session_id, cik, series=None):
        cik = cik_id(cik)
        context = self._context(session_id)
        limitations = [
            "Most recent N-CEN filing in the registrant's recent submissions only.",
            "Fields are shown exactly as tagged in the filing; no field meaning is assumed.",
            "Series match is an exact series-identifier value match inside the filing XML.",
            "SEC's quarterly N-CEN structured datasets (DERA) are not ingested here.",
        ]
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            doc = self._fetch(submissions_url, context)
            listing = ncen_candidates(decimal_json(doc.text), cik)
            sub_source = self._store(session_id, "ncen_submissions", submissions_url, doc, listing)
        except (ResearchError, ValueError, TypeError, KeyError, InvalidOperation) as exc:
            return {**self._unavailable("ncen", submissions_url, exc), "limitations": limitations}
        if not listing["filings"]:
            return {"kind": "ncen", "status": "unavailable", "code": "no_ncen_filing_in_recent_submissions",
                    "http_status": None, "source_url": submissions_url, "sources": [sub_source],
                    "registrant": listing, "limitations": limitations}
        filing = listing["filings"][0]
        url = filing["raw_document_url"]
        try:
            filing_doc = self._fetch(url, context)
            parsed = parse_ncen(filing_doc.text, cik, series)
            source = self._store(session_id, "ncen_filing", url, filing_doc, parsed)
        except (ResearchError, ValueError, TypeError, KeyError) as exc:
            return {**self._unavailable("ncen", url, exc), "sources": [sub_source], "registrant": listing,
                    "limitations": limitations}
        return {"kind": "ncen", "status": "available", "sources": [sub_source, source], "registrant": listing,
                "filing": filing, "result": parsed, "limitations": limitations}


# -- HTTP boundary ------------------------------------------------------------------------------

def sec_extra_router(settings, store, session_dependency):
    from fastapi import APIRouter, Depends, Query

    from aplomb.api.errors import ServiceError
    from aplomb.api.limiter import SessionLimiter

    from .company_routes import StatusRecordingTransport, sec_contact
    from .core import PublicHTTP, ResearchService

    router = APIRouter()
    limiter = SessionLimiter(store)

    def engine():
        """None when no descriptive SEC contact is configured (explicit unavailable state)."""
        contact = sec_contact(settings)
        if not contact:
            return None
        try:
            transport = StatusRecordingTransport(PublicHTTP(contact))
        except ValueError:
            return None
        return SecExtra(ResearchService(transport, lambda: datetime.now(timezone.utc)), store)

    def unconfigured(kind):
        return {"kind": kind, "status": "unavailable", "code": "sec_contact_unconfigured", "http_status": None,
                "limitations": ["A descriptive SEC User-Agent contact (APLOMB_SEC_CONTACT) is required; "
                                "none is invented."]}

    def invalid(message):
        return ServiceError("validation_error", message)

    def checked_cik(value):
        try:
            return cik_id(value)
        except ValueError as exc:
            raise invalid("A valid exact SEC CIK is required") from exc

    def checked_tag(taxonomy, tag):
        if taxonomy not in TAXONOMIES or not TAG.fullmatch(tag):
            raise invalid("Unsupported taxonomy or concept tag")

    @router.get("/v1/research/sec/concept/{cik}")
    def concept(cik: str, sid: str = Depends(session_dependency),
                taxonomy: str = Query(default="us-gaap", max_length=12),
                tag: str = Query(max_length=151), as_of: str | None = Query(default=None, max_length=10)):
        cik = checked_cik(cik)
        checked_tag(taxonomy, tag)
        if as_of is not None:
            try:
                as_of = str(date.fromisoformat(as_of))
            except ValueError as exc:
                raise invalid("as_of must be an ISO date") from exc
        limiter.take(sid, "sec-extra", 6, 60)
        sec = engine()
        return sec.concept(sid, cik, taxonomy, tag, as_of) if sec else unconfigured("company_concept")

    @router.get("/v1/research/sec/frames")
    def frames(sid: str = Depends(session_dependency), taxonomy: str = Query(default="us-gaap", max_length=12),
               tag: str = Query(max_length=151), unit: str = Query(default="USD", max_length=45),
               period: str = Query(max_length=12), limit: int = Query(default=100, ge=1, le=500),
               order: str = Query(default="desc", pattern="^(asc|desc)$")):
        checked_tag(taxonomy, tag)
        if not FRAME_UNIT.fullmatch(unit) or not FRAME_PERIOD.fullmatch(period):
            raise invalid("Unit must look like USD or USD-per-shares; period like CY2023, CY2023Q4 or CY2023Q4I")
        limiter.take(sid, "sec-extra", 6, 60)
        sec = engine()
        return sec.frame(sid, taxonomy, tag, unit, period, limit, order) if sec else unconfigured("xbrl_frame")

    @router.get("/v1/research/sec/latest-filings")
    def latest(sid: str = Depends(session_dependency), form: str = Query(default="", max_length=20),
               cik: str | None = Query(default=None, max_length=10), count: int = Query(default=40, ge=10, le=100)):
        if form and not FORM_FILTER.fullmatch(form):
            raise invalid("Unsupported form type filter")
        cik = checked_cik(cik) if cik else None
        limiter.take(sid, "sec-extra", 6, 60)
        sec = engine()
        return sec.feed(sid, form, cik, count) if sec else unconfigured("edgar_feed")

    @router.get("/v1/research/sec/ncen/{cik}")
    def ncen(cik: str, sid: str = Depends(session_dependency),
             series: str | None = Query(default=None, max_length=10)):
        cik = checked_cik(cik)
        if series is not None and not SERIES.fullmatch(series):
            raise invalid("Series identifier must look like S000000000")
        limiter.take(sid, "sec-extra", 6, 60)
        sec = engine()
        return sec.ncen(sid, cik, series) if sec else unconfigured("ncen")

    return router
