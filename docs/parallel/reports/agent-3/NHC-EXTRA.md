# NOAA NHC current GIS feed check

SRC-177 and MASTER-069 were checked anonymously on 2026-11-15 at approximately 17:25 UTC. The official current feeds were reachable but contained no current storm data. No provider snapshot, runtime rows, storm coordinates, or additional dataset registration was created.

| Official endpoint | HTTP | Checked result |
| --- | --- | --- |
| [NHC GIS catalogue](https://www.nhc.noaa.gov/gis/) | 200 | Page as of 2026-11-15 17:20:27 UTC shows “No current data” for the advisory forecast track, cone and watches/warnings in all three basins. |
| [GIS RSS description](https://www.nhc.noaa.gov/gis/rss.php) | 200 | HTML documentation, not an XML RSS response. Lists feed product types and links to actual basin feeds. |
| [Atlantic GIS RSS](https://www.nhc.noaa.gov/gis-at.xml) | 200 | One informational item: “There are no tropical cyclones at this time.” No storm product link or geometry. |
| [Eastern Pacific GIS RSS](https://www.nhc.noaa.gov/gis-ep.xml) | 200 | One identical informational item. No storm product link or geometry. |
| [Central Pacific GIS RSS](https://www.nhc.noaa.gov/gis-cp.xml) | 200 | One identical informational item. No storm product link or geometry. |
| [Current storms JSON](https://www.nhc.noaa.gov/CurrentStorms.json) | 200 | `{"activeStorms": []}`. |
| [NWS disclaimer and reuse terms](https://www.weather.gov/disclaimer) | 200 | NWS information and NOAA/NWS geospatial data are public domain unless specifically noted otherwise. |

Raw responses, final URLs, retrieval times, byte counts, SHA-256 hashes, feed channel timestamps and individual item metadata are preserved in `docs/evidence/parallel/agent-3/nhc-extra/`; `checks.json` indexes them. Requests used fixed official HTTPS endpoints, 25-second socket timeouts and a 2,000,000-byte response read cap. The HTML description is saved as `gis-rss-description.html`, avoiding an XML label for the landing page.

## Time and geometry limitations

The empty-feed sentinel is source status metadata, not a tropical cyclone event. Its lack of geometry cannot justify a substitute point. It also does not establish an absence of storms outside NHC's Atlantic, eastern Pacific and central Pacific coverage.

The Atlantic sentinel item reports `Tue, 17 Nov 2026 05:10:42 GMT`, which is later than capture time, while the channel and description report 2026-11-15. These raw values are retained as a source timestamp anomaly. They are not normalized into an observation or used to claim future or historical availability.

NHC's catalogue distinguishes advisory forecast track and cone of uncertainty from preliminary best track. A forecast track describes predicted future cyclone-center positions; a cone describes uncertainty in that forecast and must not be labeled an observed storm footprint or damage area. Preliminary best track is a provisional past-track product, distinct from the final best tracks linked in the catalogue. Advisory wind field and forecast wind radii likewise have different time semantics. A future adapter must preserve product identity, advisory issuance, forecast validity and the original geometry; it must avoid treating a polygon display anchor as a measured center or a forecast position as an observed event.

The current empty responses provide no active advisory/GIS payload from which to verify a product schema, validity times or source geometry. Historical sample products and archives were not substituted for current-feed data. No historical replay, storm monitoring completeness, financial impact, country attribution or issuer relationship is established by this check.

## Rights and next integration condition

The captured [NWS disclaimer](https://www.weather.gov/disclaimer) says its information is public domain unless specifically annotated otherwise and can be used without charge for lawful purposes, with no claim of ownership, implied NOAA/NWS endorsement, or modified content presented as official government material. It explicitly identifies NOAA/NWS data exposed through map services as public domain; third-party imagery and third-party material have separate rights. Any normalized product should credit NOAA/NHC and identify Aplomb's adaptation. No logos, imagery or linked third-party content are proposed for runtime display.

The remaining condition is a nonempty official storm feed with a checked advisory/GIS product and precise time/geometry semantics. Recheck during active cyclone conditions, then implement bounded fixed-host retrieval and immutable publication through the existing snapshot writer after validating real source data. The empty current-feed outcome should remain deferred rather than counted as a loaded storm dataset. No new tests were added.
