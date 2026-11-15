# Public geospatial capture batch

This batch adds `backend/aplomb/world/providers/geo_public_extra.py` and three real immutable captures. It does not add tests, commit, deploy, modify the active manifest, or edit the source ledger or status/handoff/requirements/blockers reports. Shared runtime/catalog/passport wiring is assigned to the returning Agent-3 coordinator to avoid simultaneous edits.

## Captured sources

| Ledger rows | Dataset | Actual bounded capture | Normalized SHA-256 |
|---|---|---|---|
| SRC-148, MASTER-060 | `world_osm_eiffel_tower` | OSM API way 5013364 and its referenced nodes, normalized to one Tour Eiffel mapped footprint polygon in Paris | `f7f58df7b5f5c9418444c4f31477a1f00d4801636cc595910385125d70df1d6b` |
| SRC-151, MASTER-061 | `world_nominatim_eiffel_lookup` | One Eiffel Tower, Paris, France query, one validated French OSM way result and its source point | `261736705de3a7f19d73b99f13e9bb6815632aaec2a1e38d93683b0cb8389020` |
| SRC-157, MASTER-063 | `world_nasa_gibs_modis_tile` | One actual 512×512 NASA Terra MODIS true-color JPEG for 2026-11-14, matrix set 250m / matrix 0 / row 0 / column 0; corresponding WMTS capabilities and footprint | `dc9eafcc82e73ee658b049183705a27ff9b856a2fa4fefdc83be87f2a11443fc` |

All three normalized captures were published at `2026-11-15T18:04:53Z`. The dataset version is the dataset ID plus `-2026-11-15-` and the first sixteen normalized checksum characters. Captures live under `backend/aplomb/world/bundle/providers/`. Each directory includes `manifest.json`, `observations.json` and all original responses with their hashes. The loader verifies raw/normalized integrity and gates availability at capture. Historical queries before capture cannot consume these records.

OSM supplies the actual way polygon; the adapter supplies no invented center point. The source edit timestamp remains metadata and is not treated as an event or original availability date. The Nominatim point is the source's geocoder location, not proof of surveying precision, operational status, ownership, or issuer exposure. Both record exact OSM way identity. No fuzzy company matching is introduced.

NASA capabilities advertise the selected layer and 2026-11-14 within its available daily range. The parser checks layer identity, JPEG format, CRS84 matrix parameters and actual JPEG dimensions. The footprint is derived from the official matrix scale and tile dimensions, clipped to Earth: longitude -180 to 108 and latitude -90 to 90. It describes tile extent, not complete or cloud-free observation coverage. The tile visibly contains genuine satellite swaths and missing-data gaps. The `250m` matrix-set label is not the resolution of this matrix-zero overview. This provides an imagery reference and footprint; a full satellite raster overlay remains unimplemented.

## Rights and public service constraints

[OSM copyright](https://www.openstreetmap.org/copyright) identifies ODbL, attribution and sharing obligations. Both separate OSM-derived databases explicitly retain © OpenStreetMap contributors, the ODbL 1.0 URL, indication of selection/normalization, and an ODbL 1.0 licence for the derived database. Raw and normalized derivatives are available in their capture directories. Database rights do not relabel application code. The licence evidence is captured and checked before new publication.

[Public Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/) allows small one-time tasks with a single thread, at most one request per second, an identifying application User-Agent, attribution and caching. This review made one search request. The collector uses an identifying User-Agent, a minimum delay exceeding one second, no automatic retries, a single fixed query and persistent saved-capture reuse. A repeated ingestion returns the existing integrity-verified capture and does not send another geocoder request. Neither API requests nor autocomplete call public Nominatim. User-triggered unrestricted geocoding, systematic searches and bulk collection are not introduced. A different endpoint would require a deliberate reviewed code configuration change.

[NASA Earthdata data-use guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance) assigns CC0 to unmarked data from NASA-led missions. This capture specifically selects NASA Terra MODIS corrected reflectance, rather than assuming identical rights for all GIBS layers. [Official GIBS guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api) requests: “We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).” The manifest and observation retain that acknowledgement and NASA Terra MODIS attribution. Both guidance documents are preserved in the immutable capture. No NASA endorsement is implied.

