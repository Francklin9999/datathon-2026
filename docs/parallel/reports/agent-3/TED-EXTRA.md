# TED published procurement notice metadata

`SRC-145` is registered for runtime use. Provider: `backend/aplomb/world/providers/ted_extra.py`. Dataset: `world_ted_published_notice_metadata`, category `trade`. The anonymous [Search API](https://api.ted.europa.eu/v3/notices/search) accepted a POST without a key, account, login, or payment. It returned five projected notices from the first page of a fixed 2026-11-01 through 2026-11-15 publication window; the API reported 35,200 matching notices. This is an incomplete sample, with latest versions selected and upstream ordering among tied dates.

Immutable runtime capture: `backend/aplomb/world/bundle/providers/world_ted_published_notice_metadata-2026-11-15-6aca3e8f62dda9af`. Captured `2026-11-15T17:30:36Z`; normalized SHA-256 `6aca3e8f62dda9af66aea5a02889b5e621db3024a7cf77928477a810c1ded06e`. Four raw responses total 729,200 bytes: projected search response, legal notice, official Search API documentation, and official OpenAPI specification. The complete POST body is retained in the manifest.

The projection requests only `publication-number`, `publication-date`, and `buyer-country`. The API also supplies notice links, retained in the raw response. Normalized records use the source English permalink. No documents are followed. Captured IDs are `789917-2026` (SWE), `790513-2026` (BEL), `791560-2026` (ESP), `792113-2026` (DEU), and `792498-2026` (NLD). All report publication date `2026-11-13+01:00`. This is a source date with timezone offset, not a precise publication instant; its verbatim value and day precision are preserved in properties. `publishedAt` and `observedAt` remain unset, and `availableAt` is capture time.

Country represents the explicitly reported buyer country, not the place of contract performance or an affected asset. Coordinates remain unset. No buyer names, winner names, contacts, tender text, amounts, companies, securities, awards, realized spending, or financial links are requested or inferred.

## Exact rights and access evidence

The official [TED legal notice](https://ted.europa.eu/en/legal-notice), retrieved on 2026-11-15, states: “Unless otherwise noted, the procurement notices published in the Supplement to the Official Journal of the European Union can be freely reused, for commercial or non-commercial purposes.” It separately states that “SIMAP’s system metadata is dedicated to the public domain” under CC0 1.0. The captured notice facts rely on the explicit published-notice reuse permission; this report does not equate all tender content with system metadata or assign a blanket CC0 licence to it.

The same legal notice licenses SIMAP editorial content, including TED Developer Docs, under CC BY 4.0, requiring credit and indication of changes. Raw legal/documentation evidence is saved unchanged and attributed to the European Union, Publications Office, TED; parsed notice metadata is explicitly identified as projected and normalized by Aplomb. Third-party works, identifiable private individuals, logos, and industrial-property rights carry exclusions or may need additional clearance. This bounded fact projection avoids those content classes.

The official [Search API documentation](https://docs.ted.europa.eu/api/latest/search.html) says the API “does not require authentication, making it openly accessible to any system or user.” The [OpenAPI specification](https://api.ted.europa.eu/api-v3.yaml) describes the public read-only published-notice search, its projected fields, pagination and scope. Authentication for unpublished notice submission is outside this provider.

## Manual verification

Live collection succeeded. The standard snapshot loader verified normalized and raw checksums, loaded five unique rows, and confirmed that coordinates and `publishedAt` are unset. A pre-capture as-of query returned no TED rows. No tests were added or run.

Reproduce: `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.ted_extra --directory backend/aplomb/world/bundle/providers`. Transport fixes its endpoint allowlist, rejects redirects, caps each response at 2 MB, uses a 25-second timeout/read deadline and up to three attempts for transient errors, and never requests another page. Runtime registration now includes the catalog, datastore and world passports, trade observations, the provider refresh dispatcher (`--source ted`), and the source ledger.

## Runtime registration verification

The `/v1/datasets` list and individual dataset route return an `in_use` passport with five rows and incomplete pagination coverage. The trade observations route returns all five notices with procurement-specific summaries and European Union Publications Office attribution, source-reported buyer country, no location or geometry, no publication timestamp, and `capture_only` time basis. The SWE country filter returns one TED notice; an as-of query for 2026-11-14 returns zero. The saved manifest SHA-256 remains unchanged. Its missing `scope` is handled by a passport fallback; future captures explicitly include the bounded scope. Contract generation and `npm run typecheck` succeeded. Verification used a temporary smoke script; no tests were added.
