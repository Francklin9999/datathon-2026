# External dependencies

These are external requirements, not labels for missing engineering. REQUIREMENTS.md separately lists remaining cross-agent integration and unimplemented coverage.

- **SEC access:** an actual bounded request using the existing authorised project source contact returned HTTP403 on 2026-11-15. Evidence: `docs/evidence/parallel/agent-2/sec-live-status.json`. Live SEC acquisition is now removed by owner instruction. No signup requirement is invented and no bypass is attempted. It is excluded from credential requests; prior safe parsers and captures remain reviewable.
- **Signup/key sources:** the owner deferred required accounts/keys and restricted portals. Exact per-row requirements are in SOURCES.csv. JP J-Quants remains aside; KR OpenDART now works with the supplied key. Existing adapters stay inactive.
- **Paid sources:** Databento, Intrinio, Financial Datasets, Glassnode, and GeckoTerminal storage are removed from active coverage under the owner's instruction. Audit rows remain to explain the disposition. No purchases or paid signups were made.
- **Reuse permission:** Stooq, iShares/Vanguard/SPDR, Coinbase/Kraken/CoinLore/CoinPaprika, DefiLlama and certain live hosted feeds have source-specific access/reuse restrictions. Their exact primary-source findings are in CONT reports/SOURCES.csv and issuer_holdings.py. No operator flag is treated as universal rights. Mempool hosted-data output rights remain unestablished despite public endpoint reachability; it stays aside.
- **FRED/ALFRED:** source terms cover AI development and caching restrictions; an API key alone does not resolve permitted use. No actual vintage is fed to agents. Rights-cleared parser remains available as source code, with no fabricated historical data.
- **Original historical/source coverage:** unobserved original publication/vintage times, undocumented facility/issuer links and absent ownership/constituent records cannot be manufactured. New directly documented source records are needed before these can support claims. Retrieval-time availability is used conservatively where it is the only proof.

Working no-key APIs and local noncommercial research paths were completed independently. No production/IAM/feature-flag changes or deployment occurred.

Current owner-facing access guide: ACCESS-REQUESTS.md. Portal public searches require no login; Blockchain.com public endpoints require no key. These need engineering/access work. The signup list is not a claim that adapters are already implemented.
