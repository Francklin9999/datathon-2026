# T13/T14 web handoff — 2026-11-14

T13 (shell, Home, Portfolio, Profiles, Sources, shared components, API client) and T14 (Decision Desk, Evidence & Audit, run/brief/rule/audit components) are implemented in `web/` against `contracts/api.md` v1 and `contracts/schemas.md`. No backend file was changed.

## Run it

| Command (from `web/`) | Purpose |
|---|---|
| `npm run dev` | Live mode against `NEXT_PUBLIC_APLOMB_API_BASE` (default `http://localhost:8000/v1`) |
| `npm run dev:fixtures` | `NEXT_PUBLIC_APLOMB_FIXTURES=true`: serves only `contracts/fixtures` (profiles + the Robert run); every other endpoint answers a typed `503 upstream_unavailable` under a banner. No invented data and no fallback from a failed live call. |
| `npm run build` | Static export to `web/out/` (10 routes, `trailingSlash: true`) |
| `npm run typecheck`, `npm run test:contracts` | Strict TypeScript; node tests including `tests/web-logic.test.ts` and `tests/web-api.test.ts` |

When the backend providers exist, nothing in the web app should need to change: start the API on `:8000` (its CORS already allows `http://localhost:3000`) and run `npm run dev`, or set `NEXT_PUBLIC_APLOMB_API_BASE` to the API Gateway URL at build time.

## Where things are

| Path | Contents |
|---|---|
| `src/api/client.ts` | Every endpoint in api.md; validates each 2xx body with `validateContract`; non-2xx → `ApiRequestError` (code, status, requestId, Retry-After); session header on protected calls, `Content-Type` only with a body, `Idempotency-Key` on run creation |
| `src/api/fixtures.ts` | Development fixture adapter (above) |
| `src/state/app.tsx` | Bootstrap: `/meta` → session (`s_` + UUIDv4 in localStorage) → `/profiles`; persona, window, language, feature flags |
| `src/state/useQuery.ts` | Keyed cache; keys include session, profile ID + version, data version, window, language |
| `src/state/useRun.ts` | Polling per run-events.md §3: 1 s / 5 s, `since` = contiguous completed seq, one full fetch at terminal, pause while hidden, backoff + Retry-After |
| `src/lib/*` | Pure logic: check-request building, latest-response gate, brief helpers, EN/FR labels for every displayed catalog code, holdings and profile-form validation |
| `src/components/run/*` | T14 shared components: `BriefView`, `RuleTable`, `RunTimeline`, `Results` (verdict, boundary, scenarios, funding, before/after), `AuditPanel`. T15 should reuse these. |
| `src/features/*` | Page bodies; `src/app/*` are thin static routes. World Explorer, Time Machine and Agents & System are route skeletons for T15. |
| `web/page-specs/` | The page specs, moved from `web/pages/`: Next.js treats a `pages/` folder as the Pages Router and refuses to build next to `src/app`. `web/SPEC.md` links were updated. |

## Verification performed

- `npm run typecheck`; `npm run test:contracts` (96 passing, including the existing FastAPI composition test); `npm run check:generated`; `python3 scripts/check_specs.py` (54 documents linked); `next build`.
- Browser check with Playwright at 1440 px and 375 px, in EN and FR, against a **temporary** contract-shaped mock API that validated its own responses with the shared schema. The mock was deleted afterwards. Exercised: Home auto-brief (exactly one `POST /runs`); fact drawer (run scope, Escape, focus return); Decision Desk rapid size changes (latest response shown); parse refusal and interpretation → form; decision run (delta polling `since=1..5`, then a full fetch); stale-brief note after changing size; waiting_input → answer → same run completes; failed run keeps its steps and error; compare with a per-item batch error; Evidence & Audit `?factId=` deep link and URL sync; struck sentence shown only in the audit view; sabotage child run; Portfolio rule PATCH → version bump and refetch; Sources passport drift warning, `javascript:` URL not linked, markup shown as text; Profiles validation (actual weight sum shown) and save.
- Real API (after commit `7cd493b`, default composition, starter snapshot ingested into a temporary directory): every response from `/meta`, `/profiles`, `/profiles/{id}/overview|performance`, `/check`, `/check/batch`, `/assets`, `/datasets`, `/datasets/{id}`, rule PATCH and derive passed the web client's contract validation. `/check` in the UI reproduced AT-01 (Robert +25 TSLA pro-rata: conflict, 6 conflict / 1 tension / 1 fit + 3 info, vol 16.96 %, drawdown 25.31 %, stress −21.88 %, boundary 6.0 pts) and AT-02 (25 pts: both conflict, boundaries 6 and 11; 10 pts: Robert conflict, Amira tension). Endpoints not wired yet (`/profiles/{id}/brief`, `/requests/parse`, `/runs*`) answered typed `503` and the UI showed honest unavailable states with the deterministic cards intact.
- Not verified: runs/parse/world/replay against the real backend (T08 worker and parser not wired), deployed CloudFront/API Gateway, screen-reader behaviour, hidden-tab pause in a real browser, measured contrast/Lighthouse.

