# Financial provider pass — latest user scope

Latest instructions: prioritize adding APIs, do not add test cases for now, remove paid plans and set aside anything requiring login. No account, subscription, purchase, production configuration change or deployment was performed.

## Connected captured feeds

Five actual new captured feeds power `/v1/risk/source-inputs` and the Risk page: NY Fed SOFR, CFTC COT, CFTC weekly interest-rate swaps aggregate, Treasury par curve and Treasury FiscalData Debt to the Penny. Their source modules validate captured bytes and preserve source URL, retrieval timestamp, SHA and units. These are dated captures, not live streams. Existing BoC calculations remain unchanged.

## Additional anonymous connectors

`financial_connectors.py` implements six further anonymous transport/parser paths. `financial_provider_api.py` exposes the provider list, capture and inspection routes; `FinancialProviders.tsx` provides their UI. No new provider test cases were written after the user requested API-first work.

| Connector | Actual upstream | Numerical/source interpretation | Current boundary |
|---|---|---|---|
| `fama-french` | Official French daily three-factor ZIP | Percent-to-fraction conversion; dated market, size, value and risk-free observations | Official host previously reset connections; rights confirmation required before runtime download |
| `aqr` | Official monthly BAB equity XLSX | Bounded OOXML parser, worksheet/cell identities, original values and source units | Workbook-specific terms/units must be confirmed; no exposure or percent conversion guessed |
| `cboe` | Official VIX daily history CSV | Dated OHLC, finite/nonnegative values and OHLC ordering; index points | Data-use/redistribution permission requires confirmation; not an options chain |
| `occ` | Official documented daily-volume CSV report URL | Report row identity and original group/header/source fields preserved | Applicable public-report rights require confirmation; volume report is not prices/Greeks |
| `finra-volume` | Official CNMS daily report | Exact symbol, decimal shares, counts, source date; exempt volume is included in short volume | FINRA data-use restrictions require clarification; never relabeled as short interest |
| `finra-interest` | Official public consolidatedShortInterest REST dataset | Exact symbol and settlement cutoff; provider-reported position, ADV and days to cover | Anonymous only; an authentication rejection remains unavailable, no login/token fallback |

All six are implementation-ready connectors, **not six independently verified live integrations**. They default to `permission_required` until the operator has actual permission for the intended use and configures `APLOMB_SOURCE_<FAMA_FRENCH|AQR|CBOE|OCC|FINRA>_RIGHTS_CONFIRMED=true`. These flags are rights assertions, not a way to bypass provider restrictions; this branch does not set them. An HTTP success or public download link alone does not grant redistribution rights.

Capture requests use a fixed provider URL, a validated date/symbol/sheet/limit, a 15-second timeout, a 3 MB response limit and no redirects. There is no arbitrary URL proxy or user-authored code. Responses retain exact input/query and data limitations. Validated raw bytes and normalized responses are immutable session-owned records in the existing application store (existing DynamoDB/S3 spilling when on AWS), with a one-hour query pointer. Capture inspection verifies its raw SHA; unavailable data produces a truthful error rather than an empty fabricated observation. Existing session validation and request limits apply.

## Excluded and set aside

- CME DataMine: paid/entitled source excluded by user. No acquisition code remains active.
- OANDA v20: account/login/token required; set aside, no active acquisition.
- FRED credit spreads and STLFSI4: API key/account required; set aside. Additionally, the official general terms restrict use in AI/software development. The new uncommitted raw STLFSI4 CSV was removed; only metadata/hash/rights evidence remains. No baseline data or manifests were removed. Agent 2's rights-gated FRED interface remains the future integration point if scope/permissions change.

Official references: [French library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), [AQR dataset](https://www.aqr.com/Insights/Datasets/Betting-Against-Beta-Equity-Factors-Monthly), [AQR terms](https://www.aqr.com/terms-of-use), [Cboe VIX history](https://www.cboe.com/tradable-products/vix/vix-historical-data/), [Cboe policies](https://cdn.cboe.com/resources/membership/Market_Data_Policies.pdf), [OCC current batch URLs](https://www.theocc.com/specialpages/batch-processing-changes), [OCC subscriber terms](https://www.theocc.com/data-subscriber-terms), [FINRA dataset documentation](https://developer.finra.org/docs), [FINRA terms](https://developer.finra.org/specific-terms-equity-data), [CME API/entitlements](https://www.cmegroup.com/datamine/datamine-api.html), [OANDA pricing](https://developer.oanda.com/rest-live-v20/pricing-ep/), [FRED terms](https://fred.stlouisfed.org/legal/terms/).
