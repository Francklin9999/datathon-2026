# OpenFlights and remaining energy/transport review

This batch implements SRC-217 through a bounded immutable OpenFlights capture.
Paid sources are excluded and login/account/key sources remain deferred by user instruction.
No new test files, deployment, commit, push or active manifest changes were made.

## Captured and consumed

Dataset `world_openflights_airport_reference`, version
`world_openflights_airport_reference-2026-11-15-7198f95df5aefbb6`, captured
2026-11-15T17:45:32Z, contains 678 IATA-coded static airport references:
Australia 282, France 124, United Kingdom 108, Japan 94, South Africa 59,
United Arab Emirates 11. The source file contains 7,698 records; only exact
selected-country labels and airport-type records with IATA identifiers are
retained. All 678 selected rows passed identity/coordinate validation; zero
selected rows were rejected. Country codes map explicit country labels.

The API consumes this data through `/v1/world/observations?mode=aviation`;
country, search, viewport and ordinary pagination use the existing pipeline.
The existing World Explorer aviation mode consumes that endpoint, preserving
source coordinates and attribution. The source-specific summary explicitly
describes static airport reference. No aircraft movement, current operational
status, schedule, issuer relationship or financial exposure is inferred.
This does not replace the existing OurAirports endpoint.

Normalized SHA-256:
`7198f95df5aefbb62a6365aaf7a060d073e750cf46f971ee63b88862a4d4aa72`.
Raw airport source SHA-256:
`9387cdb38df5bd664da823f8ccb69fdd9b33a1888f5b7cca09c34a3cd9ff59f9`.
Rights/schema documentation source SHA-256:
`122ef40826eca4c9d288da6b46c9c091be4b67f2b639fcfdee119102a4a10e44`.

Rights are documented by the publisher's official repository `data.php`,
whose licensing section grants ODbL 1.0 for the database and DbCL 1.0 for
individual contents. The raw and normalized database are separately licensed
ODbL 1.0; the attribution and modifications are retained in the manifest,
source passport, observation summaries and limitations. The original database
and this normalized derivative remain downloadable in the captured directory.
ODbL share-alike applies to this derived database. The application code is
not part of that database.

The catalogue `/data.html` URL previously returned 404. The canonical
`https://openflights.org/data.php` is documented by the official README; it
returned 403 during this review. Official repository data/documentation were
available without a login. Raw captures retain the complete source file and
publisher documentation with checksums. Original update/publication dates are
unknown; first proven availability is the capture timestamp. Earlier replay
excludes the capture.

Reconstruction:

```bash
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.ingest --source openflights
```

This creates a new content-addressed version and never modifies an existing
capture. Source transport uses existing HTTPS host restrictions, byte caps,
timeouts, retries and rate limits; reads at most 2 MB per source response.

## Verification

Bounded HTTP checks exercise current aviation observations, Japan filtering,
historical exclusion, and `/v1/datasets/world_openflights_airport_reference`.
Evidence: `docs/evidence/parallel/agent-3/openflights-runtime.json`.
The checked aviation response reports 678 records; Japan reports 94; asOf
2026-11-14 reports zero matching records. Passport row count is 678.
The existing snapshot loader verifies raw and normalized checksums.
No browser verification or newly written test suite is claimed.

## Exact remaining blockers

| Rows | Finding | Status |
|---|---|---|
| SRC-198, MASTER-039, MASTER-085 JODI Oil | Official download page is accessible and identifies public annual CSV files, including the 2026 primary CSV. The page has a JODI copyright notice; free download does not establish redistribution rights. Guessed terms locations returned 404 and were not treated as licences. No data redistribution or integration is claimed. | Rights not established |
| SRC-191, SRC-223 Ember API | Existing audit identifies account/API key dependency. User requested deferring login sources. | Deferred login |
| MASTER-040, MASTER-095 Ember yearly | Explicit yearly data page returned HTTP 403. No accessible download/schema/licence was established in this bounded review. | Access and rights unresolved |
| MASTER-084 Ember monthly | Distinct source row remains unimplemented; yearly/API review is not counted as monthly integration. | Unimplemented |
| SRC-203, SRC-204, SRC-205, MASTER-074, MASTER-075, MASTER-076 PortWatch | Public PortWatch site links `https://www.imf.org/external/terms.htm` as Copyright & Usage. The terms URL returned HTTP 200 with a 392-byte HTML document containing an empty body. No readable reuse conditions were established, so existing parser/ports layer is not published and chokepoint/activity is not newly integrated. | Rights not established |

Access review evidence and response hashes:
`docs/evidence/parallel/agent-3/energy-transport-source-review.json`.

## Shared additive bridges

Added one DatasetId row in `contracts/catalog.md` and its Python/TypeScript
enum mirrors; the returning integrator regenerates schema/type mirrors after
concurrent catalogue edits settle. Added a datastore descriptor, the world
passport ID, one ingestion CLI registration and a source-specific summary.
New provider module and capture are otherwise self-contained. No source,
status, handoff or requirements summary was edited by this batch.
