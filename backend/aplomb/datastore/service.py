"""``DataService`` for the HTTP API (api.md §2 and §8): universe, assets and dataset passports.

Reads the pinned snapshot through a current-mode gate at the snapshot's data date. On-demand
fetching and attention need live providers that are not wired (unverified Yahoo terms, T09
page views), so those endpoints report ``upstream_unavailable`` instead of inventing data.
"""

from __future__ import annotations

from typing import Callable

from aplomb.api.errors import NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.contracts import models as m

from .constants import LISTED_ASSET_CLASSES, TIERS
from .errors import DatasetNotFound, UnknownTicker
from .snapshot import Snapshot


class DatastoreService:
    def __init__(self, snapshot: Callable[[], Snapshot]) -> None:
        self.snapshot = snapshot

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

    def fetch(self, session_id: str, ticker: str) -> a.FetchAssetResponse:
        raise unavailable("On-demand price provider")

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
