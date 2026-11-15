"""Time Machine backend (track T12; see SPEC.md in this folder)."""

from .service import (
    EligibleRange,
    HistoricalContext,
    ReplayServiceImpl,
    build_presets,
    eligible_range,
    gate_report,
    replay_result,
    reveal,
    validate_asof,
)

__all__ = ["EligibleRange", "HistoricalContext", "ReplayServiceImpl", "build_presets", "eligible_range",
           "gate_report", "replay_result", "reveal", "validate_asof"]
