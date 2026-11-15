"""Reader for the French library's US daily three-factor ZIP capture.

Values in the source are percentages, returned as fractional daily returns.
Factor returns describe portfolios, not exposures of a user's portfolio. A
freshly downloaded revision is available no earlier than its capture timestamp.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import zipfile
from dataclasses import dataclass

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date

SOURCE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"


@dataclass(frozen=True)
class DailyFactors:
    date: str
    market_excess: float
    size: float
    value: float
    risk_free: float


@dataclass(frozen=True)
class FactorCapture:
    source_url: str
    retrieved_at: str
    sha256: str
    observations: tuple[DailyFactors, ...]

    def through(self, known_at: str, through_date: str) -> tuple[DailyFactors, ...]:
        known_at = normalize_ts(known_at, "known_at")
        cutoff = parse_date(through_date, "through_date")
        if known_at < self.retrieved_at:
            return ()
        return tuple(row for row in self.observations if parse_date(row.date) <= cutoff)


def read_capture(payload: bytes, metadata: dict) -> FactorCapture:
    try:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != metadata["rawSha256"] or metadata["sourceUrl"] != SOURCE:
            raise ValueError("capture hash or source mismatch")
        retrieved = normalize_ts(metadata["retrievedAt"], "retrievedAt")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if (len(entries) != 1 or entries[0].filename.lower() != "f-f_research_data_factors_daily.csv"
                    or entries[0].file_size > 10_000_000 or entries[0].is_dir()):
                raise ValueError("unexpected ZIP content")
            content = archive.read(entries[0]).decode("utf-8-sig")
        data, in_table, seen = [], False, set()
        for row in csv.reader(io.StringIO(content)):
            values = [x.strip() for x in row]
            if values == ["", "Mkt-RF", "SMB", "HML", "RF"]:
                if in_table:
                    raise ValueError("duplicate header")
                in_table = True
                continue
            if not in_table or not values or not re.fullmatch(r"\d{8}", values[0]):
                continue
            if len(values) != 5:
                raise ValueError("unexpected factor columns")
            raw_date = values[0]
            day = parse_date(f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}")
            numbers = tuple(float(v) for v in values[1:])
            if (day in seen or day.isoformat() > retrieved[:10]
                    or any(not math.isfinite(v) or abs(v) >= 99.99 for v in numbers)):
                raise ValueError("invalid, missing or duplicate factor value")
            seen.add(day)
            data.append(DailyFactors(day.isoformat(), *(v / 100 for v in numbers)))
        if not in_table or not data:
            raise ValueError("factor table missing")
        data.sort(key=lambda row: row.date)
        return FactorCapture(SOURCE, retrieved, digest, tuple(data))
    except (KeyError, TypeError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        raise IngestionError(f"invalid Fama-French capture: {exc}") from exc
