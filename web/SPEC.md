# Web application contract

**Tracks:** T13 shell/Home/Portfolio/Profiles/Sources, T14 Decision/Audit, T15 World/History/System. **Stack:** Next.js + TypeScript, static export, D-03. [Design](DESIGN.md), [API](../contracts/api.md), [schemas](../contracts/schemas.md).

## 1. Routes and ownership

| Static route | Menu entry (group › label) | Owner | Page spec |
|---|---|---|---|
| `/` | Overview › Home | T13 | [Home](page-specs/home.md) |
| `/portfolio/` (`?tab=` holdings, risk, rules or accounts) | Plan › Portfolio | T13 | [Portfolio](page-specs/portfolio.md) |
| `/decision-desk/` | Plan › Decide | T14 | [Decision Desk](page-specs/decision-desk.md) |
| `/strategies/` | Plan › Strategies | T13 | [Strategies](page-specs/strategies.md) |
| `/time-machine/` | Plan › Replay (flag `time_machine`) | T15 | [Time Machine](page-specs/time-machine.md) |
| `/world-explorer/` | Explore › World (flag `world_explorer`) | T15 | [World Explorer](page-specs/world-explorer.md) |
| `/evidence-audit/` | Trust › Evidence | T14 | [Evidence & Audit](page-specs/evidence-audit.md) |
| `/agents-system/` | Trust › System | T15 | [Agents & System](page-specs/agents-system.md) |
| `/sources/` | Footer › Sources | T13 | [Sources](page-specs/sources.md) |
| `/labs/` (`?tool=`) | Footer › Labs | unassigned | none yet (Labs, `src/features/labs/LabsPage.tsx`; the tools in `registry.ts`) |
| `/profiles/` | none: "Manage profiles" in the investor switcher (flag `profile_creator`) | T13 | [Profile creator](page-specs/profile-creator.md) |
| `/investor-lab/` (`?mode=` quick, full or new; `?profileId=`) | none: "Test my profile" in the investor switcher and on Decide, "Create with Investor Lab" on Profiles | T13 | [Investor Lab](page-specs/investor-lab.md) |
| `/markets/` | none (retired) | — | redirect to `/decision-desk/` |
| `/risk-intelligence/` | none (retired) | — | redirect to `/portfolio/?tab=risk` |

**Navigation.** The pages are grouped (`NAV_GROUPS` in `src/lib/ui/nav.ts`, icons in `src/components/shell/NavRail.tsx`, tested in `tests/nav-groups.test.ts`), in this order: Overview (Home); Plan (Portfolio, Decide, Strategies, Replay); Explore (World, drawn as the mini globe); Trust (Evidence, System); then a footer without heading, Sources and Labs. Every entry shows its label: a caption under the icon in the compact rail, beside it with the group headings in the expanded rail ([Design](DESIGN.md), Layout). Replay and World are hidden when their `time_machine` / `world_explorer` feature flag is off, once `/meta` has loaded; a group left empty is dropped. The phone menu drawer lists the same groups. Profiles open from the investor switcher ("Manage profiles", shown when `profile_creator` is on) and from the phone menu, not from the rail. Labs has no owner or page spec yet; until one is written it is still held to the §6 page states. Page by page, the kept sections, their API calls, requirements and grading criteria: [UI inventory](../docs/UI-INVENTORY.md).

**Retired routes.** Markets and Risk Intelligence left the menu in the navigation overhaul (2026-11-15): instrument analytics moved to Decide's asset panel and Labs' instrument search, the risk diagnostics and the focus candidates to Portfolio's Risk tab, and the planning and comparison tools to Labs; the research connectors and risk calculators were removed with their API routes in release `8e560ef` ([UI inventory](../docs/UI-INVENTORY.md) §19). Their routes stay for old bookmarks. The static export has no server redirects, so each renders `Redirect` (`src/components/common/Redirect.tsx`), which replaces the address on the client with its `MOVED_ROUTES` target (`src/lib/redirect.ts`), merging the old query and hash into the target's own query (a parameter the target sets, such as `tab=risk`, wins), and shows a plain "This page moved to …" link meanwhile. Links that arrive as data (an API navigation target, such as the `/risk-intelligence/` that `backend/aplomb/quant/candidates.py` still returns) are rewritten with `currentHref` before they are shown. No page links to a retired route (`tests/nav-groups.test.ts`).

