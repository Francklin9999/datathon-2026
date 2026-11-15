"""Portfolio look-through using explicit identity and dated, source-verified weights."""
from __future__ import annotations

import math
import re
from datetime import date

from pydantic import Field, field_validator, model_validator

from .entities import Evidence, Model, valid_isin


def security_id(value: str) -> str:
    if re.fullmatch(r"listing_[0-9a-f]{24}", value) or (value.startswith("isin:") and valid_isin(value[5:])):
        return value
    raise ValueError("security ID must be an exact listing lifecycle ID or a valid ISIN")


class Holding(Model):
    security_id: str = Field(min_length=1, max_length=200)
    weight_pct: float = Field(ge=0, le=100, strict=True)

    @field_validator("security_id")
    @classmethod
    def validate_security_id(cls, value):
        return security_id(value)


class HoldingsSnapshot(Model):
    fund_id: str = Field(min_length=1, max_length=200)
    effective_date: date
    holdings: tuple[Holding, ...]
    evidence: Evidence
    # A source may be a top subset even when it represents most of the value.
    complete: bool = Field(default=False, strict=True)

    @field_validator("fund_id")
    @classmethod
    def validate_fund_id(cls, value):
        return security_id(value)

    @model_validator(mode='after')
    def validate_holdings(self):
        if len({h.security_id for h in self.holdings}) != len(self.holdings):
            raise ValueError('duplicate constituent identifier')
        total = math.fsum(h.weight_pct for h in self.holdings)
        if total > 100.01:
            raise ValueError('constituent weights exceed 100 percent')
        if self.complete and abs(total - 100) > 0.01:
            raise ValueError('complete holdings must sum to 100 percent')
        return self


def portfolio_lookthrough(positions: list[Holding], snapshots: list[HoldingsSnapshot],
                          as_of: date, *, fund_ids: set[str], historical: bool = False) -> dict:
    """Direct + fund-derived weights, conservatively quantified from valid disclosures.

    ``security_id`` must be the same authoritative ISIN or listing lifecycle ID across all
    records; a symbol or fuzzy name match is never performed. A missing snapshot leaves an
    explicit unresolved fund weight rather than turning unknown exposure into zero.
    """
    if len({p.security_id for p in positions}) != len(positions):
        raise ValueError('duplicate portfolio security ID')
    if abs(math.fsum(p.weight_pct for p in positions) - 100) > .01:
        raise ValueError('portfolio weights must sum to 100 percent')
    seen = set()
    by_fund = {}
    for snap in snapshots:
        key = (snap.fund_id, snap.effective_date, snap.evidence.content_sha256)
        if key in seen:
            raise ValueError('duplicate snapshot')
        seen.add(key)
        if snap.effective_date <= as_of and snap.evidence.visible(as_of, historical=historical):
            old = by_fund.get(snap.fund_id)
            if old is None or (snap.effective_date, snap.evidence.available_at, snap.evidence.retrieved_at) > (old.effective_date, old.evidence.available_at, old.evidence.retrieved_at):
                by_fund[snap.fund_id] = snap
    exposures, source_funds, disclosures, unavailable = {}, {}, [], []
    for position in positions:
        snap = by_fund.get(position.security_id)
        if not snap and position.security_id in fund_ids:
            unavailable.append({'fund_id': position.security_id, 'unresolved_portfolio_weight_pct': position.weight_pct,
                                'reason': 'no_visible_dated_holdings'})
            continue
        if not snap:
            # This is a directly held security; no claim about issuer or geography is inferred.
            exposures[position.security_id] = exposures.get(position.security_id, 0) + position.weight_pct
            continue
        coverage = math.fsum(h.weight_pct for h in snap.holdings)
        unresolved = position.weight_pct * max(0.0, 100 - coverage) / 100
        disclosures.append({'fund_id': snap.fund_id, 'effective_date': str(snap.effective_date),
                            'reported_constituents_pct': coverage, 'portfolio_weight_pct': position.weight_pct,
                            'unresolved_portfolio_weight_pct': unresolved, 'complete': snap.complete,
                            'source': snap.evidence.model_dump(mode='json')})
        for holding in snap.holdings:
            value = position.weight_pct * holding.weight_pct / 100
            exposures[holding.security_id] = exposures.get(holding.security_id, 0) + value
            source_funds.setdefault(holding.security_id, []).append(snap.fund_id)
    return {'as_of': str(as_of), 'exposures': [{'security_id': k, 'weight_pct': v,
             'contributing_funds': sorted(source_funds.get(k, []))} for k, v in sorted(exposures.items(), key=lambda x: (-x[1], x[0]))],
            'fund_disclosures': disclosures, 'unavailable_funds': unavailable,
            'unresolved_portfolio_weight_pct': math.fsum(x['unresolved_portfolio_weight_pct'] for x in disclosures + unavailable),
            'overlap': [k for k, funds in sorted(source_funds.items()) if len(funds) >= 2],
            'limitations': ['Direct IDs require reviewed mapping; no fuzzy or ticker-only matching.',
                            'Missing/unreported constituents are unknown, not zero.',
                            'Weights use dated fund disclosures, which are not live positions.']}
