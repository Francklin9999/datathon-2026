"""Bounded Japan/Korea provider routes; missing credentials or rights fail closed.

Results are captured current observations, not original historical vintages. API keys
never leave this module. No symbol or name matching is used to infer issuer identity.

Field names follow the official provider specifications checked on 2026-11-15:
J-Quants v2 (https://jpx-jquants.com/en/spec/eq-bars-daily, /eq-master, /fin-summary,
/pagination) and OpenDART (company, list,
fnlttSinglAcntAll, majorstock, elestock guide pages).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import socket
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

JQ_URL = 'https://api.jquants.com/v2/equities/bars/daily'
JQ_MASTER = 'https://api.jquants.com/v2/equities/master'
JQ_FINANCIALS = 'https://api.jquants.com/v2/fins/summary'
DART_COMPANY = 'https://opendart.fss.or.kr/api/company.json'
DART_LIST = 'https://opendart.fss.or.kr/api/list.json'
DART_FINANCIALS = 'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json'
DART_MAJOR = 'https://opendart.fss.or.kr/api/majorstock.json'
DART_INSIDER = 'https://opendart.fss.or.kr/api/elestock.json'
DART_VIEWER = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='

KINDS = {'JP': ('prices', 'company', 'financials'),  # EDINET holdings removed: paid J-Quants plan
         'KR': ('filings', 'financials', 'ownership')}
UNCONFIGURED = 'provider_credentials_or_usage_rights_not_configured'

# J-Quants /fins/summary items (all JSON strings, "" when absent; monetary items in yen).
# (field, English label from the specification, section, period basis, unit)
JQ_SUMMARY_ITEMS = (
    ('Sales', 'Net sales', 'results', 'current', 'JPY'),
    ('OP', 'Operating profit', 'results', 'current', 'JPY'),
    ('OdP', 'Ordinary profit', 'results', 'current', 'JPY'),
    ('NP', 'Profit attributable to owners of parent', 'results', 'current', 'JPY'),
    ('EPS', 'Earnings per share', 'results', 'current', 'JPY/share'),
    ('DEPS', 'Diluted earnings per share', 'results', 'current', 'JPY/share'),
    ('TA', 'Total assets', 'results', 'current', 'JPY'),
    ('Eq', 'Equity', 'results', 'current', 'JPY'),
    ('BPS', 'Book value per share', 'results', 'current', 'JPY/share'),
    ('CFO', 'Cash flows from operating activities', 'results', 'current', 'JPY'),
    ('CFI', 'Cash flows from investing activities', 'results', 'current', 'JPY'),
    ('CFF', 'Cash flows from financing activities', 'results', 'current', 'JPY'),
    ('CashEq', 'Cash and equivalents', 'results', 'current', 'JPY'),
    ('DivAnn', 'Annual dividend per share', 'dividends', 'fiscal_year', 'JPY/share'),
    ('NCSales', 'Net sales', 'non-consolidated results', 'current', 'JPY'),
    ('NCOP', 'Operating profit', 'non-consolidated results', 'current', 'JPY'),
    ('NCOdP', 'Ordinary profit', 'non-consolidated results', 'current', 'JPY'),
    ('NCNP', 'Profit', 'non-consolidated results', 'current', 'JPY'),
    ('NCEPS', 'Earnings per share', 'non-consolidated results', 'current', 'JPY/share'),
    ('NCTA', 'Total assets', 'non-consolidated results', 'current', 'JPY'),
    ('NCEq', 'Equity', 'non-consolidated results', 'current', 'JPY'),
    ('NCBPS', 'Book value per share', 'non-consolidated results', 'current', 'JPY/share'),
    ('FSales', 'Net sales', 'forecast', 'fiscal_year', 'JPY'),
    ('FOP', 'Operating profit', 'forecast', 'fiscal_year', 'JPY'),
    ('FOdP', 'Ordinary profit', 'forecast', 'fiscal_year', 'JPY'),
    ('FNP', 'Profit attributable to owners of parent', 'forecast', 'fiscal_year', 'JPY'),
    ('FEPS', 'Earnings per share', 'forecast', 'fiscal_year', 'JPY/share'),
    ('FDivAnn', 'Annual dividend per share', 'forecast', 'fiscal_year', 'JPY/share'),
    ('NxFSales', 'Net sales', 'next-year forecast', 'next_fiscal_year', 'JPY'),
    ('NxFOP', 'Operating profit', 'next-year forecast', 'next_fiscal_year', 'JPY'),
    ('NxFOdP', 'Ordinary profit', 'next-year forecast', 'next_fiscal_year', 'JPY'),
    ('NxFNp', 'Profit attributable to owners of parent', 'next-year forecast', 'next_fiscal_year', 'JPY'),
    ('NxFEPS', 'Earnings per share', 'next-year forecast', 'next_fiscal_year', 'JPY/share'),
    ('NxFDivAnn', 'Annual dividend per share', 'next-year forecast', 'next_fiscal_year', 'JPY/share'),
)
# Ratio items (EqAR, ROE, payout ratios) are omitted: the specification does not state
# whether they are fractions or percentages for every item, so no unit is asserted.

class RegionalError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url: str, headers: dict) -> bytes:
    try:
        req = Request(url, headers={'Accept': 'application/json', **headers})
        with build_opener(_NoRedirect).open(req, timeout=8) as response:
            if response.status != 200:
                raise RegionalError('provider_unavailable')
            payload = response.read(8_000_001)
    except (HTTPError, URLError, OSError, socket.timeout):
        # Exceptions can include credential-bearing URLs. Never propagate their text.
        raise RegionalError('provider_unavailable') from None
    if len(payload) > 8_000_000:
        raise RegionalError('provider_response_too_large')
    return payload


def _json(payload: bytes, *, exact: bool = False) -> dict:
    """Parse strictly; with ``exact`` JSON decimals become Decimal, never binary floats."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RegionalError('provider_duplicate_fields')
            result[key] = value
        return result
    try:
        result = json.loads(payload, object_pairs_hook=pairs, parse_float=Decimal if exact else None)
    except (ValueError, UnicodeError) as exc:
        raise RegionalError('provider_invalid_response') from exc
    if not isinstance(result, dict):
        raise RegionalError('provider_invalid_response')
    return result