Run IDs, profile IDs, fact IDs and page state use query parameters on fixed routes: Portfolio's `?tab=` and Labs' `?tool=` are kept with `history.replaceState` (`useTabParam`, `src/components/ui/Tabs.tsx`), so a link or a refresh lands on them; static export must not require unknown runtime dynamic routes. An unknown address gets the 404 page (`src/app/not-found.tsx`, exported as `404.html`): a page in the app shell with a title, one sentence and the same page list as the rail, Sources and Labs included, in the active language.

## 2. Shared shell and files

T13 owns AppShell, sidebar, persona/currency context, language/window selector, disclaimer, metadata banners, FactDrawer and loading/error boundaries. T14 supplies BriefView, RuleTable, ScenarioCards, RunTimeline and compare components; T15 reuses these rather than defining alternate statuses. Shared files are owned, not concurrently rewritten. T01 owns `src/contracts/*`, T13 API client `src/api/client.ts` subject to frozen contract.

Bootstrap: fetch meta, restore/generate session capability with crypto.randomUUID, then profiles and selected profile. Store only session ID, UI preferences and selected IDs locally; server remains authority for profile edits/runs. A lost capability loses access to private demo state; never imply authenticated account recovery. Query caches include session/profile version/data version/asOf/window/language.

## 3. API and polling

Typed client methods return validated models or ApiError. Add session header to all protected calls; Content-Type only for bodies. Use AbortController/request sequence IDs to ignore stale selection/slider responses. Poll active runs at 1 s, waiting at 5 s, pause/backoff on hidden tab/rate-limit/network failure and resume full fetch when foregrounded. Follow completed-step watermark rules in API/lifecycle; merge maps by ID and steps by seq, terminal full fetch before showing signed result.

Run ID is preserved in URL to restore after refresh. Current deterministic preview and signed brief are separate state: after changing move/rule/window, mark old prose stale with original analyzed size/time. Do not rewrite old fact values into old sentences. Batch compare sends same explicit funding and move to both profiles.

## 4. Static export constraints

Set output export; use only known static routes. Fetch account/session data in client components; no Server Actions, runtime route handlers or server-only secrets. Browser-only globe dynamically imports with SSR disabled inside client boundary. Use local font files when licensed or documented fallbacks; no build-time account/API calls. Images require static-compatible handling. Verify against [Next.js static-export docs](https://nextjs.org/docs/app/guides/static-exports) with the pinned version.

## 5. Fixture development

`NEXT_PUBLIC_APLOMB_FIXTURES=true` selects a local typed adapter loading contract fixture JSON; banner “Development fixtures — no agents executed.” Never auto-switch from failed live API to successful fixture data. Keep fixture run flags true and artificial model IDs clearly labelled. This development aid is not the rejected offline replay product feature. Live build requires flag false.

## 6. Acceptance and done

WEB-01 all deep links build/export/refresh. WEB-02 keyboard paths/disclaimer/mobile layout. WEB-03 session/data/profile cache isolation. WEB-04 race-safe slider and persona switches. WEB-05 full/delta polling with failed/waiting/terminal states. WEB-06 fact references always open correct scope (preview/run/reveal). WEB-07 disabled flags remove entry points but tolerate bookmarked routes with unavailable state. WEB-08 no model text injected as HTML. WEB-09 no fixture fallback in live build. WEB-10 both language keys work or English repeats if cut.

T01 has initialized the npm workspace, `web/package.json`, root lockfile, strict TypeScript, generated contracts and runtime validation. `npm ci` from root installs it; `npm run typecheck` and `npm run test:contracts` verify the foundation. T13 adds the Next.js dependencies and actual dev/build commands through the shared-manifest owner when the shell is implemented. A page is complete only with loading, empty, insufficient-data, unavailable and failure states plus genuine API integration; a screenshot alone is not completion.
