# Original master-source catalogue reconciliation

The 243-row Downloads catalogue is an expanded candidate directory, not an exhaustive transcription of the pasted master specification. This table separately assigns **all 99 source rows in master sections 13.1–13.9**, including repeated providers used in different sections. Both tables are binding checklists. Exact URL correspondence is a catalogue cross-reference, never proof of source integration or rights. Different URLs under one provider may describe additional datasets and must be evaluated explicitly.

Additional explicit entries include the organizer starter dataset (Agent 1), Coin Metrics Community (Agent 2), SEC structured-disclosure RSS/Data Library (Agent 2), STLFSI4 (Agent 1 using Agent 2’s FRED adapter), specific PortWatch layers/GDELT geographic data/GEM oil-gas and coal trackers/USGS Minerals 2026 release (Agent 3). Source owners coordinate shared provider adapters without duplicating bulk fetches. Wikidata is Agent 2 acquisition; Agent 3 consumes its documented geographic metadata.

| Master ID | Section | Source / endpoint | Owner | Exact Downloads URL rows |
|---|---|---|---|---|
| MASTER-001 | 13.1 | Organizer starter dataset: `Datathon2026/alphaforge_starter` | Agent 1 | Additional endpoint/dataset |
| MASTER-002 | 13.1 | [Alpha Vantage](https://www.alphavantage.co/documentation/) | Agent 2 | SRC-001 |
| MASTER-003 | 13.1 | [Twelve Data](https://twelvedata.com/pricing) | Agent 2 | Additional endpoint/dataset |
| MASTER-004 | 13.1 | [Nasdaq Data Link](https://docs.data.nasdaq.com/v1.0) | Agent 2 | Additional endpoint/dataset |
| MASTER-005 | 13.1 | [CoinGecko](https://www.coingecko.com/en/api/pricing) | Agent 2 | Additional endpoint/dataset |
| MASTER-006 | 13.1 | [Coin Metrics Community](https://docs.coinmetrics.io/packages/coin-metrics-community-data) | Agent 2 | Additional endpoint/dataset |
| MASTER-007 | 13.1 | [DefiLlama](https://github.com/DefiLlama/api-docs) | Agent 2 | Additional endpoint/dataset |
| MASTER-008 | 13.1 | [Binance Public Data](https://github.com/binance/binance-public-data) | Agent 2 | Additional endpoint/dataset |
| MASTER-009 | 13.1 | [OCC](https://www.theocc.com/market-data) | Agent 1 | SRC-025 |
| MASTER-010 | 13.1 | [CFTC Commitments of Traders](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm) | Agent 1 | SRC-028 |
| MASTER-011 | 13.1 | [FINRA Short Sale Volume](https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data) | Agent 1 | SRC-026 |
| MASTER-012 | 13.1 | [Fama–French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | Agent 1 | SRC-022 |
| MASTER-013 | 13.1 | [US Treasury Yield Curves](https://home.treasury.gov/resource-center/data-chart-center/interest-rates) | Agent 1 | SRC-032 |
| MASTER-014 | 13.1 | [NY Fed Markets Data](https://markets.newyorkfed.org/static/docs/markets-api.html) | Agent 1 | SRC-033;SRC-101 |
| MASTER-015 | 13.1 | [St Louis Financial Stress Index STLFSI4](https://fred.stlouisfed.org/series/STLFSI4) | Agent 1 | Additional endpoint/dataset |
| MASTER-016 | 13.2 | [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Agent 2 | SRC-034;SRC-035;SRC-036;SRC-037 |
| MASTER-017 | 13.2 | [SEC Structured Disclosure RSS](https://www.sec.gov/data-research/structured-data/structured-disclosure-rss-feeds) | Agent 2 | Additional endpoint/dataset |
| MASTER-018 | 13.2 | [SEC Insider Transactions](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets) | Agent 2 | SRC-042 |
| MASTER-019 | 13.2 | [SEC Form 13F](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets) | Agent 2 | SRC-039 |
| MASTER-020 | 13.2 | [SEC Form N-PORT](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets) | Agent 2 | SRC-040 |
| MASTER-021 | 13.2 | [SEC Form N-CEN](https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets) | Agent 2 | SRC-041 |
| MASTER-022 | 13.2 | [SEC Data Library](https://www.sec.gov/data-research/sec-markets-data) | Agent 2 | Additional endpoint/dataset |
| MASTER-023 | 13.2 | [GLEIF LEI API](https://www.gleif.org/en/lei-data/gleif-api/) | Agent 2 | SRC-043 |
| MASTER-024 | 13.2 | [Wikidata Query Service](https://query.wikidata.org/) | Agent 2 | SRC-057 |
| MASTER-025 | 13.2 | [iShares](https://www.ishares.com/) | Agent 2 | SRC-054 |
| MASTER-026 | 13.2 | [State Street SPDR](https://www.ssga.com/) | Agent 2 | SRC-056 |
| MASTER-027 | 13.2 | [SEDAR+](https://www.sedarplus.ca/) | Agent 2 | SRC-048 |
| MASTER-028 | 13.3 | [FRED](https://fred.stlouisfed.org/docs/api/fred/) | Agent 2 | SRC-086;SRC-087 |
| MASTER-029 | 13.3 | [ALFRED](https://fred.stlouisfed.org/) | Agent 2 | Additional endpoint/dataset |
| MASTER-030 | 13.3 | [Bank of Canada Valet](https://www.bankofcanada.ca/valet/docs/) | Agent 1 | SRC-088 |
| MASTER-031 | 13.3 | [Statistics Canada](https://www.statcan.gc.ca/en/microdata/api) | Agent 3 | Additional endpoint/dataset |
| MASTER-032 | 13.3 | [World Bank Indicators](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api) | Agent 3 | SRC-089 |
| MASTER-033 | 13.3 | [IMF Data](https://data.imf.org/en/Resource-Pages/IMF-API) | Agent 3 | SRC-091 |
| MASTER-034 | 13.3 | [OECD API](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html) | Agent 3 | SRC-092 |
| MASTER-035 | 13.3 | [ECB SDMX](https://data.ecb.europa.eu/help/getting-data-web-services-sdmx-0) | Agent 3 | SRC-093 |
| MASTER-036 | 13.3 | [BIS Statistics](https://stats.bis.org/api-doc/v2/) | Agent 3 | SRC-094 |
| MASTER-037 | 13.3 | [NY Fed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr) | Agent 1 | Additional endpoint/dataset |
| MASTER-038 | 13.3 | [US EIA](https://www.eia.gov/opendata/documentation.php) | Agent 3 | SRC-190 |
| MASTER-039 | 13.3 | [JODI Oil](https://www.jodidata.org/oil/database/data-downloads.aspx) | Agent 3 | SRC-198 |
| MASTER-040 | 13.3 | [Ember Yearly Electricity](https://ember-energy.org/data/yearly-electricity-data/) | Agent 3 | Additional endpoint/dataset |
| MASTER-041 | 13.3 | [US Treasury Fiscal Data](https://fiscaldata.treasury.gov/api-documentation/) | Agent 1 | SRC-100 |
| MASTER-042 | 13.4 | [GDELT DOC 2.0](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) | Agent 3 | SRC-115 |
| MASTER-043 | 13.4 | [GDELT Event/GKG](https://gdeltproject.org/data.html) | Agent 3 | SRC-116;SRC-117;SRC-118;SRC-234 |
| MASTER-044 | 13.4 | [GDELT Geographic Graph](https://gdeltproject.org/data.html) | Agent 3 | SRC-116;SRC-117;SRC-118;SRC-234 |
| MASTER-045 | 13.4 | [SEC Latest Filings RSS](https://www.sec.gov/about/rss-feeds) | Agent 2 | SRC-038 |
| MASTER-046 | 13.4 | [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm) | Agent 3 | SRC-104 |
| MASTER-047 | 13.4 | [ECB RSS](https://www.ecb.europa.eu/home/html/rss.en.html) | Agent 3 | SRC-105 |
| MASTER-048 | 13.4 | [Canada Gazette RSS](https://gazette.gc.ca/rss/sc-rb-eng.html) | Agent 3 | SRC-143 |
| MASTER-049 | 13.4 | [Congress.gov](https://api.congress.gov/) | Agent 3 | SRC-140 |
| MASTER-050 | 13.4 | [Guardian Open Platform](https://open-platform.theguardian.com/access/) | Agent 3 | SRC-119 |
| MASTER-051 | 13.4 | [ReliefWeb](https://apidoc.reliefweb.int/) | Agent 3 | SRC-132 |
| MASTER-052 | 13.4 | [UCDP](https://ucdp.uu.se/downloads/) | Agent 3 | SRC-130 |
| MASTER-053 | 13.4 | [V-Dem](https://v-dem.net/data/the-v-dem-dataset/) | Agent 3 | SRC-146 |
| MASTER-054 | 13.4 | [UN Sanctions](https://main.un.org/securitycouncil/en/sanctions/un-sc-consolidated-list) | Agent 3 | SRC-137 |
| MASTER-055 | 13.4 | [OFAC](https://ofac.treasury.gov/sanctions-list-service) | Agent 3 | SRC-136 |
| MASTER-056 | 13.4 | [Google Trends API](https://developers.google.com/search/apis/trends) | Agent 3 | SRC-128;SRC-230 |
| MASTER-057 | 13.4 | [NewsAPI](https://newsapi.org/pricing) | Agent 3 | SRC-120 |
| MASTER-058 | 13.5 | [Natural Earth](https://www.naturalearthdata.com/downloads/) | Agent 3 | SRC-153 |
| MASTER-059 | 13.5 | [geoBoundaries](https://www.geoboundaries.org/api.html) | Agent 3 | SRC-154 |
| MASTER-060 | 13.5 | [OpenStreetMap](https://www.openstreetmap.org/copyright) | Agent 3 | Additional endpoint/dataset |
| MASTER-061 | 13.5 | [Nominatim](https://operations.osmfoundation.org/policies/nominatim/) | Agent 3 | Additional endpoint/dataset |
| MASTER-062 | 13.5 | [Wikidata SPARQL](https://query.wikidata.org/) | Agent 2 | SRC-057 |
| MASTER-063 | 13.5 | [NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/access-basics/) | Agent 3 | SRC-157 |
| MASTER-064 | 13.5 | [OurAirports](https://ourairports.com/data/) | Agent 3 | SRC-215 |
| MASTER-065 | 13.6 | [NASA EONET](https://eonet.gsfc.nasa.gov/docs/v3) | Agent 3 | SRC-173 |
| MASTER-066 | 13.6 | [USGS Earthquake GeoJSON](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) | Agent 3 | SRC-171 |
| MASTER-067 | 13.6 | [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/usfs/api/area/) | Agent 3 | Additional endpoint/dataset |
| MASTER-068 | 13.6 | [GDACS](https://www.gdacs.org/gdacsapi/swagger/index.html) | Agent 3 | SRC-134;SRC-175 |
| MASTER-069 | 13.6 | [NOAA NHC](https://www.nhc.noaa.gov/gis/rss.php) | Agent 3 | Additional endpoint/dataset |
| MASTER-070 | 13.6 | [NOAA AviationWeather](https://aviationweather.gov/data/api/) | Agent 3 | SRC-216 |
| MASTER-071 | 13.6 | [Copernicus Emergency Management](https://emergency.copernicus.eu/data/) | Agent 3 | Additional endpoint/dataset |
| MASTER-072 | 13.6 | [World Bank Climate Knowledge Portal](https://climateknowledgeportal.worldbank.org/download-data) | Agent 3 | SRC-228 |
| MASTER-073 | 13.6 | [NASA POWER](https://data.nasa.gov/dataset/prediction-of-worldwide-energy-resources-power) | Agent 3 | Additional endpoint/dataset |
| MASTER-074 | 13.7 | [IMF PortWatch](https://portwatch.imf.org/) | Agent 3 | SRC-203 |
| MASTER-075 | 13.7 | [PortWatch Ports Layer](https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/PortWatch_ports_database/FeatureServer) | Agent 3 | SRC-204 |
| MASTER-076 | 13.7 | [PortWatch Chokepoints](https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0) | Agent 3 | SRC-205 |
| MASTER-077 | 13.7 | [UN Comtrade](https://comtradeplus.un.org/en/api-docs) | Agent 3 | SRC-112;SRC-206 |
| MASTER-078 | 13.7 | [Danish Maritime Authority AIS](https://www.dma.dk/safety-at-sea/navigational-information/ais-data) | Agent 3 | SRC-210 |
| MASTER-079 | 13.7 | [NOAA MarineCadastre AIS](https://github.com/NOAA-OCM/ocm-marinecadastre-ais-vessel-traffic) | Agent 3 | Additional endpoint/dataset |
| MASTER-080 | 13.7 | [Global Fishing Watch](https://api-doc.globalfishingwatch.org/our-apis/documentation/) | Agent 3 | Additional endpoint/dataset |
| MASTER-081 | 13.7 | [Global Energy Monitor Oil/Gas](https://globalenergymonitor.org/projects/global-oil-gas-extraction-tracker) | Agent 3 | Additional endpoint/dataset |
| MASTER-082 | 13.7 | [Global Energy Monitor Coal](https://globalenergymonitor.org/projects/global-coal-plant-tracker) | Agent 3 | Additional endpoint/dataset |
| MASTER-083 | 13.7 | [WRI Power Plants](https://datasets.wri.org/datasets/global-power-plant-database) | Agent 3 | SRC-196 |
| MASTER-084 | 13.7 | [Ember Monthly Electricity](https://ember-energy.org/data/monthly-electricity-data/) | Agent 3 | Additional endpoint/dataset |
| MASTER-085 | 13.7 | [JODI Oil Database](https://www.jodidata.org/oil/database/data-downloads.aspx) | Agent 3 | SRC-198 |
| MASTER-086 | 13.7 | [USGS Minerals 2026 release](https://www.usgs.gov/data/mineral-commodity-summaries-2026-data-release) | Agent 3 | Additional endpoint/dataset |
| MASTER-087 | 13.7 | [FAOSTAT](https://www.fao.org/faostat/en/) | Agent 3 | SRC-200 |
| MASTER-088 | 13.7 | [USDA PSD](https://fas.usda.gov/psdonline) | Agent 3 | Additional endpoint/dataset |
| MASTER-089 | 13.7 | [ENTSO-E Transparency](https://transparency.entsoe.eu/) | Agent 3 | SRC-193 |
| MASTER-090 | 13.8 | [ECCC Facility Emissions](https://open.canada.ca/data/en/dataset/a8ba14b7-7f23-462a-bdbb-83b0ef629823) | Agent 3 | SRC-218 |
| MASTER-091 | 13.8 | [EPA ECHO](https://echo.epa.gov/tools/data-downloads) | Agent 3 | SRC-220 |
| MASTER-092 | 13.8 | [EPA Envirofacts](https://www.epa.gov/enviro/envirofacts-data-service-api) | Agent 3 | SRC-219 |
| MASTER-093 | 13.8 | [OpenAQ](https://docs.openaq.org/about/about) | Agent 3 | Additional endpoint/dataset |
| MASTER-094 | 13.8 | [Wikimedia Pageviews](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/) | Agent 3 | SRC-126;SRC-229 |
| MASTER-095 | 13.8 | [Ember Yearly Electricity](https://ember-energy.org/data/yearly-electricity-data/) | Agent 3 | Additional endpoint/dataset |
| MASTER-096 | 13.8 | [Google Trends](https://developers.google.com/search/apis/trends) | Agent 3 | SRC-128;SRC-230 |
| MASTER-097 | 13.9 | [OpenSky REST API](https://opensky-network.org/about/faq) | Agent 3 | Additional endpoint/dataset |
| MASTER-098 | 13.9 | [OurAirports](https://ourairports.com/data/) | Agent 3 | SRC-215 |
| MASTER-099 | 13.9 | [NOAA AviationWeather](https://aviationweather.gov/data/api/) | Agent 3 | SRC-216 |
