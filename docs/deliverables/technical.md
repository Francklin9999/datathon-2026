# Aplomb — technical documentation

AlphaForge AI, Datathon 2026 · release `8e560ef` (API and worker version 18) · contract 1.6.0 · data snapshot `snap-20261115-globalfx` · live site https://d1r325uzu5fe7x.cloudfront.net · **Simulation only. Fictional profiles. Not financial advice.**

## 1. Problem and scope

Aplomb answers one question for a fictional investor: *does this hypothetical move fit the investor's own plan, and if not, how much would?* Code computes every number and every rule outcome; agents frame the request, gather official context, write the explanation and audit it; every figure in the result links to the data it came from.

| Persona (case brief) | Plan used by Aplomb | What the case tests | What Aplomb shows (live API, TSLA funded pro rata) |
|---|---|---|---|
| Robert, 59, low–moderate risk, 3–5 years | Preserve capital; position cap 10%, fixed-income floor 35%, volatility budget 9%, crypto excluded, attention flag | Challenge a publicized request instead of agreeing | +25 pts: **6 rule conflicts** (position, sector, growth assets, volatility, 2022 stress, drawdown); largest compatible size **6.0 pts** |
| Amira, 26, high risk, 15+ years | Growth; position cap 25%, crypto cap 15%, diversifiers floor 8% | "High risk" is not "anything goes" | +25 pts: 3 conflicts (diversifiers floor, volatility, 2022 stress), limit **11.0 pts**; +10 pts: tension only |
| Mateo, 41, moderate, 8–12 years | Balanced; Energy excluded, controversy evidence required, crypto cap 5% | Non-financial preferences, not only return and risk | CNQ +5 pts: **conflict on the Energy exclusion** although 8 checks pass; controversy reported as *not enough evidence* |

Supported requests: a move (ticker, size, funding), a goal ("reach X% in a theme"), a complete target allocation, a portfolio brief, a world-event brief, a historical replay (Time Machine), a profile draft from free text, the audit test, and deterministic standing-strategy simulations. Out of scope by design: orders or any execution tool, real client data, forecasts of future returns.

## 2. Architecture

```
 Browser (Next.js static export, EN/FR)
        │ HTTPS
 CloudFront ──► S3 (private web bucket, origin access control)
        │
 API Gateway (HTTP API, throttled) ──► API Lambda (FastAPI, Python 3.12)
        │                                 │  deterministic endpoints: overview, /check, strategies,
        │                                 │  world, datasets; creates runs
        │                                 ▼ async invoke (pinned worker version)
        │                              Worker Lambda (agent workflow)
        │                                 ├─► Amazon Bedrock: strong model, fast model, Guardrail
        │                                 └─► allow-listed official web sources (HTTPS fetch)
        ▼
 DynamoDB (profiles, runs, cache) · S3 data bucket (immutable snapshots, evidence bundles,
 release artifacts) · SQS (worker failure destination) · CloudWatch (logs, alarms, dashboard)
```

| AWS service | Role in the flow | Why |
|---|---|---|
| CloudFront + S3 | Serve the static web app; private bucket behind origin access control | No server to run for the UI; versioned objects allow rollback |
| API Gateway (HTTP API) | Public entry point with CORS and throttling (100 req/s, burst 200) | Managed TLS, limits and routing in front of Lambda |
| AWS Lambda (API) | Validates every request against the contracts; deterministic analytics in milliseconds to seconds | Scales to zero; 30 s budget is enough for code-only endpoints |
| AWS Lambda (worker) | Runs the agent workflow asynchronously, reserved concurrency 2, retry 1 | Agent runs take 40–60 s; isolation from the request path |
| Amazon Bedrock | Strong model (`us.openai.gpt-6-astra`) plans, researches and reviews; fast model (`us.anthropic.claude-opus-5-5`) writes; Guardrail version 3 screens output | Managed models with IAM scoping to two exact inference profiles; no keys in code |
| DynamoDB | Profiles, runs with checkpoints, cache; conditional writes for session ownership, idempotency and cancellation | Durable, serverless, on-demand capacity |
| S3 (data bucket) | Immutable, hashed data snapshots; run evidence bundles; release artifacts | Each Lambda can read only its pinned snapshot prefix |
| SQS + CloudWatch | Failed async deliveries kept; alarms and an operations dashboard keyed by run ID | Failures are visible instead of silent |