def _day(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise RegionalError('invalid_date') from exc


def _compact_day(value) -> str:
    """Accept the documented YYYYMMDD or YYYY-MM-DD receipt-date forms only."""
    if isinstance(value, str) and re.fullmatch(r'[0-9]{8}', value):
        value = value[:4] + '-' + value[4:6] + '-' + value[6:]
    return _day(value)


def _optional_day(value):
    return _day(value) if isinstance(value, str) and value else None


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise RegionalError('provider_invalid_price')
    return value


def _decimal(value, *, thousands=False):
    """Keep reported precision exactly; empty or ambiguous amounts are never zero."""
    if not isinstance(value, str) or len(value) > 80:
        raise RegionalError('provider_invalid_amount')
    pattern = r'-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?' if thousands else r'-?[0-9]+(?:\.[0-9]+)?'
    if not re.fullmatch(pattern, value):
        raise RegionalError('provider_invalid_amount')
    try:
        return str(Decimal(value.replace(',', '')))
    except InvalidOperation:
        raise RegionalError('provider_invalid_amount') from None


def _amount(row, field, unparsed, *, thousands=True):
    """Optional textual amount: blank or '-' is missing (not zero); malformed text is flagged."""
    value = row.get(field)
    if value is None or (isinstance(value, str) and value.strip() in ('', '-')):
        return None
    try:
        return _decimal(value.strip() if isinstance(value, str) else value, thousands=thousands)
    except RegionalError:
        unparsed.append(field)
        return None


def _exact(value, *, signed=False):
    """JSON number parsed as int/Decimal; floats are refused so no binary rounding occurs."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise RegionalError('provider_invalid_amount')
    number = Decimal(value)
    if not number.is_finite() or (number < 0 and not signed):
        raise RegionalError('provider_invalid_amount')
    return number


def _plain(number):
    if number is None:
        return None
    text = format(number.normalize(), 'f')
    return '0' if text in ('-0', '') else text


def _text(row, field, limit):
    value = row.get(field)
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    value = str(value).strip()
    return value[:limit] or None


def _rows(data, field='data', limit=10000):
    rows = data.get(field)
    if not isinstance(rows, list) or len(rows) > limit or not all(isinstance(row, dict) for row in rows):
        raise RegionalError('provider_invalid_response')
    return rows


def _dart_rows(data):
    if data.get('status') not in ('000', '013'):
        raise RegionalError('provider_unavailable')
    rows = data.get('list', [])
    if (not isinstance(rows, list) or len(rows) > 50000 or (data['status'] == '013' and rows)
            or not all(isinstance(row, dict) for row in rows)):
        raise RegionalError('provider_invalid_response')
    return rows


def _receipt(row):
    receipt = row.get('rcept_no', '')
    if not isinstance(receipt, str) or not re.fullmatch(r'[0-9]{14}', receipt):
        raise RegionalError('provider_invalid_disclosure')
    return receipt


def _stamp(now: datetime) -> str:
    if now.tzinfo is None:
        raise RegionalError('invalid_clock')
    return now.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _jst(day, clock):
    """Provider date + HH:MM:SS clock in JST to UTC; None when the clock is absent/invalid."""
    if not isinstance(clock, str) or not re.fullmatch(r'[0-2][0-9]:[0-5][0-9]:[0-5][0-9]', clock):
        return None
    try:
        moment = datetime.fromisoformat(day + 'T' + clock + '+09:00')
    except ValueError:
        return None
    return moment.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class RegionalResearch:
    """Live read-only queries limited to explicit regional provider IDs, not bare tickers."""
    def __init__(self, fetch=_fetch, env=None, clock=None, *, store=None, session_id=None):
        self.fetch = fetch
        self.env = env if env is not None else os.environ
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.store, self.session_id = store, session_id

    def _capture(self, result, payloads, key):
        """Store an immutable owner-scoped capture without retaining query credentials."""
        if any(key.encode('utf-8') in payload for payload in payloads.values()):
            raise RegionalError('provider_response_contains_credential')
        if self.store is None:
            return result
        if not self.session_id:
            raise RegionalError('invalid_session')
        from aplomb.api.errors import Conflict
        from aplomb.api.storage import Write, canonical

        raw_hashes = {name: hashlib.sha256(body).hexdigest() for name, body in payloads.items()}
        identity = {'provider': result['provider'], 'identifier': result['identifier'],
                    'start': result['requestedStart'], 'end': result['requestedEnd'],
                    'kind': result.get('kind', 'overview'), 'fiscalYear': result.get('fiscalYear'),
                    'reportCode': result.get('reportCode'), 'statementType': result.get('statementType'),
                    'hashes': raw_hashes}
        capture_id = hashlib.sha256(canonical(identity)).hexdigest()
        owner = hashlib.sha256(self.session_id.encode()).hexdigest()
        pk, sk = 'REGIONAL#' + owner, 'CAPTURE#' + capture_id
        result = {**result, 'captureId': capture_id, 'datasetVersion': 'regional-' + capture_id,
                  'storage': 'session-owned immutable capture'}
        try:
            raw = {name: body.decode('utf-8') for name, body in payloads.items()}
        except UnicodeDecodeError as exc:
            raise RegionalError('provider_invalid_response') from exc
        record = {'revision': 1, 'sessionId': self.session_id, 'raw': raw, 'rawSha256': raw_hashes,
                  'identity': identity, 'result': result}
        try:
            self.store.transact([Write('cache', pk, sk, record, None)])
        except Conflict:
            old = self.store.get('cache', pk, sk)
            if not old or old.get('sessionId') != self.session_id or old.get('identity') != identity or old.get('raw') != raw:
                raise RegionalError('provider_capture_conflict') from None
            # Preserve the original retrieval time for an identical immutable capture.
            return old['result']
        return result

    def query(self, region: str, identifier: str, start: str, end: str, *,
              kind: str = 'overview', fiscal_year: str | None = None,
              report_code: str = '11011', statement_type: str = 'CFS') -> dict:
        first, last = _day(start), _day(end)
        if first > last or (date.fromisoformat(last) - date.fromisoformat(first)).days > 366:
            raise RegionalError('invalid_date_range')
        stamp = _stamp(self.clock())
        if last > stamp[:10]:
            raise RegionalError('future_date')
        if region not in KINDS:
            raise RegionalError('unsupported_region')
        if kind == 'overview':  # Backwards-compatible alias for the original default view.
            kind = KINDS[region][0]
        if kind not in KINDS[region]:
            raise RegionalError('unsupported_research_type')
        if region == 'JP':
            if not re.fullmatch(r'[0-9A-Z]{5}', identifier):
                raise RegionalError('jquants_requires_five_character_issue_code')
            handler = {'prices': self._japan, 'company': self._japan_company,
                       'financials': self._japan_financials}[kind]
            return handler(identifier, first, last, stamp)
        if not re.fullmatch(r'[0-9]{8}', identifier):
            raise RegionalError('opendart_requires_eight_digit_corp_code')
        if kind == 'financials':
            year = fiscal_year or last[:4]
            if not re.fullmatch(r'[0-9]{4}', year) or not 2015 <= int(year) <= int(stamp[:4]):
                raise RegionalError('invalid_fiscal_year')
            if report_code not in ('11011', '11012', '11013', '11014') or statement_type not in ('CFS', 'OFS'):
                raise RegionalError('invalid_report_selection')
            return self._korea_financials(identifier, first, last, stamp, year, report_code, statement_type)
        if kind == 'ownership':
            return self._korea_ownership(identifier, first, last, stamp)
        return self._korea(identifier, first, last, stamp)

    def _configured(self, provider):
        key = self.env.get('APLOMB_' + provider + '_KEY', '').strip()
        rights = self.env.get('APLOMB_' + provider + '_RIGHTS_CONFIRMED', '').lower() == 'true'
        if not key or not rights:
            return None
        return key

    def _base(self, region, identifier, stamp, url):
        return {'region': region, 'identifier': identifier, 'retrievedAt': stamp,
                'availableAt': stamp, 'publicationAt': None, 'sourceUrl': url,
                'availabilityBasis': 'capture; original provider availability unknown',
                'historicalReplayEligibleBeforeCapture': False}

    def _frame(self, region, kind, identifier, start, end, stamp, url):
        base = self._base(region, identifier, stamp, url)
        if region == 'JP':
            base.update(provider='J-Quants', identifierType='J-Quants five-character issue code',
                        mic='XTKS', currency='JPY')
        else:
            base.update(provider='OpenDART', identifierType='OpenDART corporate code', mic=None, currency=None)
        base.update(kind=kind, prices=[], filings=[], company=None, financials=[], ownership=[],
                    requestedStart=start, requestedEnd=end)
        return base

    @staticmethod
    def _unavailable(base):
        return {**base, 'status': 'unavailable', 'reason': UNCONFIGURED}

    # --- Japan -----------------------------------------------------------------------

    def _japan_pages(self, endpoint, params, key, name, *, max_rows=50000):
        """Follow provider cursors to exhaustion or fail without publishing partial results.

        J-Quants sets no total count and splits at about 5 MB. All pages are
        retained with hashes in one immutable capture; looped cursors, excessive
        pages or responses and secret echoes fail before any capture is saved.
        """
        rows, payloads, seen = [], {}, set()
        cursor = None
        total_bytes = 0
        for page in range(1, 21):
            query = dict(params)
            if cursor is not None:
                query['pagination_key'] = cursor
            raw = self.fetch(endpoint + '?' + urlencode(query), {'x-api-key': key})
            if not isinstance(raw, bytes) or key.encode() in raw:
                raise RegionalError('provider_response_contains_credential')
            total_bytes += len(raw)
            if total_bytes > 20_000_000:
                raise RegionalError('provider_result_limit_requires_shorter_window')
            data = _json(raw)
            page_rows = _rows(data, limit=max_rows)
            rows.extend(page_rows)
            if len(rows) > max_rows:
                raise RegionalError('provider_result_limit_requires_shorter_window')
            payloads[name if page == 1 else f'{name}_page_{page}'] = raw
            if 'pagination_key' not in data:
                return rows, payloads
            cursor = data['pagination_key']
            if (not isinstance(cursor, str) or not cursor or len(cursor) > 2048
                    or key in cursor or cursor in seen):
                raise RegionalError('provider_invalid_pagination')
            seen.add(cursor)
        raise RegionalError('provider_result_limit_requires_shorter_window')

    def _japan(self, identifier, start, end, stamp):
        base = self._frame('JP', 'prices', identifier, start, end, stamp, JQ_URL)
        key = self._configured('JQUANTS')
        if not key:
            return self._unavailable(base)
        rows, payloads = self._japan_pages(JQ_URL, {'code': identifier, 'from': start, 'to': end}, key, 'prices')
        raw = payloads['prices']
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or row.get('Code') != identifier:
                raise RegionalError('provider_identifier_mismatch')
            d = _day(row.get('Date'))
            if not start <= d <= end or d in seen:
                raise RegionalError('provider_invalid_dates')
            seen.add(d)
            base['prices'].append({'date': d, 'close': _number(row.get('C')),
                                   'adjustedClose': _number(row.get('AdjC')), 'currency': 'JPY'})
        base['prices'].sort(key=lambda item: item['date'])
        result = {**base, 'status': 'ok', 'sourceSha256': hashlib.sha256(raw).hexdigest(),
                  'partial': False, 'pagesInspected': len(payloads),
                  'sourceHashes': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()},
                  'limitations': ['Tokyo Stock Exchange only; issue code is not an ISIN or issuer identity.',
                                  'Current capture; original availability and correction history unknown.',
                                  'Adjusted prices are recalculated retroactively and omit cash dividends.']}
        return self._capture(result, payloads, key)

    def _japan_company(self, identifier, start, end, stamp):
        base = self._frame('JP', 'company', identifier, start, end, stamp, JQ_MASTER)
        key = self._configured('JQUANTS')
        if not key:
            return self._unavailable(base)
        rows, payloads = self._japan_pages(JQ_MASTER, {'code': identifier, 'date': end}, key, 'company', max_rows=50)
        raw = payloads['company']
        listings = []
        for row in rows:
            if row.get('Code') != identifier:
                raise RegionalError('provider_identifier_mismatch')
            listings.append({'asOf': _day(row.get('Date')), 'name': _text(row, 'CoName', 300),
                             'englishName': _text(row, 'CoNameEn', 300), 'stockCode': identifier,
                             'sector17Code': _text(row, 'S17', 10), 'sector17Name': _text(row, 'S17Nm', 120),
                             'sector33Code': _text(row, 'S33', 10), 'sector33Name': _text(row, 'S33Nm', 120),
                             'scaleCategory': _text(row, 'ScaleCat', 60), 'marketCode': _text(row, 'Mkt', 10),
                             'marketName': _text(row, 'MktNm', 120), 'marginCode': _text(row, 'Mrgn', 10),
                             'marginName': _text(row, 'MrgnNm', 60), 'productCategory': _text(row, 'ProdCat', 10)})
        if len({item['asOf'] for item in listings}) != len(listings):
            raise RegionalError('provider_invalid_dates')
        listings.sort(key=lambda item: item['asOf'], reverse=True)
        result = {**base, 'status': 'ok', 'sourceSha256': hashlib.sha256(raw).hexdigest(),
                  'company': listings[0] if listings else None, 'listings': listings,
                  'partial': False, 'pagesInspected': len(payloads),
                  'sourceHashes': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()},
                  'limitations': [
                      'Issue information as of the requested end date; the provider returns the next business day for non-business dates.',
                      'An empty result can mean the issue was not listed on that date; listing and delisting dates are not provided.',
                      'Company, sector and market names are provider-reported (sector and market names in Japanese); not an issuer identity proof.']}
        return self._capture(result, payloads, key)

    def _japan_financials(self, identifier, start, end, stamp):
        base = self._frame('JP', 'financials', identifier, start, end, stamp, JQ_FINANCIALS)
        key = self._configured('JQUANTS')
        if not key:
            return self._unavailable(base)
        rows, payloads = self._japan_pages(JQ_FINANCIALS, {'code': identifier}, key, 'financials')
        raw = payloads['financials']
        seen = set()
        unparsed = []
        for row in rows:
            if row.get('Code') != identifier:
                raise RegionalError('provider_identifier_mismatch')
            day = _day(row.get('DiscDate'))
            number = row.get('DiscNo')
            if not isinstance(number, str) or not re.fullmatch(r'[0-9]{1,30}', number) or number in seen:
                raise RegionalError('provider_invalid_disclosure')
            seen.add(number)
            if not start <= day <= end:
                continue
            periods = {
                'current': (_optional_day(row.get('CurPerSt')), _optional_day(row.get('CurPerEn')),
                            _text(row, 'CurPerType', 10)),
                'fiscal_year': (_optional_day(row.get('CurFYSt')), _optional_day(row.get('CurFYEn')), 'FY'),
                'next_fiscal_year': (_optional_day(row.get('NxtFYSt')), _optional_day(row.get('NxtFYEn')), 'Next FY')}
            document = _text(row, 'DocType', 180)
            disclosed_at = _jst(day, row.get('DiscTime'))
            for field, label, section, basis, unit in JQ_SUMMARY_ITEMS:
                value = _amount(row, field, unparsed, thousands=False)
                if value is None:
                    continue
                period_start, period_end, period_label = periods[basis]
                base['financials'].append({
                    'disclosureNumber': number, 'disclosedDate': day, 'disclosedAt': disclosed_at,
                    'documentType': document, 'period': period_label, 'periodStart': period_start,
                    'periodEnd': period_end, 'section': section, 'accountId': field, 'accountName': label,
                    'value': value, 'unit': unit,
                    'classification': 'forecast' if 'forecast' in section else 'reported', 'url': None})
        base['financials'].sort(key=lambda item: (item['disclosedDate'], item['disclosureNumber']), reverse=True)
        limitations = ['Disclosure date/time is the TDnet disclosure time (JST); provider availability before capture is unknown.',
                       'Reported figures and company forecasts are distinct; missing values are omitted, not zero.',
                       'Pre-correction values are not provided by the source; PDF-only disclosures are excluded.',
                       'Ratio items (equity ratio, ROE, payout) are omitted because their unit is not asserted here.',
                       'Financial data belongs to the issue code, not a verified security-to-issuer relationship.']
        if unparsed:
            limitations.append('Some provider values were malformed and omitted: ' + ', '.join(sorted(set(unparsed))[:20]))
        result = {**base, 'status': 'ok', 'sourceSha256': hashlib.sha256(raw).hexdigest(),
                  'partial': False, 'pagesInspected': len(payloads),
                  'sourceHashes': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()},
                  'limitations': limitations}
        return self._capture(result, payloads, key)

    # --- Korea -----------------------------------------------------------------------

    def _korea(self, identifier, start, end, stamp):
        base = self._frame('KR', 'filings', identifier, start, end, stamp, DART_LIST)
        key = self._configured('OPENDART')
        if not key:
            return self._unavailable(base)
        params = {'crtfc_key': key, 'corp_code': identifier}
        company_raw = self.fetch(DART_COMPANY + '?' + urlencode(params), {})
        company = _json(company_raw)
        if company.get('status') != '000' or (company.get('corp_code') is not None and company['corp_code'] != identifier):
            raise RegionalError('provider_identifier_or_status_mismatch')
        params.update(bgn_de=start.replace('-', ''), end_de=end.replace('-', ''), page_count='100')
        base['company'] = {'name': str(company.get('corp_name', ''))[:300],
                           'englishName': str(company.get('corp_name_eng', ''))[:300],
                           'stockCode': company.get('stock_code') or None}
        payloads = {'company': company_raw}
        page_hashes, seen = {}, set()
        total_pages, total_reported = None, None
        for page in range(1, 51):
            raw = self.fetch(DART_LIST + '?' + urlencode({**params, 'page_no': str(page)}), {})
            data = _json(raw)
            if data.get('status') not in ('000', '013'):
                raise RegionalError('provider_rejected_filings_request')
            rows = data.get('list', [])
            if not isinstance(rows, list) or len(rows) > 100:
                raise RegionalError('provider_invalid_response')
            try:
                pages = int(data.get('total_page', 0 if data.get('status') == '013' else 1))
                total = int(data.get('total_count', len(rows)))
            except (TypeError, ValueError):
                raise RegionalError('provider_invalid_pagination') from None
            if pages < 0 or pages > 50 or total < 0 or total > 5000:
                raise RegionalError('provider_result_limit_requires_shorter_window')
            if total_pages is None:
                total_pages, total_reported = pages, total
            elif (pages, total) != (total_pages, total_reported):
                raise RegionalError('provider_pagination_changed')
            name = 'filings' if page == 1 else f'filings_page_{page}'
            payloads[name] = raw
            page_hashes[str(page)] = hashlib.sha256(raw).hexdigest()
            for row in rows:
                if not isinstance(row, dict) or row.get('corp_code') != identifier:
                    raise RegionalError('provider_identifier_mismatch')
                receipt, day = row.get('rcept_no', ''), row.get('rcept_dt', '')
                if not re.fullmatch(r'[0-9]{14}', receipt) or not re.fullmatch(r'[0-9]{8}', day):
                    raise RegionalError('provider_invalid_response')
                filed = _day(day[:4] + '-' + day[4:6] + '-' + day[6:])
                if not start <= filed <= end or receipt in seen:
                    raise RegionalError('provider_invalid_dates')
                seen.add(receipt)
                base['filings'].append({'title': str(row.get('report_nm', ''))[:500], 'date': filed,
                                        'receiptNumber': receipt, 'url': DART_VIEWER + receipt})
            if page >= total_pages:
                break
        if len(base['filings']) != total_reported:
            raise RegionalError('provider_incomplete_filings_result')
        base['filings'].sort(key=lambda item: (item['date'], item['receiptNumber']), reverse=True)
        result = {**base, 'status': 'ok', 'sourceSha256': page_hashes['1'],
                  'companySourceSha256': hashlib.sha256(company_raw).hexdigest(), 'partial': False,
                  'totalReported': total_reported, 'pagesInspected': len(page_hashes), 'pageSourceSha256': page_hashes,
                  'limitations': ['Company lookup is scoped by the requested corporate code; the response does not guarantee it echoes that code.',
                                  'Corporate code identifies a filer; stock code is provider-reported, not a global security mapping.',
                                  'Filing date is not a proven exact publication or availability timestamp.',
                                  'All pages in the requested interval are captured; source revisions remain possible.']}
        return self._capture(result, payloads, key)

    def _korea_financials(self, identifier, start, end, stamp, year, report, statement):
        base = self._frame('KR', 'financials', identifier, start, end, stamp, DART_FINANCIALS)
        base.update(fiscalYear=year, reportCode=report, statementType=statement)
        key = self._configured('OPENDART')
        if not key:
            return self._unavailable(base)
        query = urlencode({'crtfc_key': key, 'corp_code': identifier, 'bsns_year': year,
                           'reprt_code': report, 'fs_div': statement})
        raw = self.fetch(DART_FINANCIALS + '?' + query, {})
        data = _json(raw)
        rows = _dart_rows(data)
        unparsed = []
        for row in rows:
            if (row.get('corp_code') != identifier or row.get('bsns_year') != year
                    or row.get('reprt_code') != report):
                raise RegionalError('provider_identifier_mismatch')
            receipt = _receipt(row)
            base['financials'].append({
                'receiptNumber': receipt, 'disclosedDate': None, 'disclosedAt': None,
                'reportCode': report, 'fiscalYear': year, 'statementType': statement,
                'period': _text(row, 'thstrm_nm', 200), 'periodStart': None, 'periodEnd': None,
                'section': _text(row, 'sj_div', 20), 'sectionName': _text(row, 'sj_nm', 120),
                'accountId': _text(row, 'account_id', 200), 'accountName': _text(row, 'account_nm', 300),
                'accountDetail': _text(row, 'account_detail', 300),
                'value': _amount(row, 'thstrm_amount', unparsed),
                'cumulativeValue': _amount(row, 'thstrm_add_amount', unparsed),
                'priorPeriod': _text(row, 'frmtrm_nm', 200), 'priorValue': _amount(row, 'frmtrm_amount', unparsed),
                'order': _text(row, 'ord', 10), 'unit': _text(row, 'currency', 20),
                'classification': 'reported', 'url': DART_VIEWER + receipt})
        limitations = ['Report is selected by fiscal year and report code; it is not filtered by the date range.',
                       'The source response carries a receipt number but no receipt date; capture time bounds availability.',
                       'Quarterly and half-year income statement values are three-month amounts; cumulative values are shown separately.',
                       'Currency and accounting basis are as reported; the source does not state a monetary scale. Amendments may differ from originals.']
        if unparsed:
            limitations.append('Some provider amounts were malformed and omitted: ' + ', '.join(sorted(set(unparsed))))
        result = {**base, 'status': 'ok', 'sourceSha256': hashlib.sha256(raw).hexdigest(), 'partial': False,
                  'limitations': limitations}
        return self._capture(result, {'financials': raw}, key)

    def _korea_ownership(self, identifier, start, end, stamp):
        base = self._frame('KR', 'ownership', identifier, start, end, stamp, DART_MAJOR)
        key = self._configured('OPENDART')
        if not key:
            return self._unavailable(base)
        query = urlencode({'crtfc_key': key, 'corp_code': identifier})
        raw_by_type = {}
        unparsed = []
        for category, url in (('major_shareholder', DART_MAJOR), ('executive_or_major_holder', DART_INSIDER)):
            raw = self.fetch(url + '?' + query, {})
            raw_by_type[category] = raw
            for row in _dart_rows(_json(raw)):
                if row.get('corp_code') != identifier:
                    raise RegionalError('provider_identifier_mismatch')
                receipt = _receipt(row)
                filed = _compact_day(row.get('rcept_dt'))
                if not start <= filed <= end:
                    continue
                item = {'category': category, 'receiptNumber': receipt, 'documentId': None,
                        'filed': filed, 'filedAt': None, 'obligationDate': None,
                        'reporter': _text(row, 'repror', 300), 'holderCount': None, 'title': None,
                        'amendment': None, 'amendsDocumentId': None, 'outstandingShares': None,
                        'url': DART_VIEWER + receipt}
                if category == 'major_shareholder':
                    item.update(reportType=_text(row, 'report_tp', 120), reason=_text(row, 'report_resn', 500),
                                position=None,
                                shares=_amount(row, 'stkqy', unparsed),
                                sharesChange=_amount(row, 'stkqy_irds', unparsed),
                                ratioPct=_amount(row, 'stkrt', unparsed),
                                ratioChangePct=_amount(row, 'stkrt_irds', unparsed),
                                contractShares=_amount(row, 'ctr_stkqy', unparsed),
                                contractRatioPct=_amount(row, 'ctr_stkrt', unparsed))
                else:
                    position = ' · '.join(filter(None, (_text(row, 'isu_exctv_ofcps', 120),
                                                        _text(row, 'isu_exctv_rgist_at', 60),
                                                        _text(row, 'isu_main_shrholdr', 120))))
                    item.update(reportType=None, reason=None, position=position or None,
                                shares=_amount(row, 'sp_stock_lmp_cnt', unparsed),
                                sharesChange=_amount(row, 'sp_stock_lmp_irds_cnt', unparsed),
                                ratioPct=_amount(row, 'sp_stock_lmp_rate', unparsed),
                                ratioChangePct=_amount(row, 'sp_stock_lmp_irds_rate', unparsed))
                base['ownership'].append(item)
        base['ownership'].sort(key=lambda item: (item['filed'], item['receiptNumber']), reverse=True)
        limitations = ['Disclosed positions, not a live or exhaustive ownership register or a list of trades.',
                       'Receipt date (rcept_dt) only; not a proven exact publication or provider availability timestamp.',
                       'Major-shareholder (majorstock) and executive/major-holder (elestock) reports are provider-reported; capture time bounds availability.',
                       'Records are filtered to the requested receipt-date range after retrieval.']
        if unparsed:
            limitations.append('Some provider amounts were malformed and omitted: ' + ', '.join(sorted(set(unparsed))))
        hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in raw_by_type.items()}
        result = {**base, 'status': 'ok', 'sourceHashes': hashes, 'sourceUrls': [DART_MAJOR, DART_INSIDER],
                  'partial': False, 'limitations': limitations}
        return self._capture(result, raw_by_type, key)
