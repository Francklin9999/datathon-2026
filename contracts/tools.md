# contracts/tools.md — tools the agents can call

A **tool** is a Python function with a fixed name, typed arguments and a typed result. The Planner names tools in its plan, the Researcher calls research tools in its loop, and the workflow code executes them. Every call is recorded as a `ToolCall` in the run (`schemas.md` §9), which is what the "What the agents did" timeline shows.

Three tracks implement tools; one track consumes them:

| Namespace | Implemented by | Spec |
|---|---|---|
| `data.*`, `universe.*`, `profile.*`, `macro.*` | T04 datastore / T06 profiles | `backend/aplomb/datastore/SPEC.md`, `profiles/SPEC.md` |
| `quant.*` | T05 quant | `backend/aplomb/quant/SPEC.md` |
| `optimizer.*`, `rules.*` | T07 optimizer / T06 rules | `optimizer/SPEC.md`, `rules/SPEC.md` |
| `research.*`, `edgar.*`, `gdelt.*`, `web.*`, `attention.*` | T09 research | `backend/aplomb/research/SPEC.md` |
| `world.*`, `emissions.*` | T11 world | `backend/aplomb/world/SPEC.md` |
| registry, execution, recording | T08 agents | `backend/aplomb/agents/SPEC.md` |

---

## 1. Rules that apply to every tool

1. **Signature.** `def tool(ctx: ToolContext, **args) -> ToolResult`. Tools never read environment variables, clocks or global state directly; everything comes from `ctx`.
2. **`ToolContext`** carries: `run_id`, `profile` (may be None), `lang`, `as_of` (date), `gate` (the temporal gate, `datastore/SPEC.md` §4), `ledger` (to register facts and evidence), `store` (cache), `limits`, `logger`.
3. **`ToolResult`** = `{ ok: bool, summary: str, fact_ids: list[str], evidence_ids: list[str], data: dict, datasets_read: list[DatasetRead], error: str | None }`. `data` is what the model sees; it must contain **fact IDs next to every number** so the model can cite them and never needs to retype a value.
4. **Numbers leave tools only as facts.** A tool that computes or reads a number registers a `Fact` in the ledger and returns its ID. The `data` shown to the model repeats the value for reasoning, tagged with the fact ID: `{"value": 16.96, "unit": "pct", "factId": "F-008"}`.
5. **Determinism.** Same arguments + same `dataVersion` + same `asOf` → same result. Research tools are deterministic through their cache (keyed by arguments and retrieval date).
6. **Temporal gate.** Every data read goes through `ctx.gate`. A tool cannot bypass it; there is no "raw" accessor.
7. **Errors are results.** A tool never raises to the model. On failure it returns `ok = false` with a short `error`; the workflow decides what to do.
8. **Timeouts.** Quant and data tools: 5 s. Research tools: 20 s per call. Enforced by the executor.
9. **No side effects outside the ledger and caches.** No tool writes profiles, places orders or sends messages. There is no order tool (EF-16).
10. **Argument validation** with Pydantic models named `<ToolName>Args`; a validation failure is returned as `ok = false`.

The JSON schema handed to the model for each tool is generated from the Pydantic args model plus the description below. Descriptions are written for the model: say what the tool returns and when to use it.

---

## 2. Lookup tools (read-only, available to Planner and Researcher)

| Tool | Args | Returns (`data`) | Use |
|---|---|---|---|
| `universe.search` | `q?: str, asset_class?: str, theme?: str, limit: int = 10` | `assets: [{ticker, name, assetClass, sector, themes, nObsMaster}]` | Find candidate assets for a goal or resolve a company name to a ticker |
| `universe.get` | `ticker: str` | one `Asset` | Check that an asset exists and how much history it has |
| `profile.get` | — | profile summary: risk level, horizon, objective, preferences, rule list with thresholds, positions | Start of every plan |
| `data.describe` | `dataset_id: str` | passport summary: coverage, frequency, limitations | Decide whether a dataset can answer a question |
| `macro.series` | `series_id: str, start?: date, end?: date` | first, last, min, max with dates, each as a fact | Macro context for the brief (D-27) |

Macro series IDs available in the starter snapshot: `V39079`, `BD.CDN.2YR.DQ.YLD`, `BD.CDN.10YR.DQ.YLD`, `STATIC_TOTALCPICHANGE`, `DFF`, `DGS2`, `DGS10`, `CPIAUCSL`, `UNRATE` (verified in `macro_rates.csv`).

---

## 3. Quant tools (executed by code in the `quant` step)

The Planner requests these by name in its plan; it does not call them itself. A fixed **mandatory set** runs for every decision regardless of the plan (`agents/SPEC.md` §4.3).

