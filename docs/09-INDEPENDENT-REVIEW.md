# 09 — Independent review of the built product

**Reviewed:** Saturday 2026-11-14, 23:35–23:52 EST, starting at commit `7c4c457` (`main`, then equal to `origin/main`).
**Reviewer:** a separate review session that wrote none of the implementation.
**Companion:** [as-built status matrix](10-STATUS-AS-BUILT.md).

**Follow-up completed 2026-11-15:** [verification continuation](11-VERIFICATION-FOLLOWUP.md) adds the remaining page sweeps, local interactions, French/accessibility checks and cloud readback. It also identifies a new goal edge-case failure. Findings below describe the original observation window; consult the follow-up for current verification coverage.

**Verdict in one paragraph.** The core product works on AWS, end to end, with real models, and its numbers are right. The engineering around trust (ledger, audit, durable runs) is far beyond what a datathon needs. The weak spot is the thing the jury reads: **the written explanation is stiff, does not mention the investor's goals, and loses its two best sentences to the auditor.** The second weak spot is the "agentic" criterion: a live decision makes three model calls and zero tool calls, and the Planner's output changes nothing visible. Most of the remaining day should go to those two, the demo video and the three written deliverables, not to more infrastructure.

---

## 1. What was checked, and how

| # | Check | Method | Result |
|---|---|---|---|
| 1 | Repository gate | `npm run check` from the root | Python lint clean; **742** Python tests pass; **155** web tests pass; **6** infrastructure tests pass and CDK synth succeeds. At 23:38 the spec-link step failed on 9 broken links in `docs/deliverables/`, which another session was still writing. That session committed the pack as `f46c453`; `scripts/check_specs.py` re-run at 23:52 passes (69 documents linked, 3 fixtures, numeric controls, 20 acceptance rows). The full gate was not re-run after that commit. |
| 2 | Deployed configuration | `GET /v1/meta` on the deployed API | See §2. |
| 3 | Deployed site revision | `deployment.json` on CloudFront | `revision` = `7c4c457`, built 2026-11-15T04:36Z. |
| 4 | Home page, deployed | Headless Chrome, 1440 px | Renders; a real portfolio-brief run started and finished. |
| 5 | Free-text request, deployed | Typed "I keep reading about Tesla. What if I put a quarter of the portfolio into it, selling everything else pro-rata?" | Parsed correctly (TSLA, 25 points, pro-rata, confidence high). |
| 6 | Decision run, deployed | "Analyze evidence" for Robert +25 TSLA; run `run_01M7ERBNQM5DVKQ01XX4DKRJ4D` | Succeeded. Details in §3. |
| 7 | Deterministic checks, deployed | `POST /v1/check` for Amira +25 TSLA and Mateo +10 CNQ.TO | Match the control numbers (§3). |
| 8 | Evidence & Audit and Agents & System pages, deployed | Read the rendered pages for the run above | Render; audit report readable. |
| 9 | World Explorer, local | Headless Chrome against another session's local build | Renders; see §4.6. |
| 10 | Auditor and writer source | Read `backend/aplomb/ledger/audit.py` and `agents/workflow.py` | Root causes in §4.1. |
| 11 | Secrets | `git grep` for key patterns over tracked files | Only dummy test values. The AWS account ID and a deploy role ARN are committed in 7 files (not credentials). |

