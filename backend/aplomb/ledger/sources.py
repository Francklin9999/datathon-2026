"""Narrow code-owned numeric proofs for captured research source formats.

These attest exact extraction/arithmetic and source identity, not external truth.
No caller-supplied verification result is consumed.
"""

import csv
import io
import json
import math
import re
from datetime import date, timedelta
from urllib.parse import quote, urlsplit

from aplomb.contracts.models import Fact, Verification


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate source JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def fact_data(fact):
    return fact.to_wire() if isinstance(fact, Fact) else dict(fact)


def prepare(ledger, data, document):
    ledger.register_document(document)  # run ownership and immutable original text
    sources = data.get("sources", [])
    if not sources or any(
        (s.source_url if hasattr(s, "source_url") else s.get("sourceUrl", s.get("source_url")))
        != document.source_url
        for s in sources
    ):
        raise ValueError("Every source must match the captured document URL")
    url = urlsplit(document.source_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.fragment
    ):
        raise ValueError("Captured source requires canonical HTTPS URL")
    return url


def exact_number(value, expected):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or type(expected) not in (int, float)
        or not math.isfinite(expected)
        or value != expected
    ):
        raise ValueError("Declared value differs from finite code-extracted value")


def context(data, period, available_at):
    supplied = data.get("period")
    if hasattr(supplied, "to_wire"):
        supplied = supplied.to_wire()
    if supplied is not None and (supplied.get("start"), supplied.get("end")) != (
        period["start"],
        period["end"],
    ):
        raise ValueError("Declared period differs from source period")
    supplied_availability = data.get("availableAt", data.get("available_at"))
    if supplied_availability is not None and supplied_availability != available_at:
        raise ValueError("Declared availability differs from source availability")
    data.pop("available_at", None)
    data["period"], data["availableAt"] = period, available_at


def seal(ledger, data, document, *, code, detail, method, params):
    data = {
        **data,
        "createdBy": "research",
        "method": {
            "id": method,
            "description": {"en": detail, "fr": detail},
            "params": {
                "documentRef": document.reference,
                "documentHash": document.content_hash,
                **params,
            },
        },
    }
    fid = ledger.add_fact(data)
    ledger._facts[fid].verification = Verification.model_validate(
        {
            "status": "verified",
            "checks": [
                {"code": code, "ok": True, "detail": detail + "; SHA-256 " + document.content_hash}
            ],
        }
    )
    return fid


