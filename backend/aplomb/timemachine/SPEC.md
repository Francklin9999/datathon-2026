# Time Machine — date-gated decisions and separate reveal

**Track:** T12. **Tier:** P1, cut item 3. This feature is unrelated to offline replay; D-38 still rejects an offline application mode.

## 1. Inputs and public services

`presets(profile_id) -> ReplayPresetResponse` matches [HTTP §7](../../../contracts/api.md). `validate_asof(date, profile, snapshot) -> HistoricalContext`; `gate_report(context) -> GateReport`; `reveal(run, until) -> RevealResult`. Replay run creation and orchestration remain T03/T08 responsibilities. T04 owns the generic availability gate; this module chooses historical eligibility, restrictions and reveal isolation.

## 2. Eligibility and gate counts (`M_GATE_COUNT`)

Earliest preset has >=252 master **price observations**, not 252 calendar days. Calculate from the loaded snapshot, do not hardcode an invented “before 2022 crash” date. Latest offered date is at least 60 master days before snapshot end, matching the HTTP contract. Presets include the eligible last master day before the largest subsequent 60-day SPY drawdown, plus eligible year-end dates; this hindsight-selected demonstration date is explicitly labelled and never enters decision inputs. Reject dates outside eligible range, future dates and portfolios containing assets unknown before cutoff. Each data row is available only under the datastore's next-day-exclusive UTC policy. Count withheld candidate rows by dataset and expose the last visible date. Empty visible datasets are omitted from gate report or use an explicitly documented no-visible-data row; do not invent a lastVisibleDate.

## 3. Historical evidence policy

No live document/news/browser research, attention lookups, current ETF look-through or on-demand ticker fetch in replay. Thresholds are derived with only eligible pre-cutoff data; no stored current-data derivation may leak its future inputs. Keep profile assumptions/user-provided present-day fictional holdings visible as such: replay asks about a hypothetical portfolio at that date, not a recovered historical account. Macro with unknown release date or unreconstructed revised vintages is withheld. A 45-day assumed lag is insufficient for the point-in-time claim.

Price timestamps are simulated daily availability policies on a retrospectively adjusted snapshot; dividends/splits and vendor revisions can alter earlier adjusted history. Universe selected in 2026 introduces survivorship. Mandatory notices: `LIM_LLM_KNOWLEDGE`, `LIM_SAMPLE_WINDOW`, `LIM_SURVIVORSHIP`, `LIM_YAHOO_NOT_CERTIFIED`, plus macro revision/lag notices if context warrants. Prompt tells the model the cutoff but does not claim to erase model knowledge. Code audits fact availability and excludes post-cutoff facts from writer input.

2022 stress is unavailable before its last boundary; rules depending on it return nee (`not_visible_at_asof`). Do not hide those rules to make the historical verdict green. A01/A11 violations fail signing.

## 4. Reveal isolation

Require succeeded replay run owned by session. Validate `asOf < until <= snapshot last date`. Use parent's pinned scenario weights/version and a **new reveal ledger/context**, with no model call. Index each scenario at 100 on the actual last master day <=asOf and compute constant-weight returns/drawdown through last master day <=until. Return explicit actual dates in facts and independent fact IDs; UI namespace is reveal, not parent's signed fact map.

Reveal never adds facts to the parent, changes its decision/verdict, or reruns the model with future outcomes. Fixed statement: outcomes describe what those hypothetical fixed mixes did in this dataset; they do not establish that a prediction was made or that one choice is generally superior. Reject empty/unsupported windows with insufficient_data.

## 5. Verification and delivery

TM-01 derive earliest eligible date from actual master calendar. TM-02 perturb future prices/FX and prove historical fact outputs unchanged. TM-03 future/unknown-release/revised macro withheld. TM-04 direct tool registry cannot bypass gate. TM-05 before-2022-end stress rule nee. TM-06 derived thresholds use pre-cutoff data. TM-07 reveal shares pinned weights but not ledger/state with decision. TM-08 parent hash unchanged after reveal. TM-09 date/ownership validation. TM-10 mandatory model-knowledge/vintage limitations in UI and brief.

Provide T15 presets with date-disabled reasons, gate report and separate reveal fixture. No marketing wording should describe this as leakage-free historical forecasting.
