"""Deterministic portfolio mathematics (track T05; see SPEC.md in this folder).

    engine = QuantEngine(gate, ledger, currency="CAD", subject_id="robert", created_at=now)
    before = engine.view(weights, "before", 600_000)
    after = engine.view(apply_move(weights, "TSLA", 25, "pro_rata").weights, "after", 600_000)
    after.measure("vol.annualized")   # Measurement(value, fact_id, ...)
    after.snapshot()                  # contracts PortfolioSnapshot
"""

from .engine import Measurement, PortfolioMetrics, PortfolioView, QuantEngine, WindowRange, slug
from .facts import FactContext, FactSink, LedgerError, LocalLedger, display, fact_key, make_fact
from .funding import FundingError, MoveResult, apply_move
from .market import MarketData, Unavailable

__all__ = [
    "FactContext", "FactSink", "FundingError", "LedgerError", "LocalLedger", "MarketData", "Measurement",
    "MoveResult", "PortfolioMetrics", "PortfolioView", "QuantEngine", "Unavailable", "WindowRange",
    "apply_move", "display", "fact_key", "make_fact", "slug",
]