def source_fact(ledger, fact, document, extraction):
    data = fact_data(fact)
    url = prepare(ledger, data, document)
    if data.get("inputs"):
        raise ValueError("Source extraction cannot claim caller-supplied dependencies")
    form = extraction.get("format")
    if form == "sec_companyfacts":
        if set(extraction) != {"format", "concept", "unit", "row_index"}:
            raise ValueError("Unexpected SEC proof fields")
        match = re.fullmatch(r"/api/xbrl/companyfacts/CIK([0-9]{10})\.json", url.path)
        if url.hostname != "data.sec.gov" or url.query or not match:
            raise ValueError("SEC proof requires canonical companyfacts source")
        source = strict_json(document.text)
        cik = source.get("cik")
        if type(cik) is not int or str(cik).zfill(10) != match[1]:
            raise ValueError("SEC source CIK mismatch")
        subject = data.get("subject", {})
        if (
            str(subject.get("id")) not in (str(cik), str(cik).zfill(10))
            or subject.get("type") != "asset"
        ):
            raise ValueError("SEC numeric fact must identify the source CIK")
        concept, unit, index = extraction["concept"], extraction["unit"], extraction["row_index"]
        if (
            not isinstance(concept, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", concept)
            or unit not in ("USD", "CAD")
            or type(index) is not int
            or index < 0
        ):
            raise ValueError("Unsupported SEC concept/unit/row index")
        try:
            row = source["facts"]["us-gaap"][concept]["units"][unit][index]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("SEC requested source row absent") from exc
        exact_number(data.get("value"), row.get("val"))
        if (
            data.get("unit") != unit.lower()
            or data.get("currency") != unit
            or data.get("metric") != "quote.figure"
        ):
            raise ValueError("SEC unit/currency/metric mismatch")
        filed, end = date.fromisoformat(row["filed"]), date.fromisoformat(row["end"])
        start = date.fromisoformat(row.get("start", row["end"]))
        if not start <= end <= filed <= date.fromisoformat(ledger.as_of):
            raise ValueError("SEC source period or availability is future/inconsistent")
        context(data, {"start": str(start), "end": str(end)}, f"{filed}T23:59:59Z")
        data["kind"] = "evidence"
        return seal(
            ledger,
            data,
            document,
            code="LED_SEC_XBRL",
            detail="Code extracted exact SEC XBRL value, explicit currency unit, CIK and filing period",
            method="M_OBSERVED_ROW",
            params={"concept": concept, "sourceUnit": unit, "rowIndex": index},
        )
    if form == "issuer_holdings_csv":
        if url.hostname != "www.ishares.com":
            raise ValueError("Holdings proof requires a reviewed issuer domain")
        if set(extraction) != {
            "format",
            "identifier",
            "effective_date",
            "identifier_column",
            "weight_column",
        }:
            raise ValueError("Unexpected holdings proof fields")
        identifier, effective = extraction["identifier"], extraction["effective_date"]
        id_col, weight_col = extraction["identifier_column"], extraction["weight_column"]
        if not all(isinstance(v, str) and v for v in (identifier, effective, id_col, weight_col)):
            raise ValueError("Invalid holdings extraction fields")
        source_date = date.fromisoformat(effective)
        if source_date > date.fromisoformat(ledger.as_of):
            raise ValueError("Future holdings effective date")
        if data.get("subject", {}).get("type") != "asset" or data["subject"]["id"] != identifier:
            raise ValueError("Holdings identifier differs from fact subject")
        if (
            data.get("metric") != "quote.figure"
            or data.get("unit") != "pct"
            or data.get("currency") is not None
        ):
            raise ValueError("Holdings require percent quote figure with no currency")
        if not re.search(r"(?:%|\bpercent\b|\bpct\b)", weight_col, re.I):
            raise ValueError("Holdings weight header does not prove percentage units")
        rows = list(csv.reader(io.StringIO(document.text)))
        headers = [(i, r) for i, r in enumerate(rows) if id_col in r and weight_col in r]
        if len(headers) != 1:
            raise ValueError("Missing or ambiguous holdings header")
        header_index, header = headers[0]
        if len(set(header)) != len(header):
            raise ValueError("Duplicate CSV headers")
        dates = [
            r[1].strip()
            for r in rows[:header_index]
            if len(r) >= 2
            and r[0].strip().casefold()
            in ("holdings date", "holdings as of", "as of", "effective date")
        ]
        if dates != [effective]:
            raise ValueError("Source preamble does not unambiguously prove holdings date")
        id_index, weight_index = header.index(id_col), header.index(weight_col)
        selected = [
            r
            for r in rows[header_index + 1 :]
            if len(r) == len(header) and r[id_index].strip() == identifier
        ]
        if len(selected) != 1:
            raise ValueError("Missing or duplicate holdings identifier")
        value_text = selected[0][weight_index].strip()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value_text):
            raise ValueError("Ambiguous/non-numeric holdings weight")
        value = float(value_text)
        if not 0 <= value <= 100:
            raise ValueError("Holdings percentage outside bounds")
        exact_number(data.get("value"), value)
        # Effective holdings date is not proof of the file's publication time.
        context(data, {"start": effective, "end": effective}, None)
        data["kind"] = "evidence"
        return seal(
            ledger,
            data,
            document,
            code="LED_HOLDINGS_CSV",
            detail="Code extracted exact holding percentage from named unit header and dated issuer CSV",
            method="M_OBSERVED_ROW",
            params={
                "identifier": identifier,
                "weightColumn": weight_col,
                "effectiveDate": effective,
            },
        )
    raise ValueError("Unsupported structured source proof format")


