"""GLEIF Golden Copy metadata and bounded exact-LEI lookup in current intraday delta.

A delta is only updates since the prior publication. No match never means the
LEI is absent from the Golden Copy. Full archives are reported but not fetched.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import socket
import zipfile
from datetime import datetime, time, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

from .entities import valid_lei

METADATA = 'https://goldencopy.gleif.org/api/v2/golden-copies/publishes/lei2/latest'
DOCS = 'https://www.gleif.org/en/lei-data/gleif-golden-copy'
TERMS = 'https://www.gleif.org/en/meta/lei-data-terms-of-use'
MAX_META = 100_000
MAX_ZIP = 2_000_000
MAX_UNPACKED = 12_000_000
MAX_ROWS = 20_000


class GoldenCopyError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, *, maximum, media):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'goldencopy.gleif.org' or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.query or parsed.fragment):
        raise GoldenCopyError('invalid_source_url')
    if url != METADATA and not re.fullmatch(r'/storage/golden-copy-files/[0-9/]+/[A-Za-z0-9.-]+\.csv\.zip', parsed.path):
        raise GoldenCopyError('invalid_source_url')
    req = Request(url, headers={'Accept': media, 'User-Agent': 'Aplomb research https://github.com/Francklin9999/datathon-2026'})
    try:
        with build_opener(NoRedirect).open(req, timeout=15) as response:
            if response.status != 200:
                raise GoldenCopyError('source_unavailable')
            size = response.headers.get('Content-Length')
            if size and int(size) > maximum:
                raise GoldenCopyError('source_too_large')
            raw = response.read(maximum + 1)
    except HTTPError as exc:
        raise GoldenCopyError('rate_limited' if exc.code == 429 else 'source_unavailable') from exc
    except (URLError, OSError, socket.timeout) as exc:
        raise GoldenCopyError('source_unavailable') from exc
    if len(raw) > maximum:
        raise GoldenCopyError('source_too_large')
    return raw


def metadata(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_META:
        raise GoldenCopyError('invalid_metadata')
    try:
        data = json.loads(raw)['data']
        if data['type'] != 'lei2':
            raise ValueError('wrong dataset')
        content_date = datetime.strptime(data['publish_date'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        out = []
        for mode in ('full_file', 'IntraDay', 'LastDay', 'LastWeek', 'LastMonth'):
            item = data['full_file']['csv'] if mode == 'full_file' else data['delta_files'][mode]['csv']
            expected = 'GoldenCopy' if mode == 'full_file' else mode
            if (item['type'] != 'lei2' or item['format'] != 'csv' or item['delta_type'] != expected
                    or type(item['size']) is not int or item['size'] <= 0
                    or type(item['record_count']) is not int or item['record_count'] < 0):
                raise ValueError('bad metadata dimensions')
            url = item['url']
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'goldencopy.gleif.org' or parsed.query or parsed.fragment
                    or parsed.username or parsed.password or parsed.port not in (None, 443)
                    or not re.fullmatch(r'/storage/golden-copy-files/[0-9/]+/[A-Za-z0-9.-]+\.csv\.zip', parsed.path)):
                raise ValueError('unsafe archive url')
            out.append({'kind': expected, 'format': 'csv', 'url': url, 'compressed_bytes': item['size'],
                        'record_count': item['record_count'], 'cdf_version': item['cdf_version'],
                        'within_import_limit': expected == 'IntraDay' and item['size'] <= MAX_ZIP})
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise GoldenCopyError('invalid_metadata') from exc
    return {'content_as_of': content_date.isoformat(), 'published_at': None, 'archives': out,
            'source_url': METADATA, 'metadata_sha256': hashlib.sha256(raw).hexdigest(),
            'limitations': ['The source content timestamp does not prove publication or availability time.',
                            'A delta includes only changes since its prior publication, not the full LEI index.']}


def select(raw, lei, expected_count):
    if not valid_lei(lei):
        raise ValueError('Valid LEI checksum required')
    if not isinstance(raw, bytes) or len(raw) > MAX_ZIP:
        raise GoldenCopyError('source_too_large')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].is_dir() or not members[0].filename.endswith('.csv') or members[0].file_size > MAX_UNPACKED:
                raise GoldenCopyError('invalid_archive')
            with archive.open(members[0]) as source:
                reader = csv.DictReader(io.TextIOWrapper(source, encoding='utf-8-sig', newline=''))
                header = reader.fieldnames
                required = ('LEI', 'Entity.LegalName', 'Entity.LegalJurisdiction', 'Entity.EntityStatus')
                if not header or len(header) != len(set(header)) or any(field not in header for field in required):
                    raise GoldenCopyError('invalid_csv_header')
                match, count = None, 0
                for row in reader:
                    count += 1
                    if count > MAX_ROWS or None in row:
                        raise GoldenCopyError('invalid_csv_rows')
                    if row.get('LEI') == lei:
                        if match is not None:
                            raise GoldenCopyError('duplicate_lei')
                        match = {'lei': lei, 'legal_name': row['Entity.LegalName'],
                                 'jurisdiction': row['Entity.LegalJurisdiction'], 'entity_status': row['Entity.EntityStatus'],
                                 'registration_status': row.get('Registration.RegistrationStatus'),
                                 'source_updated_at': row.get('Registration.LastUpdateDate')}
                if count != expected_count:
                    raise GoldenCopyError('record_count_mismatch')
    except (zipfile.BadZipFile, UnicodeError, csv.Error, OSError, EOFError) as exc:
        raise GoldenCopyError('invalid_archive') from exc
    return match


def _put(store, partition, key, item):
    try:
        store.transact([Write('cache', partition, key, item, None)])
        return item
    except Conflict:
        old = store.get('cache', partition, key)
        if not old or old.get('sessionId') != item['sessionId'] or old.get('source_sha256') != item['source_sha256']:
            raise GoldenCopyError('capture_integrity_failure') from None
        return old


def discover(store, session_id, *, get=fetch, now=None):
    raw = get(METADATA, maximum=MAX_META, media='application/json')
    result = metadata(raw)
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('timezone-aware capture clock required')
    if datetime.fromisoformat(result['content_as_of']) > stamp.astimezone(timezone.utc):
        raise GoldenCopyError('metadata_content_after_capture')
    stamp = stamp.astimezone(timezone.utc).isoformat()
    owner = 'GLEIF_GOLDEN#' + hashlib.sha256(session_id.encode()).hexdigest()
    digest = hashlib.sha256(raw).hexdigest()
    item = _put(store, owner, 'METADATA#' + digest, {'revision': 1, 'sessionId': session_id,
        'source_sha256': digest, 'raw_base64': base64.b64encode(raw).decode('ascii'),
        'retrieved_at': stamp, 'normalized': result})
    return {**item['normalized'], 'retrieved_at': item['retrieved_at'], 'available_at': item['retrieved_at'],
            'licence': 'GLEIF LEI access service data CC0 1.0', 'licence_url': TERMS}, raw


def ingest_delta(store, session_id, lei, *, get=fetch, now=None):
    if not valid_lei(lei):
        raise ValueError('Valid LEI checksum required')
    meta, raw_meta = discover(store, session_id, get=get, now=now)
    item = next(x for x in meta['archives'] if x['kind'] == 'IntraDay')
    if item['compressed_bytes'] > MAX_ZIP or item['record_count'] > MAX_ROWS:
        raise GoldenCopyError('delta_exceeds_safety_limit')
    raw = get(item['url'], maximum=MAX_ZIP, media='application/zip')
    if len(raw) != item['compressed_bytes']:
        raise GoldenCopyError('archive_size_mismatch')
    found = select(raw, lei, item['record_count'])
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('timezone-aware capture clock required')
    stamp = stamp.astimezone(timezone.utc).isoformat()
    owner = 'GLEIF_GOLDEN#' + hashlib.sha256(session_id.encode()).hexdigest()
    digest = hashlib.sha256(raw).hexdigest()
    archive = _put(store, owner, 'ARCHIVE#' + digest, {'revision': 1, 'sessionId': session_id,
        'source_sha256': digest, 'raw_base64': base64.b64encode(raw).decode('ascii'),
        'retrieved_at': stamp, 'source_url': item['url'], 'metadata_sha256': hashlib.sha256(raw_meta).hexdigest(),
        'record_count': item['record_count'], 'content_as_of': meta['content_as_of']})
    source = {'url': archive['source_url'], 'content_sha256': digest, 'metadata_sha256': archive['metadata_sha256'],
              'content_as_of': archive['content_as_of'], 'retrieved_at': archive['retrieved_at'],
              'available_at': archive['retrieved_at'], 'published_at': None,
              'licence': 'GLEIF LEI access service data CC0 1.0', 'licence_url': TERMS}
    if found:
        record = {'revision': 1, 'sessionId': session_id, 'source_sha256': digest, 'lei': lei,
                  'entity': found, 'source': source, 'archive_key': 'ARCHIVE#' + digest,
                  'dataset_version': 'gleif-golden-' + digest[:16]}
        _put(store, owner, 'ENTITY#' + lei + '#' + digest, record)
    return {'status': 'found_in_delta' if found else 'not_in_delta', 'entity': found, 'source': source,
            'dataset_version': 'gleif-golden-' + digest[:16], 'records_scanned': item['record_count'],
            'limitations': ['This intraday delta only contains changes since the preceding Golden Copy.',
                            'No match does not establish that an LEI or entity is absent.',
                            'A legal entity record does not prove any security issuer or ownership relationship.']}


def latest_entity(store, session_id, lei, as_of=None):
    if not valid_lei(lei):
        raise ValueError('Valid LEI checksum required')
    owner = 'GLEIF_GOLDEN#' + hashlib.sha256(session_id.encode()).hexdigest()
    records = store.query('cache', owner)
    if len(records) > 5000:
        raise GoldenCopyError('capture_limit_exceeded')
    selected = []
    for record in records:
        if record.get('sessionId') != session_id or record.get('lei') != lei:
            continue
        source = record.get('source', {})
        try:
            captured = datetime.fromisoformat(source['retrieved_at'])
            if captured.tzinfo is None:
                raise ValueError('missing timezone')
            if as_of and captured > datetime.combine(as_of, time.max, tzinfo=timezone.utc):
                continue
            archived = store.get('cache', owner, record['archive_key'])
            raw = base64.b64decode(archived['raw_base64'], validate=True)
            digest = hashlib.sha256(raw).hexdigest()
            if (archived['sessionId'] != session_id or digest != source['content_sha256']
                    or digest != record['source_sha256'] or archived['source_url'] != source['url']):
                raise ValueError('source hash mismatch')
            entity = select(raw, lei, archived['record_count'])
            if not entity or entity != record['entity']:
                raise ValueError('record differs from source')
        except (KeyError, TypeError, ValueError) as exc:
            raise GoldenCopyError('capture_integrity_failure') from exc
        selected.append(record)
    return max(selected, key=lambda item: item['source']['retrieved_at']) if selected else None
