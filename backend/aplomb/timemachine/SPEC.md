# Time Machine — date-gated decisions and separate reveal

**Track:** T12. **Tier:** P1, cut item 3. This feature is unrelated to offline replay; D-38 still rejects an offline application mode.

## 1. Inputs and public services

`presets() -> ReplayPresetsResponse` matches [HTTP §7.1](../../../contracts/api.md): it is derived from the loaded snapshot alone and takes no profile (the service method receives only the session ID). `validate_asof(date, profile, snapshot) -> HistoricalContext`; `gate_report(context) -> GateReport`; `reveal(run, until) -> RevealResult`. Replay run creation and orchestration remain T03/T08 responsibilities. T04 owns the generic availability gate; this module chooses historical eligibility, restrictions and reveal isolation.

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

## 6. Implementation status (T12, 2026-11-15)

Replay is implemented in `backend/aplomb/timemachine/service.py`; the run composition that calls it is `backend/aplomb/api/runtime.py`, and `ReplayServiceImpl` is built in `backend/aplomb/api/domain.py`. The folder also holds the module below. The ALFRED vintage rights status (`pit_routes.py`, `vintages.py`, `GET /v1/timemachine/vintages/status`) was removed with the Markets research surface: it only reported that no vintage is fetched, and revised macro series stay withheld in replays (`LIM_MACRO_REVISED`).

| Module | Content |
|---|---|
| `records.py` | `PointInTimeRecords`: cutoff selector for source records with evidenced availability. No production caller; only its unit test uses it |

| Call | Use |
|---|---|
| `eligible_range(snapshot)` | Earliest = 252nd master observation, latest = 60 master days before the snapshot end |
| `build_presets(snapshot)` / `ReplayServiceImpl.presets` | Body of `GET /replay/presets` |
| `validate_asof(as_of, profile, snapshot, request)` | Called when a replay run is created; returns the pinned `HistoricalContext` or raises `validation_error` |
| `gate_report(gate)` | Visible and withheld rows per dataset (`M_GATE_COUNT`) |
| `replay_result(decision, ctx, private)` | `AgentServices.replay_result_factory`: actual gate metadata of a signed replay |
| `reveal(run, snapshot, until, created_at)` / `ReplayServiceImpl.reveal` | Body of `POST /runs/{id}/reveal` |

On the starter data the eligible range is 2022-11-22 to 2026-08-18. Presets: the eligible day followed by the largest fall of SPY within the next 60 master days (2025-02-19, labelled as selected with hindsight), the last master day of each completed year in range, and the earliest date.

### 6.1 Decisions taken in this track

- **Accepted dates.** Any calendar date inside the eligible range, including a non-trading day (the gate then shows the last earlier row). Outside the range the API answers `422` with `details.earliestAsOf` and `details.latestAsOf`; a held or requested asset with no visible price at the date answers `422` with `details.unknownAtAsOf`.
- **Thresholds.** At run creation every rule whose origin is `derived` is recomputed through a historical gate at the as-of date and pinned in the run; user-edited and preference rules are kept as they are. A derived rule that cannot be recomputed at that date rejects the run instead of keeping a threshold built from later data.
- **Cutoff stamp.** Each re-derived rule carries `derivation.inputs.asOf`; the worker refuses to open the gate of a replay whose pinned profile holds a derived rule stamped with another date.
- **Themes.** Theme tags are 2026 assignments, so none is visible at a historical date. A replay goal that names a theme is refused at creation (`422`, `details.themesVisibleAtAsOf = false`) instead of failing later with no candidate, and a theme rule evaluates to `nee` (`not_visible_at_asof`), never to a passing zero.
- **Gate report.** A dataset with no dated visible row is omitted (for example `asset_themes`, whose assignments date from 2026, and `assets_universe`, which has no date column), because the wire type requires a `lastVisibleDate` and none is invented.
- **Timeless facts in the audit.** A historical run rejects any fact whose availability is unknown. A fact that reads no dataset row (a user input, a stated assumption, or a figure derived only from those, such as a weight of the stipulated portfolio) is timeless and allowed; a fact that reads rows needs `availableAt` (see `ledger.core.is_timeless`).
- **Reveal.** Weights come from the signed result (`portfolioBefore` and each scenario's `portfolioAfter`), valued through a gate at `until` in a fresh `LocalLedger`. The first outcome, `sc_unchanged`, is the portfolio without the change; it is not one of the run's scenarios. Each outcome has two facts (`return.period`, `drawdown.max`) with `createdBy = "timemachine"` and the actual first and last master days. Nothing is written to the run.
- **Notices.** `LIM_LLM_KNOWLEDGE`, `LIM_SAMPLE_WINDOW`, `LIM_SURVIVORSHIP`, `LIM_YAHOO_NOT_CERTIFIED` always, plus `LIM_MACRO_REVISED` (revised U.S. macro series are withheld in a replay, and that is disclosed).

### 6.2 Verification

`uv run pytest backend/tests/unit/timemachine` (offline; `test_timemachine.py` for replay, plus `test_records.py`): TM-01 range from the master calendar, TM-02 future prices, FX and macro perturbed on a synthetic snapshot with identical historical facts, TM-05 stress 2022 `nee` before the window ends, TM-06 thresholds from pre-cutoff data, TM-07 reveal in a separate ledger and checked against an independent calculation, TM-08 run unchanged after reveal, TM-09 date and ownership validation. `backend/tests/integration/test_run_composition.py` runs a replay through the real workflow over HTTP: no research step, no fact available after the cutoff (TM-03, TM-04 through the registry and the audit), mandatory notices in the result (TM-10, backend part), then the reveal. Not verified: a replay written by a real Bedrock model.
