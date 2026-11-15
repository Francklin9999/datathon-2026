"""Bounded SEC structured-disclosure RSS ingestion, using a declared operator contact."""
from __future__ import annotations

import hashlib
import os
import re
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

URL = 'https://www.sec.gov/Archives/edgar/xbrlrss.all.xml'


class SecFeedError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch():
    contact = os.getenv('APLOMB_SEC_CONTACT', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{1,79} [^\s@]+@[^\s@]+\.[^\s@]+', contact):
        raise SecFeedError('operator_contact_unconfigured')
    request = Request(URL, headers={'User-Agent': contact, 'Accept': 'application/rss+xml, application/xml, text/xml'})
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200:
                raise SecFeedError('source_unavailable')
            body = response.read(2000001)
    except (HTTPError, URLError, OSError, socket.timeout) as exc:
        raise SecFeedError('source_unavailable') from exc
    if len(body) > 2000000:
        raise SecFeedError('source_too_large')
    return body


def parse(payload: bytes, *, now=None):
    if len(payload) > 2000000 or b'<!DOCTYPE' in payload.upper() or b'<!ENTITY' in payload.upper():
        raise SecFeedError('invalid_xml')
    try:
        root = ET.fromstring(payload)
        if root.tag != 'rss':
            raise ValueError('not RSS')
        items = []
        for item in root.findall('./channel/item')[:200]:
            title = (item.findtext('title') or '').strip()
            url = (item.findtext('link') or '').strip()
            parsed = urlsplit(url)
            if not title or len(title) > 500 or parsed.scheme != 'https' or parsed.hostname != 'www.sec.gov' or parsed.username or parsed.password:
                continue
            if not parsed.path.startswith('/Archives/edgar/data/'):
                continue
            edgar = '{http://www.sec.gov/Archives/edgar}'
            filing = item.find(edgar + 'xbrlFiling')
            metadata = {}
            if filing is not None:
                cik = filing.findtext(edgar + 'cikNumber') or ''
                accession = filing.findtext(edgar + 'accessionNumber') or ''
                form = filing.findtext(edgar + 'formType') or ''
                filing_date = filing.findtext(edgar + 'filingDate') or ''
                company = filing.findtext(edgar + 'companyName') or ''
                if re.fullmatch(r'\d{1,10}', cik):
                    metadata['cik'] = cik.zfill(10)
                if re.fullmatch(r'\d{10}-\d{2}-\d{6}', accession):
                    metadata['accession'] = accession
                if re.fullmatch(r'[A-Za-z0-9 /-]{1,30}', form):
                    metadata['form'] = form
                try:
                    metadata['filing_date'] = datetime.strptime(filing_date, '%m/%d/%Y').date().isoformat()
                except ValueError:
                    pass
                if 0 < len(company) <= 300:
                    metadata['company_name'] = company
            items.append({'title': title, 'url': url, 'published_at': item.findtext('pubDate'), **metadata})
    except (ValueError, ET.ParseError) as exc:
        raise SecFeedError('invalid_response') from exc
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('clock must be timezone-aware')
    return {'items': items, 'source_url': URL, 'source_sha256': hashlib.sha256(payload).hexdigest(),
            'retrieved_at': stamp.isoformat(), 'available_at': stamp.isoformat(),
            'limitations': ['Feed is a recent discovery index, not a complete filing history.',
                            'No filing content or corporate identity is inferred from a title.',
                            'Original publication time is not inferred from retrieval time.']}


def capture(store, session_id: str, *, get=fetch):
    payload = get()
    result = parse(payload)
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    pk, sk = 'SEC_RSS#' + owner, 'CAPTURE#' + result['source_sha256']
    record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', pk, sk, record, None)])
    except Conflict:
        old = store.get('cache', pk, sk)
        if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id:
            raise
        return old['result']
    return result


DATA_LIBRARY = 'https://www.sec.gov/about/divisions-offices/division-economic-risk-analysis/dera-data-library'


def parse_data_library(payload: bytes, *, now=None):
    """Extract SEC-owned dataset links from a captured DERA library HTML page."""
    from html.parser import HTMLParser
    from urllib.parse import urljoin

    if len(payload) > 2_000_000:
        raise SecFeedError('source_too_large')

    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.url = None
            self.text = []
            self.items = []

        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.url = dict(attrs).get('href')
                self.text = []

        def handle_data(self, text):
            if self.url is not None:
                self.text.append(text)

        def handle_endtag(self, tag):
            if tag != 'a' or self.url is None:
                return
            label = ' '.join(''.join(self.text).split())
            url = urljoin(DATA_LIBRARY, self.url)
            parsed = urlsplit(url)
            if (label and len(label) <= 200 and parsed.scheme == 'https'
                    and parsed.hostname == 'www.sec.gov' and not parsed.username and not parsed.password
                    and ('/data-research/' in parsed.path or '/dera/data/' in parsed.path)):
                self.items.append({'title': label, 'url': url})
            self.url = None

    try:
        parser = Links()
        parser.feed(payload.decode('utf-8'))
        if not parser.items:
            raise ValueError('no dataset links')
    except (UnicodeDecodeError, ValueError) as exc:
        raise SecFeedError('invalid_response') from exc
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('clock must be timezone-aware')
    # Preserve source order while avoiding repeated navigation links.
    unique = {x['url']: x for x in parser.items}
    return {'items': list(unique.values())[:200], 'source_url': DATA_LIBRARY,
            'source_sha256': hashlib.sha256(payload).hexdigest(),
            'retrieved_at': stamp.isoformat(), 'available_at': stamp.isoformat(),
            'limitations': ['Dataset links are discovery only; no dataset contents were acquired.',
                            'Descriptions and update dates require individual source verification.']}


def fetch_data_library():
    contact = os.getenv('APLOMB_SEC_CONTACT', '')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{1,79} [^\s@]+@[^\s@]+\.[^\s@]+', contact):
        raise SecFeedError('operator_contact_unconfigured')
    request = Request(DATA_LIBRARY, headers={'User-Agent': contact, 'Accept': 'text/html'})
    try:
        with build_opener(NoRedirect).open(request, timeout=10) as response:
            if response.status != 200 or response.headers.get_content_type() != 'text/html':
                raise SecFeedError('source_unavailable')
            payload = response.read(2_000_001)
    except (HTTPError, URLError, OSError, socket.timeout) as exc:
        raise SecFeedError('source_unavailable') from exc
    if len(payload) > 2_000_000:
        raise SecFeedError('source_too_large')
    return payload


def capture_data_library(store, session_id: str, *, get=fetch_data_library):
    payload = get()
    result = parse_data_library(payload)
    owner = hashlib.sha256(session_id.encode()).hexdigest()
    pk, sk = 'SEC_LIBRARY#' + owner, 'CAPTURE#' + result['source_sha256']
    record = {'revision': 1, 'sessionId': session_id, 'raw': payload.decode('utf-8'), 'result': result}
    try:
        store.transact([Write('cache', pk, sk, record, None)])
    except Conflict:
        old = store.get('cache', pk, sk)
        if old is None or old.get('raw') != record['raw'] or old.get('sessionId') != session_id:
            raise
        return old['result']
    return result
