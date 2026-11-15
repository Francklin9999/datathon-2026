"""EIA international annual crude production capture; requires EIA_API_KEY.

A single country, product, activity, unit and year selection is fetched. Runtime
consumes only the immutable snapshot; the credential is never stored in it.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .public import base
from .snapshot import publish, validate_row

URL = 'https://api.eia.gov/v2/international/data/'
PAGE = 'https://www.eia.gov/international/data/world'
RIGHTS = 'https://www.eia.gov/about/copyrights_reuse.php'
PARAMS = [('frequency', 'annual'), ('data[0]', 'value'), ('facets[productId][]', '57'),
          ('facets[activityId][]', '1'), ('facets[countryRegionTypeId][]', 'c'),
          ('facets[unit][]', 'TBPD'), ('start', '2024'), ('end', '2024'), ('length', '5000')]
# ISO 3166-1 alpha-3 codes, fixed to avoid interpreting EIA-only geography IDs as ISO.
ISO3 = frozenset("ABW AFG AGO AIA ALA ALB AND ARE ARG ARM ASM ATA ATF ATG AUS AUT AZE BDI BEL BEN BES BFA BGD BGR BHR BHS BIH BLM BLR BLZ BMU BOL BRA BRB BRN BTN BVT BWA CAF CAN CCK CHE CHL CHN CIV CMR COD COG COK COL COM CPV CRI CUB CUW CXR CYM CYP CZE DEU DJI DMA DNK DOM DZA ECU EGY ERI ESH ESP EST ETH FIN FJI FLK FRA FRO FSM GAB GBR GEO GGY GHA GIB GIN GLP GMB GNB GNQ GRC GRD GRL GTM GUF GUM GUY HKG HMD HND HRV HTI HUN IDN IMN IND IOT IRL IRN IRQ ISL ISR ITA JAM JEY JOR JPN KAZ KEN KGZ KHM KIR KNA KOR KWT LAO LBN LBR LBY LCA LIE LKA LSO LTU LUX LVA MAC MAF MAR MCO MDA MDG MDV MEX MHL MKD MLI MLT MMR MNE MNG MNP MOZ MRT MSR MTQ MUS MWI MYS MYT NAM NCL NER NFK NGA NIC NIU NLD NOR NPL NRU NZL OMN PAK PAN PCN PER PHL PLW PNG POL PRI PRK PRT PRY PSE PYF QAT REU ROU RUS RWA SAU SDN SEN SGP SGS SHN SJM SLB SLE SLV SMR SOM SPM SRB SSD STP SUR SVK SVN SWE SWZ SXM SYC SYR TCA TCD TGO THA TJK TKL TKM TLS TON TTO TUN TUR TUV TWN TZA UGA UKR UMI URY USA UZB VAT VCT VEN VGB VIR VNM VUT WLF WSM YEM ZAF ZMB ZWE".split())


def attribution(stamp: str) -> str:
    return ('Source: U.S. Energy Information Administration, International Energy Statistics '
            f'(publication date not supplied; captured {stamp[:10]}); selected and normalized by Aplomb.')


def fetch(url: str, key: str | None = None, cap: int = 2_000_000) -> bytes:
    if url not in {URL + '?' + urllib.parse.urlencode(PARAMS), RIGHTS}:
        raise ValueError('Unexpected EIA URL')
    headers = {'User-Agent': 'AplombDatathon/1.0 bounded capture'}
    if key:
        headers['X-Api-Key'] = key
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=55) as response:
                body = response.read(cap + 1)
                if len(body) > cap:
                    raise ValueError('EIA response exceeds byte limit')
                return body
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 1:
                # Never surface a URL/header or credential in logs.
                raise ValueError('EIA request failed after bounded retry') from exc
            time.sleep(1)
    raise ValueError('EIA request failed')


def parse(payload: bytes, stamp: str) -> tuple[list[dict], dict]:
    result = json.loads(payload)
    response = result['response']
    data = response['data']
    total = int(response['total'])
    if response.get('frequency') != 'annual' or response.get('dateFormat') != 'YYYY' or not isinstance(data, list):
        raise ValueError('EIA response schema changed')
    if total != len(data) or total > 5000:
        raise ValueError('EIA selection incomplete; pagination required')
    rows, seen, excluded = [], set(), 0
    for item in data:
        if (item.get('period') != '2024' or item.get('productId') != '57'
                or item.get('activityId') != '1' or item.get('countryRegionTypeId') != 'c'
                or item.get('unit') != 'TBPD' or item.get('unitName') != 'thousand barrels per day'):
            raise ValueError('Unexpected EIA selection or unit')
        code, name = item.get('countryRegionId'), item.get('countryRegionName')
        if not isinstance(code, str) or code not in ISO3 or not isinstance(name, str) or not name:
            excluded += 1
            continue
        value = item.get('value')
        if value in (None, '--', ''):
            excluded += 1
            continue
        value = float(value)
        if not math.isfinite(value) or value < 0 or code in seen:
            raise ValueError('Invalid or duplicate EIA country value')
        seen.add(code)
        row = base('world_eia_crude_production_2024', code + ':2024', 'energy',
                   name + ' crude oil production, 2024', PAGE, stamp,
                   countryIso3=code, observedAt='2024-01-01T00:00:00Z', properties={
                       'referenceYear': '2024', 'temporalPrecision': 'year',
                       'productionThousandBarrelsPerDay': value,
                       'product': 'Crude oil including lease condensate',
                       'dataFlagId': item.get('dataFlagId'),
                       'dataFlagDescription': item.get('dataFlagDescription'),
                       'geographicRole': 'country_aggregate_no_coordinate', 'attribution': attribution(stamp),
                   })
        validate_row(row)
        rows.append(row)
    return rows, {'sourceRows': total, 'rejected': excluded, 'coverageComplete': False,
                  'scope': '2024 annual country crude oil including lease condensate production, thousand barrels per day; one product, year and unit only. Missing values and non-ISO 3166-1 codes excluded.'}


def collect(directory: Path) -> dict:
    key = os.environ.get('EIA_API_KEY', '').strip()
    if not key:
        raise ValueError('EIA_API_KEY is required')
    url = URL + '?' + urllib.parse.urlencode(PARAMS)
    payload = fetch(url, key)
    rights = fetch(RIGHTS)
    if b'public domain' not in rights.lower() or b'distribute' not in rights.lower():
        raise ValueError('EIA reuse terms unavailable')
    # API response request metadata may echo submitted credentials. Remove before storage.
    payload = payload.replace(key.encode(), b'[REDACTED]')
    if key.encode() in rights:
        raise ValueError('Unexpected credential in terms response')
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    rows, quality = parse(payload, stamp)
    metadata = {'datasetId': 'world_eia_crude_production_2024', 'sourceIds': ['SRC-190', 'MASTER-038'],
                'name': 'EIA 2024 annual country crude oil production', 'sourceUrl': PAGE,
                'retrievedAt': stamp, 'frequency': 'Annual; manually captured selected 2024 revision',
                'attribution': attribution(stamp), 'licence': 'EIA U.S. government data public domain; attribution requested',
                'licenceUrl': RIGHTS, **quality,
                'limitations': [quality['scope'], 'Reported national average rate is not current output, plant activity, or issuer exposure.',
                                'January 1 is an annual display anchor, not an observation instant.',
                                'Original historical availability is unproven; gate at capture time.',
                                'Source API response is credential-sanitized if needed; the request URL contains no key.']}
    return publish(directory, rows, metadata, [(url, payload), (RIGHTS, rights)])
