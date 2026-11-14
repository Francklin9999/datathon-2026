# contracts/controls.md — reference numbers computed from the starter data

Every number on this page was **computed on 2026-11-14 from the CSV files in `Datathon2026/alphaforge_starter/`** (data built by the organizers on 2026-11-13, window 2021-11-12 to 2026-11-12) with the small reference scripts in `contracts/controls/`. Nothing here was copied from another source.

**Purpose.** These are the expected values for unit tests of the quant, optimizer and rules modules, and for the acceptance tests. If your implementation gives a different number, either the implementation or the method description is wrong; resolve it before shipping.

**Tolerance.** Tests compare at the precision printed here (±0.05 for values printed with one decimal, ±0.005 for two decimals).

**What was not checked.** The prices themselves were not compared with any other provider. The control numbers prove that our calculations follow the stated method on this dataset, not that Yahoo's data is right.

**Boundary terminology.** The historical script/table phrase “largest compatible size” and wire field `maxCompatibleSizePct` mean the last grid point before the first rule conflict. Tension or insufficient evidence may remain. The UI uses “Largest size before the first rule conflict.” Printed drawdowns are negative declines; API drawdowns are positive magnitudes.

---

## 1. Dataset facts

| Fact | Value |
|---|---|
| Assets in `assets_universe.csv` | 31 (10 Canadian equities, 10 US equities, 9 ETFs, 2 crypto) |
| Rows in `prices_daily.csv` | 40,049 |
| Rows per equity or ETF | 1,255 each (29 tickers) |
| Rows per crypto asset | 1,827 each (BTC-USD, ETH-USD) |
| First and last price date, every ticker | 2021-11-12 and 2026-11-12 |
| Rows in `corporate_actions.csv` | 658 (651 dividends, 7 splits) |
| Rows in `fx_usdcad_daily.csv` | 1,245 |
| Rows in `macro_rates.csv` | 8,281 across 9 series |
| `data_quality_warnings.txt` | "No warnings." |

Macro series row counts: `BD.CDN.10YR.DQ.YLD` 1,245; `BD.CDN.2YR.DQ.YLD` 1,245; `V39079` 1,293; `DFF` 1,826; `DGS10` 1,248; `DGS2` 1,248; `CPIAUCSL` 59; `UNRATE` 59; `STATIC_TOTALCPICHANGE` 58.

## 2. Calendars (method `M_CAL_INTERSECTION`)

| Fact | Value |
|---|---|
| TSX trading days in the window (dates of XIU.TO) | 1,255 |
| US trading days in the window (dates of SPY) | 1,255 |
| **Master calendar** (days with both) | **1,228** days, 2021-11-12 to 2026-11-12 → 1,227 daily returns |
| Union of the two | 1,282 |
| Master days per year | 2021: 32; 2022: 245; 2023: 245; 2024: 247; 2025: 245; 2026: 214 |
| Every TSX-listed asset has exactly the XIU.TO dates; every US-listed non-crypto asset has exactly the SPY dates | true (checked for all 29) |
| Master days without a USD/CAD rate | 10: 2022-09-30, 2022-11-11, 2023-10-02, 2023-11-13, 2024-09-30, 2024-11-11, 2025-09-30, 2025-11-11, 2026-09-30, 2026-11-11 |
| Last base date for calendar-2022 returns | 2021-12-31 (present in both calendars) |
| Last master day of 2022 | 2022-12-30 |

On the 10 days without a rate, `M_FX_BOC_FFILL` uses the last rate published before that day.

## 3. Exchange rates

| Date | USD/CAD |
|---|---|
| 2021-12-31 | 1.2678 |
| 2022-12-30 | 1.3544 |
| 2026-11-12 (last) | 1.4255 |

## 4. Asset controls

Method: calendar-2022 return = `adj_close` on the asset's last trading day of 2022 ÷ `adj_close` on its last trading day of 2021 − 1 (`M_RET_CALENDAR_YEAR`). CAD figures multiply USD prices by the USD/CAD rate of the same day (`M_FX_BOC_FFILL`). Volatility (`M_VOL_STDEV_252`) and maximum drawdown (`M_MDD_PEAK_TROUGH`) are in CAD, on the master calendar, over the full window (1,227 returns).

