"""Captured CFTC Legacy futures-only positioning; no options chain or trade signal."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date

SOURCE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"


@dataclass(frozen=True)
class LegacyPosition:
    contract_code: str
    market: str
    observation_date: str
    open_interest: int
    noncommercial_long: int
    noncommercial_short: int

    @property
    def net_noncommercial_contracts(self) -> int:
        return self.noncommercial_long - self.noncommercial_short


@dataclass(frozen=True)
class CotCapture:
    source_url: str
    retrieved_at: str
    sha256: str
    positions: tuple[LegacyPosition, ...]

    def latest(self, contract_code: str, known_at: str, on_or_before: str) -> LegacyPosition | None:
        """Exact CFTC contract code only; capture time is the availability boundary."""
        known_at = normalize_ts(known_at, "known_at")
        cutoff = parse_date(on_or_before, "on_or_before")
        if known_at < self.retrieved_at:
            return None
        candidates = (p for p in self.positions if p.contract_code == contract_code
                      and parse_date(p.observation_date) <= cutoff)
        return max(candidates, key=lambda p: p.observation_date, default=None)


def read_capture(payload: bytes, metadata: dict) -> CotCapture:
    try:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != metadata["rawSha256"] or metadata["report"] != "legacy-futures-only":
            raise ValueError("capture hash or report mismatch")
        retrieved = normalize_ts(metadata["retrievedAt"], "retrievedAt")
        url = metadata["sourceUrl"]
        parts = urlsplit(url)
        if (f"{parts.scheme}://{parts.netloc}{parts.path}" != SOURCE
                or parts.fragment or parts.username or parts.password):
            raise ValueError("unexpected CFTC source URL")
        items = json.loads(payload)
        if not isinstance(items, list) or not items:
            raise ValueError("no positions")
        result, seen = [], set()
        for row in items:
            code = row["cftc_contract_market_code"]
            stamp = row["report_date_as_yyyy_mm_dd"]
            if (not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.000)?", stamp)
                    or not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9]{6}", code)):
                raise ValueError("invalid report date or contract code")
            day = parse_date(stamp[:10], "report date")
            key = (code, day)
            market = row["market_and_exchange_names"]
            raw = [row[x] for x in ("open_interest_all", "noncomm_positions_long_all",
                                    "noncomm_positions_short_all")]
            if (key in seen or day.isoformat() > retrieved[:10] or not isinstance(market, str)
                    or not market.strip() or any(not isinstance(n, str) or not n.isascii()
                                                 or not n.isdigit() for n in raw)):
                raise ValueError("invalid or duplicate position")
            oi, long, short = map(int, raw)
            if long > oi or short > oi:
                raise ValueError("position exceeds open interest")
            seen.add(key)
            result.append(LegacyPosition(code, market, day.isoformat(), oi, long, short))
        return CotCapture(url, retrieved, digest, tuple(result))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IngestionError(f"invalid CFTC COT capture: {exc}") from exc
