# External dependencies only

- Data-use rights: French, AQR, Cboe, OCC and FINRA public access does not establish permission for the intended app's storage/display/AI use. Anonymous connectors are wired, but their rights assertions are not enabled. Exact provider references/settings are in PROVIDERS.md and SOURCES.csv. No owner approval was requested and no terms were bypassed.
- French ZIP host: prior real acquisition attempts reset the connection. The validated ZIP reader and bounded acquisition path are present; no successful capture is claimed.
- Agent 2 integration: actual verified issuer constituent captures and security crosswalks are needed to connect the exact-ISIN consumer to real portfolio holdings. User-supplied/synthetic fixtures do not prove that integration.
- Real investor inputs: source-verified private valuations, liabilities, available spending capital, return/contribution assumptions, liquidity restrictions and factor sensitivities cannot be inferred from persona names. Explicit-input workflows and exact missing-input states are implemented.
- Reviewed agent/replay execution: local real gateway reports missing APLOMB_MODEL_STRONG/APLOMB_MODEL_FAST; no live Bedrock demonstration is claimed. Actual Home wording/auditor orchestration and issuer acquisition belong to Agent 2. Same-latest-day replay is also rejected by the baseline eligibility guard because a future reveal window is required; explicit historical /check at equality is implemented separately.

Paid CME and account/API-key OANDA/FRED/FINRA short-interest are excluded/set aside by the user's latest instruction, **not blockers for the present anonymous-feed scope**. No account creation or subscription is needed or requested. FRED also has an independently documented data-use restriction; the new raw capture was removed.

Unimplemented engineering/quantitative coverage is recorded in REQUIREMENTS.md, not misclassified as an external blocker. Production deployment, merged acceptance and snapshot selection remain integrator-owned.

Git publication is no longer blocked: after the explicit exact-destination/payload approval, checkpoint `9683eff487cf62e663d271a9191ad21f25c5d5bc` was pushed successfully to `https://github.com/Francklin9999/datathon-2026` on `codex/agent-1-investor-quant`. Earlier automatic-review rejection was resolved by that approval, with no workaround. No credentials are part of the evidence; captures are official public aggregate sources and all investor/model QA fixtures are synthetic.
