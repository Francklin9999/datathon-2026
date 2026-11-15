# External source dependencies, 2026-11-15

These dependencies describe source access and rights. They do not excuse the unimplemented
engineering listed source by source in SOURCES.csv. A documentation HTTP 200 is reachability
only. No production settings, cloud resources, accounts, credentials or subscriptions were changed.

## PortWatch reuse rights

The ArcGIS port layer is reachable. Its linked item specifies
`https://www.imf.org/external/terms.htm` as licenseInfo; that terms request returned HTTP 403.
The layer has empty copyright text, which is not a public-domain grant. Owner action:
establish permitted application redistribution/use under the IMF terms and record the applicable
terms. Completed independently: pure port parser rejects truncated pagination and projected
coordinates, validates port IDs and coordinates, and avoids issuer relationships.
The exact chokepoint table is reachable but has no geometry; a sourced geographic crosswalk and
activity capture remain unimplemented.

Canada Gazette's RSS feed is publicly reachable without a login. Its catalogue
links to the Canada.ca terms, which require prior written permission for
commercial redistribution unless otherwise specified. Feed reuse rights for
this application were not established, so SRC-143 and MASTER-048 remain
unpublished; the observed feed and terms are recorded in
`docs/evidence/parallel/agent-3/source-audit/canada-gazette-rights.json`.

## User access preference

Paid or billing dependent integrations are excluded from this branch, and sources
requiring login, an account, a key, a token or approval are set aside. The source
ledger retains these assigned rows for audit and marks them `excluded_paid_plan`
or `deferred_login`. Five paid or billing dependent rows and 56 login gated rows
are affected; some rows name the same underlying provider. No enabled new
provider capture requires a paid plan or login.

## Credentials and restricted plans

SOURCES.csv identifies provider-specific prerequisites rather than asserting every catalog
free tier needs a key. Required credentials/plans include FIRMS MAP_KEY, EIA, OpenAQ, WTO,
BEA, Congress, Regulations.gov, approved ACLED access, registered ReliefWeb appname, and
commercial/registered mapping, satellite, weather, electricity and patent APIs. Google Trends
requires alpha authorization; NewsAPI developer terms exclude production use; Reddit/GDELT TV
rights need explicit review. Owner action: provide permitted account access and usage rights
when enabling those providers. No credentials were printed or copied.

## Transient source access and exact release evidence

The UCDP download documentation states CC BY 4.0 with required scholarly attribution.
Both bounded API probes returned HTTP 401 Unauthorized. Owner action for that API: provide its
permitted authorization. The official versioned download remains an independent acquisition
path; download ingestion and citation metadata are still engineering work.
Eurostat's live HICP endpoint returned old-series observations ending 2025-12, while the
copyright reference tried returned 404; use the replacement series and current reuse notice.
IMF/OECD/BIS/Statistics Canada and other accessible sources remain unimplemented where marked
as such in SOURCES.csv. GDELT DOC remains baseline unavailable; its article location cannot be
invented from publisher location.

## Work completed without these dependencies

Five real new content addressed datasets were captured and schema/coordinate validated:
WRI power plants (34,936), NOAA AviationWeather (six selected international stations), NOAA
active weather alerts with valid polygons (three; 335 without supported geometry excluded), and
Federal Register recent policy metadata (20; publication dates bounded at capture), and GDACS
disaster alert metadata (100; newest page across six event types). Raw bytes,
normalized checksums, quality reports, rights, scope and conservative temporal availability are
preserved. Baseline WDI, EONET, USGS catalog, OurAirports, ECCC and Natural Earth remain separate.

All 153 assigned SRC rows and 65 assigned MASTER rows are dispositioned in SOURCES.csv.
Most rows remain unimplemented. Five capture pipelines alone do not complete the full assignment.
