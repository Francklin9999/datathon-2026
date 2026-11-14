"""Universe under a gate: assets known at ``as_of`` with history computed from visible rows only
(datastore SPEC §5, schemas.md §3 ``Asset``)."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    CALENDAR_REF_CAD,
    CALENDAR_REF_USD,
    CASH_TICKERS,
    MIN_MASTER_OBS_FOR_RISK,
    TIERS,
)
from .errors import InvalidGateRequest, UnknownTicker
from .types import DatasetRead


@dataclass(frozen=True)
class AssetHistory:
    first_date: str
    last_date: str
    n_obs: int
    n_obs_master: int


@dataclass(frozen=True)
class AssetRecord:
    ticker: str
    name: str
    asset_class: str
    asset_group: str
    market: str
    currency: str
    sector: str
    gics_sector: str | None
    is_single_name: bool
    country: str | None
    themes: tuple[str, ...]
    tier: str
    history: AssetHistory
    flags: tuple[str, ...]
    data_version: str
    dataset_id: str
    asset_id: str

    def to_wire(self) -> dict:
        """``Asset`` as in schemas.md §3 (camelCase)."""
        return {
            "ticker": self.ticker,
            "name": self.name,
            "assetClass": self.asset_class,
            "assetGroup": self.asset_group,
            "market": self.market,
            "currency": self.currency,
            "sector": self.sector,
            "gicsSector": self.gics_sector,
            "isSingleName": self.is_single_name,
            "country": self.country,
            "themes": list(self.themes),
            "tier": self.tier,
            "history": {
                "firstDate": self.history.first_date,
                "lastDate": self.history.last_date,
                "nObs": self.history.n_obs,
                "nObsMaster": self.history.n_obs_master,
            },
            "flags": list(self.flags),
            "dataVersion": self.data_version,
            "datasetId": self.dataset_id,
        }


class Universe:
    """Assets known under one gate. Cash pseudo-assets are reachable with ``get``/``cash`` but are
    not listed, searched or counted (``Meta.universe.total`` counts listed assets only)."""

    def __init__(self, gate) -> None:
        self._gate = gate
        snap = gate._snap
        as_of = gate.as_of.isoformat()
        u_rows = snap._table("assets_universe").rows
        known = [r for r in u_rows if gate._visible(r)]
        u_withheld = len(u_rows) - len(known)

        cad, _ = gate._price_rows(CALENDAR_REF_CAD, None, as_of)
        usd, _ = gate._price_rows(CALENDAR_REF_USD, None, as_of)
        master = sorted({r["date"] for r in cad} & {r["date"] for r in usd})
        master_set = set(master)

        themes: dict[str, list[str]] = {}
        theme_rows = theme_withheld = 0
        if "asset_themes" in snap.loaded_datasets:
            for r in snap._table("asset_themes").rows:
                if gate._visible(r):
                    themes.setdefault(r["ticker"], []).append(r["theme"])
                    theme_rows += 1
                else:
                    theme_withheld += 1

        anomalies = {t for t, rows in gate._anomalies.items() if any(gate._visible(a) for a in rows)}
        price_rows = price_withheld = 0
        assets: dict[str, AssetRecord] = {}
        for r in known:
            t = r["ticker"]
            rows, withheld = gate._price_rows(t, None, as_of)
            price_rows += len(rows)
            price_withheld += withheld
            n_master = sum(1 for x in rows if x["date"] in master_set)
            flags = set()
            if n_master < MIN_MASTER_OBS_FOR_RISK:
                flags.add("short_history")
            if any(x["volume"] == 0 for x in rows):
                flags.add("zero_volume_rows")
            if t in anomalies:
                flags.add("split_anomaly")
            if r["tier"] == "on_demand":
                flags.add("on_demand")
            if r["asset_class"] == "crypto":
                flags.add("seven_day_calendar")
            if r["sector"] == "unknown":
                flags.add("sector_label_unsourced")
            assets[t] = AssetRecord(
                ticker=t, name=r["name"], asset_class=r["asset_class"], asset_group=r["asset_group"],
                market=r["market"], currency=r["currency"], sector=r["sector"], gics_sector=r["gics_sector"],
                is_single_name=r["is_single_name"], country=r["country"], themes=tuple(sorted(themes.get(t, ()))),
                tier=r["tier"],
                history=AssetHistory(rows[0]["date"], rows[-1]["date"], len(rows), n_master),
                flags=tuple(sorted(flags)), data_version=gate.data_version, dataset_id="prices_daily",
                asset_id=r["asset_id"],
            )
        self._assets = assets
        self._order = tuple(sorted(assets, key=lambda t: (assets[t].asset_id, t)))
        self._master = tuple(master)
        reads = [DatasetRead("assets_universe", gate.data_version, len(known), u_withheld),
                 DatasetRead("prices_daily", gate.data_version, price_rows + len(cad) + len(usd), price_withheld)]
        if "asset_themes" in snap.loaded_datasets:
            reads.append(DatasetRead("asset_themes", gate.data_version, theme_rows, theme_withheld))
        self.reads: tuple[DatasetRead, ...] = tuple(reads)

    # Lookups ----------------------------------------------------------------------------------

    def __contains__(self, ticker: str) -> bool:
        return ticker in self._assets or (ticker in CASH_TICKERS and bool(self._master))

    def __len__(self) -> int:
        return len(self._assets)

    def get(self, ticker: str) -> AssetRecord:
        if ticker in CASH_TICKERS:
            return self.cash(CASH_TICKERS[ticker])
        asset = self._assets.get(ticker)
        if asset is None:
            where = (f"at as_of {self._gate.as_of.isoformat()}" if self._gate.mode == "historical"
                     else f"in snapshot {self._gate.data_version}")
            raise UnknownTicker(f"{ticker} is not known {where}")
        return asset

    def all(self) -> tuple[AssetRecord, ...]:
        return tuple(self._assets[t] for t in self._order)

    def search(self, q: str | None = None, asset_class: str | None = None, theme: str | None = None,
               tier: str | None = None, limit: int = 10) -> tuple[AssetRecord, ...]:
        """Case-insensitive match on ticker or name; exact ticker matches first."""
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise InvalidGateRequest("limit must be an integer between 1 and 500")
        needle = (q or "").strip().lower()
        hits = []
        for t in self._order:
            a = self._assets[t]
            if asset_class and a.asset_class != asset_class:
                continue
            if theme and theme not in a.themes:
                continue
            if tier and a.tier != tier:
                continue
            if needle and needle not in a.ticker.lower() and needle not in a.name.lower():
                continue
            hits.append(a)
        if needle:
            hits.sort(key=lambda a: 0 if a.ticker.lower() == needle else 1)  # stable: keeps asset order
        return tuple(hits[:limit])

    def counts(self) -> dict:
        """``Meta.universe``: listed assets known under this gate, by tier."""
        by_tier = {tier: 0 for tier in TIERS}
        for a in self._assets.values():
            by_tier[a.tier] += 1
        return {"total": len(self._assets), "byTier": by_tier}

    def cash(self, currency: str) -> AssetRecord:
        """Cash pseudo-asset: zero return in its own currency (``LIM_CASH_NO_INTEREST``)."""
        ticker = {v: k for k, v in CASH_TICKERS.items()}.get(currency)
        if ticker is None:
            raise UnknownTicker(f"no cash pseudo-asset for currency {currency!r}")
        if not self._master:
            raise UnknownTicker(f"{ticker} has no master-calendar dates at as_of {self._gate.as_of.isoformat()}")
        n = len(self._master)
        return AssetRecord(
            ticker=ticker, name=f"Cash ({currency})", asset_class="cash", asset_group="cash",
            market="n/a (pseudo-asset)", currency=currency, sector="Cash", gics_sector=None,
            is_single_name=False, country=None, themes=(), tier="starter",
            history=AssetHistory(self._master[0], self._master[-1], n, n), flags=(),
            data_version=self._gate.data_version, dataset_id="assets_universe", asset_id=ticker,
        )
