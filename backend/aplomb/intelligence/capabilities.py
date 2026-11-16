"""Conservative source capabilities and catalogue for the current application runtime.

'available' denotes a demonstrated workflow within its documented supported scope.
Sources without demonstrated access and permitted use stay aside, and sources the owner
excluded are 'removed' (their historical captures are kept for audit only). No other state
is emitted. Current provider uptime remains subject to the actual request.
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
    add('nport_example', 'SEC N-PORT historical example', 'removed',
        'SEC excluded by owner; historical capture retained for audit only.', source_ids=('SRC-040', 'MASTER-020'))
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
    add('sec', 'SEC live company, filings and funds', 'removed',
        'Removed by owner after HTTP403; no SEC credentials requested.',
        source_ids=('SRC-034', 'SRC-035', 'SRC-036', 'SRC-037', 'SRC-038', 'SRC-039', 'SRC-041', 'SRC-042'))
    # Same rule as the /intelligence/regional adapter, so the panel shows exactly when its requests work.
    from aplomb.research.regional import configured_key
    japan = configured_key('JQUANTS') is not None
    add('regional', 'Japan J-Quants', 'available' if japan else 'aside',
        'Daily prices, listing and financial summary captures verified; dates depend on account entitlement. Complete bounded pagination.', source_ids=('SRC-020',))
    dart = configured_key('OPENDART') is not None
    add('opendart', 'Korea OpenDART', 'available' if dart else 'aside',
        'Verified corporate filings, complete paginated interval, financial statements and ownership; account key required.')
    tiingo = bool(settings.tiingo_token) or bool(os.getenv('APLOMB_TIINGO_TOKEN'))
    add('tiingo', 'Tiingo US equity daily history', 'available' if tiingo else 'aside',
        'Actual metadata/history verified with the supplied token. Internal use only; no public redistribution entitlement asserted.', source_ids=('SRC-008',))
    for provider, label, key, ids in (
        ('alpha_vantage', 'Alpha Vantage quote', 'APLOMB_ALPHA_VANTAGE_KEY', ('SRC-001','MASTER-002')),
        ('twelve_data', 'Twelve Data exact-MIC daily history', 'APLOMB_TWELVEDATA_KEY', ('SRC-003','MASTER-003')),
        ('finnhub', 'Finnhub company profile', 'APLOMB_FINNHUB_KEY', ('SRC-002',)),
    ):
        active = bool(os.getenv(key)) and os.getenv(key.removesuffix('_KEY')+'_RIGHTS_CONFIRMED') == 'true'
        add(provider, label, 'available' if active else 'aside',
            'Live workflow validated; requires the configured account key and its permitted data use.', source_ids=ids)

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
    from aplomb.research import chain_accounts, stock_accounts
    source_ids = {'fmp':('SRC-004',),'eodhd':('SRC-005',),'massive':('SRC-006',),
                  'marketstack':('SRC-009',),'coinmarketcap':('SRC-060',),
                  'blockscout':('SRC-074',),'alchemy':('SRC-080',),'goldrush':('SRC-083',)}
    for item in stock_accounts.connection_status()+chain_accounts.connection_status():
        configured = item['credential_present'] and item['rights_confirmed']
        add(item['id'], item['id'], 'available' if configured else 'aside',
            item['supported_operation'] + '; source/account limitations remain attached to each response.',
            source_ids=source_ids[item['id']])
    add('fred', 'FRED / ALFRED', 'aside',
        'Supplied key stored. This app’s AI/capture workflow still requires compatible provider permission; no data fetched.',
        source_ids=('SRC-086','SRC-087','MASTER-028','MASTER-029'))
    path = Path(__file__).resolve().parent / 'data' / 'source_dispositions.json'
    with path.open(encoding='utf-8') as stream:
        catalog = json.load(stream)
    for entry in entries:
        if entry['source_ids'] and all(any(row['id']==source_id and row['status'].startswith('removed') for row in catalog['rows']) for source_id in entry['source_ids']):
            entry['state']='removed'
        elif entry['source_ids'] and any(any(row['id']==source_id and row['status'].startswith('aside') for row in catalog['rows']) for source_id in entry['source_ids']):
            entry['state']='aside'
    return {'families': entries, 'catalogue': catalog,
            'note': 'Available means a demonstrated workflow within its stated scope; it does not guarantee current provider uptime. Evidence-only captures are not live adapters.'}
