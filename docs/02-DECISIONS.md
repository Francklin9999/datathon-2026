# 02 — Decision log, assumptions and open items

This file records **what was decided, by whom, and what is still a guess**. Every other spec refers to the IDs here (`D-xx`, `A-xx`, `O-xx`). If you disagree with a decision, change it here first, then update the specs that cite it.

## How to read the markers used in all specs

| Marker | Meaning |
|---|---|
| `[D-xx]` | A decision recorded in this file. |
| `[A-xx]` | A team assumption. It must be shown to the user as an assumption wherever it affects a result. |
| `[O-xx]` | An open item. Somebody must close it; the owner is named below. |
| `[CONTROL]` | A number computed from the starter CSVs on 2026-11-14 (see `contracts/controls.md`). Tests must reproduce it. |
| `[VERIFY]` | A statement about an external service, library or API that **nobody verified in the session that wrote this spec**. The track owner must check it against the official documentation before relying on it, then replace the marker with a link. |
| `[BRIEF p.X]` / `[DECK s.X]` | Requirement traced to the official brief (English PDF, 19 pages) or the participant deck (12 slides). |

## 1. Deadlines

Source: the team's SRS v0.1 and initial plan. These dates are **not in any file in the repository**; the brief says logistics are communicated separately (brief p.16).

| When (EST) | What |
|---|---|
| Sun 2026-11-15 16:00 | On-site period ends |
| Sun 2026-11-15 23:59 | Application and repository submission |
| Mon 2026-11-16 13:59 | Organizer AWS accounts close |
| Mon 2026-11-16 14:00 | Video, technical documentation, one-pager |
| Fri 2026-11-20 | Finalist presentations |

## 2. Decisions made by the product owner (Q&A of 2026-11-14)

