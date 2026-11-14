"""Typed datastore errors. The API maps them to ``ApiError`` codes (catalog §7)."""

from __future__ import annotations


class DatastoreError(Exception):
    """Base class for every datastore failure."""


class IngestionError(DatastoreError):
    """Raw input failed validation; nothing was published."""

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        self.problems = list(problems or [])
        detail = message
        if self.problems:
            shown = "; ".join(self.problems[:20])
            more = f" (+{len(self.problems) - 20} more)" if len(self.problems) > 20 else ""
            detail = f"{message}: {shown}{more}"
        super().__init__(detail)


class SnapshotIntegrityError(DatastoreError):
    """A published snapshot is missing, partial, tampered with or uses an unknown schema."""


class DatasetNotFound(DatastoreError):
    """Dataset ID is not in the catalog (maps to ``not_found``)."""


class DatasetMissing(DatastoreError):
    """Dataset ID is in the catalog but not loaded in this snapshot (maps to nee ``dataset_missing``)."""


class UnknownTicker(DatastoreError):
    """Ticker is not in this snapshot (maps to ``not_found`` / nee ``asset_unknown``)."""


class UnknownSeries(DatastoreError):
    """Macro series ID is not in this snapshot (maps to ``not_found``)."""


class InvalidGateRequest(DatastoreError, ValueError):
    """Malformed read request (bad date, bad mode, start after end...). Maps to ``validation_error``."""
