"""On-demand tickers (D-24, api.md §2.3, datastore SPEC §3).

A fetched asset is validated, then published as a **new** immutable snapshot whose raw inputs
are the parent's raw files plus the addition. The parent snapshot is never modified; a run that
needs the new asset must pin the new version before it starts. A rejected or failed fetch
publishes nothing and leaves ``manifests/active.json`` unchanged.

A parent published by ``global_fx.publish_global_fx`` (the Bank of Canada multi-currency
capture, dataset ``fx_boc_global``) carries a raw file and a dataset that ``ingest`` can neither
accept nor rebuild. Such a child is composed in two steps: the organizer and on-demand files are
ingested, then the parent's exact capture is re-applied by ``publish_global_fx`` (which validates
it again). Both steps run in a private staging root, so only the final version is published and
its ``parentVersion`` names the real parent.

A provider adapter implements ``PriceProvider`` and returns a ``FetchedAsset`` with its own
retrieval timestamp. The live adapter is ``providers.TiingoProvider``, built in
``api/domain.py`` when ``APLOMB_TIINGO_TOKEN`` is set and the data directory is local; Yahoo is
not used for live fetching (data/SOURCES.md). Tests inject synthetic providers.
"""

from __future__ import annotations

import csv
import io
import json
import os
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .constants import CASH_TICKERS, CURRENCIES, LISTED_ASSET_CLASSES, MIN_ROWS_ON_DEMAND
from .errors import IngestionError, SnapshotIntegrityError, UnknownTicker
from .global_fx import publish_global_fx
from .ingest import (
    Clock,
    SourceBundle,
    _remove_if_empty,
    _write_manifest,
    ingest_bundle,
    set_active_version,
    system_clock,
    validate_version_label,
)
from .integrity import canonical_sha256
from .quality import fmt_number, fmt_volume, parse_finite
from .schemas import RAW_HEADERS
from .snapshot import LocalDataStore
from .timeutil import normalize_ts, parse_date


@dataclass(frozen=True)
class FetchedAsset:
    ticker: str
    name: str
    asset_class: str
    market: str
    currency: str
    sector: str | None                # None -> "unknown" + flag sector_label_unsourced
    rows: tuple[dict, ...]            # date, open, high, low, close, adj_close, volume
    provider: str
    retrieved_at: str                 # ISO-8601 UTC, when the provider was actually called
    source_url: str | None = None
    terms: str | None = None


class PriceProvider(Protocol):
    def fetch(self, ticker: str, start: str, end: str) -> FetchedAsset: ...


@dataclass(frozen=True)
class OnDemandResult:
    ticker: str
    accepted: bool
    rejected_reason: dict | None      # I18nText
    data_version: str                 # new version when accepted, else the unchanged base version
    asset: dict | None                # wire Asset; None when the input cannot form a valid Asset
    passport: dict                    # prices_daily passport of `data_version`

    def to_wire(self) -> dict:
        return {"asset": self.asset, "accepted": self.accepted, "rejectedReason": self.rejected_reason,
                "passport": self.passport}


def _reason(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


def validate_fetched(fetched: FetchedAsset) -> dict | None:
    """Return an I18n rejection reason, or None when the fetched asset is acceptable."""
    t = fetched.ticker
    if not t or t != t.upper() or any(c.isspace() for c in t) or t in CASH_TICKERS:
        return _reason(f"Ticker {t!r} is not a valid listed ticker.", f"Le ticker {t!r} n'est pas un ticker coté valide.")
    if fetched.currency not in CURRENCIES:
        return _reason(f"Listing currency {fetched.currency!r} is not supported by the configured currency catalog.",
                       f"La devise de cotation {fetched.currency!r} n'est pas prise en charge par le catalogue de devises.")
    if fetched.asset_class not in LISTED_ASSET_CLASSES:
        return _reason(f"Asset class {fetched.asset_class!r} is not supported.",
                       f"La classe d'actifs {fetched.asset_class!r} n'est pas prise en charge.")
    if not fetched.name.strip() or not fetched.market.strip() or not fetched.provider.strip():
        return _reason("Name, market or provider is missing.", "Le nom, le marché ou le fournisseur est manquant.")
    try:
        normalize_ts(fetched.retrieved_at, "retrieved_at")
    except ValueError:
        return _reason("Retrieval timestamp is missing or invalid.", "L'horodatage de récupération est absent ou invalide.")
    if len(fetched.rows) < MIN_ROWS_ON_DEMAND:
        return _reason(f"Only {len(fetched.rows)} price rows; at least {MIN_ROWS_ON_DEMAND} are required.",
                       f"Seulement {len(fetched.rows)} lignes de prix; il en faut au moins {MIN_ROWS_ON_DEMAND}.")
    seen = set()
    for row in fetched.rows:
        try:
            d = parse_date(row.get("date"), "date").isoformat()
            values = [parse_finite(str(row.get(k)), k) for k in ("open", "high", "low", "close", "adj_close", "volume")]
        except ValueError as exc:
            return _reason(f"Malformed price row: {exc}.", f"Ligne de prix invalide : {exc}.")
        if d in seen:
            return _reason(f"Duplicate date {d}.", f"Date en double {d}.")
        seen.add(d)
        if min(values[:5]) <= 0:
            return _reason(f"Non-positive price on {d}.", f"Prix non positif le {d}.")
        if values[5] < 0:
            return _reason(f"Negative volume on {d}.", f"Volume négatif le {d}.")
    return None


def _encode(name: str, rows: list[list[str]]) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(RAW_HEADERS[name])
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _existing_rows(data: bytes | None) -> list[list[str]]:
    if not data:
        return []
    reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""))
    next(reader, None)
    return [r for r in reader if r]