| Ticker | 2022 return, listing currency | 2022 return, CAD | Volatility, CAD | Max drawdown, CAD |
|---|---|---|---|---|
| TSLA | −65.0% | −62.6% | 59.4% | −69.8% |
| NVDA | −50.3% | −46.9% | 51.4% | −63.5% |
| SPY | −18.2% | −12.6% | 16.9% | −22.2% |
| QQQ | −32.6% | −28.0% | 23.1% | −31.7% |
| ESGV | −24.0% | −18.9% | 18.2% | −26.7% |
| AGG | −13.0% | −7.1% | 7.5% | −12.8% |
| TLT | −31.2% | −26.5% | 16.1% | −39.7% |
| GLD | −0.8% | +6.0% | 18.6% | −26.0% |
| XIU.TO | −6.3% | −6.3% | 13.2% | −16.4% |
| XBB.TO | −11.7% | −11.7% | 6.8% | −15.5% |
| ZST.TO | +1.2% | +1.2% | 0.6% | −0.4% |
| CNQ.TO | +52.9% | +52.9% | 30.7% | −33.1% |
| RY.TO | −1.5% | −1.5% | 15.6% | −21.0% |
| SHOP.TO | −73.0% | −73.0% | 65.1% | −83.5% |
| BTC-USD | −64.3% | −61.8% | 51.2% | −73.7% |
| ETH-USD | −67.5% | −65.3% | 68.7% | −77.2% |

Crypto note: the listing-currency return uses 2022-12-31 (crypto trades every day); the CAD volatility and drawdown use master-calendar days only.

TSLA detail for a from-scratch test: `adj_close` 352.2600 on 2021-12-31 and 123.1800 on 2022-12-30.

### 4.1 CNQ.TO around 2022-08-22

| Date | close | adj_close |
|---|---|---|
| 2022-08-19 | 35.450539 | 28.506203 |
| 2022-08-22 | 35.665001 | 29.298502 |

`close` rose 0.61% and `adj_close` rose 2.78%. `corporate_actions.csv` lists a 0.75 CAD dividend and a 1.021 "split" on 2022-08-22. The 2.2-point gap is of the size of the dividend (0.75 ÷ 35.45 = 2.1%). We use `adj_close` as is and attach `LIM_CNQ_FACTOR` to every CNQ.TO fact whose period includes that date. Nothing was checked with the company.

## 5. Universe statistics used by the threshold formulas

Volatility in CAD, master calendar, full window.

| Statistic | Value |
|---|---|
| Single-stock volatilities, sorted (20 starter equities) | FTS.TO 14.9, RY.TO 15.6, ENB.TO 16.3, TD.TO 17.8, JNJ 18.6, PG 19.1, CNR.TO 20.1, MFC.TO 21.8, JPM 24.1, ATD.TO 24.3, XOM 26.4, AAPL 28.3, MSFT 28.5, CNQ.TO 30.7, CSU.TO 30.8, GOOGL 32.6, AMZN 36.8, NVDA 51.4, TSLA 59.4, SHOP.TO 65.1 |
| Quartiles (inclusive method) | Q1 18.9, median 25.4, **Q3 31.22** (`ref.sigma_single_stock_q3`) |
| Crypto volatilities | BTC-USD 51.2, ETH-USD 68.7 → **median 59.97** (`ref.sigma_crypto_median`) |

"Inclusive method" = Python `statistics.quantiles(values, n=4, method="inclusive")`, equivalent to linear interpolation between order statistics (NumPy default).

## 6. Reference mixes (`ref.mix_volatility`)

Equity proxy = 50% XIU.TO + 50% SPY; bond proxy = XBB.TO; constant weights; CAD; master calendar; full window.

| Equity share | Volatility | Max drawdown | 2022 return |
|---|---|---|---|
| 0% | 6.75% | −15.48% | −11.66% |
| 10% | 6.48% | −14.99% | −11.30% |
| 20% | 6.51% | −14.67% | −10.96% |
| 30% | 6.84% | −14.36% | −10.65% |
| 40% | 7.44% | −14.22% | −10.37% |
| 50% | 8.25% | −14.49% | −10.12% |
| 55% | 8.71% | — | — |
| 60% | 9.21% | −14.81% | −9.89% |
| 70% | 10.28% | −15.14% | −9.69% |
| 80% | 11.43% | −15.48% | −9.52% |
| 85% | 12.03% | — | — |
| 90% | 12.64% | −15.83% | −9.38% |
| 100% | 13.88% | −16.20% | −9.27% |

