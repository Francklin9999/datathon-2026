# SDMX supplementary capture and access review

SRC-090 World Bank SDMX is integrated as a bounded three-country, one-indicator capture. SRC-091 / MASTER-033 IMF SDMX remains rights blocked. SRC-092 / MASTER-034 OECD SDMX remains access and rights blocked. No paid service, account, login, deployment, commit or new test was used.

## World Bank SDMX: integrated selected slice

- Adapter: `backend/aplomb/world/providers/sdmx_extra.py`. Refresh command: `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.sdmx_extra`.
- Dataset: `world_bank_sdmx_gdp_2024`. Immutable runtime version: `world_bank_sdmx_gdp_2024-2026-11-15-ee998b9bcb10ebf6`.
- Capture timestamp: 2026-11-15T18:04:03Z. Normalized SHA-256: `ee998b9bcb10ebf66f23b6d95fe5aac9b1b2f4d20a4ff389f682a63c288f1f44`.
- Runtime directory: `backend/aplomb/world/bundle/providers/world_bank_sdmx_gdp_2024-2026-11-15-ee998b9bcb10ebf6/`. Five immutable raw captures retain current terms, indicator metadata and the three SDMX XML responses.
- Source endpoint pattern from the official [SDMX documentation](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886701-sdmx-api-queries): `https://api.worldbank.org/v2/sdmx/rest/data/WDI/A.NY_GDP_MKTP_CD.CAN/?startperiod=2024&endPeriod=2024`, replacing CAN with JPN or BRA. All three returned anonymous HTTP 200.
- [Indicator-specific metadata](https://api.worldbank.org/v2/sources/2/series/NY.GDP.MKTP.CD/metadata?format=json) explicitly reports `License_Type=CC BY-4.0`, `Unitofmeasure=current US$` and annual periodicity. Its underlying sources are national statistical organizations/central banks, OECD national accounts files and World Bank staff estimates. This explicit indicator licence supports this selection despite third-party inputs.
- Current [dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets) explicitly permit copying/sharing and apply CC BY 4.0 unless otherwise labeled. They retain mandatory additional dispute-resolution terms, third-party exceptions, no endorsement and no association. The collector verifies the licence and unit in series metadata before publication, preserves the full terms and credits underlying sources. The older legal URL redirected to generic website terms; that generic page was not used as the dataset licence.
- Current datacatalog web pages returned 403, but the accessible official indicator metadata and complete current official dataset terms establish the rights used here. Access to datacatalog is not claimed.

| Country | Reference year | GDP, current US dollars |
|---|---|---:|
| Canada | 2024 | 2,270,076,189,683.46 |
| Japan | 2024 | 4,190,008,188,358.57 |
| Brazil | 2024 | 2,185,821,610,689.31 |

These are national annual nominal GDP levels in current US dollars, not real GDP growth, purchasing power parity, forecasts or live market signals. Methods differ between countries and data may be revised. No coordinates or issuer relationships are fabricated. January 1 is a reference-year display anchor. SDMX Prepared/Extracted are response-generation timestamps, not original publication times. Proven availability is capture time; historical replay before capture is excluded.

The collector accepts exactly one WDI generic SDMX 2.1 series and one 2024 observation per country. It validates sender, data structure, dimensions, year, multiplier and finite positive value. It rejects XML entity declarations, redirects and unexpected URLs, bounds payloads to 300 KB, uses 20-second timeouts/read deadlines and two attempts for transient failures, and spaces requests. Missing observations fail publication rather than becoming zeros. This is intentionally incomplete provider coverage.

Existing World Explorer provider loading consumes the new immutable directory automatically. `/v1/world/observations?mode=macro&q=World%20Bank%20SDMX` returned three real rows through the existing FastAPI route, and `country=JPN` returned one. Explicit `asOf=2024-12-31` returned zero. Rows retain source links, country identity, annual reference precision, source attribution and manifest limitations; map locations are null. Existing `provider_passports()` produces an `in_use` passport with three checksum-verified records. Contract/catalog and datastore passport descriptor registration remains root-owned.

Verification evidence: `docs/evidence/parallel/agent-3/sdmx-extra/capture-validation.json` and `runtime.json`. All raw/normalized hashes passed the existing immutable loader. Direct validation rejected wrong country, year, unit scaling and missing observations. HTTP validation used a temporary in-memory app with the actual WorldService and actual bundle; production flags were not changed. No new automated tests were written. No separate browser scenario was run for this supplemental slice; it uses the existing macro observation feed.

## IMF SDMX: rights blocked, evidence only

The anonymous [IMF WEO SDMX endpoint](https://api.imf.org/external/sdmx/2.1/data/IMF.RES,WEO/USA.NGDP_RPCH.A?startPeriod=2024&endPeriod=2024) returned HTTP 200 and a structure-specific SDMX 2.1 observation: United States 2024 real GDP percent change `2.951816`. Dataset structure version is WEO 9.0.0, source publication/update metadata is 2026-10-13, and latest actual year is 2025.

The payload explicitly states `LICENSE="© International Monetary Fund Copyright. All Rights Reserved. https://www.imf.org/external/terms.htm"`. Its `PUBLIC_OPEN` access classification is not a redistribution licence. Both that exact terms URL and the newer copyright/terms page returned 403. The current API resource page also returned 403. This audit therefore does not establish explicitly reusable terms for the intended product.

The genuine XML is retained only as bounded research evidence in `docs/evidence/parallel/agent-3/sdmx-extra/imf-data.bin`. There is no enabled IMF dataset, runtime capture, passport or reusable feature claim. Before enabling SRC-091 / MASTER-033, verify complete current terms, commercial/redistribution permissions and WEO-specific exceptions, then build and validate a bounded adapter.

## OECD SDMX: access and rights blocked

The current OECD terms page, its legacy terms URL and an official public SDMX dataflow request returned 403. An initial financial-market query returned 403; a more explicit version/series probe returned 404, establishing neither a valid observation nor licensing. No workaround for access controls was attempted.

There is no enabled OECD capture, dataset, passport or feature claim. Before enabling SRC-092 / MASTER-034, obtain complete current OECD data/API terms, inspect dataset-specific rights and identify a valid anonymously accessible SDMX series. Provider documentation links alone do not establish reusable data.

All requests, statuses, URLs and retained response bodies are in `docs/evidence/parallel/agent-3/sdmx-extra/{access,followup-access,metadata-access}.json` and sibling `.bin` files. Source catalog/status/handoff/contracts shared edits are deferred to root as instructed.