| ID | Topic | Decision |
|---|---|---|
| D-01 | Scope | Full plan P0 + P1: Decision Desk, Evidence & Audit, World Explorer globe, Time Machine, sabotage demo, profile creator. All tracks start in parallel. |
| D-02 | Cut order | If behind on Sunday 18:00, cut in this order: (1) bilingual toggle, (2) extra globe layers (emissions, natural disasters), (3) Time Machine, (4) profile creator and free-text goals. Nothing else is cut before these. |
| D-03 | Frontend | New Next.js app (TypeScript). Static export hosted on S3 + CloudFront. |
| D-04 | Design | Page layout and navigation from the plan (sidebar, seven pages); colour palette and typography from the existing HTML prototype (navy, teal, gold; Fraunces + IBM Plex). |
| D-05 | Backend packaging | One FastAPI application deployed on AWS Lambda behind API Gateway. |
| D-06 | Run execution | Asynchronous: `POST /runs` returns a `runId`; a worker executes the run and persists each step; the frontend polls `GET /runs/{id}`. |
| D-07 | Agent runtime | Agents written with the Strands Agents SDK calling Amazon Bedrock, executed inside Lambda. Move to Bedrock AgentCore Runtime only after the flow works end to end. |
| D-08 | Deployment | AWS CDK. One stack creates all resources. |
| D-09 | AWS operator | A teammate handles the AWS account and deployments. Specs must not assume AWS access from any other machine. |
| D-10 | Models | Strong Claude model for reasoning roles (Planner, Researcher, LLM auditor); fast Claude model for parsing and writing. Exact model IDs depend on what the account has enabled `[O-01]`. |
| D-11 | Guardrails | Use Amazon Bedrock Guardrails on model outputs for advice-like wording and off-topic content, in addition to our own auditor. |
| D-12 | Storage | Amazon DynamoDB for profiles, runs and caches. No login was requested; see `[A-20]`. |
| D-13 | Request types | The Decision Desk accepts **both** an exposure goal ("more AI exposure, lose at most 15% in a bad year") and a specific move ("25% into Tesla"). One free-text box; the system works out which it is and the user confirms the structured interpretation. |
| D-14 | Goal output | For a goal: the best-fit scenario plus 2–3 candidate scenarios, each explained; a rebalance scenario when the situation calls for it. |
| D-15 | Funding a move | All funding options are available (sell others pro-rata, from cash, from named holdings, new money). The agent evaluates them and recommends the one that keeps the plan most intact. |
| D-16 | On conflict | The system (a) computes the largest compatible size, (b) recommends the funding source, (c) explores hypothetical alternatives, (d) asks the user for missing information. |
| D-17 | Profiles | Three default personas from the brief (Amira, Mateo, Robert) plus a profile creator: core fields and a free-text description that an agent turns into a draft profile. |
| D-18 | Rule types | Concentration caps, stress-loss limit, volatility and drawdown budget, allocation floors and exclusions. |
| D-19 | Thresholds | Thresholds are derived with portfolio maths rather than hand-picked. The owner answered "all" to the three approaches offered; see `[A-01]` for how they are combined. |
| D-20 | Number safety | Deterministic code check on every number **plus** an LLM auditor that reviews wording. |
| D-21 | Sabotage demo | A visible "make the writer lie" toggle on the Evidence & Audit page. |
| D-22 | Agent roster | The plan's six roles: Planner, Researcher, Quant Engine, Risk Officer, Writer, Auditor. |
| D-23 | Universe | As many tickers as online public sources allow, beyond the 31 starter assets. |
| D-24 | Ingestion | Versioned snapshot in S3 plus on-demand fetch of tickers that are not in the snapshot. |
| D-25 | Exposure mapping | "All of them": documented theme tags, ETF look-through where holdings files are available, and agent research with citations. |
| D-26 | ESG evidence | Sector/asset exclusions, government emissions registries, filings and reports read by an agent, and a news controversy search. |
| D-27 | Macro data | Used as context in explanations **and** as a rate-cycle scenario. |
| D-28 | Time Machine history | "Backfill to 2021 for now with option to extend later": use the starter window (from 2021-11-12); the design must allow a longer history later. |
| D-29 | Globe engine | `react-globe.gl`. |
| D-30 | Globe events | All sources: cached GDELT batch, official releases, a curated set and live lookups. "All the events, not just 20–30." |
| D-31 | Event → holding link | The research agent looks for documented mechanisms and cites them. Financial impact is never invented. |
| D-32 | Globe layers | News/event pins, portfolio exposure by country, emissions facilities, natural disasters. |
| D-33 | Research tools | SEC EDGAR, GDELT, fetch from known public sites, Wikipedia pageviews ("hype meter"), and open-web browsing through the AgentCore Browser tool `[O-02]`. |
| D-34 | Risk window | Full available history by default, printed next to every number, with a 1Y / 3Y / 5Y selector. 2022 remains a separately named stress test. |
| D-35 | Currency | CAD by default; each profile has a reporting currency (CAD or USD). Every fact states its currency. |
| D-36 | Languages | Bilingual UI and explanations (English and French) with a toggle. First item on the cut list (D-02). |
| D-37 | Home brief | The AI "Portfolio Analyst Brief" is generated once per profile and data version, cached, and refreshed on demand. |
| D-38 | After Monday | No offline replay mode: "we won't use it after". |
| D-39 | Repository | Monorepo; everyone commits to `main`. |
| D-40 | Specs | Detailed markdown specs with API contracts in every area of the repo, in English. |

## 3. Assumptions and defaults chosen by the spec author

These were **not** confirmed by the product owner. Each is a default so that work can start. Change them here if you disagree.

