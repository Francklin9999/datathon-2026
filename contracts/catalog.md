# contracts/catalog.md — closed lists

Every code used in a payload is listed here. Adding a value is an additive contract change (see `contracts/README.md`). The Python mirror is `backend/aplomb/contracts/catalog.py`, the TypeScript mirror `web/src/contracts/catalog.ts`. The i18n dictionaries of the web app must contain a label for every code.

---

## 1. Metric codes (`MetricCode`)

| Code | Meaning | Unit | Produced by |
|---|---|---|---|
| `price.last` | Last adjusted close on or before `asOf` | cad / usd | quant |
| `fx.usdcad` | USD/CAD rate used for a conversion | ratio | quant |
| `return.period` | Total return between two dates | pct | quant |
| `return.calendar_year` | Total return over a calendar year | pct | quant |
| `return.ytd` | Return since the last master-calendar day of the previous year | pct | quant |
| `return.trailing` | Return over a trailing window (1y, 3y, 5y) | pct | quant |
| `return.worst_12m` | Worst rolling 252-observation return in the window | pct | quant |
| `vol.annualized` | Annualized volatility of daily returns | pct | quant |
| `input.goal_assumption` | Explicit user goal scenario input | currency / ratio / pct | profiles |
| `goal.projected_value` | Hypothetical goal balance under explicit assumptions | currency | profiles |
| `goal.funding_gap` | Target minus scenario balance, floored at zero | currency | profiles |
| `risk.var95` | Historical daily 95% Value at Risk, loss convention | pct | quant |
| `risk.es95` | Historical daily 95% Expected Shortfall, loss convention | pct | quant |
| `risk.variance_share` | Signed contribution to portfolio variance | pct | quant |
| `drawdown.max` | Maximum peak-to-trough decline in the window (reported as a positive number) | pct | quant |
| `corr.pair` | Correlation of daily returns between two assets | ratio | quant |
| `value.portfolio` | Total portfolio value | cad / usd | quant |
| `value.position` | Market value of a position | cad / usd | quant |
| `weight.position` | Weight of one position | pct | quant |
| `weight.position.max_single` | Largest weight among single-name positions | pct | quant |
| `weight.sector` | Weight of one sector among direct single-name equities | pct | quant |
| `weight.sector.max` | Largest sector weight | pct | quant |
| `weight.asset_class` | Weight of an asset class | pct | quant |
| `weight.asset_group` | Weight of an asset group | pct | quant |
| `weight.growth_assets` | Equity group + crypto group | pct | quant |
| `weight.fixed_income` | Fixed-income group + cash group | pct | quant |
| `weight.diversifiers` | Fixed income + cash + commodity groups | pct | quant |
| `weight.theme` | Weight of positions carrying a theme tag | pct | quant |
| `weight.currency` | Quotation-currency weight, not fund look-through or hedged economic exposure | pct | quant |
| `weight.country` | Weight by listing country | pct | quant |
| `concentration.hhi` | Sum of squared weights | ratio | quant |
| `concentration.effective_n` | 1 ÷ HHI | count | quant |
| `stress.replay_2022` | Portfolio return over calendar 2022 with today's weights; the rule uses the loss as a positive number | pct | quant |
| `stress.rate_cycle` | Portfolio return over the policy-rate hiking cycle found in the data | pct | quant |
| `size.requested` | Size of the requested move | pts | user |
| `size.max_compatible` | Largest size before the first conflict | pts | optimizer |
| `threshold.rule` | Threshold of a rule | (rule unit) | profile / optimizer |
| `budget.volatility` | Volatility budget of a profile | pct | optimizer |
| `ref.sigma_single_stock_q3` | Upper-quartile volatility of single stocks in the universe | pct | optimizer |
| `ref.sigma_crypto_median` | Median volatility of crypto assets in the universe | pct | optimizer |
| `ref.mix_volatility` | Volatility of an equity/bond reference mix | pct | optimizer |
| `frontier.point` | One point of a frontier (volatility, historical return) | pct | optimizer |
| `macro.level` | Level of a macro series on a date | (series unit) | quant |
| `macro.change` | Change of a macro series between two dates | pts | quant |
| `attention.pageviews_ratio` | Recent ÷ baseline average daily page views | ratio | research |
| `emissions.facility_total` | Reported emissions of matched facilities | count (tCO2e) | world |
| `count.rules` | Number of rules in a given status | count | rules |
| `count.sources` | Number of distinct sources for an event | count | world |
| `gate.rows_withheld` | Rows hidden by the temporal gate | count | timemachine |
| `quote.figure` | A figure quoted verbatim from a cited document | text | research |

