# External dependencies only

- Data-use rights: French, AQR, Cboe, OCC and FINRA public access does not establish permission for the intended app's storage/display/AI use. Anonymous connectors are wired, but their rights assertions are not enabled. Exact provider references/settings are in PROVIDERS.md and SOURCES.csv. No owner approval was requested and no terms were bypassed.
- French ZIP host: prior real acquisition attempts reset the connection. The validated ZIP reader and bounded acquisition path are present; no successful capture is claimed.
- Agent 2 integration: actual verified issuer constituent captures and security crosswalks are needed to connect the exact-ISIN consumer to real portfolio holdings. User-supplied/synthetic fixtures do not prove that integration.
- Real investor inputs: source-verified private valuations, liabilities, available spending capital, return/contribution assumptions, liquidity restrictions and factor sensitivities cannot be inferred from persona names. Explicit-input workflows and exact missing-input states are implemented.
- Reviewed agent/replay execution: local real gateway reports missing APLOMB_MODEL_STRONG/APLOMB_MODEL_FAST; no live Bedrock demonstration is claimed. Actual Home wording/auditor orchestration and issuer acquisition belong to Agent 2. Same-latest-day replay is also rejected by the baseline eligibility guard because a future reveal window is required; explicit historical /check at equality is implemented separately.

Paid CME and account/API-key OANDA/FRED/FINRA short-interest are excluded/set aside by the user's latest instruction, **not blockers for the present anonymous-feed scope**. No account creation or subscription is needed or requested. FRED also has an independently documented data-use restriction; the new raw capture was removed.

Unimplemented engineering/quantitative coverage is recorded in REQUIREMENTS.md, not misclassified as an external blocker. Production deployment, merged acceptance and snapshot selection remain integrator-owned.

Git publication: automatic approval review rejected `git push -u origin codex/agent-1-investor-quant`. Stated reason: external GitHub destination not verified as trusted/explicitly authorized and broad payload may contain private captures/logs/project data. No workaround or indirect push was attempted. The branch is committed locally. A credential-pattern scan of 22 evidence text files found no matching AWS/OpenAI/private-key patterns; captures are official public aggregate feeds and screenshots use synthetic investors, but this does not substitute for destination/publication approval. Explicit approval of publishing this branch and evidence to `https://github.com/Francklin9999/datathon-2026` is needed before retrying.

## Publication authorization update — 2026-11-15

The user explicitly instructed “commit and push what you have currently so a part is on remote and continue.” This authorizes the current checkpoint payload and configured origin `https://github.com/Francklin9999/datathon-2026` on `codex/agent-1-investor-quant`; the earlier automatic-review rejection is historical. Publication outcome is recorded in STATUS/HANDOFF after the push.
