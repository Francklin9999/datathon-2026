"""Shared helpers for datastore tests: repo paths, a fixed clock, the starter snapshot built once
per process, and a small synthetic bundle for edge cases. No network access."""

from __future__ import annotations

import atexit
import csv
import io
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from aplomb.datastore.ingest import SourceBundle, ingest_bundle, ingest_starter
from aplomb.datastore.schemas import RAW_HEADERS

REPO = Path(__file__).resolve().parents[4]
STARTER_DIR = REPO / "Datathon2026" / "alphaforge_starter"
METADATA_DIR = REPO / "data" / "metadata"
STARTER_VERSION = "snap-20261113-starter"
FIXED_NOW = datetime(2026, 11, 14, 22, 0, 0, tzinfo=timezone.utc)


def fixed_clock() -> datetime:
    return FIXED_NOW


def temp_root() -> Path:
    path = Path(tempfile.mkdtemp(prefix="aplomb-ds-"))
    atexit.register(shutil.rmtree, path, True)
    return path


_STARTER_ROOT: Path | None = None


def starter_root() -> Path:
    """Data root with the starter snapshot ingested once per test process."""
    global _STARTER_ROOT
    if _STARTER_ROOT is None:
        root = temp_root()
        ingest_starter(STARTER_DIR, root, STARTER_VERSION, metadata_dir=METADATA_DIR, clock=fixed_clock)
        _STARTER_ROOT = root
    return _STARTER_ROOT


_STARTER_SNAPSHOT = None


def starter_snapshot():
    """The starter snapshot opened once per test process (opening parses ~50k rows)."""
    global _STARTER_SNAPSHOT
    if _STARTER_SNAPSHOT is None:
        from aplomb.datastore import LocalDataStore

        _STARTER_SNAPSHOT = LocalDataStore(starter_root()).open(STARTER_VERSION)
    return _STARTER_SNAPSHOT


def read_starter_csv(name: str) -> list[dict[str, str]]:
    with open(STARTER_DIR / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- Synthetic bundle ----------------------------------------------------------------------------

SYN_START = date(2024, 1, 2)          # a Tuesday
SYN_DAYS = 400                        # calendar days covered by crypto
TSX_HOLIDAY_INDEX = 5                 # weekday index missing for TSX listings
US_HOLIDAY_INDEX = 9                  # weekday index missing for US listings
AAA_MISSING_INDEX = 20                # a master day where AAA.TO has no observation


def weekdays(n_calendar_days: int = SYN_DAYS) -> list[date]:
    out = []
    d = SYN_START
    for _ in range(n_calendar_days):
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def synthetic_tables(with_releases: bool = False) -> dict[str, list[list[str]]]:
    """Raw tables (header excluded) of a tiny but complete bundle."""
    wd = weekdays()
    tsx_days = [d for i, d in enumerate(wd) if i != TSX_HOLIDAY_INDEX]
    us_days = [d for i, d in enumerate(wd) if i != US_HOLIDAY_INDEX]
    aaa_days = [d for d in tsx_days if d != wd[AAA_MISSING_INDEX]]
    crypto_days = [SYN_START + timedelta(days=i) for i in range(SYN_DAYS)]

    def px(ticker, days, ccy, base):
        rows = []
        for i, d in enumerate(days):
            p = base + i * 0.5
            rows.append([d.isoformat(), ticker, str(p), str(p + 1), str(p - 1), str(p), str(p), "1000", ccy])
        return rows

    universe = [
        ["S01", "XIU.TO", "Synthetic TSX ETF", "etf_equity", "TSX", "CAD", "Broad market (Canada)"],
        ["S02", "SPY", "Synthetic US ETF", "etf_equity", "NYSE Arca", "USD", "Broad market (U.S.)"],
        ["S03", "AAA.TO", "Synthetic Bank", "equity", "TSX", "CAD", "Financials"],
        ["S04", "BTC-USD", "Synthetic Coin", "crypto", "Crypto (24/7)", "USD", "Crypto asset"],
    ]
    prices = px("XIU.TO", tsx_days, "CAD", 30) + px("SPY", us_days, "USD", 400) + px("AAA.TO", aaa_days, "CAD", 50) \
        + px("BTC-USD", crypto_days, "USD", 40000)
    fx_days = [d for i, d in enumerate(wd) if i != TSX_HOLIDAY_INDEX and i >= 1]  # no rate on the first day
    fx = [[d.isoformat(), str(1.35 + i * 0.0001), str(round(1 / (1.35 + i * 0.0001), 6))] for i, d in enumerate(fx_days)]
    actions = [[wd[30].isoformat(), "AAA.TO", "dividend", "0.5", "CAD per share"]]
    macro = []
    for d in wd:
        macro.append([d.isoformat(), "DAILYX", "2.5", "percent", "business daily", "Synthetic daily rate", "Synthetic"])
    for ref in ("2023-11-01", "2023-12-01", "2024-01-01"):
        macro.append([ref, "MONTHLYX", "3.1", "percent", "monthly", "Synthetic monthly, not revised", "Synthetic"])
        macro.append([ref, "REVX", "4.2", "percent", "monthly", "Synthetic monthly, revised", "Synthetic"])
    series = [
        ["DAILYX", "Synthetic", "daily", "false", "test"],
        ["MONTHLYX", "Synthetic", "monthly", "false", "test"],
        ["REVX", "Synthetic", "monthly", "true", "test"],
    ]
    sources = [[f, "synthetic", "Synthetic source", "https://example.invalid/data", "2026-11-13", "n/a", "daily", "none",
                "none", "Synthetic terms https://example.invalid/terms"]
               for f in ("assets_universe.csv", "prices_daily.csv", "corporate_actions.csv", "fx_usdcad_daily.csv", "macro_rates.csv")]
    themes = [
        ["XIU.TO", "broad_canada", "synthetic", "", "2024-03-01", "true"],
        ["SPY", "broad_us", "synthetic", "", "2024-03-01", "true"],
    ]
    tables = {
        "assets_universe.csv": universe, "prices_daily.csv": prices, "corporate_actions.csv": actions,
        "fx_usdcad_daily.csv": fx, "macro_rates.csv": macro, "sources_metadata.csv": sources,
        "asset_themes.csv": themes, "macro_series.csv": series,
    }
    if with_releases:
        tables["macro_release_dates.csv"] = [
            ["MONTHLYX", "2024-01-01", "2024-02-14T13:30:00Z", "", "https://example.invalid/calendar"],
            ["REVX", "2024-01-01", "2024-02-02T13:30:00Z", "2024-03-01T00:00:00Z", "https://example.invalid/vintages"],
            ["REVX", "2023-12-01", "2024-01-05T13:30:00Z", "", "https://example.invalid/vintages"],
        ]
    return tables


def encode_tables(tables: dict[str, list[list[str]]]) -> SourceBundle:
    files = {}
    for name, rows in tables.items():
        buf = io.StringIO(newline="")
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(RAW_HEADERS[name])
        w.writerows(rows)
        files[name] = buf.getvalue().encode("utf-8")
    return SourceBundle(files, {name: f"synthetic/{name}" for name in files})


def synthetic_bundle(with_releases: bool = False) -> SourceBundle:
    return encode_tables(synthetic_tables(with_releases))


def ingest_synthetic(root: Path, version: str = "snap-20240101-syn", with_releases: bool = False, activate: bool = True):
    return ingest_bundle(synthetic_bundle(with_releases), root, version, clock=fixed_clock, activate=activate)


def tree_digest(root: Path) -> dict[str, bytes]:
    """All files under a directory with their bytes (for unchanged-state assertions)."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
