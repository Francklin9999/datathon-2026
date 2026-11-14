"""Explicit role allowlists, argument schemas and temporal execution boundary."""

from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel

from aplomb.contracts import models as m

LOOKUP = {"universe.search", "universe.get", "profile.get", "data.describe", "macro.series"}
RESEARCH = {
    "edgar.find_company",
    "edgar.list_filings",
    "edgar.filing_text",
    "edgar.company_facts",
    "gdelt.search",
    "web.fetch",
    "web.browse",
    "attention.pageviews",
    "emissions.facilities",
    "etf.holdings",
    "world.search_events",
    "research.save_evidence",
}
QUANT = {
    "quant.asset_metrics",
    "quant.calendar_year_return",
    "quant.portfolio_snapshot",
    "quant.portfolio_metrics",
    "quant.apply_move",
    "quant.compare_funding",
    "quant.stress_replay",
    "quant.correlation",
    "quant.exposure",
    "quant.price_move_after",
}
RISK = {
    "rules.check",
    "optimizer.max_compatible_size",
    "optimizer.goal_candidates",
    "optimizer.alternatives",
    "optimizer.rebalance",
    "optimizer.derive_thresholds",
}


@dataclass
class ToolResult:
    ok: bool
    summary: str
    fact_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    datasets_read: list[m.DatasetRead] = field(default_factory=list)
    error: str | None = None


@dataclass
class ToolContext:
    run_id: str
    profile: m.Profile | None
    lang: str
    as_of: str
    gate: object
    ledger: object
    store: object
    limits: object
    logger: object
    historical: bool = False
    research_context: object = None


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[type[BaseModel], Callable]] = {}

    def register(self, name: str, args: type[BaseModel], function: Callable):
        if name not in LOOKUP | RESEARCH | QUANT | RISK:
            raise ValueError("Tool is absent from the shared catalog")
        if name in self._tools:
            raise ValueError("Duplicate tool")
        self._tools[name] = (args, function)

    def schemas(self, names):
        return [
            {"name": name, "schema": schema.model_json_schema()}
            for name, (schema, _) in self._tools.items()
            if name in names
        ]

    def validate(self, role: str, name: str, args: dict, ctx: ToolContext):
        allowed = {
            "planner": LOOKUP,
            "researcher": LOOKUP | RESEARCH,
            "quant": QUANT,
            "risk_officer": RISK,
        }.get(role, set())
        if name not in allowed or name not in self._tools:
            raise ValueError("Tool is unavailable for this role")
        if ctx.historical and name in RESEARCH:
            raise ValueError("Research is disabled in historical runs")
        if ctx.gate is None and name != "profile.get":
            raise ValueError("A pinned temporal context is required")
        schema, function = self._tools[name]
        accepted = set(schema.model_fields) | {
            f.alias for f in schema.model_fields.values() if f.alias
        }
        if set(args) - accepted:
            raise ValueError("Unknown tool argument")
        gate_date = getattr(ctx.gate, "as_of", None)
        if gate_date is not None and str(gate_date) != str(ctx.as_of):
            raise ValueError("Tool cutoff differs from pinned temporal gate")
        return schema.model_validate(args), function

    def execute(self, role, name, args, ctx):
        try:
            parsed, function = self.validate(role, name, args, ctx)
            if name in RESEARCH:
                ctx.limits.take("research_calls")
            return function(ctx, **parsed.model_dump())
        except Exception as exc:
            return ToolResult(False, "Tool did not complete", error=str(exc)[:300])
