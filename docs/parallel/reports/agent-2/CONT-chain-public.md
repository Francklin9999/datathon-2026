# Public chain APIs: mempool.space, Blockchain.com, Blockscout

## Mempool.space (SRC-075)

> **Current status (wiring audit, 2026-11-15):** removed. SRC-075 is `removed: owner excluded unselected provider`, and the `BitcoinNetwork` card was gated on a capability id (`mempool`) the backend never reports, so it never rendered. `BitcoinNetwork.tsx`, `chain_public.py`, `chain_routes.py` and `GET /v1/intelligence/chains/bitcoin` (with its `contracts/api.md` row) were deleted. The paragraph below is the original change log.

Implemented `intelligence/chain_public.py`, `intelligence/chain_routes.py`, and the Markets `BitcoinNetwork` card. GET `/v1/intelligence/chains/bitcoin` fetches three fixed, documented Bitcoin mainnet endpoints (recommended fee rates, mempool backlog, tip height). It validates numeric domains and strict JSON, caps bodies, refuses redirects, enforces session rate limits, persists each original response plus normalized result immutably under a session-hashed key, and retains sha256/version/source/retrieval metadata. The three observations fail independently; no failed source value is inferred. A provider estimate does not establish future fees or a security price. Observation/publication time is unknown; availability is the capture instant, not a historical claim. A chain reorganization can change the tip.

Mempool explicitly documents public endpoints and rate limits at https://mempool.space/docs/api/rest. Its software at https://github.com/mempool/mempool has an AGPL licence, but that licence is not assumed to cover hosted API outputs. Because hosted data reuse/storage/display rights were not established, access is gated by explicit operator configuration `APLOMB_MEMPOOL_REUSE_CONFIRMED=1` after reviewing applicable rights; no account or key is requested. The flag is an operator assertion and not legal verification. No automated retries or bulk scrape occur.

A single bounded read-only probe of each endpoint on 2026-11-15 returned HTTP 200 with expected media types and field shapes; no response body was retained or used as evidence of historical availability. An in-memory synthetic smoke check passed for parsing, source isolation, immutable repeat captures, permissions gate and independent malformed-source failure. HTTP check confirmed a session is required and the source fails closed without confirmed rights. These do not validate operational rights or production behavior.

## Blockchain.com (SRC-076) — deferred

Current official https://www.blockchain.com/legal/api-terms says an API key is provided for use and limits copying, storage/caching and third-party disclosure to uses explicitly authorized by its agreement. Current developer documentation also leads to key access. The recorded owner preference defers sources requiring keys or account access; no connector, capture, circumvention or key request was made. This source should not be treated as implemented until its applicable terms, requested use and credentials are independently resolved.

## Blockscout (SRC-074) — deferred

Current official https://docs.blockscout.com/devs/blockscout-api directs users to create an account and generate an API key for its multichain API. Per the recorded owner preference, account/key sources are deferred. Legacy self-hosted explorer instances may have independent policies; no claim is made that any hosted endpoint has the necessary access and reuse rights for this application.

## Integration edits and limitations

`api/app.py` has one router inclusion and `MarketsPage.tsx` has one import/render. The response is branch-local snake_case JSON and should receive shared generated contracts at integration. No deployed infrastructure or feature flags were changed. External permissions and durable backend configuration must be reviewed for the intended deployment. The root worker owns source-matrix reconciliation and final integration.
