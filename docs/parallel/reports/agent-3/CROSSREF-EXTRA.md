# Crossref bibliographic metadata capture

`SRC-236` is available anonymously without registration, payment or a key. Provider `backend/aplomb/world/providers/crossref_extra.py` captures one projected page of five journal article metadata records matching the title query `climate change`, with publication dates restricted to 2024. The projection contains only DOI, title, publication date parts and type. Abstracts, full text, authors, affiliations and references are excluded from both raw and normalized capture.

Dataset ID: `world_crossref_climate_bibliography`. Category: `research`. Runtime immutable version: `world_crossref_climate_bibliography-2026-11-15-41a6b01a19d3663d`. Captured at `2026-11-15T17:30:17Z`. Five normalized observations and one 957-byte raw API response are stored under `backend/aplomb/world/bundle/providers/`. Normalized SHA-256: `41a6b01a19d3663daaa515c61be38f83d22cd04f904a5c0771b50316cb88b39e`.

## Access, rights and request limits

The official [REST API documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), checked 2026-11-15, states: “No sign-up is required to use the REST API, and almost none of the metadata is subject to copyright, and you may use it for any purpose. Some abstracts contained in the metadata may be subject to copyright by publishers or authors.” The bibliographic projection excludes the specifically identified abstract caveat. This permission does not establish rights to linked publications, which are not fetched. The website footer's CC BY 4.0 statement is not applied as a licence for underlying publications or this metadata.

Official [access and authentication documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) explicitly permits public access with “No authentication or identification.” It recommends a contact email for the optional polite pool and identifies the request limits in response headers. Its table lists public rate 5/concurrency 1 and polite rate 10/concurrency 3; the live response is stricter: `x-api-pool: public-array`, `x-rate-limit-limit: 1`, `x-rate-limit-interval: 1s`, `x-concurrency-limit: 1`. These actual headers are retained in the manifest.

The collector makes one request at a time, identifies the script with a User-Agent, bounds the response at 100,000 bytes, rejects redirects, and retries transient failures at most three times with delays of at least two seconds. Numeric `Retry-After` up to 60 seconds is honored; longer delays terminate the capture. No invented email is used. Saved immutable captures provide a local cache and runtime reads do not call the API. Metadata Plus is a paid option and is not used.

## Meaning and verification

Titles describe deposited research records; relevance ranking does not prove a subject classification, scientific validity, geographic exposure or company relationship. Country and display coordinates are unset, including for titles naming countries. Each observation links to its DOI. Publication date parts retain source precision, including month-only dates; `observedAt` and `publishedAt` remain unset. `availableAt` is capture time because historical availability is unproven.

The live anonymous collector completed successfully. Manual inspection validated five unique rows, raw and normalized SHA-256 checksums, date parts and absent geographical assertions. No tests were added or run. Reproduce using `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.crossref_extra`.

No shared catalog, service, passport or ledger registration was edited. Coverage is explicitly incomplete: one first page of five records, no pagination. Future captures may return different relevance rankings.
