# Source register and known traps

**Owner:** T04, with T09/T11 for their adapters. This is a source plan and starter metadata register, not a claim that all integrations were tested. Per-dataset runtime passports record actual retrieval/check timestamps and licence text. Unknown terms remain unknown; public access does not establish unrestricted redistribution.

| Source / official reference | Intended data | Present status | Conditions / owner action |
|---|---|---|---|
| [Organizer starter README](../Datathon2026/alphaforge_starter/README.md) and sources_metadata.csv | Universe, prices, actions, FX, macro | Local files available, extracted 2026-11-13 per metadata | Preserve original data and limitations |
| [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) | Starter and possible on-demand adjusted prices | Starter only; live fetch unverified | T04 verify use/redistribution and pin provider adapter |
| [Bank of Canada Valet](https://www.bankofcanada.ca/valet/docs), [terms](https://www.bankofcanada.ca/terms/) | FX, rates, Canada CPI | Starter rows available; docs URL checked, live adapter not tested | T04 record publication timing and required attribution |
| [FRED terms](https://fred.stlouisfed.org/legal/) | US rates/CPI/unemployment | Starter revised values | T04 distinguish underlying source rights and vintages |
| [Statistics Canada, The Daily](https://www.statcan.gc.ca/dai-quo/index-eng.htm), [Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence) | Release dates of the Canada CPI (reference months 2021-12 to 2026-09) | Loaded in `snap-20261114-sourced`; 58 articles read on 2026-11-14, each 12-month change equal to the stored value | Release date taken as the article's 'Released' date (date only); attribution to Statistics Canada |
| Issuer and project websites (36 pages, listed per row in `data/metadata/asset_themes.csv`) | Support for theme-tag assignments | Pages read on 2026-11-14; short quotes in the justification column | Tags stay team assumptions; no page content is redistributed beyond the short quote |
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Filing metadata and company facts | API documentation checked; integration planned | T09 supplies descriptive user agent, fair-access/backoff and document provenance |
| [GDELT](https://www.gdeltproject.org/) | Article/event index | Planned; quota/latency unverified | T09/T11 batch/cache; terms on underlying stories differ |
| [Wikimedia analytics](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/) | Page-view counts | Planned | T09 verify API dimensions/availability/licence and entity mapping |
| ETF issuer holdings/methodology documents | Look-through and ESG screening method | Planned, per-fund URL required | T09 record effective/publication dates, coverage, redistribution terms |
| [ECCC greenhouse-gas reporting](https://www.canada.ca/en/environment-climate-change/services/climate-change/greenhouse-gas-emissions/facility-reporting.html) | Canadian facility emissions | Planned | T11 verify dataset/version/units/licence/name matching |
| [EPA GHGRP](https://www.epa.gov/ghgreporting) | US facility emissions | Planned | T11 verify fields/year/facility-company link |
| [USGS earthquake feeds](https://earthquake.usgs.gov/earthquakes/feed/) | Earthquakes | Planned | T11 record feed limits/time/coordinates |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Wildfire detections | Planned | T11 verify credentials/coverage/licence before enabling |
| Allow-listed official releases and news | Event context and controversy evidence | Planned | T09 reviews domains, quotes and publisher terms |

## Pitfalls mapped to implementation

| Trap | Treatment | Status required in Sources UI |
|---|---|---|
| CAD/USD mismatch | Convert adjusted levels with historical available FX, show currency | handled after tests |
| Different market/crypto calendars | Master XIU ∩ SPY, crypto sampled; no stale-price fill | handled after tests |
| FX holiday gaps | Last previously available rate only | handled after tests |
| Splits/dividends already adjusted | Use adj_close; corporate actions only annotation | handled after tests |
| CNQ 1.021 factor | Do not apply twice; disclose unverified economic interpretation | disclosed |
| Monthly reference dates | Real release/vintage metadata for replay; assumed lag context only | open until evidence exists |
| FRED revisions / Yahoo back-adjustments | Preserve version/checksums, disclose lack of original vintages | disclosed |
| 2026-selected universe | Survivor/sample selection limitation | disclosed |
| No ESG/news/fundamentals | Missing evidence remains nee; no fictitious clean rating | disclosed |
| ETF sector proxy | Direct-equity rules only, optional partial look-through informational | disclosed |

Do not pre-fill checkedAt with the spec-writing date for an integration that has not run. T04 records source rows, actual network checks and terms separately; a 200 response proves reachability only.