#: Written by ``global_fx.publish_global_fx``; never an ``ingest`` input.
GLOBAL_FX_DATASET = "fx_boc_global"
GLOBAL_FX_RAW = "boc_global_fx.json"


def _parent_bundle(data_root: Path, base_version: str) -> tuple[SourceBundle, dict]:
    """The parent's raw files (hash-checked against its manifest) and the manifest itself."""
    manifest = json.loads((data_root / "manifests" / f"{base_version}.json").read_text(encoding="utf-8"))
    files, origins = {}, {}
    for src in manifest["sources"]:
        path = data_root / src["path"]
        if not path.is_file():
            raise SnapshotIntegrityError(f"{path} missing; re-run ingestion of {base_version} to materialize it")
        data = path.read_bytes()
        if canonical_sha256(data) != src["sha256"]:
            raise SnapshotIntegrityError(f"{src['path']} does not match the {base_version} manifest")
        files[src["file"]] = data
        origins[src["file"]] = src.get("origin", "")
    return SourceBundle(files, origins), manifest


def _global_fx_capture(manifest: dict, files: dict[str, bytes]) -> tuple[bytes, dict] | None:
    """The parent's Bank of Canada capture and the metadata ``publish_global_fx`` re-validates it
    with (rebuilt from the parent manifest), or None when the parent has no global FX dataset."""
    fx = manifest.get("datasets", {}).get(GLOBAL_FX_DATASET)
    if fx is None:
        return None
    source = next((s for s in manifest["sources"] if s["file"] == GLOBAL_FX_RAW), None)
    if source is None or GLOBAL_FX_RAW not in files:
        raise SnapshotIntegrityError(f"{manifest['dataVersion']}: {GLOBAL_FX_DATASET} has no {GLOBAL_FX_RAW} source")
    details = fx["details"]
    metadata = {"sourceUrl": details["sourceUrl"], "retrievedAt": details["retrievedAt"],
                "series": list(details["currencies"]), "rawSha256": source["sha256Bytes"]}
    for key in ("captureDirectory", "captureStem"):
        if key in details:
            metadata[key] = details[key]
    return files[GLOBAL_FX_RAW], metadata


