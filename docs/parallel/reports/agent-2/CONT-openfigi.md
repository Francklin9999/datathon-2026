# OpenFIGI public API continuation

Reviewed Claude's uncommitted continuation and preserved it. The source matrix had deferred OpenFIGI because of a presumed key requirement; official documentation explicitly permits unauthenticated mapping requests (25 requests/minute), so the no-key source is implementable within the recorded owner preference.

Implemented `intelligence/openfigi.py`, `GET /v1/intelligence/openfigi?isin=&mic=`, and Markets `OpenFigi.tsx`. The caller supplies only an exact checksum-valid ISIN and optional syntactically valid MIC. The provider request is a single fixed `ID_ISIN` mapping job, with unlisted equities included. No name/ticker query, CUSIP input, credentials or arbitrary URL/query is accepted. Requests are bounded to 750 KB, 12 seconds, no redirects, no retries, four requests per session per minute plus per-process spacing. Provider failures and malformed identifiers remain explicit errors.

Every returned instrument/composite/share-class FIGI passes the provider's documented character and check-digit rules. Multiple FIGIs remain distinct; the response does not echo the input ISIN, so the exact one-job request plus response position establishes the provider assertion. MIC is a requested filter, never invented from provider `exchCode`. Original response bytes and normalized results are stored immutably in the owning session's existing cache, keyed by query and SHA-256. Identical acquisitions reuse original capture metadata. Instrument FIGIs are published to the existing session crosswalk as direct **provider identifier mappings**, not legal-issuer or ownership proof. Captures lack original publication/lifecycle evidence and are visible only after retrieval.

Live source observation: exact Apple ISIN `US0378331005` without MIC returned 553 mappings; all FIGI check digits validated and 553 crosswalk assertions persisted during a memory-store smoke using the actual captured response. A separate `XNAS` filter returned no mapping. This is preserved as a bounded negative result, not silently retried without the user's filter by the runtime. API/UI displays up to fifty of the returned mappings and reports the total. Existing source-repository bounds still apply.

Evidence:
- `docs/evidence/parallel/agent-2/security/openfigi-aapl-all-response.json` (actual response, SHA-256 `1983306b0cf69aa40dc28e6bae87d17c05870e8ffa2a1be505672276c2bf150c`)
- `openfigi-aapl-all-result.json` (normalized result and assertion IDs)
- `openfigi-aapl-response.json`, `openfigi-aapl-result.json` (actual MIC-filter negative result)

Primary references checked 2026-11-15:
- https://www.openfigi.com/api/documentation (keyless access, job/results semantics and quotas)
- https://www.openfigi.com/docs/terms-of-service (FIGI public-domain dedication and disclaimers)
- https://www.openfigi.com/about/faq (open associated metadata / licence)
- https://www.openfigi.com/docs/figi-check-digit.pdf (character and check-digit calculation)

No cloud mutations or deployment. Full worldwide listing lifecycle/issuer coverage is not established by this API. No new broad test suite was run; verification was a focused actual source acquisition, schema/checksum validation and repository publication.
