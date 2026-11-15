"""Read FINRA's daily reported short-sale volume; this is not short interest."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date


@dataclass(frozen=True)
class Volume:
    symbol: str
    date: str
    short: Decimal
    short_exempt: Decimal  # Included in short, not an additional quantity.
    total: Decimal
    facilities: str


@dataclass(frozen=True)
class VolumeCapture:
    retrieved_at: str
    sha256: str
    rows: tuple[Volume, ...]

    def find(self, symbol: str, known_at: str) -> Volume | None:
        if normalize_ts(known_at, 'known_at') < self.retrieved_at:
            return None
        return next((row for row in self.rows if row.symbol == symbol), None)


def read_capture(payload: bytes, metadata: dict) -> VolumeCapture:
    try:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != metadata['rawSha256']:
            raise ValueError('hash mismatch')
        url = metadata['sourceUrl']
        match = re.fullmatch(r'https://cdn\.finra\.org/equity/regsho/daily/CNMSshvol(\d{8})\.txt', url)
        if not match:
            raise ValueError('unexpected FINRA source URL')
        raw_date = match.group(1)
        day = parse_date(f'{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}')
        retrieved = normalize_ts(metadata['retrievedAt'], 'retrievedAt')
        if day.isoformat() > retrieved[:10]:
            raise ValueError('future trade date')
        lines = payload.decode('utf-8-sig').splitlines()
        if len(lines) < 2 or not lines[-1].isdigit():
            raise ValueError('missing trailer')
        reader = csv.DictReader(io.StringIO('\n'.join(lines[:-1])), delimiter='|')
        if reader.fieldnames != ['Date', 'Symbol', 'ShortVolume', 'ShortExemptVolume', 'TotalVolume', 'Market']:
            raise ValueError('unexpected columns')
        data, seen = [], set()
        for row in reader:
            symbol = row['Symbol']
            if (row['Date'] != raw_date or not symbol or symbol in seen or len(symbol) > 30
                    or not row['Market'] or None in row):
                raise ValueError('invalid or duplicate symbol')
            values = [Decimal(row[key]) for key in ('ShortVolume', 'ShortExemptVolume', 'TotalVolume')]
            if (any(not x.is_finite() or x < 0 for x in values)
                    or values[1] > values[0] or values[0] > values[2]):
                raise ValueError('invalid volume')
            seen.add(symbol)
            data.append(Volume(symbol, day.isoformat(), *values, row['Market']))
        if len(data) != int(lines[-1]):
            raise ValueError('trailer count mismatch')
        return VolumeCapture(retrieved, digest, tuple(data))
    except (KeyError, TypeError, ValueError, UnicodeError, InvalidOperation) as exc:
        raise IngestionError(f'invalid FINRA short sale volume: {exc}') from exc
