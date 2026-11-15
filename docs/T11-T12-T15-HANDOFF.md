# T11, T12, T15 and end-to-end integration handoff — 2026-11-15

World Explorer backend (T11), Time Machine backend (T12) and the three remaining pages (T15) are implemented, and the exported API now composes every implemented track. This note records what was built, what was verified and how, and what is still open. Details live in the [world spec](../backend/aplomb/world/SPEC.md) §8, the [Time Machine spec](../backend/aplomb/timemachine/SPEC.md) §6 and the [API spec](../backend/aplomb/api/SPEC.md).

## Run it

| Command (repository root) | Purpose |
|---|---|
| `npm run dev:api` | Local API on `http://localhost:8000/v1` with the active snapshot and the eight implemented feature flags on (on-demand tickers only with `APLOMB_TIINGO_TOKEN`, read from the environment or the git-ignored `.env`) ([scripts/dev_api.py](../scripts/dev_api.py)) |
| `npm run dev:web` | Web app on `http://localhost:3000` against that API |
| `npm run check` | Generated files, lint, Python tests, TypeScript, web tests, spec links, infra tests and synth |
| `cd backend && uv run python -m aplomb.world.ingest --start 2021-11-12 --end 2026-11-12` | Rebuild the world bundle from the public feeds (network; not needed to run) |

Runs and free-text parsing need `APLOMB_MODEL_STRONG`, `APLOMB_MODEL_FAST` and AWS credentials. Without model IDs they answer `503 upstream_unavailable` before anything is stored; every deterministic page keeps working.

## What works now

| Area | Behaviour |
|---|---|
| World Explorer API | `GET /world/layers`, `/events`, `/events/{id}`, `/exposure`, `/countries/{iso3}`, `/hazards` serve a cited bundle of 751 real events, of which 668 are earthquakes (also served as hazards). `/facilities` answers `501` (no registry loaded). |
| Time Machine API | `GET /replay/presets` (range 2022-11-22 to 2026-08-18 on the starter data), replay runs through a historical gate with thresholds re-derived at the cutoff, `POST /runs/{id}/reveal` in a separate ledger. |
| Runs | `decision` (move and goal), `replay`, `portfolio_brief`, `event_brief`, `profile_draft` execute through the real workflow, code controls, ledger and auditor. Step summaries are bilingual code templates with counts. `GET /runs` titles are built from the pinned input. |
| Home brief | `GET /profiles/{id}/brief` returns the latest succeeded brief of the session, profile and language, with `stale` when the profile or data version changed; `POST /runs` reuses a non-stale brief. |
| Sources | `world_events` and `natural_hazards` passports are `in_use` with their sources, retrieval date, counts and what is not loaded. |
| Feature flags | A flag is advertised only when configured **and** its provider exists: `bilingual`, `world_explorer`, `world_layer_hazards`, `time_machine`, `profile_creator`, `goal_requests`, `frontier_chart`. |
| Windows | The API, the tests and `npm run check` run on Windows as well as Linux and macOS. |
| Web | All nine routes are built; World Explorer, Time Machine and Agents & System are real pages (see below). |

## T15 pages

| Route | File | Content |
|---|---|---|
| `/world-explorer/` | `web/src/features/world/` | Filter toolbar, paginated feed with counts, event panel, country panel, exposure table with the "no listing country" row, layer toggles, hazards table, client-only globe (`react-globe.gl`, `next/dynamic` with `ssr: false`) with a list fallback, "Brief me" run |
| `/time-machine/?runId=` | `web/src/features/timemachine/TimeMachinePage.tsx` | Presets and bounded date input, fixed warnings, replay run with cutoff banner, gate table and rule table, reveal with per-scenario cards, chart, table alternative and a separate reveal fact scope |
| `/agents-system/?runId=` | `web/src/features/system/AgentsSystemPage.tsx` | Six role cards, architecture with the actual `/meta` state, run picker, per-step detail (actor, model, usage, tool calls, datasets read) |

Shared changes: nine client methods in `web/src/api/client.ts` (world, presets, reveal), a `reveal` scope in `FactDrawer`, labels for every displayed code in `web/src/lib/labels.ts`, pure logic in `web/src/lib/{world,replay,system,geo}.ts`. In fixture mode the three pages show the typed `503`; nothing is invented.

