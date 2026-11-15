# UN Comtrade annual merchandise exports sample

Capture: `trade_un_comtrade_exports-2026-11-15-422cd24c2edf021d`, retrieved 2026-11-15 17:11:18 UTC. Source rows SRC-112, SRC-206 and MASTER-077. Refresh with `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.trade_extra` from the repository root. The fixed query requests 2023 annual total merchandise exports to World for reporting country codes 76, 124, 156, 276, 356 and 710. The actual response contains BRA, CAN, CHN, DEU and ZAF; India (356) was absent and is not zero. The preview result is a bounded sample, not complete world or trade-partner coverage.

The adapter requires a consistent response count, matching reporter/year/flow/partner/commodity/customs/mode, unique records, valid finite nonnegative values and explicit source flags. It fails closed on schema mismatch or an empty publication; captures source JSON and normalized observations under content-addressed immutable snapshot directories. It retains the UN's `isReported` and `isAggregate` flags and commodity classification. Annual reference year is in properties, not an invented point-in-time observation. No source point or company link is asserted. Current capture availability is gated at retrieval, not retroactively at 2023.

- Source API: https://comtradeapi.un.org/public/v1/preview/C/A/HS?period=2023&reporterCode=76%2C124%2C156%2C276%2C356%2C710&cmdCode=TOTAL&flowCode=X&partnerCode=0
- Raw SHA-256: `5fe75bfdfbd742fc5aec7e927620b2b0ea90ef59875c300af188f56a70a76803`
- Normalized SHA-256: `422cd24c2edf021d54af4a826975c417083f43a327f75d64f0c66497475563cb`
- Loaded and hash-validated through `load_provider_snapshots`; a 2023 as-of query excluded this 2026 capture. `ruff check backend/aplomb/world/providers/trade_extra.py` passed.

## Access and reuse

The public preview API was accessed without login or a key. The provider's [policy](https://uncomtrade.org/docs/policy-on-comtrade-data-use/) and [re-dissemination guidance](https://uncomtrade.org/docs/re-dissemination-of-data/) require attribution **Source: UN Comtrade** and describe exemptions for free visualization/analytics and free extraction or streaming of up to 100,000 original records. Commercial APIs or streaming require a fee-bearing distribution arrangement regardless of database size. The rules depend on the entire database and product use, so the five-row capture alone does not establish rights for an unknown future product. Review the provider's terms before any commercial API/streaming or broader redistribution; no unrestricted licence is claimed. Filtered records remain original UN data, not substantially transformed outputs. The guidance also cautions against excessive automated use; this refresh issues one query, retries only transient failures, and enforces timeout and size limits.

## Registration and consumption handoff

The current snapshot loader discovers the new directory automatically. The existing globe service requires coordinates and therefore does not display these country-only observations; the current passport whitelist also lacks this dataset. Add a country-level trade consumer and a passport entry under `trade_un_comtrade_exports`, retain the source's rights conditions, year and missing-country disclosure, and make source attribution visible. Do not add synthetic point markers, link exporters to issuers, or represent this as port activity. A feature claim must wait for this integration and applicable distribution terms. The other assigned trade sources remain independent: WITS and UNCTADstat are not implemented here; PortWatch remains blocked pending its reuse terms.

## Subsequent integration

The five-row UN Comtrade capture is registered in the dataset contract, catalog, passport and trade observations API. Reporter country and reference year remain explicit without synthetic coordinates; source attribution and conditional reuse are displayed. The registration handoff above describes the pre-integration state. WITS and UNCTAD were subsequently integrated as separate bounded captures; see `TRADE-FOLLOWON.md`.
