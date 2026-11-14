# T08/T09/T10 integration — 2026-11-14

Three Sol agents at medium reasoning implemented agents/execution, research capture and ledger/audit concurrently. Root coordinated the contracts, pinned Strands 1.65.0, reviewed safety/persistence behavior, added cross-track tests and ran genuine Bedrock requests through the official AWS MCP.

## Verified results

The final `npm run check` passed on Python 3.12.16 / Node.js 24.18.0 with **310 Python tests, 73 web checks and five infrastructure tests**, plus lint, strict TypeScript, generated-file drift, fixture/numeric checks and offline CDK synthesis. A fresh index-only install reproduced the complete result without the concurrent frontend changes. This includes the teammate's T05 quant implementation and the final idempotent fact-registration regressions. One installed Mangum event-loop deprecation warning remains. Checks make no live provider calls.

Independent integration tests exercise captured research -> same-run document/evidence -> ledger -> audit/sign, hostile source text, historical research denial, actual ASGI response validation and MCP bridge response identity/attempt accounting. T08 tests execute a full synthetic decision including revision, real mandatory code callbacks and the T10 auditor; synthetic providers are test-only and are never loaded by default runtime composition.

The [genuine profile-draft record](evidence/agents-profile-draft-20261114.json) completed a fresh Haiku 5.5 call, plan/audit/sign, HTTP polling and a new FileStore reader. Run `run_01M7E58536MMNMYHYQWWXFZ8X6` used one successful inference with 5,945 input and 1,327 output tokens. Only the explicitly supplied name and occupation survived; unsupported fields remained unresolved. Session bearer capability is removed from the saved evidence. There were no portfolio calculations or saved-profile mutations.

[Earlier probe metadata](evidence/agents-live-probes-20261114.json) records two failures honestly: the model rejected explicit temperature; a later response supplied null for a nonnullable optional key. Temperature was removed, strict validation retained, and one charged schema repair is supported. The successful run did not need a repair. No account policy was changed.

Live network requests used the MCP file bridge in `scripts/live_agents_smoke.py`, not direct shell AWS SDK/CLI calls. The production Strands adapter is covered by inspected API/source and stubbed constructor/repair tests; this is not represented as a live Strands transport test. No application stack was deployed.

## Interfaces and remaining gates

See the [T08 handoff](T08-HANDOFF.md), [T09 handoff](T09-HANDOFF.md) and [T10 handoff](T10-HANDOFF.md) for exact interfaces and verification commands.

The worker requires explicit `AgentServices` composition and a configured Lambda factory. Profile drafts work with the model gateway alone. Decisions require T05–T07 controls plus the ledger, signer and pinned temporal gate. Replay additionally needs T12 metadata. Portfolio briefs, event briefs and sabotage execution remain explicit unavailable providers; T10 supplies honest sabotage ledger/audit helpers, not a fabricated caught-lie demonstration. Guardrails remain unapplied unless a verified callback is injected. These limits are exposed instead of being filled by successful fixtures.

Research has genuine Wikimedia/issuer page captures and strict same-run quote verification. SEC returned 403, GDELT timed out and a purported issuer CSV returned HTML; these remain unavailable rather than guessed. The T09 follow-up completes independently verified company-fact currency figures, attention-ratio facts and issuer CSV weight registration. A fresh live attention run passes registry, audit and ledger checkpoint restoration; the captured series also survives RunRepository/FileStore persistence. Reviewed mapping and issuer configuration remain injected. See T09 for the live record and remaining source availability limits. Missing research never certifies absence of controversy. Browser navigation remains disabled.

The teammate's T05 quant commit `c66cc87` is included. A real T05 calculation was tested with the T10 sink; semantically identical repeated facts reuse their IDs and changed provenance is rejected. T05's current aggregate facts do not register dependency facts, so T10 retains their unverified status rather than trusting the producer's verified declaration. The controls integration must supply that lineage before those facts can support a signed brief.

The default API still requires domain-provider injection. The new modules do not silently advertise a complete investment-analysis application. Numeric reference controls and shared wire shapes are unchanged. Concurrent frontend work was left with its owner; only the contract-test adjustment needed for Next.js incremental settings is included in this task.