| ID | Topic | Default | Why |
|---|---|---|---|
| A-01 | Meaning of "all" for D-19 | (a) **Risk-only maths sets the rule thresholds** (volatility budget, correlations; no return forecast). (b) The **historical frontier** is drawn as a description of the sample on the Portfolio page. (c) **Classic mean-variance** points appear only on that same chart, labelled "illustration from past returns, not a forecast". Neither (b) nor (c) ever sets a threshold or a verdict. | Brief p.18: teams are not asked to predict future returns from past performance. |
| A-02 | Volatility budget per risk level | low 6%, low-to-moderate 9%, moderate 12%, moderate-to-high 16%, high 22% (annualized). | A budget is needed to derive anything. Values are editable per profile and shown as assumptions. They were chosen so that broad reference mixes in the sample span them (see `contracts/controls.md` §6). |
| A-03 | Single-position cap | `clamp(round5(0.4 × σ_budget ÷ σ_ref), 5%, 25%)` where `σ_ref` is the upper-quartile volatility of single stocks in the universe. Gives 10% / 15% / 25% for Robert / Mateo / Amira on the starter data `[CONTROL]`. | Ties the cap to the risk budget instead of a hand-picked number; the 25% ceiling expresses "high risk is not anything goes" (brief p.5). |
| A-04 | Sector cap | `min(40%, 2 × position cap)`. | At least two names per sector at the cap. |
| A-05 | Crypto cap | `clamp(round5(0.4 × σ_budget ÷ σ_crypto), 0%, 25%)`, halved (rounded down to 5%) when the profile avoids speculative assets; replaced by an exclusion when the profile has no interest in crypto. | Same logic as A-03 with crypto volatility. |
| A-06 | Growth-assets cap and fixed-income floor | Growth cap = largest multiple of 5% of an equity reference mix (50% XIU.TO + 50% SPY, rest XBB.TO) whose volatility stays within the budget. Fixed-income floor = `max(0, 100 − growth cap − 10)`. | Risk-only answer to "how much in stocks and bonds". Sensitive to the 2021–2026 sample, in which bonds were unusually volatile; this limitation is displayed. |
| A-07 | Stress-loss limit | `m × σ_budget`, with `m` = 1.0 for a horizon midpoint ≤ 5 years, 1.25 for ≤ 10 years, 1.5 beyond. | Shorter horizon means less time to recover (brief p.18 names horizon as a factor). |
| A-08 | Drawdown ceiling | `2.0 × σ_budget`. | Simple, documented multiple. |
| A-09 | Tension band | A rule is in "tension" when the value is within the last 10% of its limit (above 90% of a cap, below 110% of a floor). | The prototype used 20%; with whole-portfolio rules that put healthy default portfolios in tension. |
| A-10 | Amira's diversification rule | At least 8% in diversifying assets (bonds, cash, gold). | Her profile says she "still wants some diversification" (brief p.5); the number is ours. |
| A-11 | Mateo's ESG rules | (a) No direct holdings in the Energy sector (editable exclusion). (b) A controversy rule that stays "insufficient data" until research evidence with verified citations is attached. | His profile says he avoids companies with significant controversies (brief p.6); the starter data contains no controversy evidence (starter README). The sector exclusion is our reading, labelled as such. |
| A-12 | Robert's crypto rule | Crypto assets are excluded (editable). | His profile says he "has little interest in crypto assets" (brief p.7). |
| A-13 | Default portfolios | Three fictional portfolios built from the 31 starter assets (see `backend/aplomb/profiles/SPEC.md`). Fictional capital: Robert 600,000 CAD, Mateo 250,000 CAD, Amira 60,000 CAD. | The SRS requires starting portfolios; none existed. Each passes its financial rules at baseline `[CONTROL]`; Mateo still has insufficient controversy evidence. |
| A-14 | Portfolio history convention | Historical risk of a portfolio = today's weights applied to historical returns, rebalanced daily (constant weights). | Standard for describing the risk of the current mix; not a track record. |
| A-15 | Master calendar | Days on which **both** the TSX and the US market have a price (1,228 days in the starter window `[CONTROL]`). Crypto is sampled on those days. USD/CAD is carried forward from the last published rate. | Avoids stale prices; documented in the starter README as something teams must decide. |
| A-16 | Annualization | 252 periods per year on the master calendar. | Convention; the actual count is 245–247 per full year in the sample `[CONTROL]`. |
| A-17 | Meaning of a move | `sizePct` = percentage points of the **current** portfolio value added to the asset. With `new_money`, cash equal to `sizePct` of current value is deposited first. | The SRS left this undefined. |
| A-18 | Largest compatible size | Largest size on a 0.5-point grid, scanning upward from zero, before the first size that produces a conflict. | Simple, monotone by construction, cheap to compute. |
| A-19 | Hype meter | Displayed as evidence and as an informational flag; it never changes a verdict on its own. | Attention is context, not a rule. |
| A-20 | Sessions | No login. The browser generates a session ID sent in `X-Aplomb-Session`; custom profiles and runs are stored under it. | D-12 did not request sign-in; Cognito was outside the SRS minimum. |
| A-21 | On-demand tickers | A ticker fetched on demand needs at least 252 master-calendar observations for risk rules; otherwise the affected rules return "insufficient data". Only CAD- or USD-listed assets are accepted. | Avoids risk numbers from a few weeks of data. |
| A-22 | Macro publication lag | Until real release dates are ingested, a monthly value becomes usable 45 days after the end of its reference month; daily series the next business day. | Conservative stand-in for the brief's time-consistency rule (p.14). Must be replaced by real release dates for the Time Machine. |
| A-23 | Rate scenario | The Bank of Canada hiking cycle found in the data (2022-03-02 to 2023-07-13, policy rate 0.25% → 5.00% `[CONTROL]`) is replayed as an **informational** scenario. It does not enter the verdict. | In the sample it is not a loss scenario for the default portfolios `[CONTROL]`, so using it as a limit would be misleading. |
| A-24 | Time Machine dates | With history starting 2021-11-12 (D-28), the earliest as-of date offered is the first date with 252 master-calendar observations behind it. | Same reason as A-21. |
| A-25 | Open-web evidence tiers | Tier 1: regulators, central banks, statistical agencies, company and fund issuers. Tier 2: established news publishers. Tier 3: everything else. Tier 3 evidence alone can never move a rule out of "insufficient data". | D-33 allows the whole internet; the brief still demands verifiable, faithful explanations (p.17). |
| A-26 | Deliverables | Video, technical documentation and one-pager are owned by track T16 and written in English. | Not decided in the Q&A. |
| A-27 | Language of specs and code | English identifiers, English specs (D-40). | — |
| A-28 | Wording | The product never calls itself an "advisor" and never issues buy/sell instructions. The plan's "Agentic Investment Advisor" is renamed "Portfolio Analyst". | Brief p.17; SRS EF-16. |