---

## 2. Method IDs (`MethodId`)

Each method is described once, with its formula, in the spec of the module that implements it. A fact's `method.id` must be one of these.

| ID | One-line definition | Spec |
|---|---|---|
| `M_PRICE_ADJ_CLOSE` | Use `adj_close` (split- and dividend-adjusted) | quant §3 |
| `M_FX_BOC_FFILL` | Convert USD to CAD with the Bank of Canada rate of the same day, or the last published rate before it | quant §4 |
| `M_CAL_INTERSECTION` | Master calendar = days with both a TSX and a US price | quant §2 |
| `M_RET_SIMPLE` | `P_end ÷ P_start − 1` on adjusted prices | quant §5 |
| `M_RET_CALENDAR_YEAR` | Simple return from the last observation of year Y−1 to the last observation of year Y | quant §5 |
| `M_VOL_STDEV_252` | Sample standard deviation (n−1) of daily simple returns × √252 | quant §6 |
| `M_GOAL_FUNDING_SCENARIO` | Allocated capital compounded with explicit annual contributions/return; not a forecast | profiles/goals |
| `M_HISTORICAL_TAIL` | Largest ceil(0.05 × n) daily losses; VaR is tail minimum, ES is tail mean, floored at zero | quant §11 |
| `M_VARIANCE_SHARE` | 100 × w_i (Σw)_i / (wᵀΣw), sample daily-return covariance | quant §11 |
| `M_MDD_PEAK_TROUGH` | Minimum of `value ÷ running maximum − 1` | quant §6 |
| `M_WORST_ROLLING_252` | Minimum 252-observation simple return | quant §6 |
| `M_CORR_PEARSON` | Pearson correlation of daily simple returns on the master calendar | quant §6 |
| `M_PORT_CONST_WEIGHTS` | Portfolio daily return = Σ weight × asset daily return, weights constant (A-14) | quant §7 |
| `M_WEIGHTS_AFTER_MOVE` | Post-move weights under a funding mode | quant §8 |
| `M_STRESS_REPLAY` | `M_PORT_CONST_WEIGHTS` over a named historical window | quant §9 |
| `M_DERIVE_VOL_BUDGET` | Lookup of risk level in the volatility-budget table (A-02) | optimizer §2 |
| `M_DERIVE_POSITION_CAP` | A-03 | optimizer §3 |
| `M_DERIVE_SECTOR_CAP` | A-04 | optimizer §3 |
| `M_DERIVE_CRYPTO_CAP` | A-05 | optimizer §3 |
| `M_DERIVE_GROWTH_CAP` | A-06 | optimizer §3 |
| `M_DERIVE_STRESS_LIMIT` | A-07 | optimizer §3 |
| `M_DERIVE_DRAWDOWN_LIMIT` | A-08 | optimizer §3 |
| `M_MAXSIZE_GRID` | A-18 | optimizer §4 |
| `M_FRONTIER_MINVAR` | Long-only minimum-variance portfolios per target (risk-only) | optimizer §6 |
| `M_FRONTIER_HIST_MV` | Long-only mean-variance with historical mean returns (illustration only) | optimizer §6 |
| `M_RULE_COMPARE` | Comparison of a value with a threshold and the tension band (A-09) | rules §3 |
| `M_USER_INPUT` | Value typed or selected by the user | — |
| `M_PROFILE_ASSUMPTION` | Value set in the profile | — |
| `M_OBSERVED_ROW` | Value read from one dataset row | datastore |
| `M_ATTENTION_RATIO` | Mean of the last 30 days ÷ mean of the previous 365 days of page views | research §6 |
| `M_QUOTE_VERBATIM` | Figure copied from a cited document, with the quote stored | research §3 |
| `M_EVENT_IMPORTANCE` | Importance score of a world event | world §4 |
| `M_PRICE_MOVE_AFTER_EVENT` | Simple return of an asset over N master days after an event date | world §6 |
| `M_GATE_COUNT` | Count of rows with `availableAt` after `asOf` | timemachine §2 |

