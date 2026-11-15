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

The Eurostat greenhouse-gas series has a staged, checksum-verified capture, but its dataset
metadata points to a reuse policy that could not be verified at the linked URL. The general
Commission and EEA notices do not resolve dataset-specific exceptions. Keep SRC-095 staged
until the applicable series licence is established. See `MACRO-EXTRA.md`.

UN Comtrade and the WITS fuel export sample are enabled only as bounded free visualizations
under the provider's limited free-use rules. Commercial APIs or streaming require a
fee-bearing distribution agreement. User instruction excludes paid plans, so do not expand
these samples into a commercial API/streaming product; see `TRADE-EXTRA.md` and
`TRADE-FOLLOWON.md`. No paid subscription was acquired.

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
or `deferred_login`. Six paid or billing dependent rows and 56 login gated rows
are affected; some rows name the same underlying provider. No enabled new
provider capture requires a paid plan or login.

Open-Meteo SRC-179 is included in the excluded set: its free API terms restrict
use to non-commercial purposes. The linked terms are recorded in
`docs/evidence/parallel/agent-3/source-audit/open-meteo-terms.json`.

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
permitted authorization. The independent official versioned ZIP was acquired anonymously and
a bounded cited sample was enabled; see `UCDP-STATIC.md`.
Eurostat's live HICP endpoint returned old-series observations ending 2025-12, while the
copyright reference tried returned 404; use the replacement series and current reuse notice.
IMF/OECD SDMX and other accessible sources remain unimplemented where marked
as such in SOURCES.csv. GDELT DOC remains baseline unavailable; its article location cannot be
invented from publisher location.

## Work completed without these dependencies

The initially reported source-backed datasets were captured and schema/coordinate validated:
WRI power plants (34,936), NOAA AviationWeather (six selected international stations), NOAA
active weather alerts with valid polygons (three; 335 without supported geometry excluded), and
Federal Register recent policy metadata (20; publication dates bounded at capture), and GDACS
disaster alert metadata (100; newest page across six event types), NASA POWER
daily gridded temperatures (186 across six locations for October 2026), and EPA
Envirofacts SEMS sites (438 source-geocoded entries from 1,200 sampled rows). Raw bytes,
normalized checksums, quality reports, rights, scope and conservative temporal availability are
preserved. Additional bounded captures include ECB press releases (4), UK sanctions update notes
(50), USGS mineral production (74), UN Comtrade country exports (5), WITS fuel exports (1),
UNCTAD export concentration (2), Statistics Canada CPI (12), and the later sources described in
their individual reports. Baseline WDI, EONET,
USGS catalog, OurAirports, ECCC and Natural Earth remain separate.

All 153 assigned SRC rows and 65 assigned MASTER rows are dispositioned in SOURCES.csv.
Most rows remain unimplemented. Bounded capture pipelines do not complete the full assignment.

## Subsequent anonymous-release integrations

The official UCDP GED 26.1 static ZIP was downloaded without a token and a bounded Ukraine 2025 sample was enabled with its CC BY 4.0 citation requirements and coordinate-precision caveats. UCDP's separate token-gated API remains deferred. A France ADM1 polygon capture from geoBoundaries and a Canada electricity-generation CO2 estimate series from Climate TRACE were also enabled from reviewed bounded releases; their passports and source reports give exact terms and scope. EPA ECHO remains staged because this capture includes fields from several upstream systems and dataset-specific redistribution rights were not established. Neither the UCDP sample nor any of these sources establishes a verified issuer or portfolio holding relationship.

NOAA NHC's three current basin GIS feeds and `CurrentStorms.json` were checked anonymously on 2026-11-15 and contained no active storms or advisory geometry. There is no truthful current storm capture to enable. `NHC-EXTRA.md` preserves the seven hashed official responses, the public-domain notice, forecast-versus-observed distinctions and a future-dated sentinel timestamp anomaly. Recheck the official feeds when a storm advisory is active; the current empty result is not a global no-storm assertion.

OFAC's Sanctions List Service and recent-actions pages were reachable anonymously. The reviewed Treasury notices did not provide an affirmative reuse licence for the chosen sanctions dataset, and a linked static sanctions application returned 403. `OFAC-EXTRA.md` records the exact access and rights evidence. No list data, named-person identity link or sanctions-screening feature was enabled; verify the applicable dataset reuse basis and actual file endpoint before implementation.

ClinicalTrials.gov's anonymous API supplied a checksum-verified three-study, six-Canadian-location sample, but its distribution guidance asks published extracts to be kept current. The immutable manual sample is staged in evidence and not served. `TRIALS-EXTRA.md` records exact fields, source processing timestamp, rights, third-party caveat and missing facility coordinate precision. A compliant refresh path and rights review of any expanded fields are needed before publication.

Open Power System Data SRC-194 was checked at a selected anonymous renewable-plants package. Its package metadata lacked a data licence declaration; the page's CC BY statement applies to text, and the package combines multiple upstream owners. `EARTHDATA-EXTRA.md` records the check. The selected data are withheld until field-level and upstream redistribution rights are established. OpenAlex SRC-235 has current documentation directing users to a key and is set aside under the user's login rule.

GDELT's released Event, GKG and Geographic Graph metadata were captured and enabled as three bounded location samples. Its separate DOC TimelineVol endpoint returned HTTP 429 and the documented GEO PointData endpoint returned HTTP 404 under bounded anonymous requests. `GDELT-EXTRA.md` records exact URLs, rights and responses. These API rows remain checked endpoint unavailable; bulk captures do not substitute for those API products. Machine-coded locations are unverified and publisher article content is not copied.

JODI oil CSVs are freely downloadable but the reviewed copyright notice and missing applicable data terms did not establish redistribution rights for the selected product. IMF PortWatch links copyright terms whose official response had an empty body; its ports/chokepoint ArcGIS access is likewise insufficient to establish redistribution rights. `OPENFLIGHTS-ENERGY-BATCH.md` gives exact source URLs and evidence. These sources remain unpublished pending applicable rights. BIS statistical rows are included in this local free demo; its terms disallow an additional charge for including BIS data. ECB source and free-access notices must stay visible if this product is sold.

Wikipedia Recent Changes serves a ten-record factual edit metadata sample, not
event or issuer claims. The Canada Gazette RSS feeds responded, but their linked
Canada.ca terms require permission for commercial redistribution. EUR-Lex web
services require a registered account. The accessible UN sanctions XML is withheld
because the reviewed general UN terms restrict redistribution and derivatives.
`POLICY-PUBLIC-BATCH.md` records the exact requests and rights basis.

ILO's official CSV API supplied three 2024 unemployment rates under the ILO
CC BY 4.0 open-data terms; SDMX transport remains separate work. UNICEF's
SDMX values were accessible, but a suitable redistribution grant was not
established. WHO GHO's retrieved terms limit purpose and adaptations. FAOSTAT
Fenix and bulk payload requests returned HTTP 521 and 403. These are held from
runtime until their respective rights or endpoint blockers are resolved; see
`GLOBAL-SOCIAL-STATS.md`.
