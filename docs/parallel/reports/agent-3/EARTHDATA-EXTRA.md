# NASA Earthdata CMR anonymous metadata capture

SRC-158 is implemented as a bounded source-backed runtime capture. Dataset
`world_nasa_cmr_modis_granules`, version
`world_nasa_cmr_modis_granules-2026-11-15-870a7104c7fdbe5e`, contains five NASA Terra
MODIS MOD14A1.061 granule coverage records from collection
`C2565791013-LPCLOUD`. Normalized SHA-256:
`870a7104c7fdbe5ef65144488d4490729ceafd7f3e588ea930f369d063d0d4d0`.

The anonymous CMR metadata query requests the first five records ordered by
latest product start date, intersecting longitude -5 to 5 and latitude 40 to 50.
Its polygons represent satellite product coverage. They do not indicate a fire,
fire intensity, damage, company operations or financial exposure. No raster,
scientific pixel values, credentials or authenticated downloads were requested.
Underlying imagery downloads remain set aside because they may require login.

NASA's official Earthdata Data Use Guidance states that NASA metadata is generally
not copyrighted and NASA-led mission data is CC0, with attribution strongly urged.
This capture selects a NASA-led MODIS product and attributes NASA Terra MODIS,
LP DAAC and NASA CMR. It includes no third-party imagery or media.
The LP DAAC policy URL redirected to the current Earthdata guidance:
https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance.
The retrieved policy HTML and hash are retained in the evidence directory.

The adapter uses fixed URLs, denies redirects, allows three bounded retry attempts
with backoff, caps each response at 500 kB and applies socket and read deadlines.
It validates the collection/version/provider, unique granule IDs, timezone-aware
source intervals and metadata revision times, finite closed polygon coordinates
and coordinate bounds. Dateline-spanning polygons are rejected for this regional
capture. CMR latitude-longitude pairs become GeoJSON longitude-latitude pairs.
There are no invented point coordinates or country assignments.

The source start time is the display anchor for the actual eight-day product
interval; the full start/end values remain in the capture and summary. Metadata
revision time is retained as metadata and is not called original publication.
Availability is conservatively gated at capture. The capture is not eligible for
historical replay based on its earlier observation interval.

The packaged immutable manifest retains normalized and raw hashes. Existing
`WorldServiceImpl.observations` consumes the capture in environment mode, including
source title/links, explicit limitations, search, pagination and geometry viewport
filtering. The existing WorldObservations source list/detail and selected polygon
renderer consume the same wire fields. A loaded passport exposes its five rows,
licence, capture date, incomplete scope and integrity checks.

Changed paths:

- `backend/aplomb/world/providers/earthdata_extra.py`: adapter and bounded capture CLI.
- `backend/aplomb/world/providers/ingest.py`: additive `--source earthdata` dispatch.
- `backend/aplomb/world/bundle/providers/world_nasa_cmr_modis_granules-2026-11-15-870a7104c7fdbe5e/`: immutable raw/normalized capture and manifest.
- `backend/aplomb/contracts/catalog.py` and `contracts/catalog.md`: additive dataset ID.
- `backend/aplomb/datastore/passports.py`: additive bilingual descriptor.
- `backend/aplomb/world/passports.py`: additive loaded-provider ID.
- `backend/aplomb/world/service.py`: environment mapping, factual source summary and geometry viewport support.
- `docs/evidence/parallel/agent-3/earthdata-extra/`: policy HTML, runtime response, passport and validation results.

Verification used the worktree virtual environment and real captures:
`PYTHONPATH=backend .venv/bin/python` with a bounded acceptance script. Immutable
raw/normalized checksums passed; the runtime returned five polygon-only records
and an in-use five-row passport; the selected European viewport returned five;
an unrelated US viewport returned zero; `asOf=2026-11-01` returned zero. The
catalog descriptor constructs successfully. No new tests were written.
Browser interaction was not independently run for this batch; consumption uses
the previously implemented polygon-only observation path. No deployment,
activation-pointer modification, commit or push was performed.

Full catalog coverage, refreshed captures, raster integration and authenticated
downloads remain unimplemented. SRC-194 Open Power System Data was investigated:
its 2020-08-25 renewable plants package and page are anonymously reachable, but
the fetched package has no `licenses` declaration, and the page's CC-BY statement
is explicitly for text. Source resources combine upstream providers. No runtime
capture was published and SRC-194 remains unimplemented pending dataset-specific
reuse verification.