---

## 3. Rule IDs (`RuleId`)

| RuleId | Type | Metric | Comparator | Applies to | Counts in verdict |
|---|---|---|---|---|---|
| `cap.position` | cap | `weight.position.max_single` | <= | single-name positions (equity, crypto) | yes |
| `cap.sector` | cap | `weight.sector.max` | <= | GICS sectors of direct single-name equities | yes |
| `cap.asset_class.crypto` | cap | `weight.asset_group` (crypto) | <= | crypto group | yes |
| `cap.growth_assets` | cap | `weight.growth_assets` | <= | equity + crypto groups | yes |
| `cap.theme.<tag>` | cap | `weight.theme` | <= | one theme tag | yes |
| `floor.fixed_income` | floor | `weight.fixed_income` | >= | fixed income + cash | yes |
| `floor.diversifiers` | floor | `weight.diversifiers` | >= | fixed income + cash + commodity | yes |
| `limit.volatility` | limit | `vol.annualized` (portfolio, after) | <= | portfolio | yes |
| `limit.stress_2022` | limit | `stress.replay_2022` loss | <= | portfolio | yes |
| `limit.drawdown` | limit | `drawdown.max` (portfolio, after) | <= | portfolio | yes |
| `exclude.sector.<slug>` | exclude | `weight.sector` | == 0 | one sector, e.g. `exclude.sector.energy` | yes |
| `exclude.asset_class.<class>` | exclude | `weight.asset_group` | == 0 | e.g. `exclude.asset_class.crypto` | yes |
| `exclude.ticker.<ticker>` | exclude | `weight.position` | == 0 | one asset | yes |
| `evidence.controversy` | evidence | — | none | assets added or increased by the move | yes (as `nee` or `tension`) |
| `flag.attention` | flag | `attention.pageviews_ratio` | none | the requested asset | no |
| `flag.rate_cycle` | flag | `stress.rate_cycle` | none | portfolio | no |
| `flag.short_history` | flag | — | none | assets with fewer than 252 master observations | no |
| `sim.only` | sim | — | none | every run | no |

Sector slugs: lower-case sector label with spaces replaced by `_` (`energy`, `information_technology`, `consumer_discretionary`, …).

---

Parameterized policy additions: `cap.country.<ISO3>` evaluates the listing-country proxy;
`cap.currency.<ISO4217>` evaluates quotation-currency weights. Both are typed user assumptions,
with percent caps in [0,100], and imply neither economic look-through nor regulatory duties.

## 4. Not-enough-evidence reasons (`NeeReason`)

| Code | When |
|---|---|
| `short_history` | An asset in the after-move portfolio has fewer than 252 master-calendar observations in the window |
| `no_evidence_loaded` | An evidence rule has no research evidence attached |
| `evidence_unverified` | Evidence exists but its citation check failed or it is tier 3 only |
| `not_visible_at_asof` | The data needed lies after the Time Machine date |
| `asset_unknown` | The ticker could not be resolved or fetched |
| `dataset_missing` | A required dataset is not in the snapshot |

---

## 5. Limitation codes (`LimitationCode`)

The web app holds the bilingual text for each code. Facts and results carry codes only.