**Not checked:** the Time Machine, profile creator, Portfolio and Sources pages in a browser; French output; keyboard and screen-reader use; mobile layouts (another session's report covers 375 px page loads); any code path of research, replay or event briefs with a real model; GitHub Actions results; whether the repository is public; AWS console contents. Nothing was changed in AWS. Two real runs (one brief, one decision) and one parse call were made on the deployed stack during this review.

---

## 2. What is live right now

From `GET /v1/meta` on the deployed API at 23:45 EST:

| Setting | Value |
|---|---|
| Data version | `snap-20261114-sourced`, data date 2026-11-12 |
| Universe | 31 assets, all starter tier |
| Models | strong `us.openai.gpt-6-astra`, fast `us.anthropic.claude-opus-5-5` |
| Languages | English only |
| Features **on** | profile creator, frontier chart, guardrails |
| Features **off** | World Explorer, Time Machine, goal requests, sabotage demo, bilingual, open-web research, on-demand tickers, both extra globe layers |

So the product a judge can open today is: Home, Portfolio, Decision Desk (specific moves only), Evidence & Audit, Agents & System, Sources, profile creator. The four "signature" P1 features chosen in D-01 are not deployed.

---

## 3. What works (verified live)

**The numbers are right.** Every figure below was produced by the deployed system and equals the reference value in [controls](../contracts/controls.md).

| Scenario | Live result | Control |
|---|---|---|
| Robert +25 TSLA, pro-rata | conflict; 6 conflicts, 1 tension, 1 fit; volatility 16.96%; 2022 replay −21.88%; drawdown 25.31%; largest size before first conflict 6.0 points | same |
| Amira +25 TSLA, pro-rata | conflict; 3 conflicts, 2 tensions; position 25.0 vs 25 (tension); diversifiers 7.5 vs 8; volatility 26.30; boundary 11 points | same |
| Mateo +10 CNQ.TO | conflict only on the Energy exclusion; controversy rule "not enough evidence"; every financial rule passes; boundary 0 | same |
| Robert baseline on Home | volatility 6.1%, drawdown 9.6%, YTD +10.3%, 1-year +10.6%, 2022 replay −4.7% | same |

**The run pipeline is real.** The decision run recorded six steps: plan (7.3 s, `gpt-6-astra`), calculations (0.6 s, code), rule check (0.7 s, code), write (17.3 s, `claude-opus-5-5`), audit (4.7 s, code plus `gpt-6-astra`), sign (0.2 s). Total 34.3 s, 36,547 input and 2,672 output tokens, 69 facts, guardrail applied with action "none". The page updated step by step and the URL kept the run ID.

**The parser challenges Robert.** For the Tesla sentence it answered, before any run: "Frequent news coverage is context, not a reason to invest." That is exactly the behaviour the brief asks for on page 7.

**Honesty mechanics hold.** Disclaimer visible on the two pages screenshotted (Home, Decision Desk); features that are off are absent from the navigation; the attention rule says "No page-view data is loaded" instead of inventing a value; the compare panel warns that equal verdicts can hide different checks.

**The interface is polished.** Clear hierarchy, consistent status colours, before/after tables, rule table with derivation drawers. No horizontal overflow on Home at 1440 px (measured).

---

## 4. Findings, most important first

### 4.1 The audited brief loses its best sentences and reads like a status dump (high)

In the live Robert run the auditor struck 2 of 19 sentences, both for check A02 ("numbers outside referenced values"):

- "Replaying calendar 2022 with the after-move weights gives a return of −21.9% …, while the before baseline replay gives −4.7% …"
- "In the alternative scenario using the largest compatible TSLA size of 6.0 pts, volatility is 7.7% …, and the 2022 replay return is −8.9% …"

These are the two sentences that carry the story: what a bad year would cost, and what size would fit. Both contain the literal year "2022". `has_literal()` in `ledger/audit.py` fails any sentence whose prose contains a numeric character or a number word (the list includes "one", "half", "quarter", "double"). The audit report of this run shows 0 rewrites, so the struck sentences were removed, not repaired; the acceptance contract reserves the single rewrite for missing structure. The Home brief written minutes earlier said "the calendar-year stress window" instead of the year, and its stress sentence was kept.

What remains after the strikes is seven sentences of the form "R1, with an assumed threshold of 10.0%, has status conflict." That is a list, not an explanation. Three causes, all in `_draft_and_audit` (`agents/workflow.py`):

1. **The writer never sees the profile.** Its input is facts, evidence, the request and the rule checks. Objective, horizon and preferences are not passed, so it cannot say why this matters for a 59-year-old who retires in a few years.
2. **The writer is told not to compare.** The instruction forbids "within, exceeds, more, less, higher, lower". The rule engine already builds correct comparison sentences in two languages ("Portfolio volatility would be 16.96% a year, above the 9.00% budget."), and they are better than what the model is allowed to write.
3. **There is no summary section.** Only facts, assumptions and limits are requested.

The limits section is also repeated: six model-written limits, then nine code-appended limitation texts that say the same things, then the same list a third time under "Limitations".

**Better way.**

| Change | Where | Effort |
|---|---|---|
| Add a code-built **"Bottom line"** section at the top: verdict, number of rules in conflict, the two largest breaches (reuse `RuleCheck.detail`), the largest size before the first conflict, and the investor's stated objective and horizon. Built from templates and tokens, so it cannot fail the audit. | `agents/workflow.py`, `rules/templates` | 1–2 h |
| Register profile fields (objective, horizon, key preferences) as `assumption` facts and pass them to the writer, with the instruction to connect one or two findings to them. | `agents/workflow.py` | 1 h |
| Use the rule engine's `detail` sentences for the assumptions section instead of asking the model to restate statuses. | `agents/workflow.py` | 30 min |
| Stop striking years: accept a four-digit year in prose when it equals a year inside the `period` of a fact cited in the same sentence, or give the writer a window-label token. Remove everyday words ("one", "half", "double", "quarter") from the number-word list unless followed by a unit. | `ledger/audit.py` | 1 h + tests |
| On an A02 or A03 strike, give the writer one repair pass for the struck sentences only (the rewrite budget of 1 was unused in this run). | `ledger/audit.py`, `agents/signing.py` | 1–2 h |
| Limits: the writer writes at most two run-specific limits; code appends the rest once; the UI shows three and folds the remainder. | workflow + web | 1 h |

This is the highest-value work left. It moves the criterion "agentic intelligence and explainability" (20%) and it is what the video will show.

### 4.2 The agents do not visibly act (high)

The live decision recorded `llmCalls: 3`, `toolCalls: 0`, `evidence: 0`, and two scenarios (requested, largest size). Step summaries read "plan done", "quant done", "risk_check done". The team's own architecture audit states that production controls run a fixed scenario set and do not honour planner proposals.

A judge following deck slide 5 ("why does this agent exist and what value does it bring?") will find that the Planner costs 7 seconds and 5,000 tokens and changes nothing they can see. Decision D-16 (on conflict: explore alternatives, recommend funding, ask for missing information) is only partly visible: the funding comparison appears; alternatives do not.

**Better way, bounded and cheap.**

1. Give the Planner a **typed menu of four actions** and execute what it picks through the existing code: `test_alternative(ticker)` (the function `optimizer.alternatives` already exists), `compare_funding`, `stress_window(rate_cycle)`, `macro_context(series)`. Record each as a real `ToolCall`. The result then shows an "alternative" scenario and a non-zero tool count, and the timeline says what was chosen and why.
2. Replace the step summaries with the counted templates already specified in [run-events](../contracts/run-events.md) §5 ("Checked 11 rules on 2 scenarios: 6 conflict, 1 tension…"). Pure presentation, about 30 minutes.
3. If neither is done, say plainly in the documentation and the video that the model's job is interpretation and explanation and that the controls are fixed by design. Do not describe the Planner as choosing calculations.

### 4.3 The persona tests are met by rules, not yet by evidence (medium)

- **Robert** (brief p.7: "a highly publicized company"). The attention rule always answers "No page-view data is loaded". The handoff estimates half a day for a Wikimedia page-view provider. It would turn "publicized" from a word in the persona into a measured fact on screen.
- **Mateo** (brief p.6: more than return and risk). The Energy exclusion works and is the right demonstration. The controversy rule is permanently "not enough evidence" because research is off in production. The ESGV-versus-SPY comparison that the SRS asked for (EF-08) does not appear in his brief. Adding those two calendar-2022 facts to his decision brief is a small change.
- **Amira** (brief p.5). Works well: the diversifier floor and the volatility budget show that high risk is not "anything goes", and the funding comparison shows a way to keep the diversifiers.

### 4.4 Model text outside the audit (medium)

The parse interpretation is model-written and shown unaudited. In this review it contained "2.5 times the 10% single-position cap" and "It will likely also strain the volatility … limits". The first is a model-computed number; the second is a prediction about rule outcomes before any calculation. Both happened to be right, but the product's central claim is that models never supply numbers. Either restrict the parser to restating the request, or render its remarks only after `/check` has run, from the real rule checks.

### 4.5 Decisions that were made but not delivered (medium)

Compared with the [decision log](02-DECISIONS.md):

| Decision | State |
|---|---|
| D-21 sabotage toggle | Not built as a run kind (handoff: "half a day"). The demo script in the original plan relied on it. |
| D-23 wide universe | 31 starter assets. On-demand tickers work locally only and are off. |
| D-26 ESG evidence from registries, filings, news | None loaded; research off (SEC answered 403 and GDELT returned nothing in the team's probes). |
| D-30 "all the events" | 176 events in the default one-year view (seen locally). Per the [source register](../data/SOURCES.md) the bundle holds Bank of Canada, Federal Reserve and Statistics Canada release titles and USGS earthquakes of magnitude 6 or more; GDELT is not loaded, so there are no news, corporate or geopolitical events. |
| D-33 open-web research | Off. |
| D-36 bilingual | Built, off in production; no French speaker has read a real French brief. |

None of this is hidden in the product, which is to the team's credit. It does need to be reflected in the one-pager and the video so they do not promise more than a judge can open.

### 4.6 World Explorer is not demo-ready as a signature feature (medium)

Seen locally: the page opens on a filter form with six text fields and fifteen checkboxes; the globe is further down. The content is a feed of official notices and earthquakes, and the link to a portfolio is "the event's country has portfolio weight". That is honest, and it is thin: an earthquake near Vanuatu says nothing about Robert's plan.

If it is deployed, put the globe first, fold the filters, and default to "only events matching this portfolio". If time is short, leave it off and show one screenshot under "what comes next". It should not take demo time from the Decision Desk.

### 4.7 Result placement and wording (low to medium)

- After "Analyze evidence" the run appears at the bottom of a page that is 4,300 px tall at desktop width. Scroll to it automatically, or move the run above the preview details.
- Product wording leaks internals: "the before baseline", "6.3 count", "0.2×", "−0.0%", "R4 has status tension", "nee". Use "current portfolio", "6.3 positions", and hide a value that rounds to zero.
- Scenario "Key facts" appear in the page text as a run of values ("25.0% 25.0% 60.2% 37.5% 17.0%") with no label between them. Check that each chip carries a visible label.
- Times are shown in UTC ("04:45 a.m. UTC") for a Montréal audience.
- `/favicon.ico` returns 404 on the deployed site.

### 4.8 Process risks (low, but cheap to fix)

- The delivery pack committed in `f46c453` marks release readiness "blocked" mainly for lack of browser journeys and a current deployed decision. This review supplies part of that evidence (a decision started from the deployed interface and completed, plus the checks in §3); the AWS operator still has to capture the matching cloud records. Its AT-08 row is "passed" on test doubles, while the live run in §4.1 shows the audit removing correct sentences: the row should mention that.
- Worker reserved concurrency is 2 (architecture audit). Several judges running decisions at once will queue past the 60-second start deadline. Raise it for the judging window if the account allows.
- The AWS account ID and deploy role ARN are in tracked files. They are identifiers, not credentials; confirm the repository's visibility is what the team intends.

---

## 5. Where the effort went, and where it should go next

Lines of Python by module (application code only): datastore 3,721; API 2,884; contracts 2,122; agents 2,061; optimizer 1,868; ledger 1,443; quant 1,297; world 1,217; research 897; profiles 756; rules 541; timemachine 341. The web app is about 14,200 lines.

The durable-execution layer (leases, generations, version-pinned workers, idempotency, checkpoint spill to S3) is production-grade. No criterion in the evaluation grid rewards it beyond "quality of AWS integration" (15%), which the current stack already satisfies. The explanation a user reads, and the agent behaviour a judge can observe, together weigh 20% and received the least product attention.

**Suggested order for the remaining time** (code deadline Sunday 23:59 EST; AWS closes Monday 13:59):

| Order | Work | Why | Estimate |
|---|---|---|---|
| 1 | Brief quality: §4.1 in full | Largest visible gain; fixes a live defect | 5–7 h |
| 2 | Counted step summaries and the Planner menu (§4.2) | Makes "agentic" true and visible | 3–4 h |
| 3 | Decide what ships: enable goal requests and Time Machine only after one real-model run of each on AWS; leave World Explorer off unless §4.6 is done; drop sabotage from the script unless built | The video must match what is deployed | 1–2 h |
| 4 | ESGV/SPY facts for Mateo; page-view provider for Robert | Persona tests backed by evidence | 0.5 h and 4 h |
| 5 | Wording and placement (§4.7) | Cheap polish the UX criterion (10%) sees | 2 h |
| 6 | Record the video on the deployed stack, capture AWS evidence, then freeze | Must happen before the account closes | 2–3 h |
| 7 | One-pager and technical document written for the jury | 15% of the grade | 2–3 h |

Stop adding infrastructure. The transactional outbox, admission control and paging listed as "next upgrades" in the architecture audit are correct for a public service and worth one sentence each under "proposed improvements"; they earn nothing before Monday.

---

## 6. Notes for the deliverables

The brief (p.15–16) asks the jury to "understand the value proposition" and wants a one-pager covering problem, agentic approach, originality, data sources, explainability and concrete user benefits.

- The current one-pager draft speaks to engineers ("run-local ledger", "conditional writes", "numeric grammar"). Lead with the person: an investor near retirement who has read about one stock all week, and a tool that answers with his own plan instead of agreeing. Then one figure a judge remembers: 25 points requested, 6 points fit, and why.
- State the originality in one line: *the model explains, code decides, and every number opens its proof.*
- Name the user. The SRS listed an advisor preparing a client conversation; with a bank as sponsor that is the clearest business case.
- Technical document: keep the traced example (Robert's 16.96% volatility) and add the audit example from this review, including the struck sentences, as proof that the control is real. Once §4.1 is fixed, show the before and after.
- Video: use only the deployed build. The parser's reply to Robert, the six conflicts, the 6-point boundary, one number opened to its source, and Amira's different answer fit in three minutes. Leave the last minute for the AWS trace of the same run ID.