Observation worth displaying (`LIM_BONDS_SAMPLE`): in this sample the all-bond mix lost more in 2022 (−11.66%) than the all-equity mix (−9.27%) in CAD.

## 7. Derived thresholds for the default profiles

Formulas: A-02 to A-08 in `docs/02-DECISIONS.md`; implementation in `backend/aplomb/optimizer/SPEC.md` §3.

| | Robert | Mateo | Amira |
|---|---|---|---|
| Risk level | low_moderate | moderate | high |
| Horizon midpoint (years) | 4 | 10 | 15 |
| Volatility budget (`limit.volatility`) | 9% | 12% | 22% |
| `cap.position` | 10% | 15% | 25% |
| `cap.sector` | 20% | 30% | 40% |
| Crypto | excluded (A-12) | cap 5% (formula 10%, halved: avoids speculative) | cap 15% |
| `cap.growth_assets` | 55% | 80% | not applicable (100%) |
| `floor.fixed_income` | 35% | 10% | not applicable |
| `floor.diversifiers` | — | — | 8% (A-10) |
| Stress multiple `m` | 1.0 | 1.25 | 1.5 |
| `limit.stress_2022` | 9.0% | 15.0% | 33.0% |
| `limit.drawdown` | 18% | 24% | 44% |

Intermediate values: position cap before rounding = 0.4 × budget ÷ 31.22 → 11.5%, 15.4%, 28.2%; rounded to the nearest 5 and clamped to [5, 25].

## 8. Default portfolios at baseline

Weights are listed in `backend/aplomb/profiles/SPEC.md` §3. Constant weights, CAD, master calendar, full window.

| | Robert | Mateo | Amira |
|---|---|---|---|
| Volatility | 6.09% | 8.72% | 19.52% |
| Max drawdown | −9.60% | −14.33% | −32.03% |
| Calendar-2022 return | −4.70% | −8.11% | −25.26% |
| Total return over the window | +50.0% | +57.4% | +125.4% |
| Return 2025-12-31 → 2026-11-12 (YTD) | +10.32% | +12.84% | +10.95% |
| Return 2025-11-12 → 2026-11-12 (1 year) | +10.60% | +12.15% | +8.38% |
| Rate cycle 2022-03-02 → 2023-07-13 | −0.02% | +4.00% | +15.27% |
| Largest single-name position | 5.0% (RY.TO) | 5.0% (MSFT) | 8.0% (NVDA) |
| Largest sector (direct equities) | 5.0% Financials | 8.0% Consumer Staples | 21.0% Information Technology |
| Equity group | 47.0% | 59.0% | 81.0% |
| Fixed income | 50.0% | 37.0% | 5.0% |
| Commodity | 3.0% | 4.0% | 5.0% |
| Crypto | 0% | 0% | 9.0% |
| **Verdict against own rules** | **compatible** (0 conflict, 0 tension) | **insufficient** (financial checks pass; controversy nee) | **compatible** |

## 9. Acceptance scenarios

Funding `pro_rata` unless stated. Status letters: C = conflict, T = tension, P = pass.

### 9.1 Robert, +25 points TSLA (acceptance AT-01)

| Rule | Value | Threshold | Status |
|---|---|---|---|
| `cap.position` | 25.0% (TSLA) | 10% | C |
| `cap.sector` | 25.0% (Consumer Discretionary) | 20% | C |
| `exclude.asset_class.crypto` | 0% | 0 | P |
| `cap.growth_assets` | 60.25% | 55% | C |
| `floor.fixed_income` | 37.5% | 35% | T |
| `limit.volatility` | 16.96% | 9% | C |
| `limit.stress_2022` | 21.88% | 9.0% | C |
| `limit.drawdown` | 25.31% | 18% | C |

Verdict **conflict**: 6 conflicts, 1 tension, 1 pass. **Largest compatible size: 6.0 points** (at 6.5 the 2022-replay loss exceeds 9.0%).

Size sweep (pro-rata): 2 points → compatible (all pass; volatility 6.47%, stress 6.12%); 5 → tension (`cap.growth_assets` 49.65, `limit.stress_2022` 8.24); 6 → tension (50.18; 8.95); 7 → conflict (stress 9.65); 10 → conflict (volatility 9.36, stress 11.74); 12 → conflict (position 12.0 as well).

### 9.2 Amira, +25 points TSLA (AT-02)

