# T08 agents and durable execution handoff

Implemented under `backend/aplomb/agents/`; no runtime import performs network I/O.
Shared public models come from `aplomb.contracts`. The runtime does not load contract
fixtures. Offline tests label their synthetic control providers explicitly.

## Composition and supported behavior

`execute_run(run_id, generation, AgentServices)` claims the T03 repository, checkpoints
observable steps, renews leases during long calls, and yields to cancellation/new generations.
`worker.make_handler(services)` works with `LocalDispatcher`; `worker.handler` is the Lambda
entry point. On its first invocation it builds `AgentServices` from the process
environment through `aplomb.api.runtime.default_agent_services`; the local API composes
the same services through `aplomb.api.runtime.build_run_services`.

`AgentServices` requires `repository` and `gateway`. Optional fields are `registry`,
`controls`, `ledger_factory`, `signer`, `gate_factory`, `store`, `logger`, `clock`, and
`replay_result_factory`. `gate_factory(private)` must open the pinned manifest/context;
`private['profile']` is the pinned profile payload. Never resolve a new current profile
inside a running decision.

* `profile_draft`: available with the gateway alone. Fast-model extraction, deterministic
  support checks, unresolved risk/horizon questions, and a code extraction-integrity hash
  run as actual plan/audit/sign steps. It never creates a saved profile or derives rules.
  Unsupported fields are omitted. Literal name/occupation, explicit risk wording and
  confirmed input fields are conservative support boundaries; other inferred values remain
  unresolved. The extraction hash is private integrity metadata, not a portfolio AuditReport.
* `decision`: executable only with explicit code controls, ledger, signer and temporal gate.
  `CodeControls.quant(ctx, request, window, tasks, scenarios)` must execute mandatory before/
  after snapshots, reporting-currency metrics/stress/exposures/funding and register facts.
  It returns JSON-serializable checkpoint state. `risk(ctx, computed)` must execute enabled
  rules and the first-conflict boundary, returning `ControlOutcome(CheckResult, scenarios,
  selected_scenario_id, limitations)`. The model cannot remove these code calls. No default
  quant/rules/optimizer provider exists in this track: missing providers fail honestly.
* `replay`: decision controls plus an explicit `replay_result_factory(decision, ctx, private)`
  supplying the actual gate/reveal metadata; absent metadata disables replay before execution.
  The result must validate as shared `ReplayResult` and preserve the cutoff. Research is denied.
* `portfolio_brief`, `event_brief`, `sabotage`: explicit unavailable-provider failures;
  no fabricated result variants or advertised successful implementations.

`signing.sign_decision` connects T10 `audit_and_sign` to required strong-model review and
one bounded writer rewrite. It does not configure Guardrails. T10 reports Guardrails as
not applied. This track does not claim a service check occurred when it was disabled.

## Model and tool boundaries

`ModelGateway.generate(role, schema, messages, tools, limits)` returns
`Generation(output, model_id, input_tokens, output_tokens, calls=1)`. Every adapter must
charge `limits.take('llm_calls')` before each physical inference attempt. Runtime rejects
successful replies whose charged count differs. Typed JSON responses, actual role/model/
usage/call metadata and validated plan outputs are persisted privately; hidden reasoning
and raw agent transcripts are not persisted. Step usage accumulates across audit/rewrite
calls. Failed attempts preserve counts and any available token metadata, without inventing
usage for requests whose provider never returned it.

Strands `1.65.0` was verified from its published wheel/source and pinned centrally by
integration. The adapter uses `Agent`, `BedrockModel`, single-turn limits, no agent tools,
no SDK retry strategy, one botocore transport attempt and one explicitly charged schema/
transient repair. Actual input/output tokens come from `result.metrics.accumulated_usage`.
Neither temperature nor provider-unsupported model options are emitted. Optional JSON
schema defaults are removed from the generation prompt; unknown nonnullable fields must
be omitted rather than set to null. Validation is retained.

Primary API references: [published package](https://pypi.org/project/strands-agents/1.65.0/),
[official SDK](https://github.com/strands-agents/sdk-python),
[official Bedrock provider guide](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/).

`ToolRegistry` uses catalog names, role allowlists, argument schemas and pinned cutoff checks.
Unknown arguments, unregistered tools and historical research are rejected before invocation.
Bind T09 tools with `research_tool_handlers(service)` and register each returned `(Args, callable)`.
The strong Researcher chooses typed actions from actual registered schemas; at most three
bounded rounds and twelve research calls execute. Source text has no execution authority.
No shell/import/order tool exists.

## Durability and limits

Completed steps cache their typed outputs. Waiting-input answers consume the saved plan;
completed model calls and code steps are reused on resume. T10 `checkpoint()/restore()`
retains immutable facts, evidence, source documents and freeze state. Step fact/evidence
IDs reflect actual ledger deltas, so polling can retrieve quantitative results.
A crash during an in-flight external request can still leave an unknown remote completion;
there is no provider idempotency claim for that window.

Tools and controls receive isolated context/ledger copies: a timed-out thread cannot mutate
what is subsequently persisted or signed. Only completed successful results are merged.
Provider caches may still complete safe retrieval writes. Actual tool calls checkpoint
immediately. Lease writes use the newest heartbeat revision; a stale/cancelled owner cannot
persist terminal success or failure.

Limits enforce 180 seconds, twelve inference calls, twelve research calls, two revisions,
one rewrite and six stable scenario IDs. Changed results cannot reuse a scenario identity.
Optional research reserves time/calls for write/audit; exhausted research is recorded as an
execution limitation and preserves code controls. Hard budget exhaustion fails with executed
steps/facts retained. A signing-required model outage never becomes a claimed successful audit.

## Verification and genuine smoke

`uv run pytest backend/tests/agents -q`: twelve offline tests pass. They exercise the full
synthetic decision with revision and actual ledger audit/sign, mandatory code invocation,
allowlists/schema/replay rejection, parser ambiguity/refusal, draft unsupported-field checks,
budget caps, duplicate dispatch, cancellation, waiting-input and stale-lease resumption,
late-timeout isolation, and Strands constructor/repair/usage behavior without network calls.
Combined agents + ledger + research suites: sixty-four tests pass at handoff.

Root integration separately executed a genuine persisted profile-draft worker through the
official AWS MCP bridge: `run_01M7E58536MMNMYHYQWWXFZ8X6`,
`us.anthropic.claude-haiku-5-5`, one successful inference, input 5945/output 1327 tokens,
actual plan/audit/sign, re-read from FileStore. See
[`docs/evidence/agents-profile-draft-20261114.json`](evidence/agents-profile-draft-20261114.json).
Earlier live probes exposed unsupported temperature and invalid optional-null output; they
were failures, not successful executions. Root retains their separate metadata. No shell
AWS SDK/CLI live call was made by this track. The real probe establishes fresh Bedrock
inference plus worker persistence; the Strands transport itself is covered by offline
source/API checks and stub verification, not misrepresented as a live Strands smoke.
