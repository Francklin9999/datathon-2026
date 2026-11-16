# UI inventory and justification

**As of:** 2026-11-15. The web app after the navigation overhaul and after the frontend handoff of the backend cleanup (release `8e560ef`, `docs/FRONTEND-HANDOFF.md`), applied on `feat/frontend-handoff` from `main` at `bb6baed`.
**Purpose:** say, for every page, what each kept section, component and main button is for, which API it calls, which requirements it serves and which official grading criterion it supports; then what moved to Labs, what was merged, what was removed and how the menu is grouped.
**Method:** read from the code. Routes come from `web/src/app/*/page.tsx` and `web/src/app/not-found.tsx`; calls from `web/src/api/client.ts`, `researchFetch` (`web/src/api/research.ts`) and the few direct `fetch` calls, matched to `backend/aplomb/api/app.py`, the routers it includes and [contracts/api.md](../contracts/api.md). The parts the handoff changes (Labs, Portfolio's Risk tab, Replay's macro note, World's modes and layers, Sources, the audit test, the persona tour) follow the handoff and the owner's target; they were written while that branch was being implemented. Design rules are in [web/DESIGN.md](../web/DESIGN.md), routes in [web/SPEC.md](../web/SPEC.md) §1. Where a mapping is uncertain, the row says so.

## How to read the tables

- **Endpoint:** method and path under `/v1` (`{id}` is the profile ID), then its reference in [contracts/api.md](../contracts/api.md): a section or index number (`3.9`, `A1.20`), or **13F** for the table "Fictional investor locations and attributed 13F comparisons". "Static" is a file served with the site. "(run)" means the data comes from the run already loaded on the page. Former routes in §19 are no longer in the API or in api.md.
- **Requirements:** `EF-xx`/`EXT-xx` and the user journeys (named in italics) of [01-PRODUCT](01-PRODUCT.md); `D-xx`/`A-xx`/`O-xx` of [02-DECISIONS](02-DECISIONS.md); `AT-nn` of [07-ACCEPTANCE](07-ACCEPTANCE.md); the verification IDs of each page spec (`HOME-01`, `PORT-02`, `DESK-03`, `AUDUI-01`, `SYS-01`, `WUI-01`, `TMUI-01`, `SRC-01`, `CRE-01`) under `web/page-specs/`; `WEB-xx` of [web/SPEC.md](../web/SPEC.md) §6. "No EF/EXT row" marks a feature added after the product table was written.
- **G:** the official grading criterion of the brief (p.19), main one first.

| Code | Criterion (brief p.19) | Weight |
|---|---|---|
| G1 | Quality, relevance and innovation | 20% |
| G2 | Agentic intelligence and explainability | 20% |
| G3 | Data analysis and processing | 20% |
| G4 | UX/UI | 10% |
| G5 | AWS integration | 15% |
| G6 | Presentation and business value | 15% |

## 1. Pages and menu entries

Groups, labels (English / French), icons and tour names come from `NAV_GROUPS` in `web/src/lib/ui/nav.ts`; §15 describes the menu. The tab title is the page's `metadata.title`, shown as "… · Aplomb".

| Page | Route | Menu entry: group › label, icon, tour | Flag | Page spec | Tab title |
|---|---|---|---|---|---|
| Home | `/` | Overview › Home / Accueil, `LayoutDashboard`, `nav-home` | — | [home](../web/page-specs/home.md) | Aplomb · Simulation only (layout default) |
| Portfolio | `/portfolio/` | Plan › Portfolio / Portefeuille, `PieChart`, `nav-portfolio` | — | [portfolio](../web/page-specs/portfolio.md) | Portfolio |
| Decide | `/decision-desk/` | Plan › Decide / Décider, `Scale`, `nav-decide` | — | [decision-desk](../web/page-specs/decision-desk.md) | Decide |
| Strategies | `/strategies/` | Plan › Strategies / Stratégies, `Repeat`, `nav-strategies` | — | [strategies](../web/page-specs/strategies.md) | Strategies |
| Replay | `/time-machine/` | Plan › Replay / Rejouer, `History`, `nav-replay` | `time_machine` | [time-machine](../web/page-specs/time-machine.md) | Replay |
| World | `/world-explorer/` | Explore › World / Monde, the mini globe (`Earth` as fallback), `nav-world` | `world_explorer` | [world-explorer](../web/page-specs/world-explorer.md) | World |
| Evidence | `/evidence-audit/` | Trust › Evidence / Preuves, `BadgeCheck`, `nav-evidence` | — | [evidence-audit](../web/page-specs/evidence-audit.md) | Evidence |
| System | `/agents-system/` | Trust › System / Système, `Cpu`, `nav-system` | — | [agents-system](../web/page-specs/agents-system.md) | System |
| Sources | `/sources/` | Footer › Sources, `Database`, `nav-sources` | — | [sources](../web/page-specs/sources.md) | Sources |
| Labs | `/labs/` | Footer › Labs / Labos, `FlaskConical`, `nav-labs` | — | none yet | Labs |
| Profiles | `/profiles/` | No rail entry: "Manage profiles" under the investors in the investor switcher, and a link in the phone menu | `profile_creator` | [profile-creator](../web/page-specs/profile-creator.md) | Profiles |
| Not found | any unknown address (`not-found.tsx`, exported as `404.html`) | None: the page lists the rail's entries | — | [web/SPEC.md](../web/SPEC.md) §1 | Page not found (set on the client) |
| Markets (retired) | `/markets/` | None: redirects to `/decision-desk/` | — | — | Decide |
| Risk (retired) | `/risk-intelligence/` | None: redirects to `/portfolio/?tab=risk` | — | — | Portfolio |

## 2. Shell, on every page

`web/src/components/shell/AppShell.tsx` composes the top bar, the rail, the page panel, the section dock and the phone menu.

| Element | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Boot (`web/src/state/app.tsx`) | Reads versions, flags and disclaimer, then the session's profiles; a failed boot shows an error with Retry and no figures | `GET /meta` (1.2), `GET /profiles` (3.1) | A-20, WEB-03, WEB-09 | G4 |
| Investor switcher (`TopBar.tsx`, `PersonaSwitcher`) | Pick the fictional investor every page follows; "Manage profiles" opens Profiles | — (boot data) | EF-01–03, D-17 | G6, G4 |
| Ask Aplomb (`CommandBar`): microphone, send | Typed or dictated request sent to Decide as `?q=`, interpreted there and confirmed; grey completion of phrases, tickers and names | `GET /assets` (2.1), read once the field is used | D-13, *Review Robert's request* | G2, G4 |
| Simulation note (`SimPill`) | The page's disclaimer: short on the bar, full text in its popover | — (`Meta.disclaimer`) | EF-15–16, AT-10, WEB-02 | G6 |
| Help (`web/src/features/tour/HelpMenu.tsx`) | Replays the basic tour, offers the persona demo tour (§15) and one short tour per page (`tours.ts`) | — | WEB-02, AT-01–03 (demo) | G4, G6 |
| Settings (`SettingsMenu`) | Language (when bilingual), theme, animations, data date | — (`Meta`) | D-36, EXT-06, WEB-10 | G4 |
| Navigation rail and phone menu (`NavRail.tsx`, `NavLink.tsx`) | The grouped pages with visible labels (§15) | — | WEB-07 | G4 |
| Mini globe (`MiniGlobe.tsx`) | The World entry, facing the focus country | Static `/geo/countries-110m.json` | EXT-02 | G4, G1 |
| Section dock (`SectionDock.tsx`) | Jumps to the page's sections (from three); its "Test a move" button (icon and words; "Describe a move" on Decide) opens Decide or its move box | — | WEB-02 | G4 |
| Analysis period (`WindowControl`) | Full, 1Y, 3Y, 5Y or YTD in the header of Portfolio, Decide and Strategies, and in the Labs instrument tool | — (sent with each read) | D-34 | G3, G4 |
| Fact drawer (`web/src/components/common/FactDrawer.tsx`) | A dotted figure opens its fact: value, method, period, currency, sources, verification, limitations | `GET /runs/{runId}/facts/{factId}` (5.6) for run facts; local facts need no call | EF-12–14, AT-07, WEB-06, *Inspect a claim* | G2, G3 |
| Fixture banner | Says when the build reads development fixtures | — | WEB-09 | G6 |

## 3. Home `/`

`web/src/features/home/HomePage.tsx` with the widgets of the same folder. Widgets can be moved and resized; none scrolls, details open in a sheet (⤢).

| Section, component or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Header: name, blurb, objective, horizon, data date | Who the fictional investor is | — (profile, `/meta`) | EF-01–03 | G6 |
| Test a move | Opens Decide | — | *Review Robert's request* | G6, G4 |
| Inspect plan | Opens Portfolio | — | home.md (actions) | G4 |
| Reset layout | Restores the default widget layout; inactive while it is the default | — (saved in this browser) | — | G4 |
| Scope bar (`ScopeBar.tsx`) | Period or custom range (sent to the API), benchmark line, asset-class and minimum-weight filters, chart view; saved in this browser | (feeds the two reads below) | D-34, D-35 | G3, G4 |
| Key figures (`KeyFigures.tsx`) | Fictional capital (the cobalt tile, with the measured risk level), historical return, volatility, drawdown; each figure opens its fact | `GET /profiles/{id}/overview` (3.9) | EF-01–03, EF-12–14, A-13, HOME-01 | G3, G6 |
| Past performance | Constant-weight value history with the optional benchmark; series table in its sheet | `GET /profiles/{id}/performance` (3.10); `GET /assets` (2.1) for the benchmark list | A-14, D-34, HOME-05 | G3 |
| Allocation (`AllocationCard.tsx`) | Donut by asset group or listing country, within the scope | overview (3.9) | EF-01–03 | G3, G4 |
| Positions (`PositionsCard.tsx`): All holdings | The holdings that fit the widget, then "+N"; the full list opens Portfolio | overview (3.9) | EF-01–03 | G3 |
| Plan health: Open rules (opens Portfolio › Rules) | Verdict and counts, the rules nearest their limit, evidence gaps kept apart from financial checks | overview (3.9) | EF-06–09, AT-04, HOME-01 | G3, G2 |
| Longer horizons, Stress test, Diversification (`FigureCards.tsx`) | 3- and 5-year totals, the 2022 replay, effective positions | overview (3.9) | D-34, EF-04–05, EF-09 | G3 |
| Portfolio brief: Refresh brief, Read the full brief, Open investigation, Inspect evidence and audit | Cached audited brief with three focus cards; at most one automatic run per session, profile and data version; Refresh starts a real run and shows its step | `GET /profiles/{id}/brief` (3.12), `POST /runs` (5.1, `portfolio_brief`), `GET /runs/{runId}` (5.2) | D-37, D-20, EF-12–14, AT-07, HOME-02–04 | G2, G5, G6 |

## 4. Portfolio `/portfolio/`

`web/src/features/portfolio/PortfolioPage.tsx`. Four tabs (`Tabs`, kept in `?tab=`: `holdings` by default, `risk`, `rules`, `accounts`). The Holdings, Risk and Rules tabs read `GET /profiles/{id}/overview` (3.9) for the selected period. The Risk tab is the app's one risk view.

| Tab › section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Header: analysis period | The window of every figure on the page | — | D-34 | G3 |
| Tabs | One section at a time; a link or a refresh lands on the tab | — | WEB-01 | G4 |
| Holdings › Holdings table | Asset, class, sector, weight, documented quantity, modeled value, historical 1-year return, totals; the listing-country note | overview (3.9) | EF-01–03, PORT-01, PORT-04, PORT-06 | G3 |
| Holdings › By asset group, By sector (direct equities), By listing country | Allocation bars; funds are not looked through; the country is a listing proxy | overview (3.9) | PORT-03 | G3 |
| Risk › Historical risk | Volatility, drawdown, 2022 replay, lowest 12 months, effective positions (HHI), correlation heatmap up to 20 holdings | overview (3.9) | EF-04–05, EF-09, A-14, D-34, PORT-04 | G3 |
| Risk › Bad-day losses, Where the swings come from (`RiskDiagnostics.tsx`) | One-day 95% historical VaR and Expected Shortfall; signed variance share of each holding (the handoff's "Historical tail losses" and "Contributions to sample variance" cards) | `GET /profiles/{id}/risk` (3.15) | EF-04–05, A-01 | G3 |
| Risk › Deterministic focus candidates (`web/src/features/risk/FocusCandidates.tsx`, moved from Labs) | At most three findings ranked from measured rule conflicts and explicit goal scenarios, with their local calculation facts; links sent by the API pass through `currentHref` | `GET /profiles/{id}/strategic-candidates` (A1.6) | No EF/EXT row | G3, G2 |
| Rules › Plan rules: Preview, Save | Each rule with value, threshold, status, headroom and derivation; edit within its bounds, preview by code, save one rule | Preview `POST /check` (4.2, overrides, not saved); Save `PATCH /profiles/{id}/rules/{ruleId}` (3.6) | EF-03, EF-06–07, EF-11, D-18, D-19, A-02–A-12, AT-20, PORT-02 | G3, G2 |
| Rules › Restore derived rules: Keep my edits, Reset my edits too | Recompute the thresholds, keeping or resetting user edits | `POST /profiles/{id}/rules/derive` (3.7) | D-19, A-01–A-08, PORT-02 | G3 |
| Rules › Add a rule (`AddRule.tsx`): Exposure cap, Cap or floor, Conditional; Save cap, Save and check, Remove rule (`ConfirmButton`) | One card for the user's own rules, checked by code; example profiles get a pointer to duplicate them in Profiles | `POST /profiles/{id}/exposure-limits` (3.21), `POST /profiles/{id}/custom-rules` (A1.5), `POST` and `DELETE /profiles/{id}/condition-rules` (A1.17, A1.18); flag `profile_creator` | D-18, EF-03 | G3, G4 |
| Rules › Risk/return frontier (historical) | Backend points: minimum-variance curve and labelled mean-variance illustration; loaded when the fold first opens | `GET /profiles/{id}/frontier` (3.11; flag `frontier_chart`) | A-01, D-19, EXT-06, PORT-05 | G3 |
| Accounts › Accounts: Analyze account, Refresh conversion, Transfer and conserve total value, Create and select account | Choose, combine, convert and transfer fictional accounts in the reporting currency | `POST /profiles/{id}/accounts/{accountId}/select` (3.17), `…/refresh` (A1.3), `…/transfer` (A1.4), `POST /profiles/{id}/accounts` (3.16); flag `profile_creator` | D-35; no EF/EXT row | G3 |
| Accounts › Documented quantities: Save quantities, Show saved quantities | Record units with their date and source; read them back | `PUT /profiles/{id}/portfolio` (3.8), `POST /profiles/{id}/position-details` (A1.26) | No EF/EXT row | G3 |
| Accounts › Edit an account: Save account | Rename an account or replace its holdings | `PUT /profiles/{id}/accounts/{accountId}` (A1.19) | No EF/EXT row | G3 |
| Accounts › Private and illiquid assets: Save appraisal | Dated appraisals, kept out of risk, performance and limits | `GET /profiles/{id}/account-valuations` (A1.1), `POST /profiles/{id}/accounts/{accountId}/private-assets` (A1.2) | No EF/EXT row | G3 |

## 5. Decide `/decision-desk/`

`web/src/features/decision/DecisionDeskPage.tsx`. Reads `?q=` (from Ask Aplomb, used once), `?runId=`, `?ticker=` (pre-fill; Labs and the `/markets/` redirect send it) and the World context (`?eventId=`, `?profileId=`, `?sourceRunId=`).

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Header: analysis period | The window sent with checks and runs | — | D-34 | G3 |
| Investigation context: Review event and original sources, Event brief evidence, Switch to | Keeps the World event that led here; flagged when it was chosen for another investor | — | EXT-02, D-31, AT-15 | G2, G6 |
| Describe the move: Interpret, Retry, Cancel interpretation, Use in the form | Free text (1–600 characters) interpreted by the model into a move or a goal; the person confirms it in the form | `POST /requests/parse` (4.1) | D-13, DESK-02 | G2 |
| Move details (`MoveFormCard`, shared with Replay) | Ticker with suggestions, funding mode and named donors, added size slider in points of current value, supported universe | `GET /assets` (2.1, read once) | EF-04–05, D-15, AT-18, DESK-08 | G4, G3 |
| Instant rule check | Verdict, counts, largest size before the first rule conflict, funding used; by code as the move changes, latest response wins | `POST /check` (4.2) | EF-06–07, EF-10–11, D-16, A-18, AT-01, AT-03, AT-05, AT-20, DESK-03, DESK-04, *Test preferences* | G3, G2 |
| Fetch {ticker} on demand | Adds a ticker the snapshot lacks, when the API accepts it | `POST /assets/{ticker}/fetch` (2.3; flag `on_demand_tickers`) | D-24, A-21 | G3 |
| Analyze evidence | Starts the audited decision analysis, kept in `?runId=` | `POST /runs` (5.1, `decision`) | D-06, D-07, D-20, AT-09, AT-12, DESK-06 | G2, G5 |
| Instant check details | Before/after snapshot, rule checks, funding options | (from `/check`) | EF-04–05, D-15, AT-18 | G3 |
| Asset history (`AssetPanel.tsx`): Inspect source passport | Period return, volatility, maximum drawdown and worst 12 months of the asset, in the plan's currency, each a fact | `GET /assets/{ticker}/analytics` (2.5) | D-34, D-35, EF-12–14; AT-06 only in part (dates, currency and source shown, but the panel follows the selected window, not calendar 2022) | G3 |
| Compare with another investor: Compare the answers; Why the answers differ (`CompareDifferences.tsx`) | The same move, funding and window for two profiles side by side, then the rules whose answer differs | `POST /check/batch` (4.2b) | EF-10, AT-02, DESK-05, *Contrast personas* | G3, G6 |
| Target allocation (`TargetAllocation.tsx`): Check this allocation, Compare 0 to 100%, Analyze this allocation | One set of final weights, checked by code with the money added or withdrawn, and on request explained by the AI and audited | `POST /decision/target-funding` (A1.13), `POST /rebalance/check` (4.3), `POST /runs` (5.1, `rebalance`), `GET /runs/{runId}` (5.2) | D-14, EXT-01, api.md "Target allocation review" | G3, G2 |
| Evidence analysis (`DecisionRun`): See the evidence and audit, Steps, Send answer, Cancel analysis | Verdict, boundary, hypothetical scenarios, before/after, funding comparison, audited brief, limitations; marked stale when the move, window or a threshold changes | `GET /runs/{runId}` (5.2, polled), `POST /runs/{runId}/answers` (5.4), `POST /runs/{runId}/cancel` (5.5) | D-14–D-16, EF-12–14, AT-01, AT-07, AT-19, AT-20, DESK-01, DESK-06, DESK-07, *Review Robert's request*, *Explore a goal* | G2, G5, G6 |

## 6. Strategies `/strategies/`

`web/src/features/strategies/StrategiesPage.tsx`; strategies are saved in this browser (`aplomb.pref.strategies.v1.<profileId>`). Deterministic, nothing executed.

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Header: analysis period | The window of the simulation | — | D-34 | G3 |
| Empty state: Create (one card per kind) | Rebalancing, regular contributions, risk guard | — | strategies.md; no EF/EXT row | G1, G6 |
| Your strategies: New strategy | The saved strategies (up to three), active or paused | — | strategies.md | G4 |
| Strategy settings: fields, Active, Delete, Undo | Configure; each change re-simulates after a short pause; Delete is immediate with a 10 s Undo | `POST /profiles/{id}/strategies/simulate` (3.13) | EF-16 | G3, G4 |
| Results: four figures, With and without, Next simulated action, Simulated trades (sheet), Plan check, limitations | What the strategy would have done to today's holdings next to the same holdings left untouched | (from 3.13) | A-14, D-34, EF-06–07 | G3, G6 |
| Compare with a public 13F filing (`FundComparison.tsx`) | A hypothetical buy-and-hold of a filing's modeled holdings next to the strategy | `GET /research/13f`, `POST /profiles/{id}/strategies/compare-13f` (13F, through `researchFetch`) | No EF/EXT row | G3, G1 |
| Older API notice | No simulation request when `/meta` reports a contract before 1.5.0 | `GET /meta` (1.2) | strategies.md | G4 |
| Failure: Retry, copy the request ID | Wording from `web/src/lib/failure.ts`; Retry only while worth retrying | — | strategies.md | G4 |

## 7. Replay `/time-machine/`

`web/src/features/timemachine/TimeMachinePage.tsx`. With `time_machine` off, the page says the replay is turned off and shows no result.

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| What this replay can and cannot show (fold, open on the first visit) | The fixed warning: model knowledge, adjusted and revised data, universe chosen later | — | time-machine.md (before analysis), D-28 | G6, G1 |
| Pick a past date: date presets | The supported as-of dates with their reasons | `GET /replay/presets` (7.1) | D-28, A-24, TMUI-01 | G3 |
| Revised macro data note | Static text: no macro vintage is fetched, so revised macro series stay withheld in replays (`LIM_MACRO_REVISED`); it replaces the vintage status line (§19) | — | O-05, A-22 | G3, G6 |
| Move details (shared with Decide) | The move to replay | `GET /assets` (2.1) | EF-04–05 | G4 |
| Start the replay: Start replay | A `replay` run computed only from rows available at the cutoff | `POST /runs` (5.1, `replay`) | EXT-04, AT-13 | G2, G5 |
| Replay result: cutoff banner, Date gate fold, checks and before/after at the cutoff, scenarios, audited brief, Signed decision ledger, See the evidence and audit, Steps, Send answer, Cancel analysis | The date-gated decision with visible and withheld row counts | `GET /runs/{runId}` (5.2), `POST /runs/{runId}/answers` (5.4), `POST /runs/{runId}/cancel` (5.5) | EXT-04, AT-13, TMUI-02, TMUI-05, *Travel back* | G2, G3 |
| Later outcomes: Reveal later outcomes, Reveal again with this date | A separate deterministic reveal ledger; the original verdict and hash stay unchanged | `POST /runs/{runId}/reveal` (5.8), `GET /runs/{runId}` (5.2) | AT-13, TMUI-03, TMUI-04 | G3, G2 |

## 8. World `/world-explorer/`

`web/src/features/world/WorldExplorerPage.tsx`. Reads `?eventId=`, `?country=` and `?runId=`. With `world_explorer` off, the page says so. Country names follow the API, which serves Palestine (PSE) everywhere; the ISR-to-PSE mapping of `web/src/lib/geo.ts` stays as a fallback for the atlas geometry (team decision).

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Modes and geographic navigation (`WorldNavigation.tsx`): All data, News, Macro & markets, ESG & environment, Portfolio exposure; Find a country (Open), regional area, custom box | The five topics the API serves, and a place | (drive the reads below) | D-30, WUI-01 | G4, G3 |
| World stage (`WorldGlobe.tsx`, `GlobeView.tsx`): Hide globe, Rotate or Pause, Full screen, Country details, Sources and linked holdings | The WebGL globe (react-globe.gl, loaded lazily, no server render) with a side column that works without WebGL | `GET /world/layers` (6.1) plus the events and exposure below; static `/geo/countries-110m.json` | D-29, D-32, WEB-08, WUI-06 | G4, G1 |
| Filters: Apply filters, Reset to the dataset coverage, fit the range | Dates (up to 366 days), categories, origins, country, ticker or theme, portfolio relevance | `GET /world/events` (6.2, every cursor page) | D-30, WUI-01 | G3 |
| Layers: layer toggles, Fictional investors and wallets | Layers by availability and flag (events, exposure, facilities, hazards); the ESG & environment preset turns on facilities and hazards; fictional residences and custody locations | `GET /world/layers` (6.1), `GET /world/investors` (13F, through `researchFetch`) | D-32 | G3, G4 |
| Source observations (`WorldObservations.tsx`) | Provider records with their provenance and holdings assessment | `GET /world/observations` (6.8): mode `news`, `macro` or `environment`; All data sends no mode | WUI-02, WUI-03 | G3 |
| Event feed: Reload, Show more events | The keyboard path to every event, 100 at a time | `GET /world/events` (6.2) | WUI-01, WUI-06 | G4, G3 |
| Event details sheet (`WorldPanels.tsx`, `EventPanel`): Brief me, Hide, Investigate, related events | The source report, location precision, "Potential exposure identified" or "No exposure identified" with its basis, an audited event brief; Investigate opens Decide with the context | `GET /world/events/{eventId}` (6.3), `GET /datasets/{datasetId}` (8.2), `POST /runs` (5.1, `event_brief`), `GET /runs/{runId}` (5.2) | EXT-02, D-31, AT-15, WUI-03, WUI-04, *Explore an event* | G2, G3 |
| Country panel: Close country | Exposure with its basis, top events, macro facts | `GET /world/countries/{iso3}` (6.5) | EXT-02, WUI-03 | G3 |
| Portfolio weight by country | The listing-country exposure table | `GET /world/exposure` (6.4) | EXT-02, WUI-03 | G3 |
| Emissions facilities and Hazards tables, Layer details sheet | Reference layers with their source and assessment; earthquakes of magnitude 6.0 or more to 2025-11-11, 5.0 or more after | `GET /world/facilities` (6.6; flag `world_layer_facilities`), `GET /world/hazards` (6.7; flag `world_layer_hazards`) | D-32, WUI-05 | G3 |
| Fictional location sheet | One fictional residence or custody location | (from `/world/investors`) | — | G4 |

## 9. Evidence `/evidence-audit/`

`web/src/features/audit/EvidenceAuditPage.tsx`. Without `?runId=`, the list of analyses; with it, that analysis (`?factId=` opens a fact).

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Analyses started in this browser: This profile, All profiles, state chips, Open evidence, See steps | The app's one list of analyses (`web/src/components/run/RunsTable.tsx`); each row opens its evidence here or its steps in System | `GET /runs` (5.3) | AT-10, AUDUI-01 | G2, G4 |
| Analysis header: See steps, All analyses, Technical details | Kind, status, verdict; identifiers only under Technical details | `GET /runs/{runId}` (5.2) | AUDUI-07 | G2 |
| Brief with audit marks | The brief with struck and repaired sentences | (run) | D-20, AT-08, AUDUI-03 | G2 |
| Audit report (`AuditPanel.tsx`) | A01–A14 results, struck and rewritten counts, the guardrail applied or "Not applied", the ledger hash and signing time (copy, download) | (run) | D-11, D-20, AT-08 | G2 |
| Audit test (formerly "Sabotage test"): kind of lie, run button | A marked child run that tries to slip a lie past the auditor; the parent stays unchanged | `POST /runs/{runId}/sabotage` (5.7; flag `sabotage_demo`) | EXT-03, D-21, AT-14, AUDUI-04, *Challenge an explanation* | G2, G1 |
| Audit test result | Injected sentence, failed checks, result after audit; "not caught" is a valid outcome | (child run) | AT-14, AUDUI-05 | G2 |
| Rule checks | The rule table of the selected scenario | (run) | EF-06–07 | G3 |
| Fact ledger: search | Every fact of the run; each opens the fact drawer | `GET /runs/{runId}/facts/{factId}` (5.6) | EF-12–14, AT-07, AUDUI-01, AUDUI-02, AUDUI-06, *Inspect a claim* | G2, G3 |
| Evidence | Evidence items with quote, publisher and tier | (run) | A-25, D-26 | G2 |
| Sources tried | The research attempts, failures included | (run) | AT-09, D-33 | G2 |
| Data sources used | Datasets and versions read, linked to Sources | (run) | EF-15, AT-11 | G3 |
| Steps | The recorded timeline (`RunTimeline.tsx`), including the quant step's tool calls | (run) | EF-14, AT-09 | G2, G5 |

## 10. System `/agents-system/`

`web/src/features/system/AgentsSystemPage.tsx`. `?runId=` comes from "See steps".

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Choose an analysis in Evidence: Go to the analyses | No second run list: the analyses are listed once, in Evidence | — | SYS-06 | G4 |
| Selected analysis: Open evidence, All analyses, Technical details, Budget used, step details, The earlier analysis | What the analysis recorded: steps, actors, models, durations, tool calls with redacted arguments and result summaries, datasets, budgets | `GET /runs/{runId}` (5.2), `GET /runs/{runId}/trace` (5.9) | D-22, AT-09, SYS-01–03, SYS-05 | G2, G5 |
| Roles: who may do what | The six roles, model work apart from deterministic controls, allowed tools (no browser tool) | — | D-22, D-10 | G2 |
| Architecture and configuration | The service diagram with the live `/meta` state: contract, data version, model IDs, Guardrails flag, every feature flag; research reads allow-listed official pages, with no open-web line (`features.research_open_web` is always false since 8e560ef) | `GET /meta` (1.2) | D-05, D-07, D-10, D-11, SYS-04 | G5, G2 |
| Release identity | The site build and the API build | Static `/deployment.json` (written by `scripts/deploy_site.py`), `GET /health` (1.1, direct fetch, `X-Aplomb-Build`) | AT-12 in part (identity, not proof of a model call) | G5 |

## 11. Sources `/sources/`

`web/src/features/sources/SourcesPage.tsx`. Reads `?datasetId=` and `?dataVersion=`.

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Passport: Close passport, Schema and processing | One dataset: provider, retrieval, coverage, schema, processing, checks, limitations; a warning when its version differs from the fact's | `GET /datasets/{datasetId}` (8.2) | EF-15, AT-11, SRC-01, SRC-03, SRC-04 | G3 |
| Dataset passports | Every dataset with role, status (in use, planned, rejected), provider, dates, rows, version; the datasets retired in 8e560ef show as planned, "Not served: removed from the World Explorer" | `GET /datasets` (8.1) | EF-15, SRC-01, SRC-02 | G3 |
| Known data traps and how they are treated | Calendar, FX fill, adjustments, CNQ, crypto dates, revisions, survivorship, missing ESG, each handled, disclosed or open | `GET /datasets` (8.1) | AT-11, A-15, SRC-05 | G3, G6 |
| Worldwide source research directory (`SourceDirectory.tsx`) | 243 candidate sources, searchable by text, category and access; a listing is not an integration | Static `web/src/data/source-directory.json` | D-23, O-06 | G3 |

## 12. Labs `/labs/`

`web/src/features/labs/LabsPage.tsx`, `registry.ts`, `labs.css`. The tool is kept in `?tool=` (default `instruments`). Six tools in three categories, listed in §16; no tool waits on a source gate.

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Header | "Planning calculations, the list of supported instruments and a comparison of two saved profiles. Nothing here is advice." | — | EF-16 | G6 |
| Tool list: one button per tool, in three categories | Name and one-line purpose of each tool | — | — | G4 |
| Tool panel | The chosen tool, its code loaded on demand; profile tools sit behind the profile gate | per tool, §16 | — | G4, G3 |

## 13. Profiles `/profiles/`

`web/src/features/profiles/ProfilesPage.tsx`. With `profile_creator` off, the page says the creator is turned off.

| Section or button | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Profiles in this session: Edit, Edit a copy, Save an exact copy, Archive, Delete | Manage custom profiles; example profiles are read-only and copied under a new ID; Delete asks to confirm (`ConfirmButton`) | `GET /profiles/{id}` (3.2), `POST /profiles/{id}/duplicate` (3.22), `PATCH /profiles/{id}/archive` (3.19), `DELETE /profiles/{id}` (3.5) | D-17, EXT-05, CRE-04, CRE-05 | G6, G4 |
| Archived profiles: Restore | The session's archived profiles | `GET /profiles/archived` (3.18), `PATCH /profiles/{id}/archive` (3.19) | EXT-05 | G4 |
| Or describe the fictional investor in words: Draft a profile, Apply draft to the form (provisional) | A `profile_draft` run proposes fields with explanations and questions; nothing is saved until the person confirms | `POST /runs` (5.1, `profile_draft`), `GET /runs/{runId}` (5.2) | EXT-05, D-17, AT-16, CRE-02 | G2, G5 |
| Profile form: Add holding, Remove, More details, Save profile or Save changes, Clear, Reload profiles | Fictional fields only, validated; a version conflict keeps the form | `POST /profiles` (3.3), `PUT /profiles/{id}` (3.4), `GET /assets` (2.1, suggestions and support check) | EXT-05, AT-16, CRE-01, CRE-03, CRE-05, CRE-07 | G4, G3 |

## 14. Not found and the two redirects

| Route and element | Purpose | Endpoints | Requirements | G |
|---|---|---|---|---|
| Not found: Back to Home | Title and one sentence in the active language (`web/src/features/notfound/NotFoundPage.tsx`) | — | [web/SPEC.md](../web/SPEC.md) §1 | G4 |
| Not found: Main pages | The rail's own entries, same flags, Sources and Labs included | — | WEB-07 | G4 |
| `/markets/` → `/decision-desk/` | Client redirect (`web/src/components/common/Redirect.tsx`, `MOVED_ROUTES` in `web/src/lib/redirect.ts`); query and hash kept, so `?ticker=` pre-fills Decide; a "This page moved to Decide" link shows meanwhile | — | WEB-01, WEB-07 | G4 |
| `/risk-intelligence/` → `/portfolio/?tab=risk` | The same; the new address keeps its own `?tab=risk` over an old `?tab=`; the focus-candidate links of the API that still name this route land on the Risk tab | — | WEB-01 | G4 |

## 15. Navigation

The rail and the phone menu list the same groups (`NAV_GROUPS`, `web/src/lib/ui/nav.ts`; checked by `web/tests/nav-groups.test.ts`):

| Group (heading English / French) | Pages |
|---|---|
| Overview / Vue d’ensemble | Home |
| Plan / Plan | Portfolio, Decide, Strategies, Replay (`time_machine`) |
| Explore / Explorer | World (`world_explorer`), drawn as the mini globe |
| Trust / Confiance | Evidence, System |
| Footer: a divider, no heading (list name "Data and labs") | Sources, Labs |

- **Visible labels.** The compact rail (92 px) shows a caption under each icon, up to two lines, never cut; the expanded rail (216 px, the arrow at the bottom, kept in this browser) shows the group headings and the labels beside the icons. Each label is in the DOM once (`NavLink.tsx`). This replaces the ten icon-only entries (Home, Portfolio, Markets, Risk, Decide, Strategies, World, Evidence, Replay, System) with tooltips, then Sources.
- **One icon per page**, never shared; one highlight glides to the current page.
- **Flags.** Replay and World are hidden only once `/meta` reports their flag off; a group left empty disappears.
- **Mini globe as the World entry** (`MiniGlobe.tsx`, `web/src/lib/ui/orthographic.ts`, `web/src/state/useFocusCountry.ts`): it faces World's `?country=`, else the listing country of Decide's `?ticker=`, else Canada, and fills it in the accent; it turns once to a new country, never spins, and expands into the World stage when opened from the rail.
- **Phone menu** (below 768 px): the same groups with headings in a drawer, plus "Manage profiles". **Profiles** has no rail entry. **Not found** lists the same entries flat.
- **Retired:** Markets and Risk are no longer listed; their routes redirect (§14) and no page links to them.
- **Tours:** the basic tour presents the grouped menu and the mini globe. The persona demo tour walks the case end to end: Robert with TSLA +25, Amira at +10, Mateo with CNQ +5, the Evidence audit, the audit test and a replay (AT-01, AT-02, AT-03 at +5 rather than its +10, AT-07, AT-14, AT-13). Every page in the menu, plus Profiles, has its own short tour.

## 16. Moved to Labs

The overhaul moved 31 tools to Labs: Markets' connector cards and instrument search, Risk's calculators, Portfolio's planning cards and Profiles' comparison. The backend cleanup of release 8e560ef then removed the routes of 24 of them (source availability's route survives only as an empty shim), and their UI went with them (§19); Focus candidates moved on to Portfolio's Risk tab. Six tools remain, in three categories (`LAB_TOOLS`, `web/src/features/labs/registry.ts`). The origin of each tool comes from the code (the comments of `registry.ts`, `LabsPage.tsx` and `InstrumentDiscovery.tsx`, and the folder its component lives in); the pre-overhaul page files were not re-read for this inventory. "Needs" is the selected profile when the tool reads it (`needsProfile`).

| Category | `?tool=` | Tool (component) | From | Endpoints | Needs | Requirements | G |
|---|---|---|---|---|---|---|---|
| Instruments | `instruments` | Instrument discovery (`features/labs/InstrumentDiscovery.tsx`): Study in Decide, Source passport | Markets | `GET /assets` (2.1), `GET /assets/{ticker}/analytics` (2.5) | — (the default tool) | D-23, D-34, D-35, EF-12–14 | G3 |
| Planning | `target-drift` | Target drift (`features/portfolio/AllocationTargets.tsx`) | Portfolio | `GET /profiles/{id}/allocation-targets` (A1.7) | profile | No EF/EXT row | G3 |
| Planning | `joint-plan` | Goals, spending and liquidity plan (`features/planning/JointPlan.tsx`) | Portfolio | `POST /profiles/{id}/joint-plan` (A1.20) | profile | EXT-01 | G3, G6 |
| Planning | `goal-funding` | Goal funding (`features/portfolio/GoalFunding.tsx`) | Portfolio | `GET /profiles/{id}/goals` (3.20) | profile | EXT-01 | G3, G6 |
| Planning | `requirements` | Spending and liquidity scenario (`features/portfolio/RequirementsScenario.tsx`) | Portfolio | `POST /profiles/{id}/requirements-scenario` (A1.8) | profile | EXT-01 | G3 |
| Comparison | `profile-compare` | Compare profiles (`features/profiles/ProfileCompare.tsx` with `FinancialComparison.tsx`) | Profiles | `POST /portfolios/compare` (A1.21) | two saved profiles | EF-10, *Contrast personas* | G3, G6 |

## 17. Merged

- **One list of analyses, in Evidence.** `RunsTable` (`web/src/components/run/RunsTable.tsx`) lists the session's analyses once, with state chips and two actions per row: **Open evidence** (`/evidence-audit/?runId=`) and **See steps** (`/agents-system/?runId=`). System has no list of its own; without `?runId=` it points to Evidence ("Go to the analyses"). `GET /runs` (5.3).
- **One target-allocation card in Decide** (`web/src/features/decision/TargetAllocation.tsx`): the final weights are typed once, then **Check this allocation** and **Compare 0 to 100%** run the deterministic check (`RebalancePanel.tsx`: `POST /decision/target-funding`, `POST /rebalance/check`) and **Analyze this allocation** starts the reviewed AI analysis (`TargetReview.tsx`, still in `features/system/`: `POST /runs` kind `rebalance`). Both read the same text and the same ticker check.
- **One risk view, Portfolio's Risk tab.** Historical risk, the VaR/ES and variance-share cards of the former Risk page (`web/src/features/portfolio/RiskDiagnostics.tsx`, `GET /profiles/{id}/risk`) and the deterministic focus candidates (`FocusCandidates.tsx`, `GET /profiles/{id}/strategic-candidates`); `/risk-intelligence/` redirects to `/portfolio/?tab=risk`.
- **Three rule builders in one "Add a rule"** (`web/src/features/portfolio/AddRule.tsx`): Exposure cap (`ExposureLimits.tsx`), Cap or floor (`CustomPolicies.tsx`) and Conditional (`ConditionalPolicies.tsx`) behind one segmented choice; all three stay mounted so typed input survives a switch.
- **Markets' instrument analytics in Decide's asset panel.** "Asset history" (`web/src/features/decision/AssetPanel.tsx`, formerly the Markets analytics card) shows the asset named in the move form; the search of the whole universe is the Labs "Instrument discovery" tool, whose **Study in Decide** opens `/decision-desk/?ticker=`.
- **Profile comparison kept in Decide.** "Compare with another investor" (`POST /check/batch`) and "Why the answers differ" (`CompareDifferences.tsx`) stay on Decide; the comparison of two saved profiles' inputs and figures (`POST /portfolios/compare`) is the Labs "Compare profiles" tool.
- **One wording for the listing-country caveat.** `ProxyNote` (`web/src/components/common/Note.tsx`) replaces the copies several pages carried (Portfolio holdings, Exposure cap, Cap or floor on country or currency).

## 18. Removed (approved by the owner)

- **Home Automations widget.** The strategies live on the Strategies page only; a stored Home layout that still names the widget loads without it (`normalizeLayout`, `web/src/lib/ui/layout.ts`; `web/tests/dashboard-logic.test.ts`; [strategies](../web/page-specs/strategies.md), Layout).
- **Dead or never-rendering components, removed upstream before the overhaul** (wiring audit, 2026-11-15): `BitcoinNetwork.tsx`, gated on a capability (`mempool`) the backend never reported; `CompanyResearch.tsx`, `SecExplorer.tsx` and the Time Machine's `PointInTimePanel.tsx`, which could not render once the owner removed every SEC source. Their routes went with them.
- **Repeated disclaimers.** One disclaimer per page: the simulation note of the top bar (`SimPill`, `TopBar.tsx`; `AppShell.tsx` calls it "the page's disclaimer"), which keeps AT-10 on every page. Each brief keeps its own disclaimer line (`BriefView.tsx`), and a page says "not advice" once where it matters (the Labs header; the Strategies header and next action). In-card copies were dropped.

## 19. Removed with the backend cleanup (release 8e560ef)

The API of release `8e560ef` stopped serving the routes below; the owner-approved frontend handoff deleted the UI that called them. "Where" is the place the item had after the overhaul.

| Removed item (component) | Where | Former routes |
|---|---|---|
| Legal entities (`EntityResearch.tsx`) | Labs › Market research | GET `/intelligence/entities` |
| Issuer relationships (`IssuerEvidence.tsx`) | Labs › Market research | GET `/intelligence/relationships`, GET `/intelligence/relationships/captures/{sha256}` |
| Register updates (`GoldenCopy.tsx`) | Labs › Market research | GET `/intelligence/gleif-golden/metadata`, POST `/intelligence/gleif-golden/delta/{lei}` |
| Wikidata candidates (`WikidataCandidates.tsx`) | Labs › Market research | GET `/intelligence/wikidata-candidates` |
| Crypto network data (`ProviderObservations.tsx`) | Labs › Market research | GET `/intelligence/coinmetrics/{asset}` |
| On-chain markets (`DefiResearch.tsx`) | Labs › Market research | GET `/intelligence/defi/sources`, GET `/intelligence/defi/pair/{chain}/{pool}` |
| Crypto exchange history (`CryptoHistory.tsx`) | Labs › Market research | GET `/intelligence/crypto-markets/venues`, GET `/intelligence/crypto-markets/vision/{symbol}/{day}` |
| European regulatory records (`EURegulatory.tsx`) | Labs › Market research | GET `/intelligence/eu/eba-market-risk/{lei}`, GET `/intelligence/eu/esma-entity/{lei}` |
| Bitcoin sentiment (`BitcoinSentiment.tsx`) | Labs › Market research | GET `/intelligence/bitcoin-sentiment` |
| Company registries (`CompanyRegistry.tsx`) | Labs › Market research | GET `/intelligence/company-registry/{jurisdiction}/{number}` |
| Japan research and Korea filings (`RegionalResearch.tsx`) | Labs › Market research | GET `/intelligence/regional` |
| Connected market data (`KeyedMarkets.tsx`) | Labs › Market research | GET `/research/market-connections`, GET `/research/market-provider/{provider}`, GET `/research/tiingo/{symbol}` |
| Identifier crosswalk (`InstrumentMaster.tsx`) | Labs › Instruments | GET `/intelligence/master/coverage`, GET `/intelligence/master/crosswalk`, POST `/intelligence/master/adapters/coinmetrics/{asset}`, `…/gleif-pair`, `…/wikidata`, GET `/intelligence/listings` |
| OpenFIGI mappings (`OpenFigi.tsx`) | Labs › Instruments | GET `/intelligence/openfigi` |
| Source availability (`SourceAvailability.tsx`) and the Labs source gates | Labs › Market research | GET `/intelligence/source-capabilities`, now a shim that reports no research family (api.md "Markets research source capabilities (shim)") |
| Covariance (`ExpandedRisk.tsx`) | Labs › Risk lab | POST `/risk/covariance` |
| Sale timing and liquidity (`ExpandedRisk.tsx`) | Labs › Risk lab | POST `/profiles/{id}/liquidity-analysis` |
| Factor exposure (`ExpandedRisk.tsx`) | Labs › Risk lab | POST `/profiles/{id}/factor-exposure` |
| Funds inside funds (`ExpandedRisk.tsx`) | Labs › Risk lab | POST `/risk/nested-fund-look-through` |
| Factor fit and fund look-through (`ModelInputs.tsx`) | Labs › Risk lab | POST `/risk/factor-fit`, POST `/risk/fund-look-through` |
| Sensitivity scenario (`SensitivityScenario.tsx`) | Labs › Risk lab | POST `/risk/scenario` |
| Public financial feeds (`FinancialProviders.tsx`) | Labs › Risk lab | GET `/risk/providers`, POST `/risk/providers/{providerId}/capture` |
| Captured rates and positioning (`FinancialInputs.tsx`) | Labs › Risk lab | GET `/risk/source-inputs` |
| Macro vintage status line (`VintageStatus.tsx`) | Replay › Pick a past date | GET `/timemachine/vintages/status`; replaced by the static note of §7 |
| Aviation, Trade & shipping, Energy, Conflicts & geopolitics, Economic infrastructure and Hazards modes | World › modes | GET `/world/observations` with those modes (now 422); the hazards layer moved to the ESG & environment preset |
| Airports layer and Airport reference table | World | GET `/world/airports` |
| Research sources available now, with its folds | Sources | GET `/intelligence/source-capabilities` |

That is 16 research tools and 8 risk calculators out of the 31 Labs tools (§16).

## 20. Notes and uncertain mappings

- **Routes with no caller in the UI** after the handoff: `GET /assets/{ticker}` (2.2; the client method exists), `GET /assets/{ticker}/attention` (2.4), `GET /research/13f/{filing_id}` (13F), and the `GET /intelligence/source-capabilities` shim, which the backend removes once a site without its callers is deployed.
- **`researchFetch` stays.** `web/src/api/research.ts` (`researchFetch`, `researchJson`) still serves two live routes outside the generated contract: the 13F comparison of Strategies (`/research/13f`, `/profiles/{id}/strategies/compare-13f`) and the investor map of World (`/world/investors`).
- **Page specs.** [agents-system](../web/page-specs/agents-system.md) still describes a run picker on System (the picker is Evidence's list), and [world-explorer](../web/page-specs/world-explorer.md) still describes the removed modes and the airport layer. Labs has no page spec yet.
- **Requirement IDs for the Labs, accounts and strategy features** are sparse because those features came after the product table: "No EF/EXT row" is stated rather than a stretched mapping.
