"""Run T16's optional browser gate with disposable local services and Chrome.

Usage: uv run python tests/run_browser_smoke.py .artifacts/t16-browser-new
Requires an existing `npm run build:web`, Node >=22 and google-chrome.
"""

import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def ready(url):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(.1)
    raise RuntimeError(f"Local QA service did not start: {url}")


def stop(process):
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT if os.name != "nt" else signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome is None:
        raise RuntimeError("Install Chrome/Chromium for this optional local gate")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with ExitStack() as stack:
        profile = stack.enter_context(tempfile.TemporaryDirectory(prefix="aplomb-t16-chrome-"))
        commands = [
            ("api", [sys.executable, str(ROOT / "tests/browser_api.py")]),
            ("static", [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1",
                        "--directory", str(ROOT / "web/out")]),
            ("chrome", [chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check",
                        f"--user-data-dir={profile}", "--remote-debugging-port=9227", "about:blank"]),
        ]
        for name, command in commands:
            log = stack.enter_context((output / f"{name}.log").open("w"))
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            stack.callback(stop, process)
        for url in ("http://127.0.0.1:8000/v1/meta", "http://127.0.0.1:8765/",
                    "http://127.0.0.1:9227/json/version"):
            ready(url)
        result = subprocess.run(
            [shutil.which("node") or "node", str(ROOT / "tests/browser-smoke.mjs"),
             "http://127.0.0.1:8765", str(output)], cwd=ROOT, timeout=180, check=False,
        )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
