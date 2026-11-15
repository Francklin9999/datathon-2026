# Remaining transport and aviation sources

This batch captures anonymous ADS-B.lol reports and NOAA MarineCadastre annual
AIS raster samples. No account, key, paid route, new test file, commit,
deployment or active datastore pointer was created.

| Source IDs | Status | Exact scope |
| --- | --- | --- |
| SRC-209 / MASTER-079 | Implemented bounded capture | Two valid annual 2024 NOAA AIS raster cells from three fixed identify queries; no vessel-level records or live AIS |
| SRC-213 | Implemented bounded capture | 49 source aircraft reports in one snapshot within 20 nautical miles of the Heathrow-area query centre |
| SRC-210 / MASTER-078 | Checked; rights unclear | Free historical Danish CSV access is documented; explicit reuse/redistribution licence was not established |
| SRC-214 | Deferred for rights | Current Airplanes.live terms require written permission for database compilation and commercial exploitation |
| MASTER-097 | Checked; rights unclear | OpenSky documentation permits anonymous latest states, but reuse rights were not established and its terms endpoint returned HTTP 403 |

## Captures, rights and quality

`world_adsblol_heathrow_positions-2026-11-15-107d6f724d27e0d2`, retrieved
`2026-11-15T18:09:31.085Z`, contains 49 validated reports and zero rejected
records. Normalized SHA-256:
`107d6f724d27e0d25d9e3b6b11290c6776ec770f21b5c40bb79fe9a1c64181dc`.
The API's official documentation at
<https://www.adsb.lol/docs/open-data/api/> explicitly states “license: ODbL 1.0”
and an anonymous quota of 500 requests/day/IP. The captured documentation is
stored alongside the raw API response. Both raw and normalized databases are
available in the immutable provider directory under ODbL 1.0. Application
code remains separate from those databases. Attribution describes the
adaptation and licence in each record, manifest and passport.

The parser validates source status, bounded schema, unique source hex IDs,
finite coordinates, the provider snapshot timestamp and source position age.
Positions older than 60 seconds at the source snapshot are rejected.
`observedAt` is the source snapshot time minus `seen_pos`; `availableAt` is
retrieval. Source position type and callsign retain their source meaning.
Multilateration and ADS-B reports do not establish aircraft operators,
ownership, issuers or holdings. This is one captured snapshot, with no
continuous tracking or worldwide coverage claim.

`trade_marinecadastre_ais_2024_samples-2026-11-15-816e6d16111746d0`, retrieved
`2026-11-15T18:09:33.352Z`, contains two validated annual raster cells.
Normalized SHA-256:
`816e6d16111746d0433226d6fc3b0077bbcf543509b6cd1751a015c675616655`.
The New York Harbor query anchor `(-74.035, 40.65)` returned cell count 9;
the Los Angeles Harbor anchor `(-118.25, 33.70)` returned 8. The San Francisco
Bay query returned `NoData` and was rejected, rather than converted to zero.
The three original responses and rights document remain in the capture.
The official NOAA repository's README explicitly dedicates all content under
CC0 1.0 and links the exact 2024 annual raster service used here.

Raster response layer identity, spatial reference, query/response coordinate
consistency and integer cell value are validated. Coordinates are query
anchors (`geographicRole: raster_query_point`), not reported vessel
locations, port boundaries or facility coordinates. Annual cell transit
counts cannot be treated as distinct vessel counts, summed as unique traffic,
interpreted as current activity or converted into cargo volumes. The
reference year is stored as a period; observation/publication timestamps
remain unset because their exact values are unknown.

## Sources checked without ingestion

The Danish Maritime Authority page explicitly states “Historical AIS-data
are free for down-load.” Its management policy distinguishes paid web
access/online flow. Free downloads establish access; the checked documents
did not establish an explicit reuse licence. No Danish AIS payload was
downloaded or published.

The old Airplanes.live `/api-guide/` and `/terms-of-service/` paths returned
404. Current official links `/api-docs/` and `/terms-of-use/` both returned
200. Current terms prohibit systematically retrieving data to create a
database without written permission and prohibit commercial exploitation
without prior written permission. No aircraft payload was requested.

OpenSky's current REST documentation explicitly permits anonymous latest
state vectors and documents a 400-credit daily anonymous allowance. It
requires OAuth client credentials for authenticated routes. Its terms URL
returned HTTP 403. No open reuse grant was established, so no state-vector
payload was requested. MASTER-097 should be recorded as rights unresolved;
anonymous access documentation does not justify a blanket login requirement.
SRC-212's earlier authenticated-route deferral was outside this batch.

## Runtime integration and verification

The generic immutable loader consumes both datasets through World Explorer's
existing `/v1/world/observations` pipeline: `mode=aviation&q=ADS-B%20report`
and `mode=trade&q=NOAA%20AIS%202024`. Source-specific summaries state aircraft
snapshot and annual raster meanings. Manifest limitations and attribution
reach the observation response and generic provider passport.

Direct runtime verification loads the genuine captures, checks normalized
and raw checksums, validates response models, compares returned row counts to
the manifests/passports and excludes both captures from `asOf=2026-11-14`.
Evidence is `docs/evidence/parallel/agent-3/transport-extra/runtime-verification.json`.
No new test files or broad test suite were run for this batch.

The adapter is
`backend/aplomb/world/providers/transport_extra.py`. Shared bridge edits are
three additive `Transport.HOSTS` entries (`coast.noaa.gov`, `api.adsb.lol`,
`www.adsb.lol`) and two source-specific summary branches in
`backend/aplomb/world/service.py`. Catalogue and passport registry additions
are assigned to root: `world_adsblol_heathrow_positions` and
`trade_marinecadastre_ais_2024_samples`. This worker did not edit SOURCES.csv,
STATUS, HANDOFF, REQUIREMENTS, BLOCKERS, contracts/catalog.md,
backend/aplomb/contracts/catalog.py or backend/aplomb/datastore/passports.py.

Reconstruction: `PYTHONPATH=backend .venv/bin/python -m
aplomb.world.providers.transport_extra`. This creates new immutable captures
and consumes six bounded source requests; it does not reproduce a past live
snapshot or overwrite previous versions. Research checks and raw source
documents are under `docs/evidence/parallel/agent-3/transport-extra/`;
`source-review.json` indexes document SHA-256 values and exact source status.
