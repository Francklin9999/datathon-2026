# Current adapter dispositions

The owner requested that partial/offline adapters either become working, be removed if paid, or be placed aside with an exact access requirement. This report supersedes the earlier checkpoint counts in CONT reports.

| Disposition | Catalogue rows |
|---|---:|
| Working demonstrated workflows | 16 |
| Aside: signup, contact, access or permission required | 77 |
| Removed paid sources | 4 |
| Total assigned rows | 97 |

Rows duplicate some providers across the Downloads and original master catalogues. Sixteen working rows represent twelve supported source workflows: GLEIF exact/Level-2 API, GLEIF Golden Copy intraday delta, Canadian federal registry, Ireland CRO open data, ESMA authorizations, EBA 2025 market risk, Wikidata exact-ISIN candidates, OpenFIGI exact mappings, DEX Screener exact pools, Alternative.me sentiment, Binance Vision daily archives, and Coin Metrics Community daily observations.

Working means the declared bounded workflow succeeded against actual provider data through its acquisition/validation/storage path. It does not mean every endpoint, country, period or product offered by that provider is implemented. Natural coverage limits remain stated. Local-only noncommercial research defaults enable the three appropriately licensed research sources; AWS and public deployments inherit no permission from this setting. Explicit environment opt-outs prevail.

No partial/offline sources are presented as active Markets controls. The source availability API and Markets list separate active workflows, preserved evidence, sources awaiting access/permission, and removed paid feeds. SEC company/filing/fund/PIT controls are set aside after a fresh actual HTTP403 using existing project contact configuration. That is an access refusal, not a signup requirement, and no bypass was attempted. The real partial indexed N-PORT example is preserved evidence, not a working live SEC adapter. Japan/Korea key-required routes remain inactive until approved account access exists. Stooq, issuer holdings and hosted feeds with unresolved rights remain aside without dead source forms.

Evidence: source-specific CONT reports; SOURCES.csv; public-working/http-results.json; security/identity-live-http-2026-11-15.json; security/openfigi-http.json; registry/sentiment/EU/Golden Copy captures; sec-live-status.json under docs/evidence/parallel/agent-2/. Paid removals are Databento, Intrinio, Financial Datasets and GeckoTerminal storage.
