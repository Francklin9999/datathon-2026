# Current adapter dispositions

The owner requested that partial/offline adapters either become working, be removed if paid, or be placed aside with an exact access requirement. This report supersedes the earlier checkpoint counts in CONT reports.

| Disposition | Catalogue rows |
|---|---:|
| Working demonstrated catalogue rows | 22 |
| Aside: signup, rights, portal or engineering work | 52 |
| Removed sources (SEC, paid or unavailable signup) | 23 |
| Total assigned rows | 97 |

Rows duplicate some providers across the Downloads and original master catalogues. The original sixteen working rows represented twelve supported source workflows: GLEIF exact/Level-2 API, GLEIF Golden Copy intraday delta, Canadian federal registry, Ireland CRO open data, ESMA authorizations, EBA 2025 market risk, Wikidata exact-ISIN candidates, OpenFIGI exact mappings, DEX Screener exact pools, Alternative.me sentiment, Binance Vision daily archives, and Coin Metrics Community daily observations.

Working means the declared bounded workflow succeeded against actual provider data through its acquisition/validation/storage path. It does not mean every endpoint, country, period or product offered by that provider is implemented. Natural coverage limits remain stated. Local-only noncommercial research defaults enable the three appropriately licensed research sources; AWS and public deployments inherit no permission from this setting. Explicit environment opt-outs prevail.

No partial/offline sources are presented as active Markets controls. The source availability API and Markets list separate active workflows, preserved evidence, sources awaiting access/permission, and removed paid feeds. SEC company/filing/fund/PIT sources are removed from active coverage by owner instruction after HTTP403. That is an access refusal, not a signup requirement, and no bypass was attempted. The indexed N-PORT example remains audit evidence only and is no longer advertised in Markets. Japan remains account-gated. Korea OpenDART is now configured and live-verified; see CREDENTIALS.md. Stooq, issuer holdings and hosted feeds with unresolved rights remain aside without dead source forms.

Evidence: source-specific CONT reports; SOURCES.csv; public-working/http-results.json; security/identity-live-http-2026-11-15.json; security/openfigi-http.json; registry/sentiment/EU/Golden Copy captures; sec-live-status.json under docs/evidence/parallel/agent-2/. Paid removals are Databento, Intrinio, Financial Datasets and GeckoTerminal storage.

Credential continuation: five supplied accounts were saved only in ignored local configuration and verified with real requests. Six previously aside catalogue rows are now working (22 working, 52 aside, 23 removed of 97); OpenDART is an additional regional workflow outside those catalogue rows. See [CREDENTIALS.md](CREDENTIALS.md) for operations, free quota limitations and signup links. Financial statement period ends are never treated as original publication times.

Owner access cleanup: all 17 SEC-refused catalogue rows are removed from active coverage and signup requests; historical audit data remains. Glassnode is excluded as paid, Flipside has no verified current signup, and Blockchain.com is corrected to a no-key engineering task. Current total: 22 working, 52 aside, 23 removed (97 assigned catalogue rows). See [ACCESS-REQUESTS.md](ACCESS-REQUESTS.md) for deduplicated official links and precise owner versus engineering actions.
