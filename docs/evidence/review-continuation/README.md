# Independent-review verification evidence

Captured 2026-11-15 just after midnight EST at repository base `f46c453`. The [verification report](../../11-VERIFICATION-FOLLOWUP.md) explains results, failures and remaining acceptance evidence.

| Artifact | Meaning |
|---|---|
| `check.log` | Fresh successful `UV_CACHE_DIR=/tmp/aplomb-uv-cache npm run check` |
| `build.log` | Fresh successful `npm run build:web` with the normal local API default |
| `deployment.json` | Live API metadata and CloudFront deployment manifest; frontend and backend release identities must be distinguished |
| `cloud.json` | Read-only AWS MCP observations: persisted original live decision, six steps, fact count, matching CloudWatch event, versioned S3 checkpoint and snapshot metadata, worker version/code hash/concurrency. Session identifiers are omitted |
| `recovered-claude-checks.json` | Sanitized final structured tool results recovered from Claude's interrupted session; these observations precede this continuation |
| `browser-isolated/browser.json` | Local nine-route sweep at three widths, followed by two form-driven persona comparisons |
| `browser-isolated/live/browser.json` | Same sweep/comparisons on CloudFront; unavailable feature screens count as rendered routes, not working feature paths |
| `browser-isolated/extra.json` | Local scripted decision/goals, all 20 numeric drawers, keyboard trapping/return, profile validation/copy/save, rapid input, French shell and 18-page axe-core scan |
| `followup/followup.json` | Corrected stale-edit probe and form-driven replay/reveal; the parent hash is re-read and matches after reveal |
| `browser/` | Interrupted setup attempt: port 8000 was already occupied by the earlier session and its CORS policy did not allow the new static origin. No product pass/fail conclusion is drawn from this directory |

The first profile concurrency probe in `extra.json` returned 422 because the probe sent response-only fields back to the update endpoint. The corrected request in `followup.json` returned 200; submitting the stale visible form then displayed its conflict message and preserved edits. This was a probe error, not a profile defect.

The completed local checks used a freshly built static export with `NEXT_PUBLIC_APLOMB_API_BASE=http://localhost:8001/v1`, a temporary starter snapshot, and `ScriptedGateway` from the existing integration-test helpers. The disposable API enabled supported P1 providers and disabled guardrails. No fixture adapter, real model, production profile mutation or AWS deployment was used. Local services created for this review were stopped afterward; earlier session services were not stopped.

The route sweeps use the existing [browser smoke script](../../../tests/browser-smoke.mjs). The interaction probes drove DOM form controls and keyboard events through Chrome's debugging protocol, and used local HTTP run creation for the signed brief and goals. The replay was launched and revealed through its visible form. axe-core 4.10.3 ran WCAG 2 A/AA, 2.1 AA and 2.2 AA tags; incomplete contrast checks remain visible in the report. No visual baseline comparison, screen-reader pass or Core Web Vitals measurement is claimed.

To reproduce the goal defect independently of a browser or credentials, run from the repository root:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/aplomb-uv-cache uv run python - <<'PY'
from tests.integration._scripted import ScriptedGateway
from tests.integration.test_run_composition import make, run_to_end, session

client = make(ScriptedGateway())
goal = {"type": "goal", "goal": {"themes": ["ai"], "assetClasses": [],
    "tickers": [], "targetExposurePct": 15, "maxLossPct": None,
    "maxVolPct": None, "notes": ""}}
run = run_to_end(client, session(), {"kind": "decision", "profileId": "amira",
    "lang": "en", "request": goal})
print(run["status"], run["error"])
PY
```

Expected at the reviewed revision: `failed`, error code `internal`. The optimizer correctly identifies an already-met exposure; its workflow adapter raises on the empty candidate list. Replacing the target with `None` succeeds. The failure also reproduces in French.

GitHub hosted CI could not be read: the connector returned `401 Bad credentials`, while the unauthenticated API returned 404. Credentials and raw session identifiers were not retained in these artifacts. The local gate is successful; hosted CI and repository visibility are unverified.
