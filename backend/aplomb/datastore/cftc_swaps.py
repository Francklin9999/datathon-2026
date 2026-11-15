"""Read the CFTC public weekly interest-rate swaps aggregate report."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date

SOURCE = 'https://www.cftc.gov/MarketReports/SwapsReports/L2IRSGrossExp.html'


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading, self.h1, self.table, self.finished = '', False, False, False
        self.cell, self.cells, self.rows, self.sup = None, [], [], False

    def handle_starttag(self, tag, attrs):
        if tag == 'h1' and not self.heading:
            self.h1 = True
        if tag == 'table' and self.heading and not self.finished and not self.table:
            self.table = True
        if self.table and tag == 'tr':
            self.cells = []
        if self.table and tag in ('td', 'th'):
            self.cell = ''
        if self.table and tag == 'sup':
            self.sup = True

    def handle_data(self, text):
        if self.h1 and 'Gross Notional Outstanding - Interest Rate' in text:
            self.heading += text
        if self.cell is not None and not self.sup:
            self.cell += text

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.h1 = False
        if tag == 'sup':
            self.sup = False
        if self.table and tag in ('td', 'th') and self.cell is not None:
            self.cells.append(self.cell.strip())
            self.cell = None
        if self.table and tag == 'tr':
            self.rows.append(self.cells)
        if self.table and tag == 'table':
            self.table, self.finished = False, True


@dataclass(frozen=True)
class SwapsCapture:
    source_url: str
    retrieved_at: str
    sha256: str
    observation: dict

    def latest(self, known_at: str, on_or_before: str) -> dict | None:
        known_at = normalize_ts(known_at, 'known_at')
        cutoff = parse_date(on_or_before, 'on_or_before')
        if known_at < self.retrieved_at or parse_date(self.observation['date']) > cutoff:
            return None
        return self.observation


def read_capture(payload: bytes, metadata: dict) -> SwapsCapture:
    try:
        digest = hashlib.sha256(payload).hexdigest()
        if (digest != metadata['rawSha256'] or metadata['sourceUrl'] != SOURCE
                or metadata['series'] != 'interest_rate_swaps_gross_notional'):
            raise ValueError('capture hash or source mismatch')
        retrieved = normalize_ts(metadata['retrievedAt'], 'retrievedAt')
        if len(payload) > 1_000_000:
            raise ValueError('oversized swaps report')
        parser = ReportParser()
        parser.feed(payload.decode('utf-8'))
        match = re.fullmatch(r'Gross Notional Outstanding - Interest Rate \(Millions of USD\) - (\d{2}/\d{2}/\d{4})', parser.heading.strip())
        if not match or not parser.finished:
            raise ValueError('unexpected report heading or table')
        day = datetime.strptime(match.group(1), '%m/%d/%Y').date()
        if day.isoformat() > retrieved[:10] or not parser.rows or parser.rows[0] != ['Product', 'Cleared', 'Uncleared', 'Total']:
            raise ValueError('invalid report date or columns')
        total = [row for row in parser.rows if row and row[0] == 'TOTAL']
        if len(total) != 1 or len(total[0]) != 4 or any(not re.fullmatch(r'\d{1,3}(?:,\d{3})*', x) for x in total[0][1:]):
            raise ValueError('invalid total')
        cleared, uncleared, aggregate = (int(x.replace(',', '')) for x in total[0][1:])
        if abs(cleared + uncleared - aggregate) > 1:
            raise ValueError('inconsistent totals')
        return SwapsCapture(SOURCE, retrieved, digest,
                            {'date': day.isoformat(), 'clearedMillionsUsd': cleared,
                             'unclearedMillionsUsd': uncleared, 'totalMillionsUsd': aggregate})
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise IngestionError(f'invalid CFTC swaps report: {exc}') from exc