| Tool | Args | Facts produced |
|---|---|---|
| `quant.asset_metrics` | `ticker, window, currency?` | `return.period`, `vol.annualized`, `drawdown.max`, `return.worst_12m` for the asset |
| `quant.calendar_year_return` | `ticker \| "portfolio", year, variant?, currency?` | `return.calendar_year` in the listing currency and in the reporting currency |
| `quant.portfolio_snapshot` | `variant: "before" \| "after" \| "scenario:<id>"` | weights by position, group, sector, country; `value.portfolio` |
| `quant.portfolio_metrics` | `variant, window` | `vol.annualized`, `drawdown.max`, `stress.replay_2022`, `concentration.hhi`, `concentration.effective_n` |
| `quant.apply_move` | `move: ProposedMove, base_variant = "before"` | registers a scenario portfolio; `weight.position` before and after for the moved asset and the funding assets |
| `quant.compare_funding` | `ticker, size_pct` | one scenario per feasible funding mode, with `M_WEIGHTS_AFTER_MOVE` facts |
| `quant.stress_replay` | `variant, window_id: "2022" \| "rate_cycle" \| custom Period` | `stress.replay_2022` or `stress.rate_cycle` |
| `quant.correlation` | `tickers: list[str], window` | `corr.pair` per pair |
| `quant.exposure` | `variant, theme` | `weight.theme` |
| `quant.price_move_after` | `ticker, date, n_days` | `return.period` with method `M_PRICE_MOVE_AFTER_EVENT` and limitation `LIM_PRICE_MOVE_NOT_CAUSAL` |

Windows are `WindowSpec` objects. Variants refer to portfolios registered in the run by `quant.apply_move`.

---

## 4. Rule and optimizer tools (executed by code)

| Tool | Args | Result |
|---|---|---|
| `rules.check` | `variant` | `RuleCheck[]`, verdict and counts for that portfolio; registers `rule_check` facts |
| `optimizer.max_compatible_size` | `ticker, funding: Funding` | `size.max_compatible` fact; the grid of sizes tested |
| `optimizer.goal_candidates` | `goal: ExposureGoal, max_candidates: int = 3` | scenarios of kind `goal_candidate`, each a set of moves sized to the largest compatible size, ranked |
| `optimizer.alternatives` | `ticker, size_pct` | scenarios of kind `alternative`: other assets sharing a theme with the requested one, sized to fit |
| `optimizer.rebalance` | `target: "within_rules"` | scenario of kind `rebalance`: smallest set of moves that removes every conflict in the current portfolio |
| `optimizer.derive_thresholds` | `risk_level, horizon, preferences` | derived `PolicyRule[]` with derivation facts |

---

## 5. Research tools (called by the Researcher inside its loop)

Every research tool returns **evidence**, not conclusions. An evidence item needs a URL, a publisher, a retrieval timestamp and, when it supports a claim, a verbatim quote of at most 400 characters stored together with the cached document (`research_documents`) so check `A08` can find it.

| Tool | Args | Returns | Tier | Flag |
|---|---|---|---|---|
| `edgar.find_company` | `name_or_ticker: str` | CIK, official name, tickers | 1 | — |
| `edgar.list_filings` | `cik, form_types: list[str], since?: date, limit = 10` | filing metadata: form, filing date, accession, URL | 1 | — |
| `edgar.filing_text` | `accession: str, query?: str, max_chars = 6000` | passages matching `query` with character offsets | 1 | — |
| `edgar.company_facts` | `cik, concept: str` | reported values with period and filing date | 1 | — |
| `gdelt.search` | `query: str, start: date, end: date, country?: str, limit = 20` | articles: title, publisher domain, date, URL, tone | 2–3 | reads the cached batch first |
| `web.fetch` | `url: str, query?: str, max_chars = 6000` | page title, publisher, retrieved text passages | by domain | domain must be on the allow-list |
| `web.browse` | `task: str, start_url?: str, max_pages = 5` | pages visited with passages | by domain | `research_open_web` (O-02) |
| `attention.pageviews` | `ticker: str` | `AttentionSignal` with fact | 1 (Wikimedia data) | — |
| `emissions.facilities` | `ticker_or_operator: str, country?: str` | matched facilities with reported emissions | 1 | `world_layer_facilities` |
| `etf.holdings` | `ticker: str, top_n = 25` | constituents and weights with the file date | 1 | when `etf_holdings` is loaded |
| `world.search_events` | `q?: str, country?: str, ticker?: str, start, end, limit = 20` | `WorldEvent[]` from our own dataset | as stored | — |
| `research.save_evidence` | `type, title, publisher, url, published_at?, quote?, claim, subject` | `evidenceId` | — | the only way evidence enters the ledger |

Rules specific to research:

- A page that is fetched but not saved with `research.save_evidence` leaves no trace in the result and cannot be cited.
- `research.save_evidence` rejects a quote that is not found verbatim (after whitespace normalization) in the document fetched during the same run.
- The tier is assigned by code from the domain (`research/SPEC.md` §4), never by the model.
- External request details marked `[VERIFY]` in `research/SPEC.md` (endpoints, rate limits, required headers) must be confirmed by T09 before the first call.

---

## 6. What each agent may call

| Agent | Tools |
|---|---|
| Planner | §2 lookup tools only. It **names** quant, rule, optimizer and research tasks in its plan. |
| Researcher | §2 lookup tools and §5 research tools. Cannot call quant or rule tools. |
| Quant Engine (code) | §3 |
| Risk Officer (code) | §4 |
| Writer | none. Receives the ledger and the rule checks as input. |
| Auditor | none through the model. Its code checks read the ledger; its LLM review receives sentences and the facts they cite. |

## 7. Adding a tool

1. Add a row here (name, args, result, facts or evidence produced).
2. If it produces a new metric or method, add it to `catalog.md`.
3. Implement it in the owning module with its `Args` model and a unit test that runs without network access.
4. Register it in `backend/aplomb/agents/registry.py`.
5. Tell T08 so the Planner or Researcher prompt mentions when to use it.
