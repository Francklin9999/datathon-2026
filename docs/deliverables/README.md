# T16 delivery pack

This pack records the current checkout's offline QA and distinguishes it from earlier cloud captures. It is not a release approval. Start with the [acceptance report](acceptance.md), [captured gate report](evidence/report.json) and [artifact manifest](manifest.json).

## Reproduce from a clean checkout

Requirements: Python 3.12, uv, Node >=22.19 and npm. From the repository root:

```bash
uv sync --locked
npm ci
npm --prefix infra ci
uv run python scripts/qa_smoke.py --output .artifacts/t16-new
```

Use a new output directory for each run. If the default uv cache is read-only, set `UV_CACHE_DIR` to a writable temporary directory before these commands. The harness runs the same root integration gate as CI, builds the normal static client, loads every page directly from a plain local static HTTP server, verifies referenced JS/CSS and the disclaimer, then ingests the immutable starter CSVs into a temporary directory and checks actual API responses. It records commands, exit codes, durations, log hashes, revision, dirty files and latency samples. Temporary data is deleted on completion. Installation needs network access; the installed gate needs no AWS credentials or provider calls. A clean-clone installation was not independently performed in this QA session.

The static check verifies HTML/asset delivery, not browser hydration, focus, mobile layout or CloudFront configuration. The API probe uses in-process ASGI HTTP and no model; its latency excludes network and Lambda. The existing integration tests explicitly use scripted model responses where needed. None of these is an offline product mode.

## Optional local browser gate

With Chrome/Chromium installed and ports 8000, 8765 and 9227 free, run:

```bash
uv run python tests/run_browser_smoke.py .artifacts/t16-browser-new
uv run python -m unittest discover -s tests -p test_qa_smoke.py
uv run ruff check scripts/qa_smoke.py tests/test_qa_smoke.py tests/browser_api.py tests/run_browser_smoke.py
node --check tests/browser-smoke.mjs
```

The browser runner manages a temporary starter-data API, plain static server and headless Chrome together, then stops them and removes the temporary snapshot/profile. Its API settings ignore environment model IDs and AWS configuration. The local test browser uses `--no-sandbox` for this restricted execution environment and only visits the local application. It loads every page at 375/768/1440 px, checks hydration, loaded persona, disclaimers, page width and Tab focus, then tests Robert/Amira TSLA comparison at 25 and 10 points. Full keyboard journeys, signed-brief drawers and production cloud behavior require separate checks. The [browser record](evidence/browser.json) and screenshots retain the actual outcomes.

## Submission material

- [One-pager](one-pager.md): product, user, evidence and limits.
- [Technical documentation](technical.md): architecture, methods and a traced figure.
- [Five-minute demo script](demo.md): timings, capture instructions and release checklist.
- [Acceptance contract](../07-ACCEPTANCE.md): authoritative required outcomes.
- [Original cloud evidence](../../infra/evidence/aws-architecture-2026-11-14.json) and [architecture audit](../FULL-ARCHITECTURE-AUDIT.md): earlier releases, not this offline run.

The video recording, current deployed-UI/cloud capture, final artifact hosting, team names and submission destination remain team delivery actions. Do not submit the release as P0-complete while acceptance rows are blocked.