Infrastructure is AWS CDK (`infra/`). Each backend release is packaged in a clean Linux environment with an import check inside the AWS Lambda Python 3.12 image, synthesized, reviewed as a CloudFormation change set, executed, verified live and recorded with its rollback in `infra/evidence/`. Pushes to `main` rebuild and publish the site after the full test gate; publication checks the live API contract version first.

## 3. Agents, coordination and controls

A decision run is a fixed, observable sequence; each step is stored with its actor, model, tokens, tool calls, datasets read and duration.

```
plan (LLM) → research (LLM + tools, ≤3 rounds) → quant (code) → risk check (code)
   → [revise (LLM) → quant → risk, ≤2 times] → write (LLM) → audit (code + LLM + Guardrail) → sign (code)
```

| Role | Actor | What it decides | What it cannot do |
|---|---|---|---|
| Planner | Strong model | Interprets the request, asks a clarifying question when an input is missing, chooses research questions, and selects up to four optional analyses from a closed list (correlation of the asset with current holdings, the asset's own metrics, a calendar-year return, an extra stress window) that the quant step runs and records as facts; any task it cannot run is reported as skipped with its reason | Change a rule, threshold, figure or the data snapshot |
| Researcher | Strong model + tools | Which allow-listed sources to read (ten exact hosts: Bank of Canada, Federal Reserve, Statistics Canada, NASA EONET, GDELT, Wikimedia, SEC, iShares), fetched over HTTPS and which verbatim quotes to keep as evidence | Use a host outside the allow-list; cite a quote that is not in the fetched page (checked by A08) |
| Quant | Python | Every number: returns, volatility, drawdown, stress, concentration, FX, size scan | — (no model involved) |
| Risk officer | Python | Every enabled rule: pass, tension, conflict, not enough evidence; scenarios | — |
| Writer | Fast model | Wording, in English or French, as typed segments that reference ledger facts | Write a number itself: figures are inserted from the ledger |
| Auditor | Code + strong model + Guardrail | Strikes or rewrites unsupported sentences (one rewrite at most), then signs | Pass a brief with a failed blocking check |

In live run `run_01M7H5M0HWSYBN5EDK3P36BR5F` (Robert, TSLA +25 points, release 8e560ef) the planner selected three optional analyses; the quant step ran them as tool calls (`quant.asset_metrics`, `quant.correlation`, `quant.stress_replay`) and its summary reads "plan calculations: 3 run, 0 already mandatory, 0 skipped". The verdict, the six conflicts and the 6.0-point limit are the same as with an empty plan, which a test asserts.

Budgets per run: 90 s target and 180 s hard limit, at most 12 model calls, 12 research calls, 2 revisions, 1 rewrite and 6 scenarios. When a budget or a model fails, the run fails visibly; deterministic results stay available.

Governance is enforced in code, not delegated to a model:

- **Rules from the profile**: caps, floors, limits, exclusions, an evidence requirement (controversies) and an attention flag (Wikipedia page views). Thresholds are visible and editable by the user, never by an agent.
- **Largest compatible size**: a contiguous scan on a 0.5-point grid that stops at the first conflict (`M_MAXSIZE_GRID`), so the answer to Robert is a limit, not just a refusal.
- **Audit checks A01–A14**: references resolve (A01), no number outside referenced values (A02), comparisons true (A03), every fact sentence cites a fact (A04), mandatory facts/assumptions/limits sections (A05), simulation disclaimer (A06), no instructions, guarantees or predictions (A07), quotes found in the cached source (A08), interpretation review by the strong model (A09), Guardrail (A10), every fact available at the run's information date (A11), assumptions cover every conflict or tension (A12), limits cover every cited fact's limitations (A13), impact claims only with a measured price move (A14).
- **Signing**: the signed brief carries the hash of the run ledger; any later change to recorded facts changes the hash.
- **Audit test**: the "sabotage" mode inserts a code-built false sentence into a real brief and runs the real audit, which must catch it; all three modes were caught live in English and French.
- **Isolation**: every run belongs to a browser session; another session receives 404.

## 4. Methods

Prices are adjusted daily closes on a master calendar of 1,228 trading days (2021-11-12 to 2026-11-12). USD prices are converted to CAD with the Bank of Canada rate of the same day or the last published one (`M_FX_BOC_FFILL`). Portfolios use constant weights (`M_PORT_CONST_WEIGHTS`).

| Measure | Method |
|---|---|
| Annualized volatility | Sample standard deviation (n−1) of daily simple returns × √252 (`M_VOL_STDEV_252`) |
| Maximum drawdown | Minimum of value ÷ running maximum − 1 (`M_MDD_PEAK_TROUGH`) |
| 2022 stress | Constant-weight replay over calendar 2022, when stocks and bonds fell together (`M_STRESS_REPLAY`) |
| Concentration | Weights by position, sector, asset group, theme, listing country and currency; HHI and effective number |
| Correlation, VaR/ES | Pearson correlation of daily returns; historical 95% VaR and expected shortfall; variance shares |
| Attention | Mean page views of the last 30 days ÷ mean of the previous 365 days (`M_ATTENTION_RATIO`), shown as public attention, not quality |
| Strategies | Calendar or band rebalancing, contributions and a drawdown guard simulated on history against the untouched holdings (`M_STRATEGY_SIM`) |

The **Time Machine** replays a decision as of a past date. A row is visible only if it was available before the start of the next UTC day after that date; monthly macro series without real release dates are excluded in historical mode. Later outcomes are revealed in a separate ledger, and the signed hash is re-checked.

Two models were chosen by role: the strong model for planning, research and review, where reasoning quality matters; the fast model for writing, which happens on every run. Neither computes figures; the writer's grammar only allows references to ledger facts.

## 5. Data

| Data | Source | Use |
|---|---|---|
| 31 assets: 10 Canadian and 10 U.S. equities, 9 ETFs (equity, bonds, gold, one ESG-screened fund), Bitcoin, Ether | Case starter dataset | Universe and portfolios |
| 40,049 daily prices, adjusted for dividends and splits | Yahoo Finance via yfinance (starter) | Returns, risk, stress |
| Dividends and splits | Starter | Adjustment checks |
| USD/CAD daily | Bank of Canada Valet API | Currency conversion |
| Policy rates, 2- and 10-year yields, CPI (Canada, U.S.), U.S. unemployment | Bank of Canada, FRED (starter) | Macro context |
| Global FX for 9 reporting currencies | Bank of Canada | Accounts in other currencies |
| Page views | Wikimedia | Attention flag |
| ETF holdings, research documents | Issuer files, official releases | Look-through, evidence |
| World events and hazards | USGS, NASA, official releases, GDELT | Event briefs and country exposure; the feed keeps official releases and earthquakes of magnitude 6.0 or more (751 events) |

Processing: the ingestion command validates and normalizes every source (duplicate dates, non-positive prices, gaps), then publishes an immutable snapshot whose manifest records each dataset's SHA-256, row counts, date range and availability rule. A **passport** per dataset (the Sources page) states its origin, licence, coverage, processing, checks and limitations. Known traps are disclosed rather than hidden: survivorship in the universe, forward-filled FX, revised macro series, Yahoo data that is not certified, missing ESG and controversy evidence, and listing country used as a proxy for economic exposure. Country codes ISR, and the place names Israel, West Bank and Gaza, are presented as PSE / Palestine by team decision; raw captures are left unchanged and the transformation is recorded in the passports.

## 6. Explainability: one conclusion traced end to end

Live run `run_01M7GYQAMCZP9RTJFW9N44QRNT` (Robert, TSLA +25 points, pro rata funding; release 1307604, whose computation path is unchanged in 8e560ef) succeeded in 52 s.

1. **Sentence** (facts section): *"The requested after-move portfolio shows annualized volatility of 16.96% (2021-11-12 – 2026-11-12) and a largest peak-to-trough fall of 25.31%."* The writer produced text and two references; the figures were inserted from facts `F-011` and `F-012`.
2. **Fact `F-011`**: metric `vol.annualized` of Robert's after-move portfolio in CAD, value 16.965%, method `M_VOL_STDEV_252`, 1,228 observations, inputs `F-009` (the position weights) and `F-010` (the gated source count), sources `prices_daily` (14,736 rows read) and `fx_usdcad_daily` (1,218 rows), availability 2026-11-12, provenance check `LED_PROVENANCE` passed, six attached limitations (sample window, survivorship, constant weights, Yahoo not certified, calendar intersection, FX forward fill).
3. **Rule**: `limit.volatility` (R5) compares `F-011` with Robert's 9.00% budget (`F-029`): conflict, 7.96 points over.
4. **Audit**: the sentence passed A01, A02, A04, A07 and A08; the brief passed the global checks (A05, A06, A09, A10, A11, A12, A13); 14 sentences checked, none struck; Guardrail applied with no action; the model review found nothing.
5. **Signature and trace**: ledger hash `dc24d5d0…6fb` matches the stored checkpoint; 29 checkpoints; 6 of 12 model calls, 4 of 12 research calls, 42.8 s of 180 s; the research step reports 4 searches, 0 sources kept and 3 rejected, rather than claiming evidence it did not find.

In the app, clicking 16.96% opens this fact with its method, inputs, sources and limitations; the Evidence page lists the audit, and the System page shows each step's model, tokens and timing.

## 7. Validation

- **Automated**: 1,278 Python tests (plus 22 subtests), 411 web tests and 7 infrastructure tests pass in the release gate (`npm run check`, also run by CI on every push). They include the API contracts, generated types checked against the documented schemas, every rule, the size scan, scripted agent runs with audit failures and the three audit-test modes, session isolation, idempotency, cancellation and the historical gate.
- **Independent numeric controls**: `scripts/check_specs.py` and `contracts/controls/` recompute Robert's after-move volatility (16.96%), drawdown (25.31%) and 2022 stress (−21.88%) from the raw CSVs, independently of the application code.
- **Live**: every release records its live checks in `infra/evidence/` (contract version, endpoints, a signed decision, session isolation, code hash of both functions).
- **Sensitivity**: the size slider re-checks every rule as it moves; the same request can be compared across profiles; the Time Machine and strategies show behaviour on other dates and rules.

## 8. Limitations and next steps

Results describe a five-year historical sample and assumed plans, not forecasts. Economic exposure is approximated by listing country; ETF rules do not look through to constituents beyond the captured holdings; ESG and controversy evidence is thin, so Mateo's controversy check often ends as *not enough evidence*; event links never establish financial impact; research is limited to an allow-list of official sources; knowledge embedded in a model cannot be gated by date; the worker runs at most two analyses at once. Next steps: a licensed ESG and controversy source, more official sources with search, broader international listings, and streaming of run progress.

## 9. Reproduce

Requirements: Python 3.12 with uv, Node 22.19 or later. From the repository root: `uv sync --locked`, `npm ci`, `npm --prefix infra ci`, then `npm run check` (generated files, lint, tests, type checks, specification links, infra synth). Local run: `npm run dev:api` (materializes the pinned snapshot and starts the API) and `npm run dev:web`. Agent runs need Bedrock access (`APLOMB_MODEL_STRONG`, `APLOMB_MODEL_FAST`); every deterministic endpoint works without it. Configuration is documented in `.env.example`.
