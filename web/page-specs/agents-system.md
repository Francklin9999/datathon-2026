# Agents & System — what actually ran

**Owner:** T15. **Tier:** P0 transparency with P1 service panels. Route `/agents-system/?runId=...`.

## Static role map and live state

Six role cards identify Planner/Researcher/Writer/LLM Auditor as model work and Quant/Risk Officer/code Auditor as deterministic controls. Show allowed tools and purpose, not decorative claims of independent agents. Architecture view uses the approved service diagram and actual `/meta` feature/model state. Distinguish planned configuration from verified execution.

Select a session run and display genuine steps, actor, iteration, model ID, measured duration/usage, tool calls, arguments with sensitive details redacted, read dataset/version/count/withheld and produced facts/evidence. Link each result to Evidence & Audit. Summaries are code-authored action descriptions. Absent optional steps are absent, not fake “skipped” completions.

## Operational display

Show run budget totals and terminal/waiting state (limits from `GET /runs/{runId}/trace`, which reports the API's configured limits; when the trace is unavailable, the run-events.md §4 contract defaults, labelled as such), errors with request ID, configured vs applied Guardrails and data snapshot date. Do not claim `/health` or model configuration proves a Bedrock call occurred. Actual usage/model fields and operator capture are separate evidence. Never expose cloud credentials, session capability, raw hidden reasoning, or cached copyrighted full documents.

## Verification

SYS-01 roles/actors match run data. SYS-02 failed tool remains visible. SYS-03 no inferred steps from timers. SYS-04 metadata service flags reflect reality. SYS-05 run ownership/redaction. SYS-06 keyboard list and mobile detail. Reuse the shared runs table (`RunsTable`, also used by Evidence & Audit) for the run picker. The selected run shows one per-step detail view built from the same `run.steps` that the shared timeline (`RunTimeline`) shows on Decision Desk and Audit, so the views agree without the timeline being repeated here. Each step is checked against the run-events.md §2 table and its §2.1 per-kind overrides.