## Not implemented (P1)

- Holdings editor (`PUT /profiles/{id}/portfolio`): the client method exists; there is no UI.
- Dedicated goal editor form: goals parsed from free text can be confirmed and analyzed as runs; there is no structured goal form.
- The frontier panel is basic (SVG plus a point list, inspect-only).

## Contract notes for the backend (frontend assumptions to confirm or fix)

1. **Rule label placeholder unit.** `contracts/fixtures/profiles.json` labels put the unit after the placeholder (`"above {threshold}% of the portfolio"`), while `backend/aplomb/rules/SPEC.md` detail templates expect a formatted value (`"the {threshold} cap"`). The UI inserts a bare number when `%`/`pts` follows the placeholder and the value with its unit otherwise (`lib/format.ts::fillThreshold`). Proposal: state in schemas.md §4.1 that `label` receives a bare number and carries its own unit.
2. **Inconsistent `factIds` keys (observed).** `factIds` maps are `Record<string, FactId>` with undocumented keys. The run fixture's snapshot uses field names (`volatilityPct`, `maxDrawdownPct`, `stress2022Pct`); the live API uses stems for `risk.factIds` and snapshot `metrics.factIds` (`volatility`, `maxDrawdown`, `stress2022`, `worst12m`) but field names for `returns.factIds` (`ytdPct`, `y1Pct`, `y3Pct`, `y5Pct`). The UI accepts both forms (`lib/format.ts::factIdFor`). Proposal: pick one convention, document it in schemas.md and align the fixture.
3. **Per-holding trailing return.** Only `concentration.topPositions[].return1yPct` exists, so the holdings table shows "—" for holdings outside the top list. Proposal: add `return1yPct` to `PortfolioSnapshot.positions`, or return every position in `topPositions`.
4. **Cached brief window.** `GET /profiles/{id}/brief` takes only `lang`, but the brief cache is keyed on window and `POST /runs` (portfolio_brief) accepts `window`. The UI keys its cache on window and sends it at creation. Proposal: add `window` to endpoint 3.12.
5. **Pinned passports.** sources.md asks to "retrieve pinned passport if supported", but `/datasets/{id}` has no version parameter. The UI warns when the passport `dataVersion` differs from the fact's. Optional proposal: `?dataVersion=`.
6. **Quote verification signal.** The evidence drawer calls a quote verified only when `verification.checks` contains `{ code: "A08", ok: true }`. Proposal: document that A08 is recorded per evidence item.
7. **Sabotage "caught".** Shown only when `caught` is true **and** at least one `failedChecks[].ok` is false.
8. **Runs list titles.** `/runs` items need a meaningful bilingual `title`; the UI uses it as the link text.
9. **Feature flags drive navigation.** `world_explorer`/`time_machine` off hides those nav entries, and bookmarked routes show an unavailable state. `profile_creator`, `sabotage_demo`, `frontier_chart`, `on_demand_tickers` and `goal_requests` gate their entry points. The fixture adapter reports every P1 flag off except `bilingual`.
10. **Shared manifests.** `web/package.json` now depends on `next@16.4.6`, `react@19.3.1`, `react-dom@19.3.1` and `@types/react*@19.3.0`; the root lockfile changed accordingly. Root `package.json` scripts (T01) were not changed; `npm run build --workspace web` builds the site. The README line "T13 will add the Next.js shell" can be updated by its owner.
