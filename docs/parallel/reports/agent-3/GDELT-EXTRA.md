# GDELT bounded metadata integrations — 2026-11-15

Implemented `backend/aplomb/world/providers/gdelt_extra.py` with genuine immutable captures: 250 GDELT Event action-location records, 250 GKG article-location records and 250 Global Geographic Graph article-location mentions. All three use the existing world observation loader, news mode, coordinate validation, immutable storage and capture-time historical gate. Shared DatasetId/passport/summary wiring is coordinated with the parent agent.

| Assigned row | Result | Evidence / precise boundary |
|---|---|---|
| SRC-115 / MASTER-042, DOC 2.0 | Access blocked | Anonymous bounded `TimelineVol` query for climate, last day, returned HTTP 429. No usable DOC payload or article-search/timeline integration claimed. |
| SRC-116, Events | Captured runtime metadata | Official 20261115174500 export: 1,021 source rows; 250 mapped city/landmark action locations; 379 coarse/missing-location skips; 392 valid records omitted by cap; zero invalid records in corrected parser. |
| SRC-117, GKG | Captured runtime metadata | Same 15-minute update: 712 source rows; 250 mapped articles with one source-listed city/landmark each; 258 unavailable/coarse skips; 204 omitted by cap; zero rejected. |
| MASTER-043, Event/GKG | Captured runtime metadata | Both actual bulk schemas implemented using the official Event 2.0 and GKG 2.1 codebooks. |
| SRC-118, GEO API | Access blocked | Official documented `PointData`, GeoJSON, climate, last day, maxpoints=20 endpoint returned HTTP 404. GEO API capture remains unavailable. Separate Geographic Graph bulk success does not change this API failure. |
| MASTER-044, Geographic Graph | Captured runtime metadata projection | Official daily 20261114 archive: 545,407 compressed bytes, 4,705 source records; 250 city/landmark mentions; 3,813 coarse/duplicate skips; 642 omitted by cap; zero rejected. Publisher contextual snippets, titles and images excluded from retained projection. |
| SRC-234, GDELT news volume | Access blocked | DOC `TimelineVol` request returned 429. Counts of loaded Event/GKG/geographic records are sample counts and are not claimed as a DOC news-volume time series. |

## Access and rights evidence

Official [about page](https://www.gdeltproject.org/about.html), retrieved successfully on 2026-11-15, says: “All datasets released by the GDELT Project are available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee.” This applies to GDELT released datasets; it does not establish rights to retrieve or republish publisher articles. Source attribution is retained in every passport. No login, cloud billing, paid API, article fetching or denial bypass was used.

The [data page](https://www.gdeltproject.org/data.html) documents 15-minute Event/GKG updates. The [Geographic Graph announcement](https://blog.gdeltproject.org/announcing-the-global-geographic-graph/) distinguishes that dataset from GKG and provides its actual master file list. The GEO failure used the endpoint/mode from its [official API documentation](https://blog.gdeltproject.org/gdelt-geo-2-0-api-debuts/). A numeric sustained API quota was not established; captures make one index request and one request per bounded archive, with a 20-second deadline and no automatic refresh or retry storm.

Evidence is under `docs/evidence/parallel/agent-3/gdelt-extra/`: access metadata, bulk access metadata, Geographic Graph HEAD metadata, captured official access/rights pages and `capture-validation.json`. Official codebooks were fetched successfully from `https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf` and `https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf`; URLs/status/byte sizes are in bulk access evidence.

## Immutable versions and validation

| Dataset | Latest immutable version | Normalized SHA-256 |
|---|---|---|
| world_gdelt_event_metadata | world_gdelt_event_metadata-2026-11-15-5ee806000fe9d6e7 | 5ee806000fe9d6e79dfd945df50750c744d272368284b3b2831ea247102fe018 |
| world_gdelt_gkg_locations | world_gdelt_gkg_locations-2026-11-15-f3e5ab8973c1bd55 | f3e5ab8973c1bd55410299002a465a7ec17272e1bfabcfc8cd3ce6243b9cb97b |
| world_gdelt_geographic_mentions | world_gdelt_geographic_mentions-2026-11-15-2171730c9e83ecf4 | 2171730c9e83ecf43a02a599da2e3201ee376b91f8905a2d3b8c54c167069423 |

Versions are stored in `backend/aplomb/world/bundle/providers/`. Bulk captures verify published archive size and MD5 from the real `lastupdate.txt`, then preserve SHA-256 of retained archives and normalized rows. ZIP members must have the expected batch filename, single-member shape and bounded expanded size; Event requires 61 columns, GKG 27. Four-digit CAMEO codes are valid. An earlier local version that conservatively omitted them remains immutable; the loader selects the later corrected version listed above. No parent snapshot or active pointer changed.

Geographic Graph retains only required date, URL, language and geographic metadata from the first 250 accepted records. Its manifest records original compressed SHA-256 `5cca3f76110584b876520cd2e7bcff5a9bbe8f7f2bd5fe389f49a27e703ee8fc`, original byte size, and `retainedProjection: true`; its second `rawCaptures` file is explicitly the retained JSON metadata projection rather than the original gzip. The original downloaded archive is not redistributed in the repository. The projection and normalized data are checksum verified.

Validation on actual captured data passed: 250 rows per dataset, valid source coordinates, source identifiers, no fabricated ISO mapping, raw/normalized integrity, idempotent identical republication and zero rows from these datasets before capture. All three samples have northern, southern, eastern and western hemisphere locations. `ruff check backend/aplomb/world/providers/gdelt_extra.py` passed. No new tests were added, following the user's fast integration instruction.

`world-runtime.json` demonstrates the real `WorldServiceImpl` consuming the full saved optional-provider collection and baseline world bundle: search selects 750 GDELT news observations, three distinct 250-row pages, 378 eastern-hemisphere viewport records, and zero before-capture observations. A separate smoke isolating the three actual GDELT captures via the service's cached provider input also passed. The full-provider query eventually passed but took substantially longer while materializing the existing 37,826-row provider collection; that performance concern was sent to the parent. No browser or performance acceptance is claimed.

After the parent's additive enum/passport wiring, all three actual `provider_passports()` results passed `DatasetPassport.model_validate`, each with `in_use`, 250 rows and the retained rights statement; see `passport-validation.json`. The passport adapter uses its contract-compatible `snap-...` version projection, while the full immutable archive versions above remain in capture manifests.

## Semantics and reconstruction

Only location types 3/4 (cities/landmarks) are mapped. Types 1/2/5 are country/state centroids and are deliberately omitted. GDELT FIPS10-4 codes stay in properties; `countryIso3` remains absent until a reviewed crosswalk exists. GKG location selection does not assert a main event location. Machine coding can be wrong. Publisher URLs remain recorded references; publisher bodies are not fetched or verified.

Event day is preserved as a day-level reported observation; DATEADDED is indexing time, not source article publication. GKG indexing time and Geographic Graph DateTime stay in properties; article publication dates are not asserted. Availability is gated at actual capture; none of these versions supports original historical replay, issuer exposure or financial impact.

Reconstruct future bounded captures:

```bash
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.gdelt_extra
PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.gdelt_extra --geographic
```

Future archives that exceed the 5 MB compressed or 15 MB expanded cap fail explicitly. This CLI is a separate source-specific entry point, avoiding concurrent edits to shared ingestion dispatch. Parent integration must retain all three DatasetId enum values, provider passport IDs and source-specific observation summaries. No commits, pushes or deployment were performed by this worker.
