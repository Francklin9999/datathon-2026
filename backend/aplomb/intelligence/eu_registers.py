"""Official EU regulator observations keyed by an exact validated LEI.

EBA market risk is an immutable 2025 dataset. ESMA is a current, bounded registry
query. Neither observation establishes a security listing or proves ownership.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

from .defi_sources import DefiSourceError, fetch, strict_load
from .entities import valid_lei

EBA_SOURCE = 'https://www.eba.europa.eu/assets/TE2025/Full_database/883401/tr_mrk.csv'
EBA_GUIDE = 'https://www.eba.europa.eu/assets/TE2025/Banks_individuals_results/883401/DE_529900S1KHKOEQL5CK20_TR_2025.pdf'
EBA_TERMS = 'https://www.eba.europa.eu/find-out-about-us/legal-notice'
EBA_SHA = '61df1e82d48c0179437e688ac8c3dbdf37000de9b662db0911d8dd917fce84bc'
EBA_RETRIEVED = '2026-11-15T17:10:59Z'
EBA_CSV = Path(__file__).parent / 'data/eba_2025_market_risk.csv.gz'
ESMA_BASE = 'https://registers.esma.europa.eu/solr/esma_registers_upreg/select'
ESMA_DOCS = 'https://registers.esma.europa.eu/publication/helpApp'
ESMA_TERMS = 'https://registers.esma.europa.eu/publication/legalNoticePage'
ESMA_FIELDS = ('id', 'ae_lei', 'ae_entityName', 'ae_entityTypeCode', 'ae_officeType',
               'ae_competentAuthority', 'ae_homeMemberState', 'ae_hostMemberState',
               'ae_status', 'ae_authorisationNotificationDate', 'ae_authorisationWithdrawalEndDateStr', 'ae_lastUpdate')
PERIODS = ('202409', '202412', '202503', '202506')


class EURegisterError(ValueError):
    pass


def lei_value(lei):
    if not isinstance(lei, str) or not valid_lei(lei):
        raise EURegisterError('invalid_lei')
    return lei


def _persist(store, sid, provider, key_suffix, record):
    owner = 'EU_REGISTRY#' + hashlib.sha256(sid.encode()).hexdigest()
    key = provider + '#' + hashlib.sha256(key_suffix.encode()).hexdigest()
    item = {'revision': 1, 'sessionId': sid, **record}
    try:
        store.transact([Write('cache', owner, key, item, None)])
    except Conflict:
        prior = store.get('cache', owner, key)
        if not prior or prior.get('sessionId') != sid or prior.get('source_sha256') != item['source_sha256']:
            raise EURegisterError('capture_integrity_failure')
        return prior
    return item


def eba_market_risk(store, sid, lei, period='202506', *, file_path=EBA_CSV):
    lei_value(lei)
    if period not in PERIODS:
        raise EURegisterError('unsupported_period')
    try:
        # The source file is 3.8 MB; cap decompression to detect corrupt/malicious bundles.
        with gzip.open(file_path, 'rb') as stream:
            raw = stream.read(4_000_001)
        if len(raw) > 4_000_000 or hashlib.sha256(raw).hexdigest() != EBA_SHA:
            raise EURegisterError('source_integrity_failure')
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        expected = ['LEI_Code', 'NSA', 'Period', 'Item', 'Label', 'Portfolio',
                    'MKT_Modprod', 'Mkt_risk', 'Amount', 'Row', 'Column', 'Sheet']
        if reader.fieldnames != expected:
            raise EURegisterError('invalid_source_schema')
        rows = []
        for lineno, record in enumerate(reader, start=2):
            if record.get('LEI_Code') != lei or record.get('Period') != period:
                continue
            try:
                value = Decimal(record['Amount'])
            except InvalidOperation as exc:
                raise EURegisterError('invalid_source_amount') from exc
            if not value.is_finite() or record['Sheet'] != 'Market Risk':
                raise EURegisterError('invalid_source_row')
            rows.append({'item': record['Item'], 'label': record['Label'], 'country_reported': record['NSA'],
                         'portfolio_code': record['Portfolio'], 'product_code': record['MKT_Modprod'],
                         'market_risk_code': record['Mkt_risk'], 'amount': str(value), 'unit': 'EUR million',
                         'source_row': lineno, 'template_row': record['Row'], 'template_column': record['Column']})
            if len(rows) > 250:
                raise EURegisterError('source_row_limit')
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise EURegisterError('source_unavailable') from exc
    result = {'status': 'available' if rows else 'not_found', 'provider': 'European Banking Authority',
              'lei': lei, 'reference_period': period, 'source_url': EBA_SOURCE, 'source_sha256': EBA_SHA,
              'dataset_version': 'eba-te2025-market-' + EBA_SHA[:16], 'retrieved_at': EBA_RETRIEVED,
              'available_at': EBA_RETRIEVED, 'published_at': None, 'rows': rows, 'source_licence': EBA_TERMS,
              'unit_reference': EBA_GUIDE,
              'limitations': ['Historical 2025 transparency exercise; source says this exercise was discontinued.',
                              'These are reported prudential market-risk exposure measures, not portfolio holdings or predictions.',
                              'Different row, column and approach codes overlap; do not sum without the data dictionary.',
                              'Original publication timestamp is not established; retrieval is the first proven availability.',
                              'A missing LEI or row does not prove zero exposure.']}
    saved = _persist(store, sid, 'EBA', lei + period + EBA_SHA,
                     {'source_sha256': EBA_SHA, 'result': result})
    return saved['result']


def esma_url(lei, start=0):
    lei_value(lei)
    # Only a validated ISO 17442 LEI is interpolated; user-supplied Solr is not accepted.
    return ESMA_BASE + '?' + urlencode({'q': f'ae_lei:"{lei}"', 'rows': 20,
                                       'fl': ','.join(ESMA_FIELDS), 'wt': 'json', 'start': start, 'sort': 'id asc'})


def esma_entities(store, sid, lei, *, get=fetch, now=None):
    lei_value(lei)
    url = esma_url(lei)
    try:
        rows, originals, seen = [], [], set()
        count = None
        for offset in range(0, 2000, 20):
            page_url = esma_url(lei, offset)
            raw = get(page_url)
            body = strict_load(raw)
            response = body['response']
            page_count, documents = response['numFound'], response['docs']
            if (type(page_count) is not int or not 0 <= page_count <= 2000
                    or not isinstance(documents, list) or len(documents) > 20):
                raise EURegisterError('source_result_limit_or_invalid_schema')
            if count is None:
                count = page_count
            elif page_count != count:
                raise EURegisterError('source_pagination_changed')
            originals.append({'url': page_url, 'sha256': hashlib.sha256(raw).hexdigest(), 'raw': raw.decode('utf-8')})
            for row in documents:
                if (not isinstance(row, dict) or row.get('ae_lei') != lei
                        or not isinstance(row.get('id'), str) or row['id'] in seen):
                    raise EURegisterError('source_identity_or_pagination_mismatch')
                seen.add(row['id'])
                rows.append({key: row[key] for key in ESMA_FIELDS if key in row})
            if len(rows) >= count:
                break
            if not documents:
                raise EURegisterError('source_incomplete_pagination')
        if len(rows) != count:
            raise EURegisterError('source_incomplete_pagination')
        raw = originals[0]['raw'].encode('utf-8')
        digest = hashlib.sha256(raw).hexdigest()
        captured = now or datetime.now(timezone.utc)
        if captured.tzinfo is None:
            raise EURegisterError('invalid_capture_time')
        result = {'status': 'available' if rows else 'not_found', 'lei': lei, 'rows': rows,
                  'total_reported': count, 'partial': False, 'pages_inspected': len(originals),
                  'page_sources': [{k:v for k,v in page.items() if k != 'raw'} for page in originals], 'provider': 'ESMA Registers',
                  'source_url': url, 'source_sha256': digest, 'dataset_version': 'esma-register-' + digest[:16],
                  'available_at': captured.isoformat(), 'retrieved_at': captured.isoformat(), 'published_at': None,
                  'source_licence': ESMA_TERMS, 'documentation': ESMA_DOCS,
                  'limitations': ['Source is ESMA Registers, available free of charge through the registers.',
                                  'Each row is an authorization record; absence is not evidence of no authorization.',
                                  'Current source capture does not establish historical availability or issuer relationships.',
                                  'Reporting ESMA data does not imply ESMA endorsement.']}
        saved = _persist(store, sid, 'ESMA', url + digest,
                         {'source_sha256': digest, 'raw': raw.decode('utf-8'), 'pages': originals, 'result': result})
        return saved['result']
    except (DefiSourceError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise EURegisterError('source_unavailable_or_invalid') from exc