def _publish_with_global_fx(data_root: Path, bundle: SourceBundle, base_version: str, new_version: str,
                            capture: tuple[bytes, dict], *, clock: Clock, activate: bool) -> None:
    """Publish ``new_version`` = ingest(``bundle``) + the parent's global FX capture.

    Both steps run in a private root under ``.staging``; only the final raw and normalized
    directories move into ``data_root``, and its manifest is written last (the commit point), as
    ``ingest_bundle`` does. Raises ``IngestionError`` when either step rejects its input.
    """
    validate_version_label(new_version)
    targets = [data_root / "raw" / new_version, data_root / "normalized" / new_version]
    if (data_root / "manifests" / f"{new_version}.json").exists() or any(path.exists() for path in targets):
        raise IngestionError(f"snapshot {new_version} already exists; publish a new version label")
    # Only ever published inside the private root, so any valid label distinct from the target works.
    intermediate = f"snap-{new_version[5:13]}-on-demand-base"
    if intermediate == new_version:
        intermediate += "-2"
    work = data_root / ".staging" / f"{new_version}.compose-{secrets.token_hex(6)}"
    moved: list[Path] = []
    try:
        built = ingest_bundle(bundle, work, intermediate, clock=clock, activate=False, parent_version=base_version)
        payload, metadata = capture
        manifest = publish_global_fx(work, intermediate, new_version, payload, metadata)
        # The intermediate is not published: the child descends from the real parent and keeps the
        # on-demand publication time (publish_global_fx stamps the capture's retrieval time).
        manifest["parentVersion"] = base_version
        manifest["createdAt"] = built.manifest["createdAt"]
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(work / target.parent.name / new_version, target)
            moved.append(target)
        _write_manifest(data_root, new_version, manifest)  # commit point
    except BaseException:
        for path in moved:
            shutil.rmtree(path, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
        _remove_if_empty(data_root / ".staging")
    if activate:
        set_active_version(data_root, new_version)


def publish_on_demand(data_root: Path | str, base_version: str, new_version: str, fetched: FetchedAsset, *,
                      clock: Clock = system_clock, activate: bool = False) -> OnDemandResult:
    """Validate ``fetched`` and publish ``new_version`` = ``base_version`` + the asset."""
    data_root = Path(data_root)
    store = LocalDataStore(data_root)
    base = store.open(base_version)
    base_passport = base.passport("prices_daily")
    gate = base.gate(base.data_as_of, "current")
    try:
        gate.universe().get(fetched.ticker)
        return OnDemandResult(fetched.ticker, False,
                              _reason(f"{fetched.ticker} is already in snapshot {base_version}.",
                                      f"{fetched.ticker} est déjà dans l'instantané {base_version}."),
                              base_version, gate.universe().get(fetched.ticker).to_wire(), base_passport)
    except UnknownTicker:
        pass
    reason = validate_fetched(fetched)
    if reason is not None:
        return OnDemandResult(fetched.ticker, False, reason, base_version, None, base_passport)

    parent, parent_manifest = _parent_bundle(data_root, base_version)
    capture = _global_fx_capture(parent_manifest, parent.files)
    files = dict(parent.files)
    origins = dict(parent.origins)
    if capture is not None:
        # Re-applied after ingest (_publish_with_global_fx); ingest rejects it as an input.
        del files[GLOBAL_FX_RAW]
        origins.pop(GLOBAL_FX_RAW, None)
    asset_rows = _existing_rows(files.get("ondemand_assets.csv"))
    asset_rows.append([fetched.ticker, fetched.name, fetched.asset_class, fetched.market, fetched.currency,
                       fetched.sector or "", fetched.provider, fetched.source_url or "",
                       normalize_ts(fetched.retrieved_at, "retrieved_at"), fetched.terms or ""])
    price_rows = _existing_rows(files.get("ondemand_prices.csv"))
    for row in sorted(fetched.rows, key=lambda r: parse_date(r["date"]).isoformat()):
        price_rows.append([
            parse_date(row["date"]).isoformat(), fetched.ticker,
            *(fmt_number(parse_finite(str(row[k]), k)) for k in ("open", "high", "low", "close", "adj_close")),
            fmt_volume(parse_finite(str(row["volume"]), "volume")), fetched.currency,
        ])
    files["ondemand_assets.csv"] = _encode("ondemand_assets.csv", asset_rows)
    files["ondemand_prices.csv"] = _encode("ondemand_prices.csv", price_rows)
    origins["ondemand_assets.csv"] = origins["ondemand_prices.csv"] = f"on-demand fetch ({fetched.provider})"
    try:
        if capture is None:
            ingest_bundle(SourceBundle(files, origins), data_root, new_version, clock=clock, activate=activate,
                          parent_version=base_version)
        else:
            _publish_with_global_fx(data_root, SourceBundle(files, origins), base_version, new_version, capture,
                                    clock=clock, activate=activate)
    except IngestionError as exc:
        return OnDemandResult(fetched.ticker, False,
                              _reason(f"Validation failed: {exc}", f"Échec de la validation : {exc}"),
                              base_version, None, base_passport)
    snap = store.open(new_version)
    asset = snap.gate(snap.data_as_of, "current").universe().get(fetched.ticker)
    return OnDemandResult(fetched.ticker, True, None, new_version, asset.to_wire(), snap.passport("prices_daily"))
