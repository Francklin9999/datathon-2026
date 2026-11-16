"""Bounded access to captured, attributed rate and futures-position context."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from .cftc_cot import read_capture as read_cot
from .cftc_swaps import read_capture as read_swaps
from .errors import IngestionError
from .nyfed_sofr import read_capture as read_sofr
from .treasury_inputs import read_debt, read_par

router = APIRouter()
# Capture folders read by this route. infra/scripts/package-backend.sh copies exactly these
# into the Lambda artifact (tests/unit/datastore/test_financial_inputs_api.py checks it).
CAPTURE_FOLDERS = ('risk-nyfed', 'risk-cftc', 'risk-treasury')


def resolve_inputs(module_file: str | Path = __file__) -> Path:
    """Locate data/inputs in the repo layout or the packaged Lambda layout.

    Repo: <repo>/backend/aplomb/datastore/<module> -> <repo>/data/inputs.
    Lambda artifact: /var/task/aplomb/datastore/<module> -> /var/task/data/inputs.
    When neither exists the repo path is returned, so every capture reports
    capture_unavailable instead of raising.
    """
    here = Path(module_file).resolve()
    candidates = [here.parents[3] / 'data' / 'inputs', here.parents[2] / 'data' / 'inputs']
    return next((path for path in candidates if path.is_dir()), candidates[0])


INPUTS = resolve_inputs()


def load(folder: str, stem: str, suffix: str, parser):
    path = INPUTS / folder
    return parser((path / (stem + suffix)).read_bytes(),
                  json.loads((path / (stem + '.metadata.json')).read_text()))


@router.get('/v1/risk/source-inputs')
def financial_source_inputs(as_of: date | None = Query(default=None, alias='asOf')) -> dict:
    """Return only observations known by the earlier of requested day-end and now."""
    now = datetime.now(timezone.utc)
    cutoff = as_of or now.date()
    known = min(now, datetime.combine(cutoff, time.max, timezone.utc))
    known_at = known.strftime('%Y-%m-%dT%H:%M:%SZ')
    result = {'asOf': cutoff.isoformat(), 'knownAt': known_at, 'sources': []}
    specifications = [
        ('sofr', 'risk-nyfed', 'sofr-202610', '.json', read_sofr),
        ('cftc-cot', 'risk-cftc', 'legacy-futures-202611', '.json', read_cot),
        ('cftc-swaps', 'risk-cftc', 'swaps-irs-202610', '.html', read_swaps),
        ('treasury-par', 'risk-treasury', 'par-202610', '.xml', read_par),
        ('treasury-debt', 'risk-treasury', 'debt-202610', '.json', read_debt),
    ]
    for name, folder, stem, suffix, parser in specifications:
        try:
            capture = load(folder, stem, suffix, parser)
            common = {'id': name, 'sourceUrl': capture.source_url,
                      'retrievedAt': capture.retrieved_at, 'sha256': capture.sha256,
                      'rights': ('Public access does not establish redistribution rights; '
                                 'provider terms and intended use require review.')}
            if name == 'sofr':
                row = capture.latest(known_at, cutoff.isoformat())
                details = ({'effectiveDate': row.effective_date, 'value': row.percent_rate,
                            'unit': 'percent', 'revisionIndicator': row.revision_indicator}
                           if row else None)
                common.update({'label': 'NY Fed SOFR', 'observation': details,
                               'limitation': 'Overnight secured funding rate; not a yield curve or a portfolio impact.'})
            elif name == 'cftc-cot':
                row = capture.latest('001602', known_at, cutoff.isoformat())
                details = ({'observationDate': row.observation_date, 'contractCode': row.contract_code,
                            'market': row.market, 'openInterest': row.open_interest,
                            'noncommercialLong': row.noncommercial_long,
                            'noncommercialShort': row.noncommercial_short,
                            'netNoncommercial': row.net_noncommercial_contracts, 'unit': 'contracts'}
                           if row else None)
                common.update({'label': 'CFTC futures-only positioning: wheat example', 'observation': details,
                               'limitation': 'Example contract; not linked to portfolio holdings or an options chain.'})
            else:
                details = capture.latest(known_at, cutoff.isoformat())
                if name == 'treasury-par':
                    common.update({'label': 'US Treasury par yield curve', 'observation': details,
                                   'limitation': 'Indicative par yields, not zero-coupon rates or a portfolio impact.'})
                elif name == 'treasury-debt':
                    common.update({'label': 'US Treasury debt to the penny', 'observation': details,
                                   'limitation': 'Nominal USD outstanding debt; not a forecast or portfolio impact.'})
                else:
                    common.update({'label': 'CFTC interest-rate swaps gross notional', 'observation': details,
                                   'limitation': 'Weekly aggregate in millions USD, not transaction prices or portfolio exposure.'})
            common['status'] = 'available' if details is not None else 'not_available_as_of'
            result['sources'].append(common)
        except (OSError, ValueError, KeyError, IngestionError):
            result['sources'].append({'id': name, 'status': 'capture_unavailable',
                                      'observation': None,
                                      'limitation': 'Capture missing or failed validation.'})
    result['sources'].append({'id': 'fama-french', 'status': 'capture_unavailable',
                              'label': 'Fama–French US daily factors', 'observation': None,
                              'sourceUrl': 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html',
                              'limitation': 'No verified factor capture is installed.'})
    return result
