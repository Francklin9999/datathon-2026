"""``DataService`` for the HTTP API (api.md §2 and §8): universe, assets and dataset passports.

Reads the pinned snapshot through a current-mode gate at the snapshot's data date. On-demand
fetching uses a configured live provider (Tiingo) and publishes a new local snapshot; without one
it reports ``upstream_unavailable``. Attention belongs to the research track (T09).
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from aplomb.api.errors import NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.contracts import models as m

from .constants import LISTED_ASSET_CLASSES, TIERS
from .errors import DatasetNotFound, UnknownTicker
from .ondemand import publish_on_demand
from .providers import ProviderError
from .snapshot import Snapshot


class OnDemandPublisher:
    """Fetch a missing ticker from a live provider and publish it as a new local snapshot.

    Only for a writable local data root; the base snapshot is never modified and the served
    version switches to the new one only when the asset is accepted.
    """

    def __init__(self, provider, data_root: Path, snapshot, *, clock: Callable[[], datetime] | None = None) -> None:
        self.provider = provider
        self.data_root = Path(data_root)
        self.snapshot = snapshot  # SnapshotProvider-like: callable + switch(version)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def _new_version(self, ticker: str) -> str:
        day = self.clock().astimezone(timezone.utc).strftime("%Y%m%d")
        label = re.sub(r"[^a-z0-9]+", "-", ticker.lower()).strip("-")[:20]
        base = f"snap-{day}-od-{label}"
        n = 1
        while (self.data_root / "manifests" / f"{base}-{n}.json").exists():
            n += 1
        return f"{base}-{n}"

    def fetch(self, ticker: str) -> a.FetchAssetResponse:
        with self._lock:
            snap = self.snapshot()
            gate = snap.gate(snap.data_as_of, "current")
            universe = gate.universe()
            if ticker in universe:
                return a.FetchAssetResponse.model_validate({"asset": universe.get(ticker).to_wire(), "accepted": True,
                                                            "rejectedReason": None, "passport": snap.passport("prices_daily")})
            start = gate.master_calendar().dates[0]
            try:
                fetched = self.provider.fetch(ticker, start, snap.data_as_of)
            except ProviderError as exc:
                if exc.code == "unavailable":
                    raise ServiceError("upstream_unavailable", exc.reason["en"], {"reason": exc.reason}) from exc
                if exc.code == "not_found":
                    raise NotFound(exc.reason["en"]) from exc
                raise ServiceError("insufficient_data", exc.reason["en"], {"reason": exc.reason}) from exc
            result = publish_on_demand(self.data_root, snap.data_version, self._new_version(ticker), fetched,
                                       clock=self.clock, activate=True)
            if result.accepted:
                self.snapshot.switch(result.data_version)
            asset = result.asset or self._provisional_asset(snap, fetched)
            return a.FetchAssetResponse.model_validate({"asset": asset, "accepted": result.accepted,
                                                        "rejectedReason": result.rejected_reason, "passport": result.passport})

    @staticmethod
    def _provisional_asset(snap: Snapshot, fetched) -> dict:
        """Asset shape of a rejected fetch, built from the provider rows (nothing was published)."""
        dates = sorted({str(r.get("date"))[:10] for r in fetched.rows if r.get("date")})
        master = set(snap.gate(snap.data_as_of, "current").master_calendar().dates)
        n_master = sum(1 for d in dates if d in master)
        flags = {"on_demand", "sector_label_unsourced"} | ({"short_history"} if n_master < 252 else set())
        return {"ticker": fetched.ticker, "name": fetched.name, "assetClass": fetched.asset_class, "assetGroup": "equity",
                "market": fetched.market, "currency": fetched.currency, "sector": "unknown", "gicsSector": None,
                "isSingleName": True, "country": "USA", "themes": [], "tier": "on_demand",
                "history": {"firstDate": dates[0] if dates else snap.data_as_of, "lastDate": dates[-1] if dates else snap.data_as_of,
                            "nObs": len(dates), "nObsMaster": n_master},
                "flags": sorted(flags), "dataVersion": snap.data_version, "datasetId": "prices_daily"}


class DatastoreService:
    def __init__(self, snapshot: Callable[[], Snapshot], on_demand: OnDemandPublisher | None = None) -> None:
        self.snapshot = snapshot
        self.on_demand = on_demand

    def current_version(self) -> tuple[str, str]:
        snap = self.snapshot()
        return snap.data_version, snap.data_as_of

    def _universe(self):
        snap = self.snapshot()
        return snap.gate(snap.data_as_of, "current").universe()

    def assets(self, session_id: str, query: dict) -> a.AssetsResponse:
        asset_class = query.get("assetClass")
        tier = query.get("tier")
        if asset_class is not None and asset_class not in LISTED_ASSET_CLASSES:
            raise ServiceError("validation_error", f"assetClass must be one of {', '.join(sorted(LISTED_ASSET_CLASSES))}",
                               {"fields": ["assetClass"]})
        if tier is not None and tier not in TIERS:
            raise ServiceError("validation_error", f"tier must be one of {', '.join(TIERS)}", {"fields": ["tier"]})
        limit = int(query.get("limit", 50))
        cursor = query.get("cursor")
        try:
            offset = int(cursor) if cursor is not None else 0
            if offset < 0:
                raise ValueError
        except ValueError as exc:
            raise ServiceError("validation_error", "cursor is invalid", {"fields": ["cursor"]}) from exc
        matches = self._universe().search(q=query.get("q"), asset_class=asset_class, theme=query.get("theme"), tier=tier, limit=500)
        page = matches[offset:offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(matches) else None
        return a.AssetsResponse.model_validate({"items": [x.to_wire() for x in page], "nextCursor": next_cursor,
                                                "total": len(matches)})

    def asset(self, session_id: str, ticker: str) -> m.Asset:
        try:
            return m.Asset.model_validate(self._universe().get(ticker).to_wire())
        except UnknownTicker as exc:
            raise NotFound(str(exc)) from exc

    def analytics(self, session_id: str, ticker: str, query: dict) -> a.AssetAnalyticsResponse:
        from aplomb.profiles.service import _window_spec
        from aplomb.quant import LocalLedger, QuantEngine

        snap = self.snapshot()
        gate = snap.gate(snap.data_as_of, "current")
        try:
            asset = m.Asset.model_validate(gate.universe().get(ticker).to_wire())
        except UnknownTicker as exc:
            raise NotFound(str(exc)) from exc
        window = _window_spec(query)
        currency = query.get("currency", "CAD")
        ledger = LocalLedger()
        engine = QuantEngine(gate, ledger, currency=currency, subject_id=ticker,
                             created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        metrics = engine.asset_metrics(ticker, window)
        return a.AssetAnalyticsResponse.model_validate({
            "asset": asset, "currency": currency, "dataVersion": snap.data_version,
            "asOf": snap.data_as_of, "window": window,
            "metrics": {key: {"value": x.value, "factId": x.fact_id, "unavailableReason": x.nee_reason}
                        for key, x in metrics.items()},
            "facts": {key: fact.to_wire() for key, fact in ledger.facts().items()},
        })

    def fetch(self, session_id: str, ticker: str) -> a.FetchAssetResponse:
        if self.on_demand is None:
            raise unavailable("On-demand price provider (configure APLOMB_TIINGO_TOKEN with a writable local data directory)")
        return self.on_demand.fetch(ticker.upper())

    def attention(self, session_id: str, ticker: str) -> a.AttentionResponse:
        raise unavailable("Attention research")

    def datasets(self, session_id: str) -> a.DatasetsResponse:
        return a.DatasetsResponse.model_validate(self.snapshot().datasets_response())

    def dataset(self, session_id: str, dataset_id: str) -> m.DatasetPassport:
        try:
            return m.DatasetPassport.model_validate(self.snapshot().passport(dataset_id))
        except DatasetNotFound as exc:
            raise NotFound(f"Unknown dataset {dataset_id}") from exc

    def universe_summary(self) -> m.UniverseSummary:
        counts = self._universe().counts()
        return m.UniverseSummary(total=counts["total"], by_tier=counts["byTier"])
