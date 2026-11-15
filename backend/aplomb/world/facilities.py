"""ECCC annual reported emissions; no fuzzy security matching or ESG scoring."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.parse import urlencode

from .geo import in_bbox

PATH = '/substances/monitor/greenhouse-gas-reporting-program-ghgrp-facility-greenhouse-gas-ghg-data/PDGES-GHGRP-GHGEmissionsGES-2004-Present.csv'
SOURCE = 'https://data-donnees.az.ec.gc.ca/api/file?' + urlencode({'path': PATH})
TERMS = 'https://open.canada.ca/en/open-government-licence-canada'
DIRECTORY = Path(__file__).resolve().parent / 'bundle'
ID = "GHGRP ID No. / No d'identification du PDGES"
YEAR = 'Reference Year / Année de référence'
NAME = "Facility Name / Nom de l'installation"
OPERATOR = 'Reporting Company Legal Name / Dénomination sociale de la société déclarante'
TOTAL = 'Total Emissions (tonnes CO2e) / Émissions totales (tonnes éq. CO2) - excl. CO2bio'
COLUMNS = (ID, YEAR, NAME, OPERATOR, 'Latitude', 'Longitude', TOTAL)


def project_source(payload: bytes) -> bytes:
    """Retain only required facility fields; public contact/personal fields are not stored."""
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if not set(COLUMNS) <= set(reader.fieldnames or []):
        raise ValueError('ECCC emissions source schema changed')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, COLUMNS, lineterminator='\n')
    writer.writeheader()
    for row in reader:
        writer.writerow({key: row[key] for key in COLUMNS})
    return output.getvalue().encode()


def normalize(payload: bytes, captured_at: str, *, original_sha256: str | None = None):
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    if not rows or not set(COLUMNS) <= rows[0].keys():
        raise ValueError('No valid ECCC emissions rows')
    try:
        latest = max(int(row[YEAR]) for row in rows)
    except (TypeError, ValueError) as exc:
        raise ValueError('Invalid emissions reference year') from exc
    if not 2004 <= latest < int(captured_at[:4]):
        raise ValueError('Emissions reference year must be completed')
    out, rejected, seen = [], 0, set()
    for row in rows:
        if int(row[YEAR]) != latest:
            continue
        try:
            key, name, operator = row[ID].strip(), row[NAME].strip(), row[OPERATOR].strip()
            lat, lon, total = (float(row[k]) for k in ('Latitude', 'Longitude', TOTAL))
            if not key or not name or not operator or key in seen:
                raise ValueError('Invalid facility identity')
            if not all(math.isfinite(v) for v in (lat, lon, total)) or not -90 <= lat <= 90 or not -180 <= lon <= 180 or total < 0:
                raise ValueError('Invalid facility observation')
            seen.add(key)
            out.append({'facilityId': 'eccc_' + key, 'name': name, 'operator': operator, 'ticker': None,
                        'matchConfidence': 'none', 'lat': lat, 'lon': lon, 'countryIso3': 'CAN',
                        'reportingYear': latest, 'emissionsTco2e': total, 'registry': 'eccc_ghgrp',
                        'sourceUrl': SOURCE})
        except (TypeError, ValueError):
            rejected += 1
    if not out:
        raise ValueError('No geolocated ECCC observations')
    out.sort(key=lambda r: (-r['emissionsTco2e'], r['facilityId']))
    # Version identifies projected source bytes plus capture; dataVersion is added before final hash.
    version = 'snap-' + captured_at[:10].replace('-', '') + '-eccc-' + hashlib.sha256(payload).hexdigest()[:10]
    for row in out:
        row['dataVersion'] = version
    content = json.dumps(out, ensure_ascii=False, sort_keys=True, indent=1) + '\n'
    meta = {'datasetId': 'emissions_facilities', 'dataVersion': version, 'sha256': hashlib.sha256(content.encode()).hexdigest(),
            'projectedSourceSha256': hashlib.sha256(payload).hexdigest(), 'originalSourceSha256': original_sha256,
            'sourceUrl': SOURCE, 'licence': 'Open Government Licence – Canada', 'licenceUrl': TERMS,
            'capturedAt': captured_at, 'publicationDate': None, 'reportingYear': latest,
            'rowCount': len(out), 'rejected': rejected, 'retainedSourceColumns': list(COLUMNS),
            'limitations': ['Annual facility-reported emissions; figures may be revised. CO2 from biomass combustion excluded from total.',
                            'Canada reporting-program coverage only; not all global facilities or a comprehensive ESG score.',
                            'Reporting-company names do not establish operator/owner status, listed-security identity, parent ownership, controversy or financial impact.',
                            'Original publication/vintage unknown; current captured reference excluded from historical reconstruction.',
                            'Public-contact/personal fields are excluded from retained source projection.']}
    return out, meta


def load_facilities(directory: Path = DIRECTORY):
    path, meta_path = directory / 'facilities.json', directory / 'facilities_manifest.json'
    if not path.exists() and not meta_path.exists():
        return [], None
    content = path.read_bytes().replace(b'\r\n', b'\n')
    meta, rows = json.loads(meta_path.read_text()), json.loads(content)
    if hashlib.sha256(content).hexdigest() != meta['sha256'] or len(rows) != meta['rowCount']:
        raise ValueError('Facility snapshot integrity failure')
    return rows, meta


def filter_facilities(rows, query):
    countries = set(query.get('country') or [])
    bbox = tuple(float(v) for v in query['bbox'].split(',')) if query.get('bbox') else None
    needle = query.get('q', '').strip().casefold()
    return [r for r in rows if (not countries or r['countryIso3'] in countries)
            and (not query.get('ticker') or r['ticker'] == query['ticker'])
            and r['emissionsTco2e'] >= query.get('minEmissions', 0)
            and (not needle or needle in (r['name'] + ' ' + r['operator']).casefold())
            and (bbox is None or in_bbox(r['lat'], r['lon'], bbox))]
