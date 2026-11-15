# Connected research accounts

Credentials supplied by the owner are stored only in the ignored local `.env` (mode 0600), never in git, source captures, logs or this report. Restart the local API with `scripts/dev_api.py --port 8102 --no-reload` from this worktree to load it. Markets → Connected market data uses server-side keys; Korea is under regional research. Keys and rights flags are listed without values in `.env.example`.

| Source | Verified live operation | Official account / credentials site |
|---|---|---|
| Finnhub | Company profile, exact returned ticker | https://finnhub.io/register |
| OpenDART | Samsung corporate code 00126380: 2,823 filings across all 29 pages; fiscal 2025 financial statements, 229 lines; 2,661 ownership disclosures | https://opendart.fss.or.kr/intro/main.do |
| Alpha Vantage | Provider quote HTTP 200. Company overview and annual/quarterly income, balance and cash-flow operations implemented, but additional live calls returned the provider free quota limit | https://www.alphavantage.co/support/#api-key |
| Tiingo | Real supported US equity metadata and dated adjusted daily prices | https://www.tiingo.com/account/api/token |
| Twelve Data | Thirty AAPL daily bars, exact MIC XNGS, USD | https://twelvedata.com/docs |

Alpha statement controls preserve fiscal periods, currency, missing values and negative numbers. Original publication/revision dates are unknown and cannot establish historical replay eligibility before capture. A working quote does not prove financial statement entitlement. No paid upgrade or paid endpoint fallback was performed.

Twelve Data requires the provider's precise MIC: AAPL returned XNGS; XNAS was rejected. Provider ticker/name/exchange labels do not establish an ISIN or global issuer identity. Tiingo account use does not grant public redistribution rights.

OpenDART filings complete the requested interval or fail explicitly above 5,000 filings or if pagination changes. ESMA completes exact-LEI pages up to 2,000 records with duplicate/count checks. These are bounded complete queries, not global bulk ingestion.

Remaining access requirements and official sites are recorded for every assigned row in SOURCES.csv. Japan J-Quants is separate: https://jpx-jquants.com/en/spec/quickstart . SEC currently refuses the configured project contact with HTTP403; a new API key is not the remedy. FRED/ALFRED require both an API account and applicable rights under https://fred.stlouisfed.org/legal/ .

Current catalogue: 22 working rows, 52 aside, 23 removed, total 97. OpenDART is additional to those catalogue rows. The full global specification remains incomplete as mapped in REQUIREMENTS.md; this continuation does not claim otherwise.

Evidence: docs/evidence/parallel/agent-2/credentialed-live/ .

Owner access cleanup: all 17 SEC-refused catalogue rows are removed from active coverage and signup requests; historical audit data remains. Glassnode is excluded as paid, Flipside has no verified current signup, and Blockchain.com is corrected to a no-key engineering task. Current total: 22 working, 52 aside, 23 removed (97 assigned catalogue rows). See [ACCESS-REQUESTS.md](ACCESS-REQUESTS.md) for deduplicated official links and precise owner versus engineering actions.
