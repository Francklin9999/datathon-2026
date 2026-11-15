"""On-demand tickers (D-24, api.md §2.3, datastore SPEC §3).

A fetched asset is validated, then published as a **new** immutable snapshot whose raw inputs
are the parent's raw files plus the addition. The parent snapshot is never modified; a run that
needs the new asset must pin the new version before it starts. A rejected or failed fetch
publishes nothing and leaves ``manifests/active.json`` unchanged.

No live price provider is wired here: the Yahoo terms for live fetching are unverified
(data/SOURCES.md). A provider adapter implements ``PriceProvider`` and returns a
``FetchedAsset`` with its own retrieval timestamp; tests use synthetic providers.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .constants import CASH_TICKERS, CURRENCIES, LISTED_ASSET_CLASSES, MIN_ROWS_ON_DEMAND
from .errors import IngestionError, SnapshotIntegrityError, UnknownTicker
from .ingest import Clock, SourceBundle, ingest_bundle, system_clock
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
    def fetch(self, ticker: str) -> FetchedAsset: ...


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


def _parent_bundle(data_root: Path, base_version: str) -> SourceBundle:
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
    return SourceBundle(files, origins)


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

    parent = _parent_bundle(data_root, base_version)
    files = dict(parent.files)
    origins = dict(parent.origins)
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
        ingest_bundle(SourceBundle(files, origins), data_root, new_version, clock=clock, activate=activate,
                      parent_version=base_version)
    except IngestionError as exc:
        return OnDemandResult(fetched.ticker, False,
                              _reason(f"Validation failed: {exc}", f"Échec de la validation : {exc}"),
                              base_version, None, base_passport)
    snap = store.open(new_version)
    asset = snap.gate(snap.data_as_of, "current").universe().get(fetched.ticker)
    return OnDemandResult(fetched.ticker, True, None, new_version, asset.to_wire(), snap.passport("prices_daily"))
