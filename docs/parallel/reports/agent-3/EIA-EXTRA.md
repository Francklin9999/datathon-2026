# EIA International Energy Statistics capture

SRC-190 and MASTER-038 are implemented for a bounded selection of EIA's
international data. `world_eia_crude_production_2024`, version
`world_eia_crude_production_2024-2026-11-15-f540406c9043afb0`, captured
2026-11-15T19:03:49Z, contains 215 annual country records for crude oil
including lease condensate production in 2024, expressed as thousand barrels
per day. The response contained 219 records and was complete for the selected
filters; four non-ISO 3166-1 country IDs were excluded (Netherlands Antilles,
former Serbia and Montenegro, U.S. Pacific Islands, and Wake Island). EIA's
missing value for former Serbia and Montenegro was not converted to zero.
The selection covers one product, activity, year and unit, not the complete
EIA catalogue. Country values are national averages; no coordinates, plant
output, issuer relationship or financial impact are inferred.

The EIA [copyright and reuse page](https://www.eia.gov/about/copyrights_reuse.php)
says U.S. government publications are public domain and permits use and
distribution of EIA data, with an acknowledgment including publication date.
The API did not supply a publication date for this selection; the passport
supplies the capture date as the first proven availability. The capture excludes
third-party website materials. Source flags remain attached to each value.
Original historical availability is unproven, so the capture is unavailable
before its retrieval; January 1 is solely an annual display anchor.

Normalized SHA-256: `f540406c9043afb094a1c5e1832def550dbbcab4a7479aa673cebbd767b9aeaa`.
API response SHA-256: `e83b2e38c24aa4705b8117a669ab2a5fcb5d8c11edd6614353e688c9322f3450`.
EIA reuse page SHA-256: `c16dcdd32bd0294eef3dbc8cdc11cd3a815502be1e938f1dfc84736358a4462c`.
Credentials are sent in an HTTP header and excluded from stored URLs and
sanitized from responses if echoed. The captured files were checked for the
configured credential.

The energy observations endpoint consumes the selection and the dataset
passport reports the source, limits and row count. Bounded in-process HTTP
verification returned 215 matching current records, one Canada result, zero
matching records as of 2026-11-14 and a 215-row passport. The existing snapshot
loader verified raw and normalized hashes and the temporal gate. Evidence:
`docs/evidence/parallel/agent-3/eia-runtime.json`. No new tests, browser check,
deployment, commit or push were made. Reconstruct with `EIA_API_KEY` set in
the environment:

```bash
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.ingest --source eia
```

The API request is bounded to one response of at most 5,000 records, 2 MB, a
55-second timeout and one retry. It fails instead of publishing a truncated
selection. The source date and annual scope are fixed by design; refreshes
produce a new content-addressed capture.
