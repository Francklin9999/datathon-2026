"""Database-backed fictional map examples and attributed 13F comparison captures.

The manager snapshots are third-party transcriptions, not verified SEC originals.
Comparisons reconstruct the covered long positions retrospectively; they never
claim to reproduce a manager's returns, private wealth, options or trading.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, ValidationError

from aplomb.api.errors import NotFound, ServiceError, unavailable
from aplomb.contracts import api as a
from aplomb.contracts.base import ISODate, ISODateTime, Number, ProfileId, String, WireModel
from aplomb.quant import LocalLedger, Unavailable
from aplomb.strategies.service import with_defaults
from aplomb.strategies.simulate import simulate

MAP_PARTITION = "SHARED#INVESTOR_MAP"
FILINGS_PARTITION = "SHARED#13F"
FILING_ID = re.compile(r"[a-z0-9][a-z0-9_-]{2,79}")


class MapLocation(WireModel):
    label: Annotated[String, Field(min_length=1, max_length=100)]
    country: Annotated[String, Field(pattern=r"^[A-Z]{2}$")]
    lat: Annotated[Number, Field(ge=-90, le=90)]
    lon: Annotated[Number, Field(ge=-180, le=180)]


class WalletLocation(MapLocation):
    account_id: Annotated[String, Field(pattern=r"^acct_[0-9a-f]{12}$")]


class InvestorLocation(WireModel):
    profile_id: ProfileId
    name: Annotated[String, Field(min_length=1, max_length=100)]
    investor_type: Annotated[String, Field(min_length=1, max_length=80)]
    home: MapLocation
    wallets: list[WalletLocation] = Field(min_length=1, max_length=20)
    is_fictional: Literal[True] = True


class DisclosedHolding(WireModel):
    ticker: String | None
    issuer: String
    share_class: String
    cusip: Annotated[String, Field(max_length=9)]
    value_usd: Annotated[Number, Field(ge=0)]
    shares: Annotated[Number, Field(ge=0)] | None
    principal: Annotated[Number, Field(ge=0)] | None
    option_type: Literal["put", "call"] | None
    source_weight_pct: Number | None


class FilingCapture(WireModel):
    filing_id: Annotated[String, Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,79}$")]
    manager: Annotated[String, Field(min_length=1, max_length=150)]
    associated_person: Annotated[String, Field(max_length=150)]
    cik: Annotated[String, Field(pattern=r"^\d{10}$")]
    accession: Annotated[String, Field(pattern=r"^\d{10}-\d{2}-\d{6}$")]
    report_date: ISODate
    filing_date: ISODate
    retrieved_at: ISODateTime
    source_url: String
    sec_url: String
    source_data_url: String
    source_sha256: Annotated[String, Field(pattern=r"^[0-9a-f]{64}$")]
    reported_value_usd: Annotated[Number, Field(gt=0)]
    indexed_long_value_usd: Annotated[Number, Field(ge=0)]
    indexed_all_value_usd: Annotated[Number, Field(ge=0)]
    holdings: list[DisclosedHolding] = Field(min_length=1, max_length=20000)
    modeled_holdings: list[DisclosedHolding] = Field(max_length=40)
    limitations: list[String]
    source_kind: Literal["third_party_indexed_transcription"]
    point_in_time_verified: Literal[False] = False


class FilingComparisonRequest(a.StrategySimulateRequest):
    filing_id: Annotated[String, Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,79}$")]


def filing_summary(capture: FilingCapture) -> dict:
    covered = math.fsum(h.value_usd for h in capture.modeled_holdings)
    return {
        "filingId": capture.filing_id,
        "manager": capture.manager,
        "associatedPerson": capture.associated_person,
        "cik": capture.cik,
        "accession": capture.accession,
        "reportDate": capture.report_date,
        "filingDate": capture.filing_date,
        "retrievedAt": capture.retrieved_at,
        "sourceUrl": capture.source_url,
        "secUrl": capture.sec_url,
        "sourceKind": capture.source_kind,
        "holdingCount": len(capture.holdings),
        "optionCount": sum(h.option_type is not None for h in capture.holdings),
        "modeledHoldingCount": len(capture.modeled_holdings),
        "reportedValueUsd": capture.reported_value_usd,
        "coverageValueUsd": capture.indexed_all_value_usd,
        "coverageBasis": "Sum of all captured indexed rows, including options.",
        "modeledValueUsd": covered,
        "modeledCoveragePct": (
            covered / capture.indexed_all_value_usd * 100 if capture.indexed_all_value_usd else 0
        ),
        "comparisonEligible": bool(covered),
        "pointInTimeVerified": False,
        "limitations": [
            *capture.limitations,
            "Coverage uses all captured indexed rows, including options, and may differ from "
            "the source-reported total.",
        ],
    }


def _read_capture(value: dict) -> FilingCapture:
    capture = FilingCapture.model_validate(value)
    if capture.filing_date < capture.report_date:
        raise ValueError("filing precedes report date")
    disclosed = {(h.ticker, h.cusip, h.value_usd, h.option_type) for h in capture.holdings}
    tickers = []
    for holding in capture.modeled_holdings:
        if not holding.ticker or holding.option_type or holding.value_usd <= 0:
            raise ValueError("modeled positions must be positive long holdings")
        if (holding.ticker, holding.cusip, holding.value_usd, holding.option_type) not in disclosed:
            raise ValueError("modeled holding not in source")
        tickers.append(holding.ticker)
    if len(set(tickers)) != len(tickers):
        raise ValueError("modeled positions must have unique symbols")
    if math.fsum(h.value_usd for h in capture.modeled_holdings) > capture.indexed_all_value_usd:
        raise ValueError("covered value exceeds captured indexed rows")
    return capture


class InvestorExamples:
    def __init__(self, store, profiles):
        self.store, self.profiles = store, profiles

    def investors(self, session_id: str) -> dict:
        investors = []
        for row in self.store.query("profiles", MAP_PARTITION):
            try:
                investor = InvestorLocation.model_validate(row["value"])
                # The public map describes the shared example. A private account
                # overlay must not change or invalidate it for that session.
                profile = self.profiles._default(investor.profile_id)
                # Only explicitly fictional shared examples are public map records.
                if profile is None or not profile.is_default or not profile.portfolio.is_fictional:
                    continue
                account_ids = {account.account_id for account in profile.accounts}
                if any(w.account_id not in account_ids for w in investor.wallets):
                    raise ValueError("unknown wallet in investor map")
                investors.append(investor.model_dump(mode="json", by_alias=True))
            except NotFound:
                continue
            except (KeyError, ValueError, ValidationError) as exc:
                raise unavailable("Fictional investor map data") from exc
        return {"investors": sorted(investors, key=lambda row: row["profileId"])}

    def captures(self) -> list[FilingCapture]:
        try:
            return [_read_capture(row["value"])
                    for row in self.store.query("cache", FILINGS_PARTITION)]
        except (KeyError, ValueError, ValidationError) as exc:
            raise unavailable("Attributed 13F captures") from exc

    def capture(self, filing_id: str) -> FilingCapture:
        if not FILING_ID.fullmatch(filing_id):
            raise NotFound("Unknown 13F capture")
        row = self.store.get("cache", FILINGS_PARTITION, f"FILING#{filing_id}")
        if row is None:
            raise NotFound("Unknown 13F capture")
        try:
            return _read_capture(row["value"])
        except (KeyError, ValueError, ValidationError) as exc:
            raise unavailable("Attributed 13F capture") from exc

    def compare(self, session_id: str, profile_id: str, body: FilingComparisonRequest) -> dict:
        capture = self.capture(body.filing_id)
        covered = math.fsum(h.value_usd for h in capture.modeled_holdings)
        if not covered:
            raise ServiceError("insufficient_data", "No covered long holdings in this filing")
        profile = self.profiles.get(session_id, profile_id)
        requested_window = body.window.to_wire() if body.window else {"code": "full"}
        engine, window = self.profiles._engine(
            profile, {"window": requested_window}, LocalLedger())
        try:
            wr = engine.window(window)
            # Never simulate a disclosed portfolio before its indexed filing date.
            i0 = next((i for i in range(wr.i0, wr.i1 + 1)
                       if engine.market.dates[i] >= capture.filing_date), wr.i1 + 1)
            i1 = wr.i1
            if i1 - i0 < 1:
                raise ServiceError(
                    "insufficient_data", "The selected window ends before usable post-filing history")
            target = self.profiles._weights(profile)
            benchmark_target = {h.ticker: h.value_usd / covered for h in capture.modeled_holdings}
            strategy = with_defaults(body.strategy.to_wire(), profile, target, engine)
            tickers = set(target) | set(benchmark_target)
            if strategy["kind"] == "risk_guard":
                tickers.add(strategy["safeTicker"])
            returns = {ticker: engine.asset_returns(ticker, i0, i1) for ticker in sorted(tickers)}
            groups = {ticker: engine.universe.get(ticker).asset_group for ticker in tickers}
            dates = engine.market.dates[i0:i1 + 1]
            run = simulate(
                dates=dates, returns=returns, target=target,
                start_value=profile.portfolio.total_value, config=strategy, groups=groups,
                safe_ticker=strategy.get("safeTicker"), currency=profile.reporting_currency)
            # Holdings drift without rebalancing. Values are indexed to 100;
            # the strategy index excludes external deposits but includes its costs.
            holdings = dict(benchmark_target)
            benchmark_index = [1.0]
            for k in range(len(dates) - 1):
                holdings = {t: value * (1 + returns[t][k]) for t, value in holdings.items()}
                benchmark_index.append(math.fsum(holdings.values()))
        except Unavailable as exc:
            raise ServiceError("insufficient_data", exc.detail) from exc
        points = lambda values: [  # noqa: E731
            {"date": day, "value": value * 100}
            for day, value in zip(dates, values, strict=True)]
        return {
            "filing": filing_summary(capture),
            "currency": profile.reporting_currency,
            "requestedWindow": requested_window,
            "sample": {"start": dates[0], "end": dates[-1], "observations": len(dates)},
            "strategy": {"series": points(run.strategy.index),
                         "returnPct": (run.strategy.index[-1] - 1) * 100},
            "benchmark": {"series": points(benchmark_index),
                          "returnPct": (benchmark_index[-1] - 1) * 100,
                          "holdings": [h.to_wire() for h in capture.modeled_holdings]},
            "limitations": [
                "Retrospective scenario, not actual fund or personal investment performance.",
                "Only price-covered disclosed long positions are modeled, normalized to 100%; "
                "omitted holdings, cash, shorts, options, leverage and later trades are excluded.",
                "Third-party indexed transcription; the original SEC table was not verified. "
                "Retrieval followed this price sample, so point-in-time availability is not verified.",
                "The common window starts on or after the indexed filing date. "
                "Both sides use the selected investor's reporting currency.",
                "The strategy index excludes contributions and includes configured trading costs; "
                "the disclosed-holdings benchmark is held without trades, fees or taxes.",
            ],
        }


def investor_examples_router(store, profiles, session_dependency):
    router = APIRouter()
    service = InvestorExamples(store, profiles)

    @router.get("/v1/world/investors")
    def investor_map(sid: str = Depends(session_dependency)):
        if profiles is None:
            raise unavailable("Profiles")
        return service.investors(sid)

    @router.get("/v1/research/13f")
    def filings(sid: str = Depends(session_dependency)):
        return {"items": [filing_summary(c) for c in sorted(
            service.captures(), key=lambda c: (c.manager, c.report_date))]}

    @router.get("/v1/research/13f/{filing_id}")
    def filing(filing_id: str, sid: str = Depends(session_dependency)):
        capture = service.capture(filing_id)
        return {**filing_summary(capture), "holdings": [h.to_wire() for h in capture.holdings]}

    @router.post("/v1/profiles/{profile_id}/strategies/compare-13f")
    def compare_filing(profile_id: ProfileId, body: FilingComparisonRequest,
                       sid: str = Depends(session_dependency)):
        if profiles is None:
            raise unavailable("Profiles")
        return service.compare(sid, profile_id, body)

    return router
