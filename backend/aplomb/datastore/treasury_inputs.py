"""Validated captured US Treasury par-curve and fiscal-debt observations."""
from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlsplit

from .errors import IngestionError
from .timeutil import normalize_ts, parse_date

PAR_URL = 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml'
DEBT_URL = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny'
NAMES = {'BC_1MONTH': '1M', 'BC_1_5MONTH': '1.5M', 'BC_2MONTH': '2M',
         'BC_3MONTH': '3M', 'BC_4MONTH': '4M', 'BC_6MONTH': '6M', 'BC_1YEAR': '1Y',
         'BC_2YEAR': '2Y', 'BC_3YEAR': '3Y', 'BC_5YEAR': '5Y', 'BC_7YEAR': '7Y',
         'BC_10YEAR': '10Y', 'BC_20YEAR': '20Y', 'BC_30YEAR': '30Y'}
NS = {'atom': 'http://www.w3.org/2005/Atom',
      'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
      'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices'}


@dataclass(frozen=True)
class TreasuryCapture:
    source_url: str
    retrieved_at: str
    sha256: str
    rows: tuple[dict, ...]

    def latest(self, known_at: str, on_or_before: str) -> dict | None:
        known_at = normalize_ts(known_at, 'known_at')
        cutoff = parse_date(on_or_before, 'on_or_before')
        if known_at < self.retrieved_at:
            return None
        return next((row for row in reversed(self.rows) if parse_date(row['date']) <= cutoff), None)


def _verify(payload: bytes, metadata: dict, source: str) -> tuple[str, str, dict]:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != metadata['rawSha256']:
        raise ValueError('hash mismatch')
    url = metadata['sourceUrl']
    parts = urlsplit(url)
    if f'{parts.scheme}://{parts.netloc}{parts.path}' != source or parts.fragment:
        raise ValueError('unexpected source URL')
    return digest, normalize_ts(metadata['retrievedAt'], 'retrievedAt'), parse_qs(parts.query)


def read_par(payload: bytes, metadata: dict) -> TreasuryCapture:
    try:
        digest, retrieved, params = _verify(payload, metadata, PAR_URL)
        if (params.get('data') != ['daily_treasury_yield_curve']
                or set(params) != {'data', 'field_tdr_date_value_month'}):
            raise ValueError('unexpected Treasury curve query')
        months = params['field_tdr_date_value_month']
        if len(months) != 1 or not re.fullmatch(r'\d{6}', months[0]):
            raise ValueError('invalid Treasury curve month')
        if len(payload) > 2_000_000 or b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
            raise ValueError('unsafe or oversized XML')
        root = ET.fromstring(payload)
        rows, seen = [], set()
        for item in root.findall('atom:entry/atom:content/m:properties', NS):
            stamp = item.findtext('d:NEW_DATE', namespaces=NS)
            if not stamp or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T00:00:00', stamp):
                raise ValueError('invalid observation date')
            day = parse_date(stamp[:10])
            if day.strftime('%Y%m') != months[0] or day.isoformat() > retrieved[:10] or day in seen:
                raise ValueError('invalid or duplicate observation date')
            points = {}
            for key, maturity in NAMES.items():
                node = item.find(f'd:{key}', NS)
                if node is None or node.text is None:
                    points[maturity] = None
                else:
                    value = float(node.text)
                    if not math.isfinite(value):
                        raise ValueError('non-finite yield')
                    points[maturity] = value
            if not any(value is not None for value in points.values()):
                raise ValueError('curve has no rates')
            seen.add(day)
            rows.append({'date': day.isoformat(), 'yieldsPercent': points})
        if not rows:
            raise ValueError('no curves')
        rows.sort(key=lambda row: row['date'])
        return TreasuryCapture(metadata['sourceUrl'], retrieved, digest, tuple(rows))
    except (KeyError, TypeError, ValueError, ET.ParseError) as exc:
        raise IngestionError(f'invalid Treasury par curve: {exc}') from exc


def read_debt(payload: bytes, metadata: dict) -> TreasuryCapture:
    try:
        digest, retrieved, params = _verify(payload, metadata, DEBT_URL)
        filters = params.get('filter', [])
        match = (re.fullmatch(r'record_date:gte:(\d{4}-\d{2}-\d{2}),'
                              r'record_date:lte:(\d{4}-\d{2}-\d{2})', filters[0])
                 if len(filters) == 1 else None)
        if metadata['series'] != 'debt_to_penny' or not match:
            raise ValueError('unexpected fiscal series')
        start, end = (parse_date(value, 'filter date') for value in match.groups())
        if start > end:
            raise ValueError('invalid fiscal date interval')
        doc = json.loads(payload)
        raw, meta, links = doc['data'], doc['meta'], doc['links']
        if (not isinstance(raw, list) or not raw or meta['count'] != len(raw)
                or meta['total-count'] != len(raw) or links['next'] is not None):
            raise ValueError('incomplete or empty fiscal page')
        rows, seen = [], set()
        keys = ('tot_pub_debt_out_amt', 'debt_held_public_amt', 'intragov_hold_amt')
        for record in raw:
            day = parse_date(record['record_date'])
            amounts = [Decimal(record[key]) for key in keys]
            if (day in seen or not start <= day <= end or day.isoformat() > retrieved[:10]
                    or any(not v.is_finite() or v < 0 for v in amounts)
                    or amounts[1] + amounts[2] != amounts[0]):
                raise ValueError('invalid or duplicate fiscal observation')
            seen.add(day)
            rows.append({'date': day.isoformat(), 'totalUsd': str(amounts[0]),
                         'heldByPublicUsd': str(amounts[1]), 'intragovernmentalUsd': str(amounts[2])})
        rows.sort(key=lambda row: row['date'])
        return TreasuryCapture(metadata['sourceUrl'], retrieved, digest, tuple(rows))
    except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError) as exc:
        raise IngestionError(f'invalid Treasury debt capture: {exc}') from exc
