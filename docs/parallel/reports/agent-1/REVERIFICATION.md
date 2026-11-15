# Reproduce Agent 1 end-to-end verification

Run in `.worktrees/investor-quant` with the installed isolated Python/node dependencies. The pinned expanded snapshot is opt-in; these commands do not change `data/manifests/active.json`. Provider rights must remain at their default denied state, and no model is used. Use a fresh ignored application-state path and a fresh Chrome profile for each complete run.

Run the gate, then the build sequentially:

```bash
UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache npm run check
NEXT_PUBLIC_APLOMB_API_BASE=http://localhost:8101/v1 APLOMB_NEXT_DIST_DIR=.next-agent1-build npm run build:web
```

Start the isolated API on its own terminal (replace the state filename for another run):

```bash
UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache APLOMB_DATA_VERSION=snap-20261115-a1-fx-expanded APLOMB_LOCAL_STATE_FILE=.artifacts/agent1-e2e-fresh-state.json APLOMB_ALLOWED_ORIGINS=http://localhost:3101,http://127.0.0.1:3101 APLOMB_MODEL_STRONG= APLOMB_MODEL_FAST= uv run python scripts/dev_api.py --host 127.0.0.1 --port 8101 --no-reload
```

Serve the production export on another terminal:

```bash
.venv/bin/python -m http.server 3101 --bind 127.0.0.1 --directory web/.next-agent1-build
```

Start a fresh isolated browser on another terminal:

```bash
google-chrome --headless=new --no-sandbox --disable-gpu --remote-debugging-port=9321 --user-data-dir="$(mktemp -d /tmp/aplomb-agent1-e2e-XXXXXX)" about:blank
```

Run all acceptance suites in order:

```bash
UV_CACHE_DIR=/tmp/aplomb-agent-1-uv-cache npm run test:investor-e2e
```

The runner stops on a failed assertion/child process and writes per-suite logs plus `reverification/summary.json`. It checks every added route against the immutable baseline inventory. Permission-denied provider requests are recorded explicitly as error-path coverage; success from live providers is not inferred. Fixture-based acquisition success and integrity/session/rights failures are covered by Python tests. The browser suites activate actual rendered form controls and exercise real HTTP; the tooltip suite separately checks physical pointer, keyboard and touch interaction. Synthetic factor values derived from the actual portfolio sample prove arithmetic/alignment only and are not independent economic evidence. No Bedrock execution, production deployment, source permission activation or paid/login feed is part of this run.