| Code | Text to display (English reference) |
|---|---|
| `LIM_PAST_NOT_FUTURE` | Past performance does not guarantee future results. These figures describe a historical sample; they are not forecasts. |
| `LIM_SAMPLE_WINDOW` | Computed on the available window only (from 2021-11-12 in the starter data). Other periods would give different values. |
| `LIM_SURVIVORSHIP` | The asset universe was chosen in 2026 among names that are large today, which flatters historical results. |
| `LIM_CONSTANT_WEIGHTS` | Portfolio history applies today's weights to past returns, rebalanced daily. It is not what an actual investor would have earned. |
| `LIM_FX_FFILL` | USD/CAD uses the Bank of Canada daily rate; on days without a published rate the previous rate is carried forward. |
| `LIM_CALENDAR_INTERSECTION` | Only days when both the Canadian and US markets were open are used; crypto weekend moves appear on the next trading day. |
| `LIM_YAHOO_NOT_CERTIFIED` | Prices come from Yahoo Finance and are not exchange-certified. Adjusted closes change when data is re-downloaded. |
| `LIM_CNQ_FACTOR` | Yahoo reports a 1.021 "split" for CNQ.TO on 2022-08-22, the day of a 0.75 CAD dividend. It likely reflects a special distribution; not confirmed with the company. |
| `LIM_ETF_NO_LOOKTHROUGH` | Funds are treated as single diversified positions; their underlying holdings are not counted in sector or single-name limits. |
| `LIM_SECTOR_LABELS` | Sector labels for starter assets were assigned by the organizers and are simplified. |
| `LIM_THEME_TAGS` | Theme tags are team assumptions documented per asset; they are not an official classification. |
| `LIM_THRESHOLDS_ASSUMED` | Rule thresholds are assumptions derived from the stated risk level and horizon. They are editable and are not regulatory limits. |
| `LIM_BONDS_SAMPLE` | In the 2021–2026 sample bonds were unusually volatile, which affects thresholds derived from it. |
| `LIM_MACRO_REVISED` | US macro values are the latest revised figures, not as first published. |
| `LIM_MACRO_LAG_ASSUMED` | Publication dates of monthly macro data are approximated with a fixed lag. |
| `LIM_NO_CONTROVERSY_DATA` | No controversy or ESG rating dataset is loaded. Absence of evidence is not evidence of absence. |
| `LIM_EVIDENCE_TIER` | Some sources are not official or established publishers and are shown for context only. |
| `LIM_IMPACT_NOT_ESTABLISHED` | A link between an event and a holding was identified; its financial impact was not measured. |
| `LIM_PRICE_MOVE_NOT_CAUSAL` | A price change after an event is an observation, not proof that the event caused it. |
| `LIM_LLM_KNOWLEDGE` | The language model may know what happened after the selected date. Numbers come from date-filtered data, but wording could reflect later knowledge. |
| `LIM_SHORT_HISTORY` | At least one asset has too little history for reliable risk figures. |
| `LIM_CASH_NO_INTEREST` | Cash is modelled with zero return and zero volatility. |
| `LIM_SIMULATION_ONLY` | Simulation with fictional profiles and portfolios. Not financial advice. No order is placed. |
| `LIM_ATTENTION_PROXY` | Page views measure public attention, not investment quality. |
| `LIM_REGISTRY_MATCH` | Facilities are matched to companies by name; some matches may be wrong or missing. |
| `LIM_MV_ILLUSTRATION` | Mean-variance points use past average returns as inputs and are shown for illustration only. |

---

## 6. Audit check codes (`AuditCheckCode`)

| Code | Kind | Check | On failure |
|---|---|---|---|
| `A01` | code | Every token in the writer output refers to an existing fact, rule or evidence ID | strike sentence |
| `A02` | code | No digit characters outside tokens (Arabic digits, and number words listed in the ledger spec) | strike sentence |
| `A03` | code + llm | Every comparison stated in prose is true for the referenced facts (LLM extracts the relation, code evaluates it) | strike sentence |
| `A04` | code | Every sentence in section `facts` contains at least one fact or evidence token | strike sentence |
| `A05` | code | Mandatory sections present: `facts`, `assumptions`, `limits` | rewrite once, else fail run |
| `A06` | code | Simulation disclaimer present | inserted by code; cannot fail |
| `A07` | code | No banned phrasing (buy/sell instructions, guarantees, predictions), English and French lists | strike sentence |
| `A08` | code | Every quoted passage is found in the cached source document | strike sentence, mark evidence failed |
| `A09` | llm | No interpretation unsupported by the cited facts or evidence | strike sentence |
| `A10` | guardrail | Bedrock Guardrail did not block the text | replace by refusal text |
| `A11` | code | Every fact's `availableAt` ≤ run `asOf` | fail run |
| `A12` | code | Assumptions section mentions every rule in conflict or tension | rewrite once |
| `A13` | code | Limits section lists every limitation code attached to a cited fact | appended by code |
| `A14` | code | An "impact" statement about a holding exists only with `impact = measured_price_move` | strike sentence |

---

