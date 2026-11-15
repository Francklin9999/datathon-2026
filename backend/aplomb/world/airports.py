"""Current-only OurAirports infrastructure reference. No aircraft movement or financial impact."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

from .geo import in_bbox

SOURCE_URL = 'https://davidmegginson.github.io/ourairports-data/airports.csv'
TERMS_URL = 'https://github.com/davidmegginson/ourairports-data/blob/main/LICENSE'
DIRECTORY = Path(__file__).resolve().parent / 'bundle'


def parse_airports(payload: bytes, country_payload: bytes, captured_at: str) -> tuple[list[dict], dict]:
    """Keep large scheduled-service airports with validated coordinates; never infer missing geography."""
    countries = json.loads(country_payload)
    if not isinstance(countries, list) or len(countries) != 2 or countries[0].get('pages') != 1:
        raise ValueError('Incomplete country crosswalk')
    crosswalk = {r['iso2Code']: r['id'] for r in countries[1]
                 if r.get('region', {}).get('id') != 'NA' and re.fullmatch('[A-Z]{2}', r.get('iso2Code', ''))}
    rows, rejected, seen = [], 0, set()
    for row in csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))):
        if row.get('type') != 'large_airport' or row.get('scheduled_service') != 'yes':
            continue
        try:
            lat, lon = float(row['latitude_deg']), float(row['longitude_deg'])
            ident, name, key = row['ident'], row['name'].strip(), row['id']
            if not name or not key.isdecimal() or key in seen or not re.fullmatch('[A-Z0-9-]{2,20}', ident):
                raise ValueError('Invalid airport identity')
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError('Invalid airport coordinates')
            seen.add(key)
            iso2 = row.get('iso_country')
            rows.append({'airportId': 'oa_' + key, 'ident': ident, 'name': name, 'lat': lat, 'lon': lon,
                         'countryIso2': iso2 if iso2 and re.fullmatch('[A-Z]{2}', iso2) else None,
                         'countryIso3': crosswalk.get(iso2), 'sourceUrl': SOURCE_URL, 'capturedAt': captured_at})
        except (KeyError, ValueError, TypeError):
            rejected += 1
    if not rows:
        raise ValueError('No validated airport references')
    rows.sort(key=lambda r: r['airportId'])
    text = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=1) + '\n'
    digest = hashlib.sha256(text.encode()).hexdigest()
    meta = {'datasetId': 'world_airports', 'dataVersion': 'snap-' + captured_at[:10].replace('-', '') + '-airports-' + digest[:10],
            'sha256': digest, 'rowCount': len(rows), 'rejected': rejected, 'capturedAt': captured_at,
            'sourceUrl': SOURCE_URL, 'sourceSha256': hashlib.sha256(payload).hexdigest(),
            'countryCrosswalkSource': 'https://api.worldbank.org/v2/country?format=json&per_page=1000',
            'countryCrosswalkSha256': hashlib.sha256(country_payload).hexdigest(),
            'licence': 'OurAirports public-domain dedication (Unlicense); country-code crosswalk: World Bank, CC BY 4.0',
            'licenceUrl': TERMS_URL, 'publicationDate': None,
            'limitations': ['Static crowdsourced reference, not aircraft tracking or operational status.',
                            'Coordinates may be approximate. No facility-to-company relationship or financial impact is established.',
                            'Only large airports with scheduled service in the captured source are included.',
                            'Country codes use the explicit World Bank crosswalk; missing mappings remain null.']}
    return rows, meta


def load_airports(directory: Path = DIRECTORY) -> tuple[list[dict], dict | None]:
    data, metadata = directory / 'airports.json', directory / 'airports_manifest.json'
    if not data.exists() and not metadata.exists():
        return [], None
    content = data.read_bytes().replace(b'\r\n', b'\n')
    manifest = json.loads(metadata.read_text())
    rows = json.loads(content)
    if hashlib.sha256(content).hexdigest() != manifest['sha256'] or len(rows) != manifest['rowCount']:
        raise ValueError('Airport snapshot integrity failure')
    return rows, manifest


def filter_airports(rows, *, country=None, query='', bbox=None):
    needle = query.strip().casefold()
    return [r for r in rows if (not country or r['countryIso3'] == country)
            and (not needle or needle in f"{r['ident']} {r['name']}".casefold())
            and (bbox is None or in_bbox(r['lat'], r['lon'], bbox))]
