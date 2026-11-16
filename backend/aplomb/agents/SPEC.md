# Agents and worker orchestration

**Track:** T08. **Tier:** P0 workflow; optional kinds P1. [Tool catalog](../../../contracts/tools.md), [run lifecycle](../../../contracts/run-events.md) and [ledger grammar](../ledger/SPEC.md) are binding.

## 1. Six roles, separate authority

| Role | Implementation | Decision / value |
|---|---|---|
| Planner | Strong model, lookup tools | Interprets confirmed request, selects scenarios/research and revises after objections |
| Researcher | Strong model + bounded research tools | Chooses documents/passages that answer specific evidence questions |
| Quant Engine | Pure code | Computes figures using explicit methods and gated data |
| Risk Officer | Pure code + optimizer | Enforces enabled rules regardless of the Planner's preference |
| Writer | Fast model, no tools | Explains ledger-backed results through references, not self-generated figures |
| Auditor | Code + strong model + configured Guardrail | Rejects missing references, false relations and unsupported language, then signs |

The two deterministic roles are components, not pretend LLM conversations. UI actor labels distinguish code/model/tool execution. The Auditor cannot change a computed number or verdict to match prose. Do not expose hidden model reasoning; persist observable actions and validated structured plans only.

## 2. Files and public entry points

Planned files: `workflow.py`, `worker.py`, `registry.py`, `limits.py`, `models.py`, `prompts/`, `summaries.py`. `execute_run(run_id, generation, services) -> None` claims/resumes work through T03 repositories. `RequestParser(gateway, profiles).parse_request(profile, text, lang) -> ParsedRequest` (called by `RequestParser.parse` for `POST /v1/requests/parse`) uses the fast model and validates against shared types. `ModelGateway.generate(role, schema, messages, tools, limits)` returns typed output, usage and actual model ID; its fake implementation is used in offline tests.

