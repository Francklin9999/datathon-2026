# contracts/run-events.md — run lifecycle and steps

A **run** is one piece of agent work: auditing a decision, reviewing a target allocation, writing the Home brief, briefing a world event, replaying a decision at a past date, drafting a profile, or the sabotage demonstration. All seven kinds share one model (`Run` in `schemas.md` §9), one storage layout and one timeline component in the UI.

The rule that makes the timeline trustworthy: **a step appears in `run.steps` only if it actually executed, with the tool calls it actually made** (brief p.15 and p.17: explanations faithful to observable actions). Nothing in a step is written by a language model; summaries are built by code from templates and counts.

---

## 1. Status machine

```text
            POST /runs
                |
             queued
                |  worker picks it up
             running  <-----------------------------+
              /  |  \                               |
             /   |   \   POST /runs/{id}/answers    |
   succeeded  failed  waiting_input ----------------+
                          |
                          |  POST /runs/{id}/cancel  (also allowed from queued/running)
                       cancelled
```

| Status | Meaning | `result` | `question` | `error` |
|---|---|---|---|---|
| `queued` | Stored, worker not started | null | null | null |
| `running` | Worker is executing steps | null | null | null |
| `waiting_input` | The Planner needs a missing input from the user (D-16 d) | null | set | null |
| `succeeded` | Final result signed by the auditor | set | null | null |
| `failed` | Unrecoverable error; steps executed so far remain visible | null | null | set |
| `cancelled` | Stopped by the user | null | null | null |

Rules:

- A run leaves `queued` within 5 seconds or the API marks it `failed` with `upstream_unavailable` when polled after 60 seconds without a worker heartbeat.
- A `waiting_input` run expires after 30 minutes (status `cancelled`).
- A `succeeded` run is immutable. A rerun creates a new run with `parentRunId`.

---

## 2. Step types

Fixed order within an iteration. The controls (`risk_check`, `audit`, `sign`) are executed by code on every run; the model chooses **what to investigate**, never **whether the controls run**.

| # | `type` | `agent` | `actor` | What it does | Must record |
|---|---|---|---|---|---|
| 1 | `plan` | planner | llm | Reads the request and the profile; produces an analysis plan: scenarios to test, quant tasks, research questions, or a clarifying question | model ID, usage, the plan summary (counts of tasks), tool calls to read-only lookup tools |
| 2 | `research` | researcher | llm+tools | Executes the research questions with the research tools; returns evidence with citations | one `ToolCall` per tool invocation, `evidenceIds` |
| 3 | `quant` | quant | code | Executes the mandatory metric set plus the tasks the plan asked for | one `ToolCall` per quant function, `datasetsRead` with row counts and `rowsWithheld`, `factIds` |
| 4 | `risk_check` | risk_officer | code | Evaluates every enabled rule for every scenario; computes verdicts, funding comparison, largest compatible size | `factIds` of rule checks, counts by status |
| 5 | `revise` | planner | llm | Only when step 4 raised a conflict, a tension or `nee`, and the iteration budget allows: decides what else to test (alternatives, other funding, more research) or to ask the user | model ID, usage, what was added |
| 6 | `write` | writer | llm | Drafts the brief using tokens that refer to facts, rules and evidence | model ID, usage, sentence count |
| 7 | `audit` | auditor | code+llm | Runs checks A01–A14 (`catalog.md` §6); strikes or repairs sentences; applies the guardrail | one `ToolCall` per check family, number struck |
| 8 | `sign` | auditor | code | Computes the ledger hash, stores the final result | `ledgerHash` in the summary |

After `revise`, steps 2–4 run again with `iteration` incremented. Maximum two revise loops per run (`MAX_REVISE = 2`).

### 2.1 Steps by run kind

