"""Exact-number public corporate registry captures for Canada and Ireland.

No name matching, listed-security attribution, beneficial-owner or historical-vintage
claims are made. Canada excludes provincial and certain financial corporations; Ireland
is the daily CRO open-data snapshot, not its separately registered Open Services API.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from aplomb.api.errors import Conflict
from aplomb.api.storage import Write

CA_API = 'https://ised-isde.canada.ca/cc/lgcy/api/corporations/'
CA_TERMS = 'https://open.canada.ca/en/open-government-licence-canada'
IE_API = 'https://opendata.cro.ie/api/3/action/datastore_search'
IE_DATASET = 'https://opendata.cro.ie/dataset/companies'
IE_RESOURCE = '3fef41bc-b8f4-4b10-8434-ce51c29b1bba'
MAX_BYTES = 200_000


class RegistryError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Aplomb Registry Research'})
    try:
        with build_opener(NoRedirect).open(request, timeout=12) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise RegistryError('source_unavailable')
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RegistryError('source_unavailable') from exc
    if len(raw) > MAX_BYTES:
        raise RegistryError('source_too_large')
    return raw


def url_for(jurisdiction: str, number: str):
    if jurisdiction not in ('ca', 'ie') or not isinstance(number, str) or not re.fullmatch(r'[1-9][0-9]{0,9}', number):
        raise ValueError('An exact numeric corporate registry number is required')
    if jurisdiction == 'ca':
        return CA_API + number + '.json?lang=eng'
    return IE_API + '?' + urlencode({'resource_id': IE_RESOURCE, 'filters': json.dumps({'company_num': int(number)}, separators=(',', ':')), 'limit': 2})


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate source field')
        result[key] = value
    return result


def parse(jurisdiction: str, number: str, raw: bytes):
    url_for(jurisdiction, number)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise RegistryError('invalid_response')
    try:
        payload = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if jurisdiction == 'ca':
            if not isinstance(payload, list) or len(payload) != 2:
                raise ValueError('response structure')
            data = payload[0]
            if isinstance(data, str) and data.startswith('could not find corporation ' + number):
                return None
            if not isinstance(data, dict) or data.get('corporationId') != number:
                raise ValueError('response identity')
            names = data.get('corporationNames', [])
            if not isinstance(names, list) or len(names) > 200:
                raise ValueError('names')
            current = [x['CorporationName']['name'] for x in names if isinstance(x, dict)
                       and isinstance(x.get('CorporationName'), dict)
                       and x['CorporationName'].get('current') is True]
            if len(current) > 5 or any(not isinstance(name, str) or len(name) > 500 for name in current):
                raise ValueError('name fields')
            return {'jurisdiction': 'CA-federal', 'number': number, 'names': current,
                    'status': data.get('status'), 'governing_act': data.get('act'),
                    'registration_date': None, 'status_date': None}
        if not isinstance(payload, dict) or payload.get('success') is not True:
            raise ValueError('response metadata')
        result = payload['result']
        if result['resource_id'] != IE_RESOURCE or not isinstance(result['records'], list):
            raise ValueError('response resource')
        rows, total = result['records'], result.get('total')
        if type(total) is not int or total < 0 or len(rows) > 1 or total > 1:
            raise ValueError('ambiguous response')
        if not rows and total == 0:
            return None
        if len(rows) != 1 or str(rows[0].get('company_num')) != number or total != 1:
            raise ValueError('response identity')
        data = rows[0]
        return {'jurisdiction': 'IE', 'number': number, 'names': [data.get('company_name')],
                'status': data.get('company_status'), 'governing_act': data.get('company_type'),
                'registration_date': data.get('company_reg_date'), 'status_date': data.get('company_status_date')}
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise RegistryError('invalid_response') from exc


def capture(store, session_id: str, jurisdiction: str, number: str, *, get=fetch,
            clock=lambda: datetime.now(timezone.utc)):
    url = url_for(jurisdiction, number)
    raw = get(url)
    record = parse(jurisdiction, number, raw)
    stamp = clock()
    if stamp.tzinfo is None:
        raise RegistryError('invalid_capture_time')
    stamp = stamp.astimezone(timezone.utc).isoformat()
    digest = hashlib.sha256(raw).hexdigest()
    source = {'url': url, 'sha256': digest, 'dataset_version': 'registry-' + digest[:20],
              'retrieved_at': stamp, 'available_at': stamp, 'published_at': None,
              'provider': 'Corporations Canada' if jurisdiction == 'ca' else 'Ireland Companies Registration Office',
              'licence': 'Open Government Licence – Canada' if jurisdiction == 'ca' else 'Creative Commons Attribution 4.0',
              'terms_url': CA_TERMS if jurisdiction == 'ca' else IE_DATASET,
              'attribution': 'Contains information licensed under the Open Government Licence – Canada' if jurisdiction == 'ca'
              else 'Contains Irish Public Sector Data licensed under CC BY 4.0'}
    result = {'status': 'found' if record else 'not_found', 'record': record, 'source': source,
              'limitations': ['Exact corporate registry number only; no link to a listed security, ISIN or portfolio is inferred.',
                              'Current capture is not a historical vintage; earlier availability and revisions are unknown.',
                              'Federal registry excludes provincial/territorial and certain financial corporations.' if jurisdiction == 'ca'
                              else 'CRO open-data snapshot is separate from its login-required Open Services API.']}
    item = {'revision': 1, 'sessionId': session_id, 'raw': raw.decode('utf-8'), 'result': result}
    pk = 'COMPANY_REGISTRY#' + hashlib.sha256(session_id.encode()).hexdigest()
    sk = 'CAPTURE#' + hashlib.sha256((url + digest).encode()).hexdigest()
    try:
        store.transact([Write('cache', pk, sk, item, None)])
    except Conflict:
        existing = store.get('cache', pk, sk)
        if not existing or existing.get('sessionId') != session_id or existing.get('raw') != item['raw']:
            raise RegistryError('capture_integrity_failure')
        return existing['result']
    return result