def pageviews_ratio(ledger, fact, document, *, article):
    data = fact_data(fact)
    prepare(ledger, data, document)
    as_of = date.fromisoformat(ledger.as_of)
    first, last = as_of - timedelta(days=395), as_of - timedelta(days=1)
    if not isinstance(article, str) or not article or len(article) > 300:
        raise ValueError("Invalid article identity")
    expected_url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia.org/all-access/user/"
        + quote(article, safe="")
        + f"/daily/{first:%Y%m%d}00/{last:%Y%m%d}00"
    )
    if document.source_url != expected_url:
        raise ValueError("Pageviews source URL/article/window mismatch")
    source = strict_json(document.text)
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("items"), list)
        or len(source["items"]) != 395
    ):
        raise ValueError("Pageviews require complete 395-day source array")
    values = {}
    for item in source["items"]:
        if not isinstance(item, dict) or any(
            item.get(k) != v
            for k, v in {
                "project": "en.wikipedia",
                "access": "all-access",
                "agent": "user",
                "article": article,
                "granularity": "daily",
            }.items()
        ):
            raise ValueError("Unexpected pageviews dimensions/article")
        timestamp, views = item.get("timestamp"), item.get("views")
        if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{8}00", timestamp):
            raise ValueError("Invalid daily pageviews timestamp")
        day = date.fromisoformat(timestamp[:4] + "-" + timestamp[4:6] + "-" + timestamp[6:8])
        if day in values or type(views) is not int or views < 0:
            raise ValueError("Duplicate, negative or noninteger daily pageviews")
        values[day] = views
    expected_days = {first + timedelta(days=i) for i in range(395)}
    if set(values) != expected_days:
        raise ValueError("Incomplete/extra/future daily pageviews coverage")
    split = as_of - timedelta(days=30)
    recent_sum = sum(v for d, v in values.items() if d >= split)
    baseline_sum = sum(v for d, v in values.items() if d < split)
    if baseline_sum <= 0:
        raise ValueError("Pageviews baseline is zero")
    ratio = (recent_sum / 30) / (baseline_sum / 365)
    exact_number(data.get("value"), ratio)
    if (
        data.get("metric") != "attention.pageviews_ratio"
        or data.get("unit") != "ratio"
        or data.get("currency") is not None
        or data.get("inputs")
    ):
        raise ValueError("Pageviews ratio metric/unit/currency/dependency mismatch")
    # Source-backed claim is about this article; ticker mapping is separate metadata.
    subject = data.get("subject", {})
    if subject.get("type") != "event" or subject.get("id") != article:
        raise ValueError("Pageviews numeric fact must identify the source article")
    # Completed observation dates do not establish when this response was published.
    context(data, {"start": str(split), "end": str(last)}, None)
    anchor = {
        **data,
        "metric": "count.sources",
        "kind": "observed",
        "value": 1.0,
        "unit": "count",
        "currency": None,
        "period": {"start": str(first), "end": str(last)},
        "subject": {"type": "event", "id": article, "variant": "source:" + document.content_hash},
        "label": {
            "en": "Validated daily pageview source",
            "fr": "Source quotidienne de consultations validée",
        },
        "nObs": 395,
        "limitations": ["LIM_ATTENTION_PROXY"],
        "inputs": [],
    }
    anchor_id = seal(
        ledger,
        anchor,
        document,
        code="LED_PAGEVIEWS_SERIES",
        detail="Code validated complete contiguous daily source, dimensions, article and count domain",
        method="M_OBSERVED_ROW",
        params={"firstDay": str(first), "lastDay": str(last), "days": 395},
    )
    data["kind"], data["inputs"], data["nObs"] = "computed", [anchor_id], 395
    data["limitations"] = sorted(set(data.get("limitations", [])) | {"LIM_ATTENTION_PROXY"})
    return seal(
        ledger,
        data,
        document,
        code="LED_PAGEVIEWS_RATIO",
        detail="Code computed recent daily mean divided by baseline daily mean from validated source",
        method="M_ATTENTION_RATIO",
        params={
            "recentDays": 30,
            "baselineDays": 365,
            "recentSum": recent_sum,
            "baselineSum": baseline_sum,
            "sourceFactId": anchor_id,
        },
    )
