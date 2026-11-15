# Owner account links and remaining engineering

Updated 2026-11-15. SEC access-refused sources are removed by owner instruction (17 catalogue rows). Public historical audit evidence is retained; no SEC key or access workaround is requested. Glassnode is removed as a paid API; Flipside has no verified current signup. Current catalogue: 22 working, 52 aside, 23 removed, total 97. OpenDART is an additional working regional workflow.

Accounts below are deduplicated. A key enables authentication, not automatic integration: adapters and consumers for many of these still require engineering. Use free access where offered; a signup link is not a claim that the required endpoint is free. No purchase is requested.

| Provider | Official account / developer entry | What is needed |
|---|---|---|
| Financial Modeling Prep | https://site.financialmodelingprep.com/developer/docs/dashboard | API key |
| EODHD | https://eodhd.com/register | API token; endpoint entitlement still needs verification |
| Massive / Polygon | https://massive.com/dashboard/signup | Market-data API key |
| Alpaca | https://app.alpaca.markets/signup | Market-data application key ID and secret; use paper/data access |
| Marketstack | https://marketstack.com/pricing | Free-plan API access key |
| Nasdaq Data Link | https://data.nasdaq.com/ | Account API key; individual datasets may be paid |
| Finazon | https://finazon.io/login | API key and available dataset name; subscription/trial entitlement matters |
| J-Quants Japan | https://jpx-jquants.com/en/spec/quickstart | V2 API key from dashboard; plan controls date coverage |
| KOSIS Korea | https://kosis.kr/openapi/ | OpenAPI authentication key; Korean registration flow |
| UK Companies House | https://developer.company-information.service.gov.uk/ | Register, create an application, obtain REST API key |
| Australian ABN Lookup | https://abr.business.gov.au/Tools/WebServices | Accept agreement/register web services; authentication GUID |
| CoinGecko | https://www.coingecko.com/en/api | Demo API key |
| CoinMarketCap | https://coinmarketcap.com/api/ | API key from account dashboard |
| CryptoCompare / CoinDesk Data | https://developers.coindesk.com/settings/api-keys | Read price/polling API key; legacy account guide: https://www.cryptocompare.com/coins/guides/how-to-use-our-api/?altTemplate=WebPageAMPGuide |
| Etherscan | https://etherscan.io/register | API key from API Keys dashboard |
| Blockscout | https://dev.blockscout.com/ | Hosted Pro API key; free tier available, bounded |
| Dune | https://dune.com/auth/register | Settings → API → create key; use read scope for existing results |
| Alchemy | https://www.alchemy.com/ | Create application, obtain data/RPC key |
| Infura / MetaMask | https://developer.metamask.io/ | Project API key / RPC endpoint |
| QuickNode | https://www.quicknode.com/ | Create endpoint; endpoint URL/token is a credential |
| Covalent GoldRush | https://goldrush.dev/ | Free API key / credits if available |
| The Graph | https://thegraph.com/studio/ | API key in Studio; network/subgraph availability and quotas apply |

Special access, not a routine free API-key request:

| Provider | Official entry | Exact issue |
|---|---|---|
| Tradier | https://tradier.com/develop/api-overview | Brokerage/developer token; market-data entitlement and account conditions apply |
| Interactive Brokers | https://www.interactivebrokers.com/campus/ibkr-api-page/ | Brokerage authentication and API session/gateway; not a simple paste-in data key. No brokerage password requested |
| OpenCorporates | https://api.opencorporates.com/ | API token plus suitable open-data programme or paid licence. Share-alike/open-data eligibility needs review before requesting access |
| FRED and ALFRED | https://fred.stlouisfed.org/docs/api/api_key.html | Same FRED account/key supports both. Current terms also restrict AI use and storage/caching, so a key alone cannot enable our capture/agent workflow: https://fred.stlouisfed.org/legal/ |

## Public portals: no login required for public searches

- SEDAR+: https://www.sedarplus.ca/ . Official public-access instructions: https://systems.securities-administrators.ca/onlinehelp/general-help/getting-started/general-public-access/ . Registration to file is separate from viewing public filings.
- SEDI: https://www.sedi.ca/ . Choose “Access public filings”; official instructions: https://www.sedi.ca/sedi/new_help/english/public/PDF_en/Viewing_Public_Reports-SEDI_%28FINAL%29.pdf .

No portal password/API key is requested. Portal automation, approved export, provenance and integration remain engineering/access tasks. Public search access does not establish automated collection rights.

## What permission/reuse review means

An API may be publicly readable while its terms separately limit automated collection, retaining copies, showing data to app users, redistribution, commercial use or AI use. Review means checking the actual source and account terms against our intended workflow. It does not mean every pending source requires a purchased licence or a letter from its provider. Unresolved review is our task; a user confirmation flag does not override provider terms.

The 16 rights-review catalogue rows represent 13 distinct providers: Stooq, Yahoo Finance, iShares, Vanguard, SPDR, CoinPaprika, CoinLore, DefiLlama, Binance live API, Coinbase, Kraken, Bitstamp and mempool.space. Their existing per-source findings remain in SOURCES.csv and CONT reports; distinguish specific documented restrictions from incomplete review.

Examples from checked primary terms:

- DefiLlama terms cover its official public APIs and distinguish access from copying, republishing and commercial exploitation: https://defillama.com/terms . Do not assume a public endpoint grants unrestricted storage/display.
- Coinbase market-data terms contain restrictions involving AI/automated systems: https://www.coinbase.com/legal/market_data . A normal exchange account key does not establish an exception.
- FRED terms restrict AI-related use and API storage/caching: https://fred.stlouisfed.org/legal/ . This is separate from free account registration.

No credentials needed for these engineering tasks:

- Blockchain.com currently documents free `/public/*` endpoints without payment/key: https://api.blockchain.info/explorer-gateway-kt/openapi.json . The adapter and reuse/access checks are unfinished.
- Blockchair's official API guide allows bounded personal/testing/noncommercial requests without a key; commercial/high-volume access differs: https://github.com/Blockchair/Blockchair.Support/blob/master/API_DOCUMENTATION_EN.md . An account should not be requested just to try the bounded no-key path.

Excluded rather than requesting credentials:

- SEC: owner excluded after source HTTP403.
- Glassnode: official docs require Professional plus paid API add-on: https://docs.glassnode.com/basic-api/api .
- Flipside: former site lacks a verified signup; official SDK archived July 2 2026: https://github.com/FlipsideCrypto/sdk .

Credentials belong in ignored local `.env`, not source files or reports. No account passwords, wallet seed phrases, or brokerage trading authorizations are needed for these research requests.