Dependencies added to `web/package.json`: `react-globe.gl` 2.38.0 (MIT; brings `globe.gl`, `three-globe`, `three`, `react-kapsule`, all MIT). Country outlines are `web/public/geo/countries-110m.json` from `world-atlas` 2.0.2 (ISC, Natural Earth geometry, public domain), decoded by a small in-repo TopoJSON decoder; no third-party request at run time.

Verification of the pages: `npm run typecheck`, `npm run test:contracts` (124 tests, 27 of them new), `next build` (ten static routes), a headless Chromium pass at 1440 px and 375 px in English and French against a temporary contract-shaped mock (89 checks) and against the real API without a model (38 checks), and the audit described below.

Contract proposals from the UI (not applied; `contracts/` is T01's):

1. `CountryExposure` has no `factId` or name; the UI matches the fact by `subject.type == "country"`.
2. `RevealOutcome` does not say which fact holds the return and which the largest fall; the backend returns them in that order. Proposal: `returnFactId`, `maxDrawdownFactId`.
3. `HoldingExposure.impactFactId` and `evidenceIds` cannot be resolved from `GET /world/events/{id}` (no fact map on that response).
4. `WorldLayer.legend` entries carry no category code.
5. `GET /replay/presets` takes no `profileId`, although a date can be refused for a profile (`details.unknownAtAsOf`).

## Integration defects found and fixed

These blocked a real run or a clean check; each has a regression test.

1. **No real decision could be signed.** The auditor verified a computed fact only through verified input facts, and quant facts declared none, so every cited figure was struck and the mandatory sections failed. Fix: lineage is now registered (the stipulated portfolio composition as an assumption fact cited by weight and concentration figures; the rule definition for statuses that rest on no figure) and a figure computed straight from gated dataset rows is verified by its dated sources, the same structure required of an observed fact ([ledger spec](../backend/aplomb/ledger/SPEC.md) §1). A producer's own "verified" flag is still ignored.
2. **No replay could be signed.** In historical mode any fact without `availableAt` failed A11, including weights of the stipulated portfolio. Fix: a fact that reads no dataset row is timeless (`ledger.core.is_timeless`); a fact that reads rows still needs its availability.
3. **Goal runs failed** with "Checkpoint exceeds 97 changed children": one step registers more than a hundred facts. The worker now writes immutable facts and evidence in batches of 40 before the final checkpoint.
4. **The exported API had no run, parser, world or replay provider**, and `portfolio_brief` and `event_brief` were refused by the workflow. See "Run composition" in the API spec.
5. **Windows.** `aplomb.api.storage` imported `fcntl` (the API could not start); files were read with the platform default encoding; hash-based checks failed on CRLF checkouts. Fixes: byte-range lock on Windows, explicit UTF-8, and a `.gitattributes` that keeps text files LF on every checkout. One web test compared a backslash path with a TypeScript host path.
6. **Startup crash on a user agent without a contact.** The research transport rejects it; the composition now logs it and leaves the research tools unregistered instead of failing at import.
7. **Lambda packaging probe imported NumPy and SciPy**, which are not dependencies; it now probes the real ones and the packaged world bundle. The stack accepts `application.features` so reviewed flags can be switched on without editing the stack ([infra README](../infra/README.md)).
8. **World dedupe.** Two copies of one story from the same publisher that differed only by a tracking parameter counted as two sources.

An independent review of the backend change then found twelve more defects, all fixed with regression tests in `backend/tests/integration/test_review_regressions.py`:

9. **A worker crash or retry during the audit step failed the run.** The writer model was read from the last step (the audit step itself on resume) and the frozen ledger was saved one write before the step output. A completed step is now one checkpoint (ledger state, cached output, references, done status) and the writer model comes from the write step.
10. **The event-brief fact assumed an end-of-day publication time** for the 726 events whose source states none, and cited the price data date as its retrieval date. It now uses the retrieval time and terms recorded in the bundle manifest, and the run's cutoff is the bundle date when later than the price data.
11. **Dataset-derived figures could pass the historical availability check without a timestamp.** Group, sector and class weights now cite `assets_universe`; the first-conflict boundary cites the price rows it searched; timeless derived facts are limited to pure arithmetic methods; re-derived thresholds carry their cutoff and a replay refuses any other.
12. **A box crossing the dateline was rejected by the API** although the service supports it.
13. **A replay goal by theme always failed late** because no theme tag is visible at a historical date; it is now refused at creation with the reason, and a theme rule answers `nee`.
14. Minor: a measured price move cited in an event brief was struck (the audit was not told which facts are measurements); the listing-country note named the event's first country instead of the holding's; a portfolio brief could run research; ISO week dates were accepted and returned nothing; macro labels were English in French and the CPI index was typed as a ratio; focus cards could show an unverified figure and raw status codes.

## Repository audit (2026-11-15)

A read-only audit of the whole repository by area (HTTP contract, persistence, datastore, quant and rules, optimizer and profiles, agents and ledger, tool registry, web pages, acceptance rows, configuration and documentation, security, world and Time Machine), each finding re-checked by independent verifiers, confirmed 76 findings (about 45 distinct defects; 8 more were refuted). A separate review of the three new pages, including a real-browser pass, confirmed 21 more (about 14 distinct). The fixes below were checked by re-running each original scenario on the final tree, not only by the new tests.

Fixed, with regression tests in `backend/tests/integration/test_fix_{workflow,profiles,historical_check,api_persistence}.py`, `backend/tests/ledger/test_fix_audit_language.py`, `backend/tests/unit/datastore/test_fix_passports.py` and `web/tests/fix-web.test.ts`:

| Area | What changed |
|---|---|
| Historical checks | `POST /check` with a past `asOf` uses thresholds and the rule set derived at that date, like a replay; a date after the data date is `422`. A replay keeps the rule set derived at its cutoff (for example a growth cap and a fixed-income floor that today's data no longer needs). The 2022 stress counts as visible on 2022-12-30. |
| Profiles | Zero-weight positions, weights at 100 ± 0.01, whitespace names, caller-supplied rules (checked against the rule definitions), unknown tickers (`422`), unknown or empty excluded sectors, short derivation windows: no `500` remains. Excluded asset classes other than crypto create their exclusion rule and the proposed portfolio avoids them. |
| Runs | A clarification answer (size or funding, in plain words in either language) is applied to the simulated request. Planner proposals outside the tool catalog or the universe are dropped and disclosed instead of failing the run; the planner is told what it may name. A move, funding or window that `/check` refuses is refused at run creation with the same `422`. A failed run carries a catalog code and a message written by this code base, never provider text (account ids, roles); model failures are `upstream_unavailable`. A worker that dies between batched fact writes resumes to the same facts. |
| Parser, idempotency, local execution | `POST /requests/parse` answers `503` when the model fails. An idempotent retry of a failed run returns its run ID. Local workers no longer let a queued run be killed by the watchdog; terminal runs close their running steps. The local state file is no longer re-parsed and rewritten on every call. An unreachable S3 snapshot answers `503`. |
| Audit and briefs | French briefs pass the audit (articles and ordinary adverbs are not numbers or comparisons). A cited "loss" figure and a true comparison with a stated threshold are kept. Status words are localized. Verified research evidence reaches the controversy rule. Ledger displays keep the precision of the unit (0.25% stays 0.25%). An event brief with no linked holding says so. |
| Tools | Every T04–T07 tool can be called repeatedly with the real ledger (fact keys carry currency, year, day count, ticker); per-run tool state survives the ledger copies; `macro.series` units are right; research facts cite the pinned data version; `research.save_evidence` shows the model its exact argument schema. |
| Sources page | Passports match what is loaded (release dates, personas, theme sources, the FX trap). `scripts/dev_api.py` no longer rewrites `active.json` and resolves a relative data directory. |
| Speed | The goal search step fell from about 24 s to 2 s on the development machine; `GET /profiles/{id}/frontier` is cached per profile content, snapshot and query (warm 22 ms instead of 3.8 s; the first call still takes about 4 s). |
| Web | Rule sentences state the threshold each check was evaluated with (replays, edited rules). Limitation codes, French section ids and raw statuses read as words. Home keeps its brief across navigation and labels a brief written for another window. Portfolio keeps disabled rules listed so they can be enabled again. Decision Desk marks the brief stale after a window or threshold change, claims no boundary without a move, and quotes the boundary scenario's own counts. Time Machine runs on the whole visible history whatever the page window, and reveal cards show the fact's own figure. World Explorer labels a brief written for another persona, says when no holding is linked, titles the hazards layer as loaded, and has no intro spin under reduced motion. Agents & System follows the selected run's live status and no longer warns about profile drafts. `npm run dev:fixtures` runs on Windows. Run polling retries a failed final fetch. |

## Verification performed

- `npm run check` on Windows 11, Python 3.12.16, Node 22.15.1, after every fix below: passed (707 Python tests, 128 web tests, 5 infrastructure tests, lint, strict TypeScript, generated-file drift, specification links, numeric controls, CDK synth). `next build`: ten static routes.
- Offline tests with the real datastore, quant, rules, optimizer, ledger and auditor: world (50), Time Machine (23), review regressions (16, including worker crashes at each model call and while persisting the audit step), and `backend/tests/integration/test_run_composition.py` (15) which drives the composed app over HTTP for every world endpoint, AT-01 through a full run, AT-07 (every numeric segment resolves to a verified fact of the same run), AT-09 (a failed model step keeps executed steps and figures), AT-13 (replay then reveal; the stored run is identical afterwards), AT-17 (goal candidates), idempotency, session isolation, the brief cache and `501` for disabled flags.
- In those tests the model is replaced by `tests/integration/_scripted.py`, a scripted gateway whose model ID is `scripted-test-gateway (no LLM)`. It is never imported by the application.
- Live network, once, on 2026-11-15: the world ingestion against USGS, the Bank of Canada, the Federal Reserve and Statistics Canada (all four answered; counts in the bundle manifest).
- Local API started with `scripts/dev_api.py` on Windows and queried over HTTP (meta, presets, events, brief lookup, rule edit persisted in `.artifacts/`).
- Cross-language check `npx tsx web/tests/live-api.check.ts <api base> [--runs]`: the web client, with the runtime contract validation the pages use, called every endpoint of a running API. 65 of 65 calls validated against the API without a model (runs and parsing answer `503`), and 91 of 91 against the same API with the scripted model stand-in, including decision, French decision, goal, replay then reveal, portfolio brief, event brief and profile draft runs.

**Not verified:** any run written by a real Bedrock model through this composition (no AWS credentials on the development machine); the Strands transport live; DynamoDB, S3 and Lambda; the deployed web export; GDELT, SEC and issuer sources; screen-reader behaviour.

## Decisions that other tracks should confirm

| Topic | What was done | Owner to confirm |
|---|---|---|
| Unknown country bucket | `countryIso3 = "ZZZ"` for crypto and cash in `GET /world/exposure` | T01 (document in api.md §6.4) |
| Reveal baseline | First outcome `sc_unchanged` is the portfolio without the change; it is not a run scenario | T01 (schemas.md §11) |
| Replay dates | Any date in the eligible range is accepted, not only the listed presets | T01 (api.md §5.1 says "one of the dates accepted by 7.1") |
| Ledger lineage rule | Dated dataset sources verify a computed fact that has no input fact | T10 |
| Timeless facts in A11 | Inputs, assumptions and figures derived only from them need no `availableAt` | T10 |
| World bundle in the package | Shipped inside `backend/aplomb/world/bundle/`, not in the S3 snapshot prefix | T02, T04 |
| Theme proxy | Monetary-policy events are tagged with the bond themes of their country, labelled as a team assumption | Product owner |
| Bilingual | Advertised; the writer is told the language. French briefs were not read by a French speaker with a real model | Product owner (first item on the cut list) |

## Still open

| Item | Why | Estimate |
|---|---|---|
| Real Bedrock decision, replay and briefs through this composition | Needs credentials; first live gate of the delivery plan | 30 minutes with the AWS operator |
| Sabotage demonstration run | T10 helpers exist; the workflow kind and the `Services.sabotage` callable are not built | Half a day |
| Research in runs | Tools register only with a contact user agent; SEC answered 403 and GDELT was empty in earlier probes; the event sources' domains are not on the research allow-list | 2 hours to review domains, more for sources |
| Attention signal and on-demand tickers | No live provider wired (`503`) | Half a day each |
| Facilities layer, NASA FIRMS | Cut-list item 2 | Half a day each |
| Older official events | The press feeds list recent items only | 2 hours for an archive crawl |
| Frontier first call | About 4 s for the first request of each profile version; later calls are cached | 2 hours to speed up the solver |
| World Explorer details (low) | Stale selection after a long "Brief me", globe country names in English only, chart axis labels small at 375 px, fact drawer stays open on browser Back, possible horizontal scroll at 375 px with the hazards layer, 404 for route prefetch files on a plain static file server (navigation still works) | About 2 hours together; none blocks a journey |
| Real-browser re-check of the fixes | The last browser pass ran before the audit fixes; the fixes are covered by unit, integration and live API checks only | 20 minutes |
| Acceptance report | T16 has not recorded AT rows under `docs/deliverables/` | 2 hours |
