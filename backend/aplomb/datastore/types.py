"""Read-side result types handed to tools and to quant (T05).

Rows are fresh ``dict`` copies per read, so a consumer mutating a row cannot affect another
read context (DS-08). Dates are ISO strings ``YYYY-MM-DD``; timestamps are UTC strings.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Literal, Mapping

GateMode = Literal["current", "historical"]
GATE_MODES: tuple[str, ...] = ("current", "historical")


@dataclass(frozen=True)
class DatasetRead:
    """One entry of ``ToolCall.datasetsRead`` (schemas.md §9)."""

    dataset_id: str
    data_version: str
    rows: int
    rows_withheld: int

    def to_wire(self) -> dict:
        return {"datasetId": self.dataset_id, "dataVersion": self.data_version, "rows": self.rows,
                "rowsWithheld": self.rows_withheld}


@dataclass(frozen=True)
class DataSlice:
    """Gated rows of one dataset.

    ``rows_read`` = rows returned. ``rows_withheld`` = candidate rows (matching the request's
    keys and date interval) rejected by availability before any other transformation.
    ``last_visible_date`` = latest observation date among returned rows (None if none or the
    dataset has no date column).
    """

    rows: tuple[dict, ...]
    dataset_id: str
    data_version: str
    rows_read: int
    rows_withheld: int
    limitations: tuple[str, ...]
    last_visible_date: str | None = None

    def dataset_read(self) -> DatasetRead:
        return DatasetRead(self.dataset_id, self.data_version, self.rows_read, self.rows_withheld)


@dataclass(frozen=True)
class MasterCalendar:
    """Master calendar (A-15, ``M_CAL_INTERSECTION``): visible XIU.TO dates ∩ visible SPY dates."""

    dates: tuple[str, ...]
    data_version: str
    reads: tuple[DatasetRead, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class PriceFrame:
    """Aligned adjusted closes in listing currency.

    ``adj_close[t][i]`` is the adjusted close of ``t`` on ``dates[i]`` or ``None`` when that
    asset has no visible observation that day. Nothing is filled. ``synthetic`` holds cash
    pseudo-assets (constant 1.0 in their own currency, zero return, ``LIM_CASH_NO_INTEREST``).
    """

    dates: tuple[str, ...]
    tickers: tuple[str, ...]
    adj_close: Mapping[str, tuple[float | None, ...]]
    currencies: Mapping[str, str]
    synthetic: frozenset[str]
    calendar: str
    data_version: str
    reads: tuple[DatasetRead, ...]
    limitations: tuple[str, ...]

    def column(self, ticker: str) -> tuple[float | None, ...]:
        return self.adj_close[ticker]

    def missing_dates(self, ticker: str) -> tuple[str, ...]:
        return tuple(d for d, v in zip(self.dates, self.adj_close[ticker]) if v is None)

    def complete(self, ticker: str) -> bool:
        return all(v is not None for v in self.adj_close[ticker])


@dataclass(frozen=True)
class FxSeries:
    """Visible USD/CAD rows (CAD per USD), including the last row before the window start."""

    dates: tuple[str, ...]
    usdcad: tuple[float, ...]
    data_version: str
    reads: tuple[DatasetRead, ...]
    limitations: tuple[str, ...]

    def rate_on(self, day: str) -> float | None:
        """Rate published that same day, if any."""
        i = bisect.bisect_left(self.dates, day)
        return self.usdcad[i] if i < len(self.dates) and self.dates[i] == day else None

    def rate_on_or_before(self, day: str) -> tuple[float, str] | None:
        """``(rate, publication_date)`` of the last visible rate on or before ``day``.

        Never a later rate: ``None`` when no earlier rate is visible (``M_FX_BOC_FFILL``)."""
        i = bisect.bisect_right(self.dates, day) - 1
        if i < 0:
            return None
        return self.usdcad[i], self.dates[i]
