# Statistics Canada monthly consumer price index capture

**Status: integrated in the application as a bounded capture.** This implements one narrow WDS series from SRC-096, not the entire service. The evidence snapshot was copied without modification into `backend/aplomb/world/bundle/providers/`, registered in the generated dataset contract and world passports, and verified through the datasets and observations service. Observation details display the adapted attribution and label the reference month without asserting an exact measurement time.

## Access and rights

- The [Statistics Canada WDS](https://www.statcan.gc.ca/en/developers/wds/user-guide) returned the three documented endpoints without login, key or payment on 2026-11-15. `getDataFromVectorsAndLatestNPeriods` was sent vector `41690973` and `latestN: 12`; `getSeriesInfoFromVector` verified Canada and all-items; `getCodeSets` verified the index unit. The exact request bodies and raw payloads are in the manifest.
- The [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence) grants royalty-free reproduction, distribution, sale and adaptation subject to its conditions. It requires accurate reproduction, no implied endorsement and specific source notices, among other conditions. For raw data: `Source: Statistics Canada, Consumer Price Index, monthly, not seasonally adjusted, 2025-10 to 2026-09. Reproduced and distributed on an "as is" basis with the permission of Statistics Canada.` For the normalized observations, each row provides the required adapted notice with the applicable reference month. Any downstream presentation must actually display the applicable notice; retaining it only in a hidden property is insufficient.
- OECD's SDMX endpoint also responded without credentials for a bounded unemployment query, but the OECD terms page returned 403 during this audit. No OECD distribution claim or capture is made here.

## Capture and interpretation

- Code: `backend/aplomb/world/providers/audit_extra.py`. Run `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.audit_extra --directory <staging-path>`.
- Evidence: `docs/evidence/parallel/agent-3/audit-extra/providers/world_statcan_cpi-2026-11-15-1890df13ca8d7480/`.
- Captured at 2026-11-15T17:16:10Z; 12 observations for October 2025 through September 2026; normalized SHA-256 `1890df13ca8d7480d55f35a267a10800d7430596029de3d6874cd432b55064fa`. All three raw response hashes are recorded in the manifest.
- [Table 18-10-0004-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401) measures the monthly all-items consumer price index for Canada, not seasonally adjusted, indexed to 2002=100. The index level is not an inflation rate. This is a national reporting area and has no source-supplied point coordinates. The first day of the month is a display anchor, not an exact measurement time. Values can be revised; publication availability for individual historical versions has not been established, so the snapshot is gated at retrieval time.
- Verification: immutable raw and normalized hashes verified through `load_provider_snapshots`, which returned 12 rows after capture and zero at a pre-capture `as_of`. Altered unit metadata was rejected. No tests were added, per assignment.

## Integration limits

`world_statcan_cpi` is registered across the dataset contract, catalog and passport. The national country dimension is preserved without a map point; the monthly period and capture-time availability gate are explicit. `audit_extra.collect` is available through manual `providers.ingest --source statcan_cpi`. The implementation does not claim full WDS coverage or a refresh schedule.
