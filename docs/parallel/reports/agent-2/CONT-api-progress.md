# API source progress and sentiment integration

Snapshot on 2026-11-15, after reconciling `SOURCES.csv` against the uncommitted Claude continuation. The assignment's source list has **97 rows**; the same provider can appear in both the Downloads and master catalogues. A case-insensitive count of display names gives 91 distinct strings, not a canonical count of distinct providers or endpoints. All 74 assigned Downloads source IDs and all 23 assigned master-source IDs appear exactly once; there are no missing or extra rows.

| Current matrix category | Rows | Meaning |
|---|---:|---|
| Source-backed or live-captured | 12 | Includes GLEIF and SEC N-PORT indexed captures, Coin Metrics rights-gated live capture and Alternative.me, OpenFIGI, Canada and Ireland registry captures; duplicate rows apply to some providers. Source-backed is not full global coverage. |
| Partial implementation / offline | 24 | Code paths exist but provider access, full source data, UI or live verification remain incomplete. Some are rights-gated. |
| Unimplemented | 0 | Every assigned row now maps to implemented or partial work, a precise external restriction, or a documented deferral. This does not mean all requested capabilities are implemented. |
| Deferred | 46 | Owner decision recorded in prior STATUS: login/API-key or restricted-portal sources deferred. Some deferred rows already contain partial code. |
| Paid sources removed | 3 | Explicit owner decision recorded in prior source matrix. |
| Externally restricted | 12 | Provider terms or access controls prevent acquisition/display without a new entitlement or documented permission. |
| Total | 97 | Row counts are not counts of unique working APIs. |

These numbers describe the matrix at this checkpoint, including the latest chain, GLEIF, ESMA and EBA workers. They are not a completion percentage: source coverage and verification vary. Most SEC and regional endpoints have no successful current live capture. Claude's code has import/type checking but multiple new paths were not exercised against provider data. Do not describe them as live integrations on that basis.

Reconciled mappings include SEC submissions/company facts, concepts, frames and latest filings, latest Form 4/13F/N-CEN filing paths (not their full bulk datasets), indexed SEC N-PORT and pending full capture, GLEIF exact pair and Level 2, Wikidata candidate query and crosswalk, Binance/Bitstamp gated adapters, and rights-only Stooq, iShares, Vanguard, SPDR, Coinbase, Kraken and CoinLore. The matrix preserves required-key and paid-source deferrals from the earlier owner direction. OpenFIGI was successfully captured without a key. CoinPaprika has a no-key API, but its general terms restrict copying, storage and redistribution; rights clarification remains necessary.

## Alternative.me SRC-067

`backend/aplomb/intelligence/sentiment.py` acquires the fixed no-key endpoint `https://api.alternative.me/fng/?limit=30`, validates integer score 0–100, known provider classification, timestamps, duplicate days, JSON shape/size, and uses session-owned immutable source-hash capture in the existing store. `GET /v1/intelligence/bitcoin-sentiment` is a rate-limited router; the Markets card prominently attributes each result to Alternative.me and links its source. Its own [provider description and API terms](https://alternative.me/crypto/fear-and-greed-index/) permit commercial use with prominent adjacent attribution. The provider describes the current index as Bitcoin-only. It is an indicator, not a forecast, trading signal or official market observation. Previous observation timestamps do not establish original publication or revision availability; retrieval is the conservative availability bound.

Live 2026-11-15 retrieval captured 30 rows: `docs/evidence/parallel/agent-2/sentiment/alternative-fng-response.json` and the adjacent normalized file contain SHA-256 and capture time. FastAPI TestClient invoked the real HTTP route successfully (200, 30 rows, attribution present). A bounded synthetic check verified capture idempotency, preservation of first retrieval time and rejection of an invalid score. Ruff passes on the new backend files. Web typecheck reports an unrelated pre-existing `SecExplorer.tsx:48` possibly-undefined error; it reports no `BitcoinSentiment.tsx` errors after the component fix. No full repository gate or new browser test was run for this incremental work.

Shared files: `backend/aplomb/api/app.py` registers the router; `web/src/features/markets/MarketsPage.tsx` mounts the sentiment card. New wire response is currently local to this UI and must be included in shared contract generation during integration.

## Canada and Ireland corporate registries

`intelligence/registries.py` implements exact corporate-number lookups against the public Corporations Canada legacy JSON endpoint and Ireland CRO Open Data CKAN datastore. The Ireland open dataset is CC BY 4.0; the federal dataset is Open Government Licence – Canada. Both require attribution, prominently shown in the Markets `CompanyRegistry` card. Records identify registry entities, never a security or issuer crosswalk. Capture time is the conservative availability boundary, and source responses are retained per session with SHA-256. Canada excludes provincial/territorial and certain financial corporations. The Ireland Open Data endpoint is separate from CRO Open Services, which requires signup and signed terms. Official references: https://ised-isde.canada.ca/site/corporations-canada/en/accessing-federal-corporation-json-datasets and https://opendata.cro.ie/dataset/companies .

Live 2026-11-15 requests and FastAPI route checks passed for exact Canada ID 1007 and Ireland ID 279457; raw and normalized evidence is under `docs/evidence/parallel/agent-2/registries/`. Repeated identical captures retain first retrieval time; Ruff and web typecheck passed.

## DeFi source status

`CONT-defi-public.md` records an exact-pool DEX Screener implementation with an in-memory live probe and an operator rights gate. DefiLlama code exists but provider permission is required before copying, retention or display, so the two associated rows are marked externally restricted. GeckoTerminal storage rights depend on a paid plan and were deferred under the existing owner direction. No DeFi response from these sources is claimed as a retained live capture.

## Latest source additions

- GLEIF Golden Copy: official metadata and one intraday delta retained with exact LEI lookup and timestamp/hash provenance. The roughly 486 MB full file was not imported; an absent LEI in a delta proves nothing about the full population.
- ESMA registers: real exact-LEI HTTP capture with five BNP authorization records, immutable session capture and UI. These records do not by themselves establish investment exposure.
- EBA 2025 transparency: retained full market-risk CSV, 23,817 rows for four periods, exact LEI query and UI. Other exercise datasets remain outside coverage.
- mempool.space: mainnet fees/backlog/tip adapter with independently failing fields, capture and UI; successful read-only probes were not retained, and hosted-source reuse rights remain unverified, so runtime is gated.
- Blockscout's documented multichain service and Blockchain.com require accounts/API keys under their current access terms and remain deferred per owner instruction.

Zero rows labelled `unimplemented` means every row has been triaged, not that every source is integrated or the platform is complete. In particular, the 46 deferred, 3 removed, 12 externally restricted and 24 partial/offline rows need the work, source access or authorization stated in the matrix. Several sources represented by code still need proper end-to-end validation and licensing review before use.
