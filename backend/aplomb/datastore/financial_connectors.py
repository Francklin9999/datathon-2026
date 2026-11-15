"""Bounded, read-only provider connectors. Entitlements/rights are configured server-side.

No orders, account creation, arbitrary URLs or credential-bearing response metadata.
Availability of a connector never asserts provider access or redistribution permission.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from xml.etree import ElementTree as ET

from aplomb.api.errors import ServiceError

from .fama_french import SOURCE as FRENCH_URL
from .fama_french import read_capture as read_french
from .finra_volume import read_capture as read_volume

MAX_BYTES = 3_000_000


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    source_ids: tuple[str, ...]
    documentation: str
    terms: str
    permission_env: str
    credentials: tuple[str, ...] = ()
    limitation: str = ''


PROVIDERS = {
    p.id: p for p in (
        Provider('oanda', 'OANDA v20 indicative FX pricing', ('SRC-013',),
            'https://developer.oanda.com/rest-live-v20/pricing-ep/',
            'https://developer.oanda.com/rest-live-v20/introduction/', 'OANDA',
            ('APLOMB_OANDA_TOKEN', 'APLOMB_OANDA_ACCOUNT_ID'),
            'Account-entitled bid/ask quotes, not executable conversions or Bank of Canada reference rates.'),
        Provider('fama-french', 'French daily US three-factor data', ('SRC-022', 'MASTER-012'),
            'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html',
            'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html', 'FAMA_FRENCH',
            limitation='Published factor portfolio returns, not estimated exposures of the active investor.'),
        Provider('aqr', 'AQR monthly Betting Against Beta equity factors', ('SRC-023',),
            'https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly',
            'https://www.aqr.com/terms-of-use', 'AQR',
            limitation='Spreadsheet values retain source units; confirm workbook terms and units before fitting exposures.'),
        Provider('cboe', 'Cboe VIX daily index history', ('SRC-024',),
            'https://www.cboe.com/tradable-products/vix/vix-historical-data/',
            'https://cdn.cboe.com/resources/membership/Market_Data_Policies.pdf', 'CBOE',
            limitation='VIX index points are an implied-volatility index, not a live option chain or portfolio volatility.'),
        Provider('occ', 'OCC daily options volume statistics', ('SRC-025', 'MASTER-009'),
            'https://www.theocc.com/specialpages/batch-processing-changes',
            'https://www.theocc.com/data-subscriber-terms', 'OCC',
            limitation='Daily reported contract-volume summary, not option prices, Greeks or an option chain.'),
        Provider('finra-volume', 'FINRA consolidated daily short-sale volume', ('SRC-026', 'MASTER-011'),
            'https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data',
            'https://developer.finra.org/specific-terms-equity-data', 'FINRA',
            limitation='Reported short-sale flow; exempt volume is included in short volume. This is not short interest.'),
        Provider('finra-interest', 'FINRA consolidated short interest', ('SRC-027',),
            'https://developer.finra.org/docs', 'https://developer.finra.org/specific-terms-equity-data', 'FINRA',
            limitation='Settlement-date reported short positions, separate from short-sale volume; no float estimate is inferred.'),
        Provider('cme', 'CME DataMine entitled historical files', ('SRC-030',),
            'https://www.cmegroup.com/datamine/datamine-api.html',
            'https://www.cmegroup.com/market-data/distributor/market-data-policy.html', 'CME',
            ('APLOMB_CME_API_ID', 'APLOMB_CME_API_PASSWORD'),
            'Requires purchased/entitled files and display rights. Formats vary; records retain original source columns.'),
        Provider('fred', 'FRED credit spreads and STLFSI4', ('SRC-031', 'MASTER-015'),
            'https://fred.stlouisfed.org/docs/api/fred/series_observations.html',
            'https://fred.stlouisfed.org/legal/terms/', 'FRED', ('APLOMB_FRED_API_KEY',),
            'Written permission for the intended AI application is required; ICE series have additional underlying rights. Capture time is not an original vintage.'),
    )
}


DEFERRED_PROVIDERS = {key: PROVIDERS.pop(key) for key in ('oanda', 'cme', 'fred')}
DEFERRED_REASONS = {'oanda': 'Login/account and token required; set aside by user.',
                    'cme': 'Paid/entitled data; excluded by user.',
                    'fred': 'API key/account and written data-use permission required; set aside by user.'}


def provider_status(provider: Provider) -> dict:
    if provider.id in DEFERRED_PROVIDERS:
        return {**asdict(provider), 'status': 'set_aside', 'reason': DEFERRED_REASONS[provider.id], 'rightsConfirmed': False, 'missingCredentials': []}
    permitted = os.environ.get(f'APLOMB_SOURCE_{provider.permission_env}_RIGHTS_CONFIRMED', '').lower() == 'true'
    missing = [name for name in provider.credentials if not os.environ.get(name)]
    return {**asdict(provider), 'rightsConfirmed': permitted, 'missingCredentials': missing,
            'status': 'permission_required' if not permitted else 'credentials_required' if missing else 'configured',
            'permissionSetting': f'APLOMB_SOURCE_{provider.permission_env}_RIGHTS_CONFIRMED',
            'note': 'Configured means the connector can be called; it does not mean a live provider response was received.'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ServiceError('upstream_unavailable', 'Provider redirected; no credentials forwarded or alternate host followed')


def _request(url: str, *, headers: dict | None = None, body: dict | None = None) -> bytes:
    request_headers = {'Accept': 'application/json,text/csv,application/zip,application/octet-stream',
                       'User-Agent': 'AplombResearch/1.0', **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        request_headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, headers=request_headers, data=data)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ServiceError('upstream_unavailable', 'Provider response exceeds the bounded capture size')
            return raw
    except urllib.error.HTTPError as exc:
        raise ServiceError('upstream_unavailable', f'Provider returned HTTP {exc.code}; access controls were not bypassed') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ServiceError('upstream_unavailable', 'Provider unavailable or timed out') from None


def _finite(value, *, nonnegative=False) -> float:
    number = float(value)
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError('nonfinite or invalid numerical observation')
    return number


def _csv_rows(raw: bytes) -> list[dict]:
    text = raw.decode('utf-8-sig')
    if '<html' in text[:1000].lower() or '<!doctype' in text[:1000].lower():
        raise ValueError('provider returned HTML rather than a data report')
    rows = list(csv.reader(io.StringIO(text)))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 2 or len(rows) > 100_000:
        raise ValueError('empty or oversized report')
    # Preambles and grouped headings are preserved rather than assigned guessed units.
    return [{'sourceRow': i + 1, 'fields': row} for i, row in enumerate(rows)]


def _xlsx_rows(raw: bytes, sheet: str) -> list[dict]:
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if sum(entry.file_size for entry in entries) > 25_000_000 or len(entries) > 200:
            raise ValueError('oversized workbook')
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        locations = {entry.attrib['Id']: entry.attrib['Target'] for entry in relationships}
        sheets = workbook.findall('s:sheets/s:sheet', ns)
        chosen = next((item for item in sheets if item.attrib['name'].casefold() == sheet.casefold()), None) if sheet else next((item for item in sheets if any(x in item.attrib['name'].casefold() for x in ('bab', 'data'))), None)
        if chosen is None:
            raise ValueError('select one of the workbook data sheets: ' + ', '.join(item.attrib['name'] for item in sheets))
        rid = chosen.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target = locations[rid]
        path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        if '..' in path or path not in archive.namelist():
            raise ValueError('invalid worksheet relationship')
        data = ET.fromstring(archive.read(path))
        result = []
        for row in data.findall('s:sheetData/s:row', ns):
            fields = {}
            for cell in row.findall('s:c', ns):
                value = cell.find('s:v', ns)
                if cell.attrib.get('t') == 'inlineStr':
                    parsed = ''.join(cell.find('s:is', ns).itertext())
                elif value is None:
                    continue
                elif cell.attrib.get('t') == 's':
                    parsed = shared[int(value.text)]
                elif cell.attrib.get('t') == 'b':
                    parsed = value.text == '1'
                elif cell.attrib.get('t') in ('str', 'e'):
                    parsed = value.text
                else:
                    parsed = _finite(value.text)
                fields[cell.attrib['r']] = parsed
            if fields:
                result.append({'sheet': chosen.attrib['name'], 'row': int(row.attrib['r']), 'sourceCells': fields})
        if not result:
            raise ValueError('empty worksheet')
        return result


def acquire(provider_id: str, *, day: date, symbol: str = 'SPY', sheet: str = '', limit: int = 100) -> tuple[dict, bytes]:
    provider = PROVIDERS.get(provider_id)
    if provider is None:
        raise ServiceError('not_found', 'Unknown financial provider')
    status = provider_status(provider)
    if status['status'] != 'configured':
        raise ServiceError('upstream_unavailable', f'{provider.name}: {status["status"]}',
                           {'provider': provider_id, 'missingCredentials': status['missingCredentials'], 'termsUrl': provider.terms})
    if day > datetime.now(timezone.utc).date():
        raise ValueError('provider observation cutoff cannot be in the future')
    if not re.fullmatch(r'[A-Z0-9.\-]{1,30}', symbol):
        raise ValueError('invalid exact symbol')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    params, headers, body = {}, {}, None
    if provider_id == 'fama-french':
        url = FRENCH_URL
    elif provider_id == 'aqr':
        if day.isoformat() != now[:10]:
            raise ValueError('AQR workbook inspection is current-capture only; original publication dates and historical availability are not established')
        url = 'https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Betting-Against-Beta-Equity-Factors-Monthly.xlsx'
    elif provider_id == 'cboe':
        url = 'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'
    elif provider_id == 'occ':
        url = 'https://marketdata.theocc.com/daily-volume-statistics'
        params = {'reportDate': day.strftime('%Y%m%d'), 'format': 'csv'}
    elif provider_id == 'finra-volume':
        url = f'https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day:%Y%m%d}.txt'
    elif provider_id == 'finra-interest':
        url = 'https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest'
        body = {'limit': limit, 'compareFilters': [
            {'compareType': 'equal', 'fieldName': 'symbolCode', 'fieldValue': symbol},
            {'compareType': 'lesserOrEqual', 'fieldName': 'settlementDate', 'fieldValue': day.isoformat()}]}
    network_url = url + ('?' + urllib.parse.urlencode(params) if params else '')
    safe_params = {key: value for key, value in params.items() if key != 'api_key'}
    source_url = url + ('?' + urllib.parse.urlencode(safe_params) if safe_params else '')
    raw = _request(network_url, headers=headers, body=body)
    digest = hashlib.sha256(raw).hexdigest()
    metadata = {'sourceUrl': source_url, 'retrievedAt': now, 'rawSha256': digest}
    if provider_id == 'fama-french':
        captured = read_french(raw, metadata)
        records = [asdict(row) for row in captured.through(now, day.isoformat())][-limit:]
        unit = 'fractional daily factor return'
    elif provider_id == 'finra-volume':
        row = read_volume(raw, metadata).find(symbol, now)
        records = [{key: str(value) for key, value in asdict(row).items()}] if row else []
        unit = 'reported shares; not short interest'
    elif provider_id == 'cboe':
        records = []
        for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
            observed = datetime.strptime(row['DATE'], '%m/%d/%Y').date()
            values = {key.lower(): _finite(row[key], nonnegative=True) for key in ('OPEN', 'HIGH', 'LOW', 'CLOSE')}
            if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
                raise ValueError('invalid VIX OHLC record')
            if observed <= day:
                records.append({'date': observed.isoformat(), **values})
        records = sorted(records, key=lambda row: row['date'])[-limit:]
        unit = 'VIX index points'
    elif provider_id == 'aqr':
        records, unit = _xlsx_rows(raw, sheet)[-limit:], 'source workbook values; units not inferred'
    elif provider_id == 'occ':
        records, unit = _csv_rows(raw)[:limit], 'source report fields; daily contract-volume summary'
    elif provider_id == 'finra-interest':
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) > limit:
            raise ValueError('unexpected short-interest response')
        records = []
        for row in data:
            if row['symbolCode'] != symbol or date.fromisoformat(row['settlementDate']) > day:
                raise ValueError('short-interest filter mismatch')
            records.append({'symbol': symbol, 'settlementDate': row['settlementDate'],
                'currentShortPositionQuantity': _finite(row['currentShortPositionQuantity'], nonnegative=True),
                'previousShortPositionQuantity': _finite(row['previousShortPositionQuantity'], nonnegative=True),
                'averageDailyVolumeQuantity': _finite(row['averageDailyVolumeQuantity'], nonnegative=True),
                'reportedDaysToCover': row.get('daysToCoverQuantity'), 'marketClassCode': row.get('marketClassCode')})
        unit = 'reported position shares; days-to-cover remains provider-reported'
    if not records:
        raise ServiceError('insufficient_data', 'No matching provider observations; no values were fabricated')
    return ({'provider': provider_id, 'label': provider.name, 'sourceIds': list(provider.source_ids),
        'asOf': day.isoformat(), 'availableAt': now, 'source': metadata,
        'version': f'risk_{provider_id}_{digest[:16]}', 'unit': unit, 'records': records,
        'status': 'captured', 'termsUrl': provider.terms, 'permission': 'server-configured rights confirmation',
        'limitations': [provider.limitation, 'Availability starts at retrieval; earlier observation dates do not establish historical knowledge.',
                         'Exact symbols/provider IDs are not a verified crosswalk to portfolio securities.']}, raw)