Transport uses an exact HTTPS URL allowlist, rejects redirects, limits source response size (6 MB capabilities; 500 KB other responses), enforces read/connect deadlines, and fails closed on source identity/geometry/licence evidence changes. No production cloud or account changes occur.

## Other requested source dispositions

| Rows | Evidence and remaining work | Disposition |
|---|---|---|
| SRC-149 Overpass | A small 30-node Paris artwork query at `overpass-api.de`, then one fixed Tour Eiffel `out geom` query at the public `overpass.private.coffee` instance, both timed out. Explicit server time/response-size limits and local timeouts were used. Underlying OSM ODbL terms apply; no successful response or feature integration is claimed. | Access unresolved; adapter/capture unimplemented |
| SRC-150 Geofabrik | Public site and `index-v1.json` were retrieved anonymously. The site credits Geofabrik and OSM contributors and links ODbL 1.0. Index describes country/region extract download URLs and extract coverage polygons; those metadata are not a capture of the contents of an OSM extract. A bounded actual PBF/shapefile release, format parser, validation and runtime dataset remain necessary. | Checked; extract integration unimplemented, no invented rights blocker |
| SRC-155 Overture Maps | Official attribution page retrieved. Buildings/divisions/base/transportation include ODbL; places include CDLA Permissive 2.0, Apache 2.0 and CC0 contributions, with upstream notices. Address licences vary by source. No particular release/theme/row's upstream notices were verified against actual captured data. A versioned bounded actual release and exact selected-theme/source obligations remain necessary. | Checked; release integration unimplemented; no blanket Overture licence asserted |
| SRC-156 OpenAddresses | Public site confirms individual openly licensed sources and usual attribution requirements. It does not establish one uniform licence or update date for all files. One prospective Montreal registry filename returned 404 and was not treated as a source. No exact upstream address source/release/licence was established for a bounded capture. | Checked only; selected-source rights/access unresolved and integration unimplemented |

No paid/login source was acquired. These findings are not a claim that all requested geospatial sources are integrated.

## Manual verification and evidence

`docs/evidence/parallel/agent-3/geo-extra/capture-verification.json` records successful checks of three current rows, zero rows before capture, raw/normalized integrity, Paris viewport intersections for both source polygons, persistent Nominatim reuse without networking, rejection of an empty geocoder result, rejection of an invalid JPEG, and rejection of an empty OSM response. Reconstruction into a temporary directory also passed all three licence evidence checks. No new test files were added.

Source status, sizes, original URLs and response hashes are in `access.json`, `second-access.json`, `overpass-second-access.json` and `rights-followup.json` in the same evidence directory. `rights-excerpts.json` records readable licence/policy excerpts. The GIBS JPEG hash is `5d38ae41ee3ad7d3166df8a84860448f612297fcbf035812849bea578d85137c`; full capabilities hash is `92dd664294e351b25aa0189f39d6ea24b56fa7063d0b6d82134efb919017a6dc`.

Standalone capture commands:

```bash
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.geo_public_extra --source osm
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.geo_public_extra --source nominatim
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.geo_public_extra --source gibs
```

## Shared bridges for coordinator

Add all three dataset IDs to the common catalogue/enums and world passport dataset set; add source-specific datastore descriptors. The existing `provider_passports` constructs actual current passports from the checked manifests. OSM and Nominatim categories already select infrastructure mode; GIBS selects environment. Add `world_osm_eiffel_tower` and `world_nasa_gibs_modis_tile` to the polygon-aware viewport dataset set, preserving geometry without arbitrary point anchors. Source summaries should state mapped footprint / permanently cached lookup / overview imagery tile and retain attribution. Optional ingestion aliases can call `geo_public_extra.collect('osm'/'nominatim'/'gibs')`.

Until those catalogue/passport/summary bridges are applied and verified by the coordinator, these three sources are capture-ready rather than fully accepted runtime integrations. HTTP passport and observation acceptance and browser imagery behavior are not claimed by this batch.
