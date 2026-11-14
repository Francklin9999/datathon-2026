"""Ingestion: raw files -> validated, normalized, immutable snapshot (data SPEC "Pipeline").

Stages: read source -> validate raw schema/rows -> preserve hashes and retrieval metadata ->
normalize types/classification -> attach availability policy -> write staged objects ->
validate cross-dataset coverage -> atomically publish the manifest. A failed ingestion never
replaces the active manifest. This module is ingestion-only: run contexts read data through
``Snapshot.gate`` and never import it.

Layout under the data root (paths in the manifest are relative to it, so the tree uploads to
S3 unchanged)::

    raw/<version>/<file>            exact input bytes (gitignored)
    normalized/<version>/<id>.csv   normalized datasets (gitignored, reproducible)
    manifests/<version>.json        commit point: hashes, counts, coverage, policies, checks
    manifests/active.json           {"dataVersion": ...}, replaced atomically

CLI (from ``backend/``)::

    python -m aplomb.datastore.ingest --source ../Datathon2026/alphaforge_starter \
        --data-root ../data --version snap-20261113-starter
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import secrets
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

from . import availability as av
from .constants import (
    ASSET_CLASS_TO_GROUP,
    CALENDAR_REF_CAD,
    CALENDAR_REF_USD,
    CASH_TICKERS,
    CONTRACT_VERSION,
    CURRENCIES,
    GICS_SECTORS,
    LISTED_ASSET_CLASSES,
    MARKET_COUNTRY,
    SINGLE_NAME_CLASSES,
    THEME_TAGS,
)
from .errors import IngestionError, SnapshotIntegrityError
from .integrity import VERSION_RE, canonical_sha256, sha256_hex
from .quality import (
    FX_INVERSE_TOLERANCE,
    MAX_GAP_DAYS_CRYPTO,
    MAX_GAP_DAYS_EXCHANGE,
    SUSPICIOUS_ONE_DAY_MOVE,
    fmt_bool,
    fmt_number,
    fmt_volume,
    is_split_anomaly,
    ohlc_consistent,
    parse_bool,
    parse_finite,
)
from .schemas import (
    MANIFEST_SCHEMA_VERSION,
    METADATA_OPTIONAL,
    METADATA_REQUIRED,
    NORMALIZED,
    RAW_HEADERS,
    STARTER_OPTIONAL,
    STARTER_REQUIRED,
)
from .timeutil import date_or_ts_to_ts, parse_date, ts, utc_now_iso

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(timezone.utc)


# --- Inputs ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceBundle:
    """Raw input files keyed by their canonical file name (see ``schemas.RAW_HEADERS``)."""

    files: dict[str, bytes]
    origins: dict[str, str]  # file name -> where it came from (repo-relative path or provider)


def read_starter_bundle(source_dir: Path, metadata_dir: Path) -> SourceBundle:
    files: dict[str, bytes] = {}
    origins: dict[str, str] = {}
    for name in STARTER_REQUIRED + STARTER_OPTIONAL:
        path = source_dir / name
        if not path.is_file():
            if name in STARTER_REQUIRED:
                raise IngestionError(f"missing required source file {path}")
            continue
        files[name] = path.read_bytes()
        origins[name] = _display_path(path)
    for name in METADATA_REQUIRED + METADATA_OPTIONAL:
        path = metadata_dir / name
        if not path.is_file():
            if name in METADATA_REQUIRED:
                raise IngestionError(f"missing required metadata file {path}")
            continue
        files[name] = path.read_bytes()
        origins[name] = _display_path(path)
    return SourceBundle(files, origins)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    for parent in resolved.parents:
        if (parent / ".git").exists():
            return resolved.relative_to(parent).as_posix()
    return resolved.as_posix()


def _read_csv(bundle: SourceBundle, name: str, problems: list[str]) -> list[dict[str, str]]:
    raw = bundle.files[name]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        problems.append(f"{name}: not UTF-8")
        return []
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        problems.append(f"{name}: empty file")
        return []
    expected = RAW_HEADERS[name]
    if tuple(header) != expected:
        problems.append(f"{name}: header {header} does not match expected {list(expected)}")
        return []
    rows: list[dict[str, str]] = []
    for line_no, record in enumerate(reader, start=2):
        if not record:
            continue
        if len(record) != len(expected):
            problems.append(f"{name}:{line_no}: {len(record)} fields, expected {len(expected)}")
            continue
        rows.append(dict(zip(expected, record)))
    return rows


# --- Normalization -----------------------------------------------------------------------------


@dataclass
class _Check:
    name: str
    ok: bool
    detail: str


@dataclass
class _Dataset:
    dataset_id: str
    rows: list[list[str]]
    first_date: str | None = None
    last_date: str | None = None
    checks: list[_Check] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class BuildOutput:
    normalized: dict[str, bytes]
    datasets: dict[str, _Dataset]
    flags: list[dict]
    data_as_of: str
    source_metadata: dict[str, list[dict[str, str]]]
    on_demand: list[dict]


def _encode_rows(dataset_id: str, rows: list[list[str]]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(NORMALIZED[dataset_id].names)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _flag(flags: list[dict], dataset_id: str, code: str, detail: str, ticker: str = "", day: str = "") -> None:
    flags.append({"datasetId": dataset_id, "code": code, "ticker": ticker or None, "date": day or None, "detail": detail})


def _req(row: dict[str, str], key: str, where: str, problems: list[str]) -> str:
    value = row.get(key, "")
    if value is None or value.strip() == "":
        problems.append(f"{where}: empty {key}")
        return ""
    if value != value.strip():
        problems.append(f"{where}: {key} has leading/trailing spaces {value!r}")
    return value


def _date(text: str, where: str, problems: list[str]) -> date | None:
    try:
        return parse_date(text, where)
    except ValueError as exc:
        problems.append(str(exc))
        return None


def _num(text: str, where: str, problems: list[str]) -> float | None:
    try:
        return parse_finite(text, where)
    except ValueError as exc:
        problems.append(str(exc))
        return None


def build_snapshot(bundle: SourceBundle) -> BuildOutput:
    """Validate and normalize a bundle. Pure: no filesystem access, no clock.

    Raises ``IngestionError`` listing every rejection found.
    """
    problems: list[str] = []
    flags: list[dict] = []
    for name in bundle.files:
        if name not in RAW_HEADERS and name not in STARTER_OPTIONAL:
            problems.append(f"unexpected input file {name}")
    for name in STARTER_REQUIRED + METADATA_REQUIRED:
        if name not in bundle.files:
            problems.append(f"missing input file {name}")
    if problems:
        raise IngestionError("input bundle rejected", problems)

    tables = {name: _read_csv(bundle, name, problems) for name in bundle.files if name in RAW_HEADERS}
    if problems:
        raise IngestionError("raw schema validation failed", problems)

    source_metadata = _sources_metadata(tables["sources_metadata.csv"], problems)

    # Universe ---------------------------------------------------------------------------------
    universe: dict[str, dict[str, str]] = {}
    asset_ids: set[str] = set()
    on_demand: list[dict] = []
    for i, row in enumerate(tables["assets_universe.csv"], start=2):
        where = f"assets_universe.csv:{i}"
        _universe_row(row, where, "starter", universe, asset_ids, problems)
    for i, row in enumerate(tables.get("ondemand_assets.csv", []), start=2):
        where = f"ondemand_assets.csv:{i}"
        prov = {k: row.get(k, "") for k in ("provider", "source_url", "retrieved_at", "terms")}
        base = {k: row[k] for k in RAW_HEADERS["assets_universe.csv"] if k in row}
        base["asset_id"] = f"OD-{row.get('ticker', '')}"
        if not row.get("sector", "").strip():
            base["sector"] = "unknown"
        _universe_row(base, where, "on_demand", universe, asset_ids, problems)
        try:
            prov["retrieved_at"] = date_or_ts_to_ts(prov["retrieved_at"], f"{where} retrieved_at")
        except ValueError as exc:
            problems.append(str(exc))
        if not prov["provider"].strip():
            problems.append(f"{where}: empty provider")
        on_demand.append({"ticker": row.get("ticker", ""), "provider": prov["provider"],
                          "sourceUrl": prov["source_url"] or None, "retrievedAt": prov["retrieved_at"],
                          "terms": prov["terms"] or None, "sectorSourced": bool(row.get("sector", "").strip())})
    for ref in (CALENDAR_REF_CAD, CALENDAR_REF_USD):
        if ref not in universe:
            problems.append(f"assets_universe: calendar reference ticker {ref} is missing (A-15)")
    if problems:
        raise IngestionError("assets_universe validation failed", problems)

    # Prices -----------------------------------------------------------------------------------
    by_ticker: dict[str, list[tuple[date, list[str], float, float]]] = defaultdict(list)
    seen_keys: set[tuple[str, str]] = set()
    price_sources = [("prices_daily.csv", tables["prices_daily.csv"])]
    if "ondemand_prices.csv" in tables:
        price_sources.append(("ondemand_prices.csv", tables["ondemand_prices.csv"]))
    for fname, rows in price_sources:
        for i, row in enumerate(rows, start=2):
            where = f"{fname}:{i}"
            d = _date(_req(row, "date", where, problems), f"{where} date", problems)
            ticker = _req(row, "ticker", where, problems)
            currency = _req(row, "currency", where, problems)
            values = {k: _num(row.get(k, ""), f"{where} {k}", problems)
                      for k in ("open", "high", "low", "close", "adj_close", "volume")}
            if d is None or not ticker or any(v is None for v in values.values()):
                continue
            asset = universe.get(ticker)
            if asset is None:
                problems.append(f"{where}: unknown ticker {ticker}")
                continue
            if currency != asset["currency"]:
                problems.append(f"{where}: currency {currency} differs from listing currency {asset['currency']}")
                continue
            key = (ticker, d.isoformat())
            if key in seen_keys:
                problems.append(f"{where}: duplicate (date, ticker) {d.isoformat()} {ticker}")
                continue
            seen_keys.add(key)
            if values["adj_close"] <= 0:
                problems.append(f"{where}: non-positive adj_close {row['adj_close']}")
                continue
            if values["volume"] < 0:
                problems.append(f"{where}: negative volume {row['volume']}")
                continue
            if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
                _flag(flags, "prices_daily", "nonpositive_ohlc", "open/high/low/close <= 0 (adj_close valid)", ticker, d.isoformat())
            elif not ohlc_consistent(values["open"], values["high"], values["low"], values["close"]):
                _flag(flags, "prices_daily", "ohlc_inconsistent", "open/close outside [low, high]", ticker, d.isoformat())
            if values["volume"] == 0:
                _flag(flags, "prices_daily", "zero_volume", "zero-volume observation retained", ticker, d.isoformat())
            avail = av.price_row(d, asset["asset_class"])
            normalized = [
                d.isoformat(), ticker,
                fmt_number(values["open"]), fmt_number(values["high"]), fmt_number(values["low"]),
                fmt_number(values["close"]), fmt_number(values["adj_close"]), fmt_volume(values["volume"]),
                currency, avail.current, avail.historical,
            ]
            by_ticker[ticker].append((d, normalized, values["adj_close"], values["volume"]))
    for ticker in universe:
        if not by_ticker.get(ticker):
            problems.append(f"prices: no rows for universe ticker {ticker}")
    if problems:
        raise IngestionError("prices_daily validation failed", problems)

    price_rows: list[list[str]] = []
    for ticker in sorted(by_ticker):
        series = sorted(by_ticker[ticker], key=lambda t: t[0])
        is_crypto = universe[ticker]["asset_class"] == "crypto"
        max_gap = MAX_GAP_DAYS_CRYPTO if is_crypto else MAX_GAP_DAYS_EXCHANGE
        for prev, cur in zip(series, series[1:]):
            gap = (cur[0] - prev[0]).days
            if gap > max_gap:
                _flag(flags, "prices_daily", "coverage_gap", f"{gap}-day gap before this observation", ticker, cur[0].isoformat())
            move = cur[2] / prev[2] - 1
            if abs(move) > SUSPICIOUS_ONE_DAY_MOVE:
                _flag(flags, "prices_daily", "suspicious_return", f"one-day adjusted move {move:+.1%}", ticker, cur[0].isoformat())
        price_rows.extend(r[1] for r in series)
    dates_of = {t: {r[0] for r in rows} for t, rows in by_ticker.items()}
    calendar_mismatch: list[str] = []
    for ticker, asset in universe.items():
        if asset["asset_class"] == "crypto" or ticker in (CALENDAR_REF_CAD, CALENDAR_REF_USD):
            continue
        ref = {"CAN": CALENDAR_REF_CAD, "USA": CALENDAR_REF_USD}.get(asset["country"])
        if ref is None:
            _flag(flags, "prices_daily", "calendar_unknown", f"market {asset['market']!r} has no reference calendar", ticker)
            continue
        if dates_of[ticker] != dates_of[ref]:
            missing = len(dates_of[ref] - dates_of[ticker])
            extra = len(dates_of[ticker] - dates_of[ref])
            calendar_mismatch.append(ticker)
            _flag(flags, "prices_daily", "calendar_mismatch",
                  f"differs from {ref} calendar: {missing} reference days missing, {extra} extra days", ticker)
    master = sorted(dates_of[CALENDAR_REF_CAD] & dates_of[CALENDAR_REF_USD])

    first_avail = {t: min(r[1][-2] for r in rows) for t, rows in by_ticker.items()}
    first_avail_hist = {t: min(r[1][-1] for r in rows) for t, rows in by_ticker.items()}
    universe_rows = []
    for ticker in sorted(universe, key=lambda t: (universe[t]["asset_id"], t)):
        a = universe[ticker]
        universe_rows.append([
            a["asset_id"], ticker, a["name"], a["asset_class"], ASSET_CLASS_TO_GROUP[a["asset_class"]], a["market"],
            a["currency"], a["sector"], a["gics_sector"], a["country"], fmt_bool(a["asset_class"] in SINGLE_NAME_CLASSES),
            a["tier"], first_avail[ticker], first_avail_hist[ticker],
        ])

    all_dates = sorted({r[0] for r in price_rows})
    datasets: dict[str, _Dataset] = {}
    n_zero = sum(1 for f in flags if f["code"] == "zero_volume")
    zero_detail = ", ".join(f"{f['ticker']} {f['date']}" for f in flags if f["code"] == "zero_volume")
    datasets["assets_universe"] = _Dataset(
        "assets_universe", universe_rows,
        checks=[
            _Check("Header matches organizer schema", True, ", ".join(RAW_HEADERS["assets_universe.csv"])),
            _Check("Ticker and asset_id unique", True, f"{len(universe_rows)} assets"),
            _Check("Asset class and currency in closed lists", True, "classes: " + ", ".join(sorted({a['asset_class'] for a in universe.values()}))),
            _Check("Every asset has price rows", True, f"{len(universe_rows)} of {len(universe_rows)}"),
        ],
        source_files=["assets_universe.csv"] + (["ondemand_assets.csv"] if on_demand else []),
        extra={"byTier": _count_by(universe_rows, 11)},
    )
    datasets["prices_daily"] = _Dataset(
        "prices_daily", price_rows, all_dates[0], all_dates[-1],
        checks=[
            _Check("Header matches organizer schema", True, ", ".join(RAW_HEADERS["prices_daily.csv"])),
            _Check("No duplicate (date, ticker) keys, valid dates, finite values", True, f"{len(price_rows)} rows"),
            _Check("Adjusted close strictly positive", True, "all rows"),
            _Check("Ticker and currency match the universe", True, f"{len(by_ticker)} tickers"),
            _Check("No zero-volume observations", n_zero == 0,
                   "none" if n_zero == 0 else f"{n_zero} flagged and retained, not deleted: {zero_detail}"),
            _Check("Each listed asset follows its market reference calendar (XIU.TO or SPY)", not calendar_mismatch,
                   "all match" if not calendar_mismatch else "mismatch: " + ", ".join(calendar_mismatch)),
            _Check(f"No one-day adjusted move above {SUSPICIOUS_ONE_DAY_MOVE:.0%}",
                   not any(f["code"] == "suspicious_return" for f in flags), _flag_summary(flags, "suspicious_return")),
            _Check(f"No observation gaps above {MAX_GAP_DAYS_EXCHANGE} days (crypto {MAX_GAP_DAYS_CRYPTO})",
                   not any(f["code"] == "coverage_gap" for f in flags), _flag_summary(flags, "coverage_gap")),
            _Check("Open/high/low/close consistent", not any(f["code"] in ("ohlc_inconsistent", "nonpositive_ohlc") for f in flags),
                   _flag_summary(flags, "ohlc_inconsistent", "nonpositive_ohlc")),
            _Check("Master calendar (XIU.TO ∩ SPY)", True, f"{len(master)} days, {master[0].isoformat()} to {master[-1].isoformat()}"),
        ],
        source_files=["prices_daily.csv"] + (["ondemand_prices.csv"] if "ondemand_prices.csv" in tables else []),
        extra={"rowsByTicker": {t: len(r) for t, r in sorted(by_ticker.items())}, "masterCalendarDays": len(master)},
    )

    # Corporate actions ------------------------------------------------------------------------
    ca_rows: list[list[str]] = []
    ca_keys: set[tuple[str, str, str]] = set()
    for i, row in enumerate(tables["corporate_actions.csv"], start=2):
        where = f"corporate_actions.csv:{i}"
        d = _date(_req(row, "ex_date", where, problems), f"{where} ex_date", problems)
        ticker = _req(row, "ticker", where, problems)
        action = _req(row, "action", where, problems)
        unit = _req(row, "unit", where, problems)
        value = _num(row.get("value", ""), f"{where} value", problems)
        if d is None or not ticker or not action or not unit or value is None:
            continue
        if ticker not in universe:
            problems.append(f"{where}: unknown ticker {ticker}")
            continue
        if action not in ("dividend", "split"):
            problems.append(f"{where}: unknown action {action!r}")
            continue
        if value <= 0:
            problems.append(f"{where}: non-positive value {row['value']}")
            continue
        key = (d.isoformat(), ticker, action)
        if key in ca_keys:
            problems.append(f"{where}: duplicate (ex_date, ticker, action) {key}")
            continue
        ca_keys.add(key)
        if action == "split" and is_split_anomaly(value):
            _flag(flags, "corporate_actions", "split_anomaly", f"split ratio {value} is not an ordinary ratio", ticker, d.isoformat())
        if action == "dividend" and unit != f"{universe[ticker]['currency']} per share":
            _flag(flags, "corporate_actions", "dividend_unit_mismatch", f"unit {unit!r} vs listing currency", ticker, d.isoformat())
        a = av.corporate_action_row(d)
        ca_rows.append([d.isoformat(), ticker, action, fmt_number(value), unit, a.current, a.historical])
    if problems:
        raise IngestionError("corporate_actions validation failed", problems)
    ca_rows.sort(key=lambda r: (r[1], r[0], r[2]))
    ca_dates = sorted(r[0] for r in ca_rows)
    n_div = sum(1 for r in ca_rows if r[2] == "dividend")
    datasets["corporate_actions"] = _Dataset(
        "corporate_actions", ca_rows, ca_dates[0] if ca_dates else None, ca_dates[-1] if ca_dates else None,
        checks=[
            _Check("Header matches organizer schema", True, ", ".join(RAW_HEADERS["corporate_actions.csv"])),
            _Check("No duplicate (ex_date, ticker, action), known tickers, positive values", True,
                   f"{len(ca_rows)} rows: {n_div} dividends, {len(ca_rows) - n_div} splits"),
            _Check("Split ratios are ordinary ratios", not any(f["code"] == "split_anomaly" for f in flags),
                   _flag_summary(flags, "split_anomaly")),
            _Check("Never re-applied to prices", True, "annotation only; prices use adj_close (M_PRICE_ADJ_CLOSE)"),
        ],
        source_files=["corporate_actions.csv"],
    )

    # FX ---------------------------------------------------------------------------------------
    fx_rows: list[list[str]] = []
    fx_dates: set[date] = set()
    for i, row in enumerate(tables["fx_usdcad_daily.csv"], start=2):
        where = f"fx_usdcad_daily.csv:{i}"
        d = _date(_req(row, "date", where, problems), f"{where} date", problems)
        usdcad = _num(row.get("usdcad", ""), f"{where} usdcad", problems)
        cadusd = _num(row.get("cadusd", ""), f"{where} cadusd", problems)
        if d is None or usdcad is None or cadusd is None:
            continue
        if d in fx_dates:
            problems.append(f"{where}: duplicate date {d.isoformat()}")
            continue
        if usdcad <= 0 or cadusd <= 0:
            problems.append(f"{where}: non-positive rate")
            continue
        fx_dates.add(d)
        if abs(cadusd - round(1 / usdcad, 6)) > FX_INVERSE_TOLERANCE:
            _flag(flags, "fx_usdcad_daily", "fx_inverse_mismatch", f"cadusd {cadusd} vs 1/usdcad {1 / usdcad:.6f}", day=d.isoformat())
        a = av.fx_row(d)
        fx_rows.append([d.isoformat(), fmt_number(usdcad), fmt_number(cadusd), a.current, a.historical])
    if problems:
        raise IngestionError("fx_usdcad_daily validation failed", problems)
    fx_rows.sort(key=lambda r: r[0])
    if not fx_rows:
        raise IngestionError("fx_usdcad_daily has no rows")
    first_fx = date.fromisoformat(fx_rows[0][0])
    no_same_day = [d for d in master if d not in fx_dates]
    no_prior = [d for d in master if d < first_fx]
    for d in no_prior:
        _flag(flags, "fx_usdcad_daily", "fx_no_prior_rate", "master day before the first published rate", day=d.isoformat())
    datasets["fx_usdcad_daily"] = _Dataset(
        "fx_usdcad_daily", fx_rows, fx_rows[0][0], fx_rows[-1][0],
        checks=[
            _Check("Header matches organizer schema", True, ", ".join(RAW_HEADERS["fx_usdcad_daily.csv"])),
            _Check("Dates unique, rates finite and positive", True, f"{len(fx_rows)} rows"),
            _Check("cadusd equals 1/usdcad rounded to 6 decimals", not any(f["code"] == "fx_inverse_mismatch" for f in flags),
                   _flag_summary(flags, "fx_inverse_mismatch")),
            _Check("Every master-calendar day has a rate on or before it", not no_prior,
                   (f"{len(no_same_day)} master days use the previous publication (LIM_FX_FFILL): "
                    + ", ".join(d.isoformat() for d in no_same_day)) if not no_prior
                   else f"{len(no_prior)} master days precede the first rate"),
        ],
        source_files=["fx_usdcad_daily.csv"],
        extra={"masterDaysWithoutSameDayRate": [d.isoformat() for d in no_same_day]},
    )

    # Macro ------------------------------------------------------------------------------------
    series_meta = _macro_series_meta(tables["macro_series.csv"], problems)
    releases = _release_dates(tables.get("macro_release_dates.csv"), series_meta, problems)
    if problems:
        raise IngestionError("macro metadata validation failed", problems)
    macro_rows: list[list[str]] = []
    macro_keys: set[tuple[str, str]] = set()
    per_series: dict[str, list[date]] = defaultdict(list)
    for i, row in enumerate(tables["macro_rates.csv"], start=2):
        where = f"macro_rates.csv:{i}"
        d = _date(_req(row, "date", where, problems), f"{where} date", problems)
        sid = _req(row, "series_id", where, problems)
        value = _num(row.get("value", ""), f"{where} value", problems)
        texts = [_req(row, k, where, problems) for k in ("unit", "frequency", "label", "source")]
        if d is None or not sid or value is None or not all(texts):
            continue
        meta = series_meta.get(sid)
        if meta is None:
            problems.append(f"{where}: series {sid} has no entry in macro_series.csv")
            continue
        key = (sid, d.isoformat())
        if key in macro_keys:
            problems.append(f"{where}: duplicate (date, series_id) {key}")
            continue
        macro_keys.add(key)
        if meta["frequency_class"] == "monthly" and d.day != 1:
            _flag(flags, "macro_rates", "monthly_date_not_first", "monthly reference date is not the 1st", sid, d.isoformat())
        rel = releases.get(key)
        published = rel["published_at"] if rel else ""
        vintage = rel["vintage_at"] if rel else ""
        m = av.macro_row(d, meta["frequency_class"], meta["revised"], published or None, vintage or None)
        per_series[sid].append(d)
        macro_rows.append([
            d.isoformat(), sid, fmt_number(value), *texts, meta["frequency_class"], fmt_bool(meta["revised"]),
            published, vintage, m.basis, m.current, m.historical,
        ])
    for key in releases:
        if key not in macro_keys:
            problems.append(f"macro_release_dates.csv: no macro_rates observation for {key}")
    for sid in series_meta:
        if sid not in per_series:
            _flag(flags, "macro_rates", "series_without_rows", "listed in macro_series.csv but no rows", sid)
    if problems:
        raise IngestionError("macro_rates validation failed", problems)
    macro_rows.sort(key=lambda r: (r[1], r[0]))
    coverage = {}
    for sid, ds in sorted(per_series.items()):
        ds.sort()
        missing: list[str] = []
        if series_meta[sid]["frequency_class"] == "monthly":
            months = [x.year * 12 + x.month - 1 for x in ds]
            for a, b in zip(months, months[1:]):
                missing.extend(f"{m // 12:04d}-{m % 12 + 1:02d}" for m in range(a + 1, b))
            gaps = len(missing)
            if gaps:
                _flag(flags, "macro_rates", "coverage_gap",
                      "reference months without a value (not filled): " + ", ".join(missing), sid)
        else:
            spans = [(a, b) for a, b in zip(ds, ds[1:]) if (b - a).days > MAX_GAP_DAYS_EXCHANGE]
            gaps = len(spans)
            if gaps:
                _flag(flags, "macro_rates", "coverage_gap",
                      "gaps above 5 days after: " + ", ".join(a.isoformat() for a, _ in spans[:10]), sid)
        coverage[sid] = {"rows": len(ds), "firstDate": ds[0].isoformat(), "lastDate": ds[-1].isoformat(),
                         "frequencyClass": series_meta[sid]["frequency_class"],
                         "revisedLatestVintage": series_meta[sid]["revised"],
                         "releaseDatesLoaded": sum(1 for k in releases if k[0] == sid), "gaps": gaps}
    macro_dates = sorted(r[0] for r in macro_rows)
    n_hist_unknown = sum(1 for r in macro_rows if r[-1] == "")
    datasets["macro_rates"] = _Dataset(
        "macro_rates", macro_rows, macro_dates[0], macro_dates[-1],
        checks=[
            _Check("Header matches organizer schema", True, ", ".join(RAW_HEADERS["macro_rates.csv"])),
            _Check("No duplicate (date, series_id), finite values", True, f"{len(macro_rows)} rows, {len(per_series)} series"),
            _Check("Per-series coverage without gaps", not any(f["code"] == "coverage_gap" and f["datasetId"] == "macro_rates" for f in flags),
                   "; ".join(f"{s} {c['rows']} rows {c['firstDate']}..{c['lastDate']}" for s, c in coverage.items())
                   + "; gaps: " + _flag_summary([f for f in flags if f["datasetId"] == "macro_rates"], "coverage_gap")),
            _Check("Real release dates loaded for monthly series", all(c["releaseDatesLoaded"] >= c["rows"] for c in coverage.values() if c["frequencyClass"] == "monthly"),
                   "none loaded (O-05): monthly values use the A-22 45-day lag in current runs and are withheld in historical runs"
                   if not releases else f"{len(releases)} release records loaded"),
            _Check("Rows readable in historical runs", n_hist_unknown == 0,
                   f"{n_hist_unknown} of {len(macro_rows)} rows withheld in historical runs (unknown release date or revised without vintage)"),
        ],
        source_files=["macro_rates.csv", "macro_series.csv"] + (["macro_release_dates.csv"] if releases else []),
        extra={"series": coverage},
    )
    if releases:
        rel_rows = []
        for (sid, ref), rel in sorted(releases.items()):
            a = av.release_metadata_row(rel["published_at"])
            rel_rows.append([sid, ref, rel["published_at"], rel["vintage_at"], rel["source_url"], a.current, a.historical])
        datasets["macro_release_dates"] = _Dataset(
            "macro_release_dates", rel_rows, min(r[1] for r in rel_rows), max(r[1] for r in rel_rows),
            checks=[_Check("Every release matches a macro observation and is not before its reference date", True, f"{len(rel_rows)} rows")],
            source_files=["macro_release_dates.csv"],
        )

    # Themes -----------------------------------------------------------------------------------
    theme_rows: list[list[str]] = []
    theme_keys: set[tuple[str, str]] = set()
    for i, row in enumerate(tables["asset_themes.csv"], start=2):
        where = f"asset_themes.csv:{i}"
        ticker = _req(row, "ticker", where, problems)
        theme = _req(row, "theme", where, problems)
        justification = _req(row, "justification", where, problems)
        url = row.get("sourceUrl", "").strip()
        d = _date(_req(row, "assignedAt", where, problems), f"{where} assignedAt", problems)
        try:
            is_assumption = parse_bool(row.get("isAssumption", ""), f"{where} isAssumption")
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not ticker or not theme or not justification or d is None:
            continue
        if ticker not in universe:
            problems.append(f"{where}: unknown ticker {ticker}")
            continue
        if theme not in THEME_TAGS:
            problems.append(f"{where}: theme {theme!r} is not in catalog §8")
            continue
        if url and not url.startswith("https://"):
            problems.append(f"{where}: sourceUrl must be https:// or empty")
            continue
        if (ticker, theme) in theme_keys:
            problems.append(f"{where}: duplicate (ticker, theme) {ticker} {theme}")
            continue
        theme_keys.add((ticker, theme))
        a = av.theme_row(d)
        theme_rows.append([ticker, theme, justification, url, d.isoformat(), fmt_bool(is_assumption), a.current, a.historical])
    if problems:
        raise IngestionError("asset_themes validation failed", problems)
    theme_rows.sort(key=lambda r: (r[0], r[1]))
    untagged = sorted(set(universe) - {r[0] for r in theme_rows})
    datasets["asset_themes"] = _Dataset(
        "asset_themes", theme_rows,
        checks=[
            _Check("Tickers known, tags in catalog §8, justification present", True, f"{len(theme_rows)} assignments"),
            _Check("Every asset has at least one theme", not untagged, "all tagged" if not untagged else "untagged: " + ", ".join(untagged)),
            _Check("Assignments backed by a source URL", all(r[3] for r in theme_rows),
                   f"{sum(1 for r in theme_rows if not r[3])} of {len(theme_rows)} rest on the organizer universe file only (team assumptions)"),
        ],
        source_files=["asset_themes.csv"],
        extra={"assignedAt": sorted({r[4] for r in theme_rows})},
    )

    normalized = {ds_id: _encode_rows(ds_id, ds.rows) for ds_id, ds in datasets.items()}
    flags.sort(key=lambda f: (f["datasetId"], f["code"], f["ticker"] or "", f["date"] or ""))
    return BuildOutput(normalized, datasets, flags, all_dates[-1], source_metadata, on_demand)


def _universe_row(row: dict, where: str, tier: str, universe: dict, asset_ids: set, problems: list[str]) -> None:
    fields = {k: _req(row, k, where, problems) for k in RAW_HEADERS["assets_universe.csv"]}
    if not all(fields.values()):
        return
    ticker = fields["ticker"]
    if ticker != ticker.upper() or any(c.isspace() for c in ticker):
        problems.append(f"{where}: ticker {ticker!r} must be upper case without spaces")
        return
    if ticker in CASH_TICKERS:
        problems.append(f"{where}: {ticker} is reserved for the cash pseudo-asset")
        return
    if fields["asset_class"] not in LISTED_ASSET_CLASSES:
        problems.append(f"{where}: asset_class {fields['asset_class']!r} not in {sorted(LISTED_ASSET_CLASSES)}")
        return
    if fields["currency"] not in CURRENCIES:
        problems.append(f"{where}: currency {fields['currency']!r} not CAD or USD")
        return
    if ticker in universe:
        problems.append(f"{where}: duplicate ticker {ticker}")
        return
    if fields["asset_id"] in asset_ids:
        problems.append(f"{where}: duplicate asset_id {fields['asset_id']}")
        return
    asset_ids.add(fields["asset_id"])
    country = "" if fields["asset_class"] == "crypto" else MARKET_COUNTRY.get(fields["market"], "")
    universe[ticker] = {
        **fields,
        "gics_sector": fields["sector"] if fields["sector"] in GICS_SECTORS else "",
        "country": country,
        "tier": tier,
    }


def _sources_metadata(rows: list[dict[str, str]], problems: list[str]) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        out[row["file"]].append(dict(row))
    for name in ("assets_universe.csv", "prices_daily.csv", "corporate_actions.csv", "fx_usdcad_daily.csv", "macro_rates.csv"):
        if name not in out:
            problems.append(f"sources_metadata.csv: no entry for {name}")
    return dict(out)


def _macro_series_meta(rows: list[dict[str, str]], problems: list[str]) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for i, row in enumerate(rows, start=2):
        where = f"macro_series.csv:{i}"
        sid = _req(row, "seriesId", where, problems)
        publisher = _req(row, "publisher", where, problems)
        freq = _req(row, "frequencyClass", where, problems)
        basis = _req(row, "basis", where, problems)
        try:
            revised = parse_bool(row.get("revisedLatestVintage", ""), f"{where} revisedLatestVintage")
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not sid or not publisher or not basis:
            continue
        if freq not in ("daily", "monthly"):
            problems.append(f"{where}: frequencyClass must be daily or monthly")
            continue
        if sid in meta:
            problems.append(f"{where}: duplicate seriesId {sid}")
            continue
        meta[sid] = {"frequency_class": freq, "revised": revised, "publisher": publisher, "basis": basis}
    return meta


def _release_dates(rows: list[dict[str, str]] | None, series_meta: dict, problems: list[str]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for i, row in enumerate(rows or [], start=2):
        where = f"macro_release_dates.csv:{i}"
        sid = _req(row, "seriesId", where, problems)
        ref = _date(_req(row, "referenceDate", where, problems), f"{where} referenceDate", problems)
        pub_text = _req(row, "publishedAt", where, problems)
        url = _req(row, "sourceUrl", where, problems)
        if not sid or ref is None or not pub_text or not url:
            continue
        if sid not in series_meta:
            problems.append(f"{where}: unknown series {sid}")
            continue
        try:
            published = date_or_ts_to_ts(pub_text, f"{where} publishedAt")
            vintage_text = row.get("vintageAt", "").strip()
            vintage = date_or_ts_to_ts(vintage_text, f"{where} vintageAt") if vintage_text else ""
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if published < ts(ref):
            problems.append(f"{where}: publishedAt {published} precedes reference date {ref.isoformat()}")
            continue
        if vintage and vintage < published:
            problems.append(f"{where}: vintageAt {vintage} precedes publishedAt {published}")
            continue
        key = (sid, ref.isoformat())
        if key in out:
            problems.append(f"{where}: duplicate (seriesId, referenceDate) {key}")
            continue
        out[key] = {"published_at": published, "vintage_at": vintage, "source_url": url}
    return out


def _count_by(rows: list[list[str]], idx: int) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r[idx]] += 1
    return dict(sorted(counts.items()))


def _flag_summary(flags: list[dict], *codes: str) -> str:
    hits = [f for f in flags if f["code"] in codes]
    if not hits:
        return "none"
    shown = ", ".join(f"{f['ticker'] or ''} {f['date'] or ''} ({f['detail']})".strip() for f in hits[:10])
    return f"{len(hits)} flagged and retained: {shown}" + (" ..." if len(hits) > 10 else "")


# --- Manifest and publication ------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    data_version: str
    manifest: dict
    created: bool     # False when an identical published version already existed
    activated: bool


def make_manifest(bundle: SourceBundle, build: BuildOutput, data_version: str, created_at: str,
                  parent_version: str | None = None) -> dict:
    sources = []
    for name in sorted(bundle.files):
        data = bundle.files[name]
        sources.append({
            "file": name,
            "path": f"raw/{data_version}/{name}",
            "origin": bundle.origins.get(name, ""),
            "sha256": canonical_sha256(data),
            "sha256Bytes": sha256_hex(data),
            "bytes": len(data),
        })
    datasets = {}
    for ds_id, ds in build.datasets.items():
        schema = NORMALIZED[ds_id]
        payload = build.normalized[ds_id]
        datasets[ds_id] = {
            "schemaVersion": schema.schema_version,
            "path": f"normalized/{data_version}/{ds_id}.csv",
            "sha256": sha256_hex(payload),
            "bytes": len(payload),
            "rowCount": len(ds.rows),
            "firstDate": ds.first_date,
            "lastDate": ds.last_date,
            "sourceFiles": ds.source_files,
            "availabilityPolicy": AVAILABILITY_POLICY_IDS[ds_id],
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail, "checkedAt": created_at} for c in ds.checks],
            **({"details": ds.extra} if ds.extra else {}),
        }
    return {
        "manifestSchemaVersion": MANIFEST_SCHEMA_VERSION,
        "contractVersion": CONTRACT_VERSION,
        "dataVersion": data_version,
        "parentVersion": parent_version,
        "createdAt": created_at,
        "dataAsOf": build.data_as_of,
        "sources": sources,
        "sourceMetadata": build.source_metadata,
        "onDemand": build.on_demand,
        "datasets": datasets,
        "qualityFlags": build.flags,
    }


AVAILABILITY_POLICY_IDS = {
    "assets_universe": "first_visible_price_row",
    "prices_daily": "daily_close_21:00Z_crypto_eod_23:59:59.999Z",
    "corporate_actions": "ex_date_00:00Z_reference_only",
    "fx_usdcad_daily": "boc_same_day_21:30Z",
    "macro_rates": "release_date_else_A22_lag_historical_requires_release_and_vintage",
    "asset_themes": "current_ungated_historical_from_assigned_at",
    "macro_release_dates": "published_at",
}


def validate_version_label(data_version: str) -> None:
    m = VERSION_RE.match(data_version or "")
    if not m:
        raise IngestionError(f"data version {data_version!r} must look like snap-YYYYMMDD-label (schemas.md §1)")
    try:
        datetime.strptime(m.group(1), "%Y%m%d")
    except ValueError as exc:
        raise IngestionError(f"data version {data_version!r} has an invalid date") from exc


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8")


def _write_manifest(data_root: Path, data_version: str, manifest: dict) -> None:
    _atomic_write(data_root / "manifests" / f"{data_version}.json", _manifest_bytes(manifest))


def set_active_version(data_root: Path, data_version: str) -> None:
    """Point ``manifests/active.json`` at a published version (atomic replace)."""
    if not (data_root / "manifests" / f"{data_version}.json").is_file():
        raise SnapshotIntegrityError(f"cannot activate unpublished version {data_version}")
    _atomic_write(data_root / "manifests" / "active.json",
                  (json.dumps({"dataVersion": data_version}, indent=2) + "\n").encode("utf-8"))


def _staging_dir(data_root: Path, data_version: str) -> Path:
    return data_root / ".staging" / f"{data_version}.{secrets.token_hex(6)}"


def _stage(staging: Path, bundle: SourceBundle, build: BuildOutput, manifest: dict) -> None:
    (staging / "raw").mkdir(parents=True)
    (staging / "normalized").mkdir(parents=True)
    for name, data in bundle.files.items():
        (staging / "raw" / name).write_bytes(data)
    for ds_id, payload in build.normalized.items():
        (staging / "normalized" / f"{ds_id}.csv").write_bytes(payload)
    # Re-read what was written and check it against the manifest before publishing.
    for src in manifest["sources"]:
        if canonical_sha256((staging / "raw" / src["file"]).read_bytes()) != src["sha256"]:
            raise SnapshotIntegrityError(f"staged raw file {src['file']} does not match its hash")
    for ds_id, meta in manifest["datasets"].items():
        if sha256_hex((staging / "normalized" / f"{ds_id}.csv").read_bytes()) != meta["sha256"]:
            raise SnapshotIntegrityError(f"staged dataset {ds_id} does not match its hash")


def ingest_bundle(bundle: SourceBundle, data_root: Path, data_version: str, *, clock: Clock = system_clock,
                  activate: bool = True, parent_version: str | None = None) -> IngestResult:
    """Validate, normalize and publish ``bundle`` as ``data_version`` (idempotent, atomic)."""
    validate_version_label(data_version)
    data_root = Path(data_root)
    manifest_path = data_root / "manifests" / f"{data_version}.json"
    raw_dir = data_root / "raw" / data_version
    norm_dir = data_root / "normalized" / data_version

    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        want = {s["file"]: s["sha256"] for s in existing.get("sources", [])}
        have = {name: canonical_sha256(data) for name, data in bundle.files.items()}
        if want != have:
            changed = sorted(set(want) ^ set(have) | {k for k in want if k in have and want[k] != have[k]})
            raise IngestionError(
                f"{data_version} is already published with different sources; versions are immutable, "
                f"publish a new version label", [f"differs: {c}" for c in changed])
        _materialize(data_root, data_version, bundle, existing)
        activated = False
        if activate:
            set_active_version(data_root, data_version)
            activated = True
        return IngestResult(data_version, existing, created=False, activated=activated)

    for path in (raw_dir, norm_dir):
        if path.exists():
            raise IngestionError(
                f"{path} exists without a manifest (left by an interrupted publish); remove it and retry")

    build = build_snapshot(bundle)  # raises IngestionError before anything is written
    manifest = make_manifest(bundle, build, data_version, utc_now_iso(clock()), parent_version)
    staging = _staging_dir(data_root, data_version)
    moved: list[Path] = []
    try:
        _stage(staging, bundle, build, manifest)
        raw_dir.parent.mkdir(parents=True, exist_ok=True)
        norm_dir.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging / "raw", raw_dir)
        moved.append(raw_dir)
        os.rename(staging / "normalized", norm_dir)
        moved.append(norm_dir)
        _write_manifest(data_root, data_version, manifest)  # commit point
    except BaseException:
        for path in moved:
            shutil.rmtree(path, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        _remove_if_empty(data_root / ".staging")
    activated = False
    if activate:
        set_active_version(data_root, data_version)
        activated = True
    return IngestResult(data_version, manifest, created=True, activated=activated)


def _materialize(data_root: Path, data_version: str, bundle: SourceBundle, manifest: dict) -> None:
    """Recreate gitignored raw/normalized files of a committed manifest, verifying every hash."""
    raw_dir = data_root / "raw" / data_version
    norm_dir = data_root / "normalized" / data_version
    if raw_dir.exists() and norm_dir.exists():
        _verify_published(data_root, manifest)
        return
    if raw_dir.exists() or norm_dir.exists():
        raise SnapshotIntegrityError(f"{data_version}: raw and normalized directories must both exist or both be absent")
    build = build_snapshot(bundle)
    for ds_id, meta in manifest["datasets"].items():
        payload = build.normalized.get(ds_id)
        if payload is None or sha256_hex(payload) != meta["sha256"]:
            raise SnapshotIntegrityError(
                f"{data_version}/{ds_id}: rebuilt dataset does not reproduce the committed hash; not published")
    staging = _staging_dir(data_root, data_version)
    try:
        _stage(staging, bundle, build, manifest)
        raw_dir.parent.mkdir(parents=True, exist_ok=True)
        norm_dir.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staging / "raw", raw_dir)
        try:
            os.rename(staging / "normalized", norm_dir)
        except BaseException:
            shutil.rmtree(raw_dir, ignore_errors=True)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        _remove_if_empty(data_root / ".staging")


def _verify_published(data_root: Path, manifest: dict) -> None:
    for src in manifest["sources"]:
        path = data_root / src["path"]
        if not path.is_file() or canonical_sha256(path.read_bytes()) != src["sha256"]:
            raise SnapshotIntegrityError(f"{src['path']} is missing or does not match the manifest")
    for ds_id, meta in manifest["datasets"].items():
        path = data_root / meta["path"]
        if not path.is_file() or sha256_hex(path.read_bytes()) != meta["sha256"]:
            raise SnapshotIntegrityError(f"{meta['path']} is missing or does not match the manifest")


def _remove_if_empty(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


def ingest_starter(source_dir: Path, data_root: Path, data_version: str, *, metadata_dir: Path | None = None,
                   clock: Clock = system_clock, activate: bool = True) -> IngestResult:
    data_root = Path(data_root)
    bundle = read_starter_bundle(Path(source_dir), Path(metadata_dir) if metadata_dir else data_root / "metadata")
    return ingest_bundle(bundle, data_root, data_version, clock=clock, activate=activate)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest the organizer starter CSVs into a versioned snapshot.")
    parser.add_argument("--source", required=True, type=Path, help="directory holding the organizer CSVs")
    parser.add_argument("--data-root", required=True, type=Path, help="repository data/ directory")
    parser.add_argument("--version", required=True, help="snapshot label, e.g. snap-20261113-starter")
    parser.add_argument("--metadata-dir", type=Path, default=None, help="defaults to <data-root>/metadata")
    parser.add_argument("--no-activate", action="store_true", help="publish without changing manifests/active.json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = ingest_starter(args.source, args.data_root, args.version, metadata_dir=args.metadata_dir,
                                activate=not args.no_activate)
    except (IngestionError, SnapshotIntegrityError) as exc:
        print(f"ingestion failed, nothing published: {exc}", file=sys.stderr)
        return 1
    m = result.manifest
    state = "published" if result.created else "already published (verified, unchanged)"
    print(f"{result.data_version}: {state}; active={'yes' if result.activated else 'unchanged'}")
    for ds_id, meta in m["datasets"].items():
        print(f"  {ds_id:20s} rows={meta['rowCount']:>6}  {meta['firstDate'] or '-'} .. {meta['lastDate'] or '-'}  sha256={meta['sha256'][:12]}")
    print(f"  quality flags: {len(m['qualityFlags'])}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