## 4. Open items

| ID | Item | Owner | Blocks |
|---|---|---|---|
| O-01 | Which Claude models are enabled in Bedrock on the organizer account, in which region, with which quotas. | T02 (AWS operator) | Agents, model configuration |
| O-02 | Whether AgentCore Runtime and the AgentCore Browser tool are available on the account. Until confirmed, open-web research is behind a feature flag and the fallback is direct fetch from known sites. | T02 | Research tool `web.browse` |
| O-03 | Whether Bedrock Guardrails can be created on the account. | T02 | Guardrail step in the auditor |
| O-04 | Product-owner approval of the default portfolios (A-13) and of the threshold formulas (A-02 to A-10). | Product owner | Nothing; defaults are usable |
| O-05 | Real publication dates for monthly macro series (to replace A-22). | T04 | Time Machine credibility |
| O-06 | Sources and licences for the extended universe (constituent lists, sector labels, theme tags). | T04 | D-23 |
| O-07 | GDELT batch feasibility: the prototype's data room recorded ~17 s per call and an HTTP 429 on a second call. Not re-verified. | T11 | D-30 |
| O-08 | Whether the finals on Nov 20 allow a live system. With D-38 the pitch relies on the recorded video. | Product owner | Pitch plan |
| O-09 | The originals of the SRS v0.1 and the initial plan are not in the repository. Add them under `docs/reference/` if they should be kept. | Product owner | — |

## 5. Known tensions the team accepted

- **Scope versus time.** D-01 is several times larger than the SRS minimum, with everyone on `main` (D-39). The specs mark every feature with a tier (P0, P1, P2) so that D-02 can be applied mechanically.
- **Frontier versus the "no prediction" rule.** See A-01. Any screen showing mean-variance output carries the limitation text `LIM_PAST_NOT_FUTURE`.
- **"All the events" versus rate limits.** See O-07. The world pipeline is batch-first; the globe never calls a third-party API directly.
- **Open web versus verifiable sources.** See A-25.


## 6. Specification completion clarifications (2026-11-14)

These resolve internal contradictions in the interrupted draft; they do not replace the owner's scope decisions. Unconfirmed engineering defaults remain defaults.

- A-03/A-05 formulas produce fractions before conversion to percent. When budgets and reference volatilities are both expressed in percent, multiply their ratio by 100 before rounding to 5-point steps. See optimizer §3 and the numeric scripts.
- Baseline portfolios pass financial checks; Mateo still has controversy `nee`, so his overall baseline is insufficient. No ESG cleanliness is asserted.
- The v1 `maxCompatibleSizePct` field means the largest 0.5-point size in the prefix before the first conflict. Tension and missing evidence can remain. UI wording makes this explicit.
- Named-holding donors are depleted in caller-specified order, with no unlisted spill. This preserves Claude's published control examples. Auto funding discloses its deterministic donor set.
- Poll deltas use a completed-step watermark, with final full fetch; otherwise updates to a previously running step could disappear. Run indexes/caches include session and profile version to isolate default overlays.
- Historical monthly macro requires real release/vintage evidence; A-22's fixed lag is context only and cannot establish point-in-time consistency. Price adjustments, later-selected universe and model knowledge remain disclosed limits.
- Profile drafts contain partial supported fields until user confirmation; a complete saved Profile is required only at persistence.
- For v1 derivation, reference-universe statistics use the starter universe, pinned version and eligible as-of history. Newly fetched names do not silently change every plan's thresholds.
