# Eurostat annual greenhouse gas emissions capture

**Status: captured in the evidence directory, not enabled for the application.** Dataset-specific reuse terms remain unresolved. This is one bounded slice of SRC-095 (Eurostat REST), not a complete Eurostat integration.

## Access and rights

- On 2026-11-15, the public Eurostat Statistics API returned HTTP 200 without login or payment for dataset `sdg_13_10`, filtered to annual `TOTX4_MEMO`, `T_HAB`, DE/ES/FR/IT/PL/SE and years from 2018. Request URL is in the manifest. Eurostat documentation: <https://ec.europa.eu/eurostat/web/main/data/web-services>.
- The dataset's own [metadata](https://ec.europa.eu/eurostat/cache/metadata/en/sdg_13_10_esmsip2.htm) identifies the EEA as source and says "Eurostat Copyright/Licence Policy is applicable". Its specific policy link redirected to a general statistics page when checked; the dataset-specific conditions were therefore **not verified**.
- The [European Commission legal notice](https://commission.europa.eu/legal-notice_en#copyright-notice) says EU-owned website content is CC BY 4.0 unless otherwise indicated, requiring credit and changes to be indicated, and warns that other rightsholders may apply. The [EEA legal notice](https://www.eea.europa.eu/en/about/contact-us/legal-notice) permits reuse of EEA materials with source attribution, subject to possible differing conditions. These general notices are helpful evidence but do not settle the specific Eurostat policy or potential exceptions. Resolve that before moving the capture to the runtime provider directory or distributing it. The metadata's licence field records attribution requirements; it is not proof of unconditional reuse rights.

## Capture and interpretation

- Code: `backend/aplomb/world/providers/macro_extra.py`. Explicit destination required: `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.macro_extra --directory <staging-path>`.
- Evidence snapshot: `docs/evidence/parallel/agent-3/macro-extra/providers/world_eurostat_ghg-2026-11-15-cd9c9b2adca12554/`.
- Captured 2026-11-15T17:11:19Z; source reports its data update as 2026-04-22T23:00:00+02:00. 42 records, 2018–2024 for six countries. Raw SHA-256 `f5f919f720ffeb08c3d52b8d53ab4e383e119babf1561a95086a24878b1db722`; normalized SHA-256 `cd9c9b2adca12554a8c3ae1747f5df0b1c0bab98b88373910981fe81dc5a3fe4`.
- Dataset definition: annual national greenhouse gas emissions in tonnes of CO₂ equivalent per capita, excluding land use, land-use change and forestry (LULUCF) and memo items. International aviation and maritime transport are excluded per Eurostat metadata. Values can be revised. It is not facility-level data, an ESG score, issuer exposure, a financial forecast or a real-time signal.
- No coordinates are supplied or invented. Country code is Eurostat's reporting geography mapped explicitly to ISO3. `observedAt` uses January 1 solely as a display anchor for the reference year; it is not a measurement instant. The source update timestamp is a dataset timestamp, not a confirmed publication date for each observation. `availableAt` and `retrievedAt` are the capture time, not the reference year.
- Quality verification: immutable raw and normalized hashes checked by `load_provider_snapshots`; pre-capture `as_of` returned zero records. Malformed dataset identity and unexpected unit were rejected. Six country codes, year boundaries and all 42 rows checked. No new automated tests added, per assignment.

## Integration requirements

After dataset-specific reuse authorization is established, register `world_eurostat_ghg` in `DatasetId`, catalog mirrors and datastore passport descriptors, add its metadata/limitations to provider and world passports, and copy the immutable evidence version into `backend/aplomb/world/bundle/providers/`. Register `macro_extra.collect` as an optional bounded manual refresh path if desired; the existing shared ingest was intentionally untouched. Make sure source failures stay isolated.

The current observation service uses January 1 as a timestamp, emits generic limitations and discards country identity for rows without coordinates. Add an annual-period description and the dataset limitations to the source view; preserve country as a non-point dimension and enable country filters for national observations without generating marker coordinates. Add the source IDs and state to `SOURCES.csv` only after verifying this path, full passport consistency, licensing and feature consumption. The capture does not cover every Eurostat indicator or country.
