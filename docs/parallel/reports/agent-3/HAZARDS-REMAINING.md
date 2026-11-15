# Remaining hazard sources

Two anonymous official distributions now have immutable captures, validated geography, existing World observations consumption, and generated provider passports. No tests or commits were added.

| Directory IDs | Result | Capture and scope |
| --- | --- | --- |
| SRC-187, MASTER-071 | Integrated | `world_copernicus_activation_centroids`: five public EMS activation records, source WKT centroids converted to longitude/latitude. First page of 1,069 records; no pagination claim. |
| SRC-174, MASTER-067 | Integrated through anonymous current distribution | `world_firms_modis_europe`: 39 Terra/Aqua MODIS Collection 6.1 NRT thermal detections in the Europe rolling 24-hour CSV. The area API still requires MAP_KEY; archive authentication remains set aside. |
| SRC-188 | Checked; rights restrict proposed product reuse | Global Flood Database V1 has explicit Creative Commons Attribution Non Commercial 4.0 terms in the Earth Engine dataset catalogue. This does not establish unrestricted reuse in this financial application. No flood rasters, geometries or records were ingested. Earth Engine extraction also needs separate access review. |

The Copernicus [service terms](https://mapping.emergency.copernicus.eu/terms-and-conditions/) explicitly permit reproduction, distribution, communication, and adaptation. They require source attribution, retain EU ownership, exclude restricted products, and distinguish linked third-party information. The selected public service metadata contains no third-party imagery. Attribution is “European Union, Copernicus Emergency Management Service, On-Demand Mapping; activation metadata normalized by Aplomb”. The terms’ citation-guidelines link currently returns 404; the source attribution is retained directly.

Copernicus centroids locate an activation’s mapping area. They do not establish a disaster epicenter, affected boundary, damage or financial impact. Source activation and update timestamps lack timezone; they remain verbatim properties and the displayed observation uses capture time. The source narrative for EMSR932 also names 2025 while activation metadata names 2026. Narratives were omitted rather than resolving that contradiction by assumption.

NASA [data-use guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance) explicitly licenses NASA-led mission data CC0 unless marked otherwise. The selected Terra/Aqua MODIS CSV contains no additional restriction. NASA FIRMS/LANCE, mission, collection and normalization attribution appear in the passport. The actual anonymous download succeeds without credentials despite the active-fire page also describing Earthdata registration for archive and daily distribution routes.

FIRMS thermal detections can include industrial heat and volcanoes. Coordinates are pixel centers; source pixel scan/track dimensions, Kelvin brightness, confidence and instantaneous fire radiative power are retained. No wildfire boundary, damage, burned area or issuer relationship is inferred. Clouds and satellite revisit prevent continuous coverage. The official discovery endpoint lists the selected CSV; the initial guessed legacy VIIRS URL returned 404 and is recorded as a failed probe.

The adapter is `backend/aplomb/world/providers/hazards_remaining.py`. It allows four exact HTTPS URLs, rejects redirects, uses a 500,000-byte cap and 25-second deadline, retries only transient errors, pauses between source and terms requests, validates schema/coordinates/chronology/identity, rejects duplicates and changed rights wording, and publishes through the existing content-addressed snapshot writer.

Immutable versions:

- `world_copernicus_activation_centroids-2026-11-15-e3eab799076179a4`
- `world_firms_modis_europe-2026-11-15-9adbf0f878d38bac`

Each version contains the original payload, checked rights page, normalized observations and manifest with raw/normalized SHA-256. Observation availability is gated at capture; neither source establishes original historical knowledge.

Evidence is in `docs/evidence/parallel/agent-3/hazards-remaining/`. `verification.json` records parser replay against retained payloads, integrity loader counts, generated passport counts, typed World observations visibility, validated coordinates and exclusion before capture. Full HTTP/browser verification is left to the root’s combined runtime check. Shared catalogue, source matrix and status reports were not edited.
