# Local selected credentials

Fifteen distinct supplied accounts are saved in ignored local `.env`, mode0600; values never appear in tracked files. See ACCESS-REQUESTS.md for the selected accounts and exact supported operations. Restart the local worktree API using `scripts/dev_api.py --port 8102 --no-reload` to load the configuration; Markets → Connected market data and regional research expose the real workflows. No deployment occurred.

New server variables: APLOMB_FMP_KEY, APLOMB_EODHD_KEY, APLOMB_MASSIVE_KEY, APLOMB_MARKETSTACK_KEY, APLOMB_COINMARKETCAP_KEY, APLOMB_BLOCKSCOUT_KEY, APLOMB_ALCHEMY_KEY, APLOMB_GOLDRUSH_KEY, APLOMB_JQUANTS_KEY and APLOMB_FRED_KEY. The previously supplied five remain configured. Blank variables and local research rights flags are in .env.example. FRED/ALFRED permission remains unconfirmed and no data is fetched.

Use AAPL.US for the EODHD provider code, a numeric CoinMarketCap ID such as 1 for Bitcoin, an exact Ethereum address for Blockscout, ethereum for Alchemy, and chains for GoldRush. Provider symbols never establish a global issuer identity. J-Quants issue code 86970 returned real company/prices/financials for 2026-01-01 through 2026-06-30; free coverage can be delayed. Twelve Data requires the exact segment MIC (AAPL returned XNGS).

Current source counts: 31 working catalogue rows, 4 FRED/ALFRED permission rows, 62 removed, total97; OpenDART is additional. Fifteen distinct supplied accounts include fourteen live supported account workflows and one disabled FRED account.