| Rule | Value | Threshold | Status |
|---|---|---|---|
| `cap.position` | 25.0% (TSLA) | 25% | T |
| `cap.sector` | 28.75% (Consumer Discretionary) | 40% | P |
| `cap.asset_class.crypto` | 6.75% | 15% | P |
| `floor.diversifiers` | 7.5% | 8% | C |
| `limit.volatility` | 26.30% | 22% | C |
| `limit.stress_2022` | 35.69% | 33.0% | C |
| `limit.drawdown` | 40.56% | 44% | T |

Verdict **conflict**: 3 conflicts, 2 tensions, 2 passes. **Largest compatible size: 11.0 points** pro-rata.

Funding comparison for the same 25 points:

| Funding | Conflicts | Tensions | Notes |
|---|---|---|---|
| `pro_rata` | 3 | 2 | diversifiers diluted to 7.5% |
| `from_holdings` [QQQ, SPY, NVDA] | 2 | 2 | diversifiers stay at 10.0%; volatility 26.27%, stress 36.51% |
| `new_money` | 2 | 1 | position 20.0%; diversifiers 8.0% (T); volatility 24.58%; stress 33.65% |

Largest compatible size with `from_holdings` [QQQ, SPY]: 12.0 points; with `new_money`: 12.5 points.

Size sweep (pro-rata): 5 → tension (volatility 20.44); 10 → tension (21.62); 12 → conflict (22.15).

### 9.3 Mateo, +10 points CNQ.TO (AT-03)

| Rule | Value | Threshold | Status |
|---|---|---|---|
| `cap.position` | 10.0% (CNQ.TO) | 15% | P |
| `cap.sector` | 10.0% (Energy) | 30% | P |
| `cap.asset_class.crypto` | 0% | 5% | P |
| `cap.growth_assets` | 63.1% | 80% | P |
| `floor.fixed_income` | 33.3% | 10% | P |
| `limit.volatility` | 8.69% | 12% | P |
| `limit.stress_2022` | 2.73% | 15.0% | P |
| `limit.drawdown` | 10.22% | 24% | P |
| `exclude.sector.energy` | 10.0% | 0 | C |
| `evidence.controversy` | — | — | nee (`no_evidence_loaded`) with starter data only |

Verdict **conflict** (1 conflict, 1 nee). Largest compatible size: 0. Every financial rule passes: the conflict comes only from the stated preference, which is the point of this persona (brief p.6).

### 9.4 Other checks

| Scenario | Result |
|---|---|
| Mateo, +25 points TSLA | conflict: position 25.0 > 15; volatility 18.89 > 12; stress 24.24 > 15; drawdown 27.60 > 24. Largest compatible size 10.0 points. |
| Robert, +5 points BTC-USD | conflict on `exclude.asset_class.crypto` (5.0%); tension on growth assets (49.65) and stress (8.16) |
| Robert, +25 points TSLA, rate-cycle scenario | +4.07% (informational only) |
| Amira, +10 points NVDA | largest compatible size for NVDA is 10.0 points pro-rata |
| Largest compatible TSLA size, `new_money` | Robert 6.0, Mateo 11.0, Amira 12.5 |

## 10. Macro context controls

| Fact | Value |
|---|---|
| Bank of Canada target rate (`V39079`) at 2021-11-12 | 0.25% |
| First increase in the data | 2022-03-03 (to 0.50%) |
| Peak | 5.00% from 2023-07-13 |
| First decrease after the peak | 2024-06-06 (to 4.75%) |
| Last value in the data | 2.50% (2026-11-12) |
| Canada CPI year-over-year (`STATIC_TOTALCPICHANGE`), maximum | 8.1% (reference month 2022-06) |
| Government of Canada 10-year yield, minimum and maximum | 1.32% (2021-12-17), 4.26% (2023-10-03) |
| US 10-year Treasury yield (`DGS10`), minimum and maximum | 1.35% (2021-12-03), 5.31% (2026-10-05) |
| US federal funds effective rate (`DFF`), maximum | 5.33% (2023-07-27) |

## 11. Reproducing these numbers

```bash
python3 contracts/controls/controls.py   Datathon2026/alphaforge_starter
python3 contracts/controls/rules_ctl.py  Datathon2026/alphaforge_starter
python3 contracts/controls/rate_ctl.py   Datathon2026/alphaforge_starter
```

The scripts use only the Python standard library. They are throwaway reference calculations, not product code: the product implementation lives in `backend/aplomb/quant`, `optimizer` and `rules`, and its tests assert the values above.
