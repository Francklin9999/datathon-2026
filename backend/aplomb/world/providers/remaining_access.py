"""Anonymous Ember monthly and Geofabrik Monaco captures; no credentials.

Run with --source ember|geofabrik --directory PATH. Runtime loads the immutable
observations through the shared provider loader. OSM derivative stays separate.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import re
import sqlite3
import struct
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import publish, validate_row

EMBER_URL = 'https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_monthly_global.csv'
EMBER_PAGE = 'https://ember-energy.org/data/monthly-electricity-data/'
GEO_URL = 'https://download.geofabrik.de/europe/monaco-latest-free.gpkg.zip'
GEO_PAGE = 'https://download.geofabrik.de/europe/monaco.html'
OSM_ATTRIBUTION = '© OpenStreetMap contributors; processed by Geofabrik GmbH; selected and normalized by Aplomb. This separate derived database is available under ODbL 1.0.'


def fetch(url: str) -> bytes:
    if url not in {EMBER_URL, EMBER_PAGE, GEO_URL, GEO_PAGE}:
        raise ValueError('Unexpected remaining source URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'AplombDatathon/1.0 bounded public capture', 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(request, timeout=25) as response:
        chunks, size, started = [], 0, time.monotonic()
        while True:
            chunk = response.read(min(65536, 12_000_001-size))
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > 12_000_000 or time.monotonic()-started > 45:
                raise ValueError('Capture exceeds byte or time limit')
            chunks.append(chunk)


def ember(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    if payload.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            payload = stream.read(40_000_001)
    if len(payload) > 40_000_000:
        raise ValueError('Ember decoded byte limit exceeded')
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    required = {'Area', 'ISO 3 code', 'Date', 'Area type', 'Electricity source', 'Generation (TWh)'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Ember monthly schema changed')
    rows, seen, count = [], set(), 0
    for item in reader:
        count += 1
        if count > 300_000:
            raise ValueError('Ember input row limit exceeded')
        if item['Area type'] != 'Country or economy' or item['Electricity source'] != 'Total generation' or not item['Date'].startswith('2026-'):
            continue
        code, date = item['ISO 3 code'], item['Date']
        if not re.fullmatch(r'[A-Z]{3}', code) or not re.fullmatch(r'2026-\d{2}-01', date):
            raise ValueError('Invalid country/month')
        datetime.fromisoformat(date)
        if (code, date) in seen:
            raise ValueError('Duplicate Ember country month')
        seen.add((code, date))
        value = float(item['Generation (TWh)'])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Invalid total generation')
        row = base('world_ember_monthly_generation_2026', code+':'+date[:7], 'energy',
                   item['Area']+' monthly electricity generation, '+date[:7], EMBER_PAGE, stamp,
                   countryIso3=code, observedAt=date+'T00:00:00Z', properties={
                       'referenceMonth': date[:7], 'temporalPrecision': 'month',
                       'generationTWh': value, 'electricitySource': 'Total generation',
                       'geographicRole': 'country_aggregate_no_coordinate',
                       'attribution': 'Ember, monthly electricity data, CC BY 4.0; selected and normalized by Aplomb.',
                   })
        validate_row(row)
        rows.append(row)
    return rows, {'sourceRows': count, 'rejected': 0, 'coverageComplete': False,
                  'scope': 'All available 2026 country/economy Total generation months in the captured global release; other years, fuels and regional aggregates excluded.'}


def geofabrik(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [m for m in archive.infolist() if m.filename.endswith('.gpkg')]
        if len(members) != 1 or members[0].file_size > 12_000_000:
            raise ValueError('Unexpected Geofabrik archive')
        database = archive.read(members[0])
    with tempfile.TemporaryDirectory(prefix='aplomb-geofabrik-') as tmp:
        path = Path(tmp)/'source.gpkg'
        path.write_bytes(database)
        with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) as db:
            db.enable_load_extension(False)
            db.execute('PRAGMA query_only=ON')
            definition = db.execute('SELECT definition FROM gpkg_spatial_ref_sys WHERE srs_id=100000').fetchone()
            if not definition or 'CRS84' not in definition[0]:
                raise ValueError('Geofabrik coordinate reference changed')
            schema = db.execute("SELECT geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name='gis_osm_transport_free'").fetchone()
            if schema != ('POINT', 100000, 0, 0):
                raise ValueError('Unexpected transport geometry schema')
            items = db.execute('SELECT osm_id,fclass,name,geom FROM gis_osm_transport_free LIMIT 1001').fetchall()
            if not 1 <= len(items) <= 1000:
                raise ValueError('Transport row count outside bounded scope')
    rows = []
    for key, feature_class, name, geometry in items:
        # This capture uses little-endian GeoPackage point blobs, no envelopes,
        # CRS84 longitude/latitude. Reject other encodings rather than guessing.
        if not re.fullmatch(r'\d+', key) or len(geometry) != 29 or geometry[:4] != b'GP\x00\x01' or struct.unpack('<i', geometry[4:8])[0] != 100000 or geometry[8:13] != b'\x01\x01\x00\x00\x00':
            raise ValueError('Invalid GeoPackage point')
        lon, lat = struct.unpack('<dd', geometry[13:])
        row = base('world_geofabrik_monaco_transport', key, 'infrastructure', name or feature_class.replace('_', ' '), GEO_PAGE, stamp,
                   latitude=lat, longitude=lon, properties={
                       'osmId': key, 'featureClass': feature_class,
                       'geographicRole': 'source_mapped_transport_point',
                       'extractRegion': 'Monaco', 'attribution': OSM_ATTRIBUTION,
                   })
        validate_row(row)
        rows.append(row)
    return rows, {'sourceRows': len(items), 'rejected': 0, 'coverageComplete': False,
                  'scope': 'Complete transport POINT layer in this Monaco extract; not a global inventory. Extract buffer may include neighboring France; no country is inferred.'}


def collect(source: str, directory: Path, fetcher=fetch) -> dict:
    url, page = (EMBER_URL, EMBER_PAGE) if source == 'ember' else (GEO_URL, GEO_PAGE)
    payload, rights = fetcher(url), fetcher(page)
    decoded_rights = gzip.decompress(rights) if rights.startswith(b'\x1f\x8b') else rights
    if source == 'ember' and b'CC-BY-4.0' not in decoded_rights:
        raise ValueError('Ember CC BY licence not established')
    if source == 'geofabrik' and b'ODbL' not in decoded_rights:
        raise ValueError('Geofabrik ODbL licence not established')
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    rows, quality = (ember if source == 'ember' else geofabrik)(payload, stamp)
    if not rows:
        raise ValueError('No usable observations in selected source scope')
    metadata = {
        'datasetId': rows[0]['sourceId'], 'sourceIds': ['MASTER-084'] if source == 'ember' else ['SRC-150'],
        'name': 'Ember monthly country electricity generation, 2026' if source == 'ember' else 'Geofabrik Monaco transport point reference',
        'sourceUrl': page, 'retrievedAt': stamp, 'frequency': 'Manual pinned capture',
        'attribution': rows[0]['properties']['attribution'],
        'licence': 'CC BY 4.0' if source == 'ember' else 'ODbL 1.0; separate derived database offered under ODbL 1.0',
        'licenceUrl': 'https://creativecommons.org/licenses/by/4.0/' if source == 'ember' else 'https://www.openstreetmap.org/copyright',
        'limitations': [quality['scope'], 'Captured reference data do not establish real-time activity, ownership, issuer exposure or financial impact.',
                        'Original historical availability is unproven; gate at capture time.'] +
                       (['Generation months and country coverage vary; first day is a monthly display anchor, not an event date.'] if source == 'ember' else
                        ['Mapped transport points may be stale or incomplete; no routes, current services or operational status established.']),
        **quality,
    }
    return publish(directory, rows, metadata, [(url,payload),(page,rights)])


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', choices=['ember','geofabrik'], required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    manifest = collect(args.source,args.directory)
    print(json.dumps({'version': manifest['dataVersion'], 'rows': manifest['rowCount']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
