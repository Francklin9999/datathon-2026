# Current selected accounts

The owner supplied fifteen distinct keys and instructed removal of other pending providers. There are no remaining signup requests. Previous signup tables are superseded.

| Account | Current implemented/live operation |
|---|---|
| Finnhub | Company profile |
| OpenDART | Complete bounded filing interval, financial statements, ownership disclosures |
| Alpha Vantage | Quote; overview/financial statement controls also implemented, additional calls previously quota-limited |
| Tiingo | Supported US equity metadata and dated adjusted history |
| Twelve Data | Thirty exact-MIC daily bars |
| Financial Modeling Prep | Provider quote |
| EODHD | Daily history by provider CODE.EXCHANGE; identity echo unavailable |
| Massive / Polygon | Listing detail |
| Marketstack | Daily bars |
| J-Quants | Listing, daily prices and financial summaries, complete bounded pagination |
| CoinMarketCap | USD quote by numeric asset ID |
| Blockscout | Exact Ethereum address native balance |
| Alchemy | Ethereum mainnet block head |
| GoldRush | Directory of 44 chains; bounded address balances implemented |
| FRED / ALFRED | Key stored; data-use restriction unresolved, no fetch |

Credentials are local-only `.env` mode0600, ignored by git. The duplicate user entries are consolidated. Blank names/flags are in `.env.example`. No secrets are returned in connection status, source URLs, captures or errors.

FRED/ALFRED is the sole remaining selected external blocker: https://fred.stlouisfed.org/legal/ API restrictions on AI use and storing/caching/archiving conflict with this app's workflow. A key alone is not compatible permission. It stays disabled; no purchase, contact or rights exception is invented.

All other formerly pending providers, including portals and rights-review sources, were removed from active coverage under the owner's instruction. Old catalogue audit rows and implementation history remain for traceability. No passwords, broker login sessions or wallet signing authorizations are needed.