## 7. Error codes (`ErrorCode`)

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Body or query does not match the schema; `details.fields` lists problems |
| `not_found` | 404 | Unknown profile, run, fact, event, dataset or asset |
| `conflict` | 409 | Version mismatch on update; run not in a state that allows the action |
| `forbidden_action` | 400 | The request asks to execute a trade or for personalised advice |
| `insufficient_data` | 422 | The computation cannot be done with the data available (details say why) |
| `rate_limited` | 429 | Too many requests for this session |
| `upstream_unavailable` | 503 | Bedrock or an external source failed after retries |
| `feature_disabled` | 501 | The endpoint belongs to a feature that is switched off |
| `internal` | 500 | Unexpected error; `requestId` identifies the log entry |

---

## 8. Theme tags (`ThemeTag`)

Tags are assumptions (`LIM_THEME_TAGS`). The assignment of tags to assets lives in the dataset `asset_themes` (see `data/SPEC.md`), with one line of justification and a source per assignment.

`ai`, `semiconductors`, `software`, `cloud`, `ecommerce`, `electric_vehicles`, `big_tech`, `banks`, `insurance`, `fossil_energy`, `pipelines`, `utilities`, `rail_transport`, `consumer_staples`, `healthcare`, `retail`, `broad_canada`, `broad_us`, `nasdaq_growth`, `esg_screened`, `bonds_canada`, `bonds_us`, `long_treasuries`, `cash_like`, `gold`, `crypto`, `dividend_payers`.

---

## 9. Asset flags (`AssetFlag`)

`short_history`, `zero_volume_rows`, `split_anomaly`, `on_demand`, `no_fx_needed`, `seven_day_calendar`, `sector_label_unsourced`.

---

## 10. Dataset IDs (`DatasetId`)

| ID | Content | Tier |
|---|---|---|
| `assets_universe` | Asset master list | P0 |
| `prices_daily` | Daily OHLC, close, adjusted close, volume | P0 |
| `corporate_actions` | Dividends and splits | P0 |
| `fx_boc_global` | Bank of Canada global exchange rates | P1 |
| `world_airports` | OurAirports static large scheduled-service airport reference | P2 |
| `world_bank_indicators` | Worldwide annual country indicators | P1 |
| `fx_usdcad_daily` | USD/CAD from the Bank of Canada | P0 |
| `macro_rates` | Policy rates, yields, CPI, unemployment | P0 |
| `asset_themes` | Theme tags per asset with justification | P0 |
| `default_profiles` | The three personas, their portfolios and rules | P0 |
| `macro_release_dates` | Publication dates of monthly series | P1 |
| `etf_holdings` | Constituents and weights of ETFs | P1 |
| `world_events` | Geolocated events | P1 |
| `world_aviation_weather` | Aviation weather observations from bounded airport station captures | P2 |
| `world_noaa_alerts` | NOAA weather alert observations with source geometry | P2 |
| `world_gdacs_alerts` | GDACS bounded global disaster alert observations | P2 |
| `world_nasa_power` | NASA POWER bounded gridded daily temperature observations | P2 |
| `world_epa_sems_sites` | EPA Envirofacts bounded geolocated SEMS site references | P2 |
| `world_federal_register` | Federal Register policy observations | P2 |
| `energy_wri_plants` | WRI power plant reference observations | P2 |
| `trade_portwatch_ports` | IMF PortWatch port reference observations | P2 |
| `attention_pageviews` | Wikipedia page views per asset | P1 |
| `emissions_facilities` | ECCC and EPA facility emissions | P1 (cut item 2) |
| `natural_hazards` | USGS earthquakes, NASA FIRMS wildfires | P1 (cut item 2) |
| `research_documents` | Cached text of documents cited as evidence | P1 |
| `filings_index` | SEC EDGAR filing metadata fetched by the researcher | P1 |

---

## 11. Feature flags (`FeatureFlag`)

Returned by `GET /meta`; the web app hides what is off. Defaults are for the first deployment.

| Flag | Default | Cut-list link (D-02) |
|---|---|---|
| `bilingual` | true | cut 1 |
| `world_explorer` | true | — |
| `world_layer_facilities` | false until the dataset exists | cut 2 |
| `world_layer_hazards` | false until the dataset exists | cut 2 |
| `time_machine` | true | cut 3 |
| `profile_creator` | true | cut 4 |
| `goal_requests` | true | cut 4 |
| `sabotage_demo` | true | — |
| `research_open_web` | false until O-02 is closed | — |
| `guardrails` | false until O-03 is closed | — |
| `on_demand_tickers` | true | — |
| `frontier_chart` | true | — |
