# Web application contract

**Tracks:** T13 shell/Home/Portfolio/Profiles/Sources, T14 Decision/Audit, T15 World/History/System. **Stack:** Next.js + TypeScript, static export, D-03. [Design](DESIGN.md), [API](../contracts/api.md), [schemas](../contracts/schemas.md).

## 1. Routes and ownership

| Static route | Owner | Page spec |
|---|---|---|
| `/` | T13 | [Home](pages/home.md) |
| `/portfolio/` | T13 | [Portfolio](pages/portfolio.md) |
| `/decision-desk/` | T14 | [Decision Desk](pages/decision-desk.md) |
| `/world-explorer/` | T15 | [World Explorer](pages/world-explorer.md) |
| `/evidence-audit/` | T14 | [Evidence & Audit](pages/evidence-audit.md) |
| `/time-machine/` | T15 | [Time Machine](pages/time-machine.md) |
| `/agents-system/` | T15 | [Agents & System](pages/agents-system.md) |
| `/profiles/` | T13 | [Profile creator](pages/profile-creator.md) |
| `/sources/` | T13 | [Sources](pages/sources.md) |

Seven primary sidebar pages; profiles via persona menu and Sources via evidence/footer link. Run IDs/profile IDs/fact IDs use query parameters on fixed routes; static export must not require unknown runtime dynamic routes.

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