Strands is the selected SDK (D-07). Verify/pin API usage against [official SDK source](https://github.com/strands-agents/sdk-python); this spec deliberately does not freeze an untested import/constructor signature. Register only the tools permitted per role in `contracts/tools.md`. Tools accept validated arguments/context; no model-selected Python function names, imports or shell execution.

## 3. Planner output contract (internal)

```ts
interface AnalysisPlan {
  interpretation: string;
  scenarioTasks: { kind: ScenarioKind; ticker: string | null; funding: Funding | null }[];
  quantTasks: { tool: string; args: Record<string, unknown> }[];
  researchQuestions: { id: string; subject: string; question: string; preferredTools: string[] }[];
  clarification: ClarifyingQuestion | null;
}
```

Validate every ticker/tool/enum and cap task counts. The interpretation describes the confirmed structured input; it cannot silently change size or funding. Unspecified size/funding may cause a clarification or a clearly recorded automatic-funding comparison. Unsupported/ambiguous parsing returns missing fields; no untyped prose becomes a tool call. Refuse execution/personalized-advice requests through `ParsedRequest.refused` and keep the manual simulation path available.

## 4. Decision workflow

### 4.1 Initialization

Read pinned profile/data/input from repository. Construct gated ToolContext with ledger, cache, logger, actual model IDs and budgets. Start wall-clock budget before first model call. Never fetch a new profile halfway through a run. Terminal/repeated claim returns without duplicating work.

### 4.2 Plan and research

Execute real plan step; if missing input persists, checkpoint and enter waiting_input. Research executes only explicit questions and only within budget. Save each kept citation through quote-verifying evidence registration. Research timeout is recorded and produces evidence gaps; it does not grant a clean ESG result. Skip research entirely for historical runs. The UI sees only steps actually executed.

### 4.3 Mandatory code controls

For every decision, regardless of plan: before snapshot, requested after snapshot, reporting-currency volatility/drawdown/2022 stress where available, single-name/sector/group exposures, enabled-rule checks, explicit/auto funding resolution and first-conflict boundary. Register request-size and threshold assumptions. These cannot be disabled by model output. Additional research/quant tasks are bounded and recorded.

### 4.4 Revision and write

After conflict/tension/nee the Planner can ask for additional evidence, alternatives or funding tests, up to two revise loops. It cannot loosen rules. Each newly tested scenario gets real quant/risk steps and stable scenario IDs, <=6 scenarios total. Exhausted budget becomes a limitation; keep core figures and proceed to write if safe. Write from immutable ledger view, checks and scenario metadata using [token grammar](../ledger/SPEC.md). Writer has no tools and cannot modify the ledger.

### 4.5 Audit and sign

Run deterministic checks, model wording review and configured Guardrail. A05/A12 allow one rewrite; re-audit the entire rewrite. Mark struck/repaired sentences. Unrecoverable structure, temporal violation, or unusable/refused output fails the run with executed steps preserved. Sign canonical facts/evidence, append disclaimer and computed limitations, then atomically persist succeeded result. `succeeded` means controls actually executed; disabled Guardrails are reported as not applied, never as passed service checks.

## 5. Other run kinds

Portfolio brief: baseline metrics/checks and three fact-backed focus cards, cached on full context. Event brief: cited event/exposure research, optional observed price move, mandatory audit/sign; no portfolio-rule step unless checks were performed. Replay: decision flow with historical context and no research. Profile draft: extract only supported fields, return unresolved questions and provisional defaults for form confirmation; do not persist a custom profile. Draft uses `Partial<Profile>`: omit unsupported fields and block save until required inputs are confirmed; never invent a risk level to satisfy a full Profile schema. The code auditor (`profile_draft.py`) keeps a drafted field only when the text states it (risk tolerance and risk capacity are told apart by clause; horizon ranges, objectives, the nine catalog currencies by code or EN/FR name, the country by its ISO alpha-2 code) or when it equals a confirmed `fields` value; `investorContext` is audited per key. Every withheld field becomes a bilingual question naming the proposed value and the reason. Sabotage: derive a child run from a signed decision, reuse immutable facts and visibly inject instruction; parent remains unchanged.

Profile-draft extraction uses the fast model, matching the profile-service spec; full decision planning/revision uses the strong model. If risk/horizon fields needed for threshold derivation are unresolved, do not derive thresholds yet: the quant step is absent and the form requests confirmation first. No draft should claim a derivation from unsupported inputs.

## 6. Limits, persistence and failure

Use lifecycle caps: 90 s target/180 s hard, <=12 LLM calls, <=12 research calls, <=2 revisions, <=1 writer rewrite, <=6 scenarios, <=8 screened goal assets/3 retained. Per-call timeout is bounded by remaining time. Default research cap does not imply 12 sequential 20-second calls fit the run: stop early and state missing questions. Reserve time for audit/sign; never drop controls to meet latency.

Checkpoint after start/end of each step and each tool result. Heartbeat while long calls run; ownership/generation checked before writes. Resume waiting input from immutable saved state, not by replaying prior model calls. Model failures receive bounded transient retry; invalid schema receives a bounded repair attempt charged to LLM budget. Audit model unavailability prevents signing a claim that model review happened; deterministic preview remains usable.

## 7. Verification and handoff

AGT-01 fake-model end-to-end decision including revision. AGT-02 ignored mandatory controls attempt. AGT-03 tool allow-list/schema enforcement. AGT-04 parse ambiguity/refusal/manual fallback. AGT-05 budget exhaustion keeps limitations/controls. AGT-06 waiting-input resume does not rerun previous tools. AGT-07 duplicate dispatch/cancel races. AGT-08 real Bedrock smoke with actual IDs/usage/log correlation. AGT-09 no invented steps or hidden-reasoning fields. AGT-10 all run result variants validate.

Done: offline fake-model suite plus one explicitly separate genuine Bedrock run, not a fixture. Provide T14 real polling examples in queued, running, waiting_input, failed and succeeded states.
