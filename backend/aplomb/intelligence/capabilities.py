"""Conservative source capabilities and catalogue for the current application runtime.

'available' denotes a demonstrated workflow within its documented supported scope.
Sources without demonstrated access and permitted use stay aside. Current provider
uptime remains subject to the actual request; preserved evidence is a separate state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def capabilities(settings):
    from .wikidata import source_contact

    entries = []

    def add(key, name, state, requirement, *, source_ids=()):
        entries.append({'id': key, 'name': name, 'state': state, 'requirement': requirement,
                        'source_ids': list(source_ids)})

    add('gleif', 'GLEIF legal entity and issuer links', 'available',
        'Exact-pair and reference records have retained captures; the issuer graph is partial.', source_ids=('SRC-043', 'MASTER-023'))
    add('golden_copy', 'GLEIF Golden Copy delta', 'available',
        'A captured intraday delta is available; it is not the complete Golden Copy.', source_ids=('SRC-044',))
    add('nport_example', 'SEC N-PORT partial example', 'evidence',
        'One captured indexed filing and mapping; derivative exposure remains unknown.', source_ids=('SRC-040', 'MASTER-020'))
    add('openfigi', 'OpenFIGI exact identifier mappings', 'available',
        'Public API has a retained ISIN lookup; source identifiers are not recommendations.', source_ids=('SRC-058',))
    add('eu', 'ESMA registers and EBA market risk', 'available',
        'ESMA exact LEI capture and EBA 2025 market-risk dataset; coverage is limited.', source_ids=('SRC-052', 'SRC-053'))
    add('sentiment', 'Alternative.me Bitcoin sentiment', 'available',
        'Live capture retained; provider methodology is an indicator, not a prediction.', source_ids=('SRC-067',))
    add('registries', 'Canada and Ireland corporate registries', 'available',
        'Exact official corporate numbers; no listed-security identity is inferred.', source_ids=('SRC-047', 'SRC-050'))
    add('master', 'Session instrument crosswalk', 'available',
        'Limited captured listings and source assertions, not a worldwide master.')
    wikidata = bool(source_contact(settings))
    add('wikidata', 'Wikidata exact-ISIN candidates', 'available' if wikidata else 'aside',
        'Configured contact; community assertions are not verified issuer identity.' if wikidata else
        'A descriptive project contact is required before querying Wikidata.', source_ids=('SRC-057', 'MASTER-024', 'MASTER-062'))
    add('sec', 'SEC live company, filings and funds', 'aside',
        'A descriptive SEC contact and accepted network access are required; recent requests returned HTTP 403.',
        source_ids=('SRC-034', 'SRC-035', 'SRC-036', 'SRC-037', 'SRC-038', 'SRC-039', 'SRC-041', 'SRC-042'))
    add('regional', 'Japan J-Quants and Korea OpenDART', 'aside',
        'Account/API keys and confirmed permitted source use are required.', source_ids=('SRC-020',))
    coin = os.getenv('APLOMB_COINMETRICS_NONCOMMERCIAL') == '1'
    add('coinmetrics', 'Coin Metrics Community', 'available' if coin else 'aside',
        'Local noncommercial research has a demonstrated live API path with attribution.' if coin else
        'Confirm noncommercial rights and configure APLOMB_COINMETRICS_NONCOMMERCIAL=1.', source_ids=('MASTER-006',))
    dex = os.getenv('APLOMB_DEXSCREENER_RIGHTS_CONFIRMED') == 'true'
    add('dexscreener', 'DEX Screener', 'available' if dex else 'aside',
        'Exact pool workflow has a demonstrated live API path for local noncommercial research.' if dex else
        'Review permitted data storage/display and configure APLOMB_DEXSCREENER_RIGHTS_CONFIRMED=true.', source_ids=('SRC-064',))
    vision = os.getenv('APLOMB_BINANCE_VISION_NONCOMMERCIAL') == '1'
    add('binance_vision', 'Binance Vision daily history', 'available' if vision else 'aside',
        'Checksum-verified daily archive; personal noncommercial research only.' if vision else
        'Enable permitted personal noncommercial use; commercial storage/display requires separate rights.',
        source_ids=('SRC-069', 'MASTER-008'))
    add('binance_rest', 'Binance live market API', 'aside',
        'Published permission for this application’s live data storage/display has not been established.', source_ids=('SRC-068',))
    add('bitstamp', 'Bitstamp live market API', 'aside',
        'Source-specific storage/display permission is required; commercial use requires a data licence.', source_ids=('SRC-072',))
    llama = os.getenv('APLOMB_DEFILLAMA_WRITTEN_DATA_RIGHTS') == 'true'
    add('defillama', 'DefiLlama', 'aside',
        'Operator confirmed written data rights; current source availability must be verified.' if llama else
        'Written permission for copying, retention and display is required.', source_ids=('SRC-065', 'MASTER-007'))
    mempool = os.getenv('APLOMB_MEMPOOL_REUSE_CONFIRMED') == '1'
    add('mempool', 'Mempool.space hosted API', 'aside',
        'Operator confirmed hosted data reuse; current source availability must be verified.' if mempool else
        'Confirm hosted-data reuse rights and configure APLOMB_MEMPOOL_REUSE_CONFIRMED=1.', source_ids=('SRC-075',))
    add('issuers', 'iShares, Vanguard and SPDR daily holdings', 'aside',
        'Provider permission is needed for automated retrieval, storage and display.', source_ids=('SRC-054', 'SRC-055', 'SRC-056'))
    add('stooq', 'Stooq', 'aside',
        'Automated access is blocked; approved access and reuse rights must be established.', source_ids=('SRC-018',))
    add('paid', 'Paid provider feeds', 'removed',
        'Databento, Intrinio and Financial Datasets were removed under the recorded owner instruction.',
        source_ids=('SRC-011', 'SRC-015', 'SRC-017'))
    path = Path(__file__).resolve().parent / 'data' / 'source_dispositions.json'
    with path.open(encoding='utf-8') as stream:
        catalog = json.load(stream)
    return {'families': entries, 'catalogue': catalog,
            'note': 'Available means a demonstrated workflow within its stated scope; it does not guarantee current provider uptime. Evidence-only captures are not live adapters.'}