| Kind | Steps that can occur |
|---|---|
| `decision` | plan → [research] → quant → risk_check → [revise → [research] → quant → risk_check]×≤2 → write → audit → sign |
| `rebalance` | plan → [research] → quant (imports the deterministic target comparison made when the run was created) → risk_check → write → audit → sign. No revise loop. |
| `portfolio_brief` | plan → quant → risk_check → write → audit → sign |
| `event_brief` | plan → [research] → quant → write → audit → sign |
| `replay` | same as `decision`, with every data read going through the temporal gate; `research` is **not** executed (documents cannot be date-filtered reliably) |
| `profile_draft` | plan → audit (code checks on the draft; actor `code`) → sign. No threshold is derived. |
| `sabotage` | write (one labelled false sentence built by code from the parent's facts; actor `code`, no model call) → audit. The brief is signed by the audit step; there is no separate `sign` step. |

Square brackets = executed only when needed. A step that is not needed is **absent**, not present with a "skipped" status. The two actors marked `code` above are the only per-kind departures from the §2 table.

---

## 3. Persistence and polling

- The worker writes after every state change: step started, tool call finished, step finished, status change. Each write bumps `run.updatedAt`.
- Clients poll `GET /v1/runs/{runId}` every 1,000 ms while status is `queued` or `running`, every 5,000 ms while `waiting_input`, and stop on any other status.
- `GET /v1/runs/{runId}?since=<seq>` returns steps whose `seq` is greater than `since`, plus facts/evidence referenced by those steps. `since` is the highest contiguous **completed** seq, never the highest running seq observed. Clients upsert by seq and fetch one full run at terminal status. A full payload remains available without `since`.
- Facts become visible as soon as the step that produced them finishes. The UI may show numbers before the brief exists.

### 3.1 Storage layout (DynamoDB table `aplomb-runs`)

| pk | sk | Content |
|---|---|---|
| `RUN#<runId>` | `META` | Run without `steps`, `facts`, `evidence` |
| `RUN#<runId>` | `STEP#<seq 4 digits>` | One `Step` |
| `RUN#<runId>` | `FACT#<factId>` | One `Fact` |
| `RUN#<runId>` | `EVID#<evidenceId>` | One `Evidence` |
| `RUN#<runId>` | `STATE` | Opaque worker state for resuming after `waiting_input` |

GSI `bySession`: pk `SESSION#<sessionId>`, sk `<createdAt>#<runId>` (list runs of a session). GSI `byProfile`: pk `SESSION#<sessionId>#PROFILE#<profileId>#V<profileVersion>#<kind>#<dataVersion>`, sk `<createdAt>#<runId>` (latest brief of an effective profile). Filter language/window and verify ownership. Details in `backend/aplomb/api/SPEC.md`.

---

## 4. Budgets and limits

| Limit | Value | Behaviour when reached |
|---|---|---|
| Wall-clock per run | 90 s target, 180 s hard | Hard limit → status `failed`, error `upstream_unavailable`, steps kept |
| Revise loops | 2 | The writer states that further alternatives were not explored |
| Research tool calls per run | 12 | Remaining questions are reported as "not researched" in the limits section |
| LLM calls per run | 12 | Run fails with `upstream_unavailable` ("The run reached its time or call budget; the steps already executed are kept."); calls spent by optional research only end that research |
| Writer rewrites after audit | 1 | Second failure of A05/A12 → run `failed` |
| Scenarios per run | 6 | Planner must rank and drop |
| Candidate assets per goal | 8 screened, 3 kept | — |

The defaults and the per-counter checks are in `backend/aplomb/agents/limits.py`. A deployment may lower, never raise, four of them by environment variable (`backend/aplomb/api/settings.py`): `APLOMB_MAX_LLM_CALLS` (≤ 12), `APLOMB_MAX_RESEARCH_CALLS` (≤ 12), `APLOMB_MAX_REVISE` (≤ 2) and `APLOMB_RUN_HARD_SECONDS` (≤ 180). Writer rewrites (1) and scenarios (6) are fixed. `GET /runs/{runId}/trace` (`api.md` §5.9) reports the limits applied by the deployment.

---

## 5. Step summary templates

Summaries are produced by code. English templates (French equivalents live next to them):

| Step | Template |
|---|---|
| plan | `Planned {nScenarios} scenario(s), {nQuant} calculation(s), {nResearch} research question(s).` or `Asked the user for: {field}.` |
| research | `Ran {nCalls} search(es) across {nTools} tool(s); kept {nEvidence} source(s), rejected {nRejected}.` |
| quant | `Computed {nFacts} fact(s); {nWithheld} row(s) withheld by the date gate.` or, when the gate reports no availability summary, `Computed {nFacts} fact(s).` |
| risk_check | `Checked {nRules} rule(s) on {nScenarios} scenario(s): {conflict} conflict, {tension} tension, {pass} fit, {nee} not enough evidence.` |
| revise | `Objection returned to the planner; added {nScenarios} scenario(s) and {nResearch} research question(s).` |
| write | `Drafted {nSentences} sentence(s) with {nTokens} reference(s).` |
| audit | `{nChecked} sentence(s) checked, {nStruck} struck, {nRepaired} repaired.` |
| sign | `Result signed. Ledger hash {hash8}.` |

---

## 6. Example (abridged)

A complete example is in `contracts/fixtures/run.decision.robert-tsla-25.json`. Shape of one step:

```json
{
  "seq": 3,
  "type": "quant",
  "iteration": 1,
  "agent": "quant",
  "actor": "code",
  "status": "done",
  "startedAt": "2026-11-14T20:25:03Z",
  "endedAt": "2026-11-14T20:25:04Z",
  "durationMs": 840,
  "summary": { "en": "Computed 14 fact(s) from 15,964 row(s) in 2 dataset(s); 0 row(s) withheld by the date gate.", "fr": "14 fait(s) calculé(s) à partir de 15 964 ligne(s) dans 2 jeu(x) de données ; 0 ligne retenue par le filtre de date." },
  "model": null,
  "usage": null,
  "toolCalls": [
    {
      "id": "T-003",
      "tool": "quant.portfolio_metrics",
      "args": { "profileId": "robert", "variant": "after", "window": { "code": "full" } },
      "startedAt": "2026-11-14T20:25:03Z",
      "durationMs": 310,
      "ok": true,
      "resultSummary": "volatility, max drawdown, 2022 replay",
      "datasetsRead": [
        { "datasetId": "prices_daily", "dataVersion": "snap-20261113-starter", "rows": 14736, "rowsWithheld": 0 },
        { "datasetId": "fx_usdcad_daily", "dataVersion": "snap-20261113-starter", "rows": 1228, "rowsWithheld": 0 }
      ],
      "factIds": ["F-008", "F-009", "F-010"],
      "evidenceIds": [],
      "error": null
    }
  ],
  "factIds": ["F-008", "F-009", "F-010"],
  "evidenceIds": []
}
```

The row counts in this example are illustrative; real steps report what the datastore actually read.
