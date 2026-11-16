"""GitHub runner entry point for the existing S3/CloudFront static site.

prepare is offline. publish uses the runner's short-lived OIDC credentials.
No backend, data, IAM or CloudFormation resources are changed by this script.
"""

import argparse
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MIME = {
    ".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".ico": "image/x-icon",
    ".webp": "image/webp", ".woff": "font/woff", ".woff2": "font/woff2",
}
MANIFEST = "deployment.json"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contracts/generated/schema.json"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def export_files(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Static export must not contain symlinks")
        if path.is_file() and path.name != MANIFEST:
            key = path.relative_to(root).as_posix()
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                raise ValueError("Static export must not contain hidden files")
            files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not {"index.html", "404.html"} <= files.keys():
        raise ValueError("Static export requires index.html and 404.html")
    return files


def parse_version(value):
    """`1.5.0` -> (1, 5, 0); a pre-release or build suffix is ignored. None when it is not a version."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", str(value or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def site_contract_version(schema=SCHEMA):
    """The API contract the web client was generated against (what the site expects of the API)."""
    return json.loads(schema.read_text(encoding="utf-8"))["x-contract-version"]


def prepare(root, revision, config, contract_version=None):
    contract_version = contract_version or site_contract_version()
    if parse_version(contract_version) is None:
        raise ValueError(f"Unreadable site contract version {contract_version!r}")
    files = export_files(root)
    # Confirm the compiled client points at the live API, rather than a fixture build.
    if not any(config["api_base"].encode() in (root / key).read_bytes()
               for key in files if key.endswith(".js")):
        raise ValueError("Compiled client is missing the configured live API URL")
    routes = sorted("/" + key.removesuffix("index.html") for key in files
                    if key.endswith("index.html") and not key.startswith("_"))
    manifest = {"revision": revision, "built_at": datetime.now(UTC).isoformat(),
                "api_base": config["api_base"], "fixtures": False,
                "contract_version": contract_version, "files": files, "routes": routes}
    save(root / MANIFEST, manifest)
    return manifest


def validate(root, revision, config):
    manifest = json.loads((root / MANIFEST).read_text())
    if (manifest["revision"] != revision or manifest["api_base"] != config["api_base"]
            or manifest["fixtures"] is not False or parse_version(manifest.get("contract_version")) is None
            or manifest["files"] != export_files(root)):
        raise ValueError("Artifact revision, configuration or file integrity mismatch")
    return manifest


def upload(root, manifest, config, s3, report):
    keys = list(manifest["files"])
    # Publish chunks first, mutable navigation payloads next, entry HTML last.
    keys.sort(key=lambda key: (2 if key.endswith(".html") else
                              0 if key.startswith("_next/static/") else 1, key))
    for key in [*keys, MANIFEST]:
        payload = (root / key).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        response = s3.put_object(
            Bucket=config["bucket"], Key=key, Body=payload,
            ContentType=MIME.get(Path(key).suffix, "application/octet-stream"),
            CacheControl="public,max-age=31536000,immutable" if key.startswith("_next/static/")
            else "public,max-age=0,must-revalidate",
            Metadata={"revision": manifest["revision"], "sha256": digest},
        )
        report["objects"].append({"key": key, "version_id": response.get("VersionId"),
                                  "sha256": digest})


def get(url):
    request = Request(url, headers={"User-Agent": "Aplomb-GitHub-Deployment-Smoke/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), error.read()


def smoke(manifest, config, fetch=get):
    checks = []
    base = config["site_url"].rstrip("/")
    status, _, body = fetch(base + "/" + MANIFEST)
    if status != 200 or json.loads(body)["revision"] != manifest["revision"]:
        raise RuntimeError("CloudFront is not serving the requested deployment revision")
    for route in manifest["routes"]:
        status, mime, _ = fetch(base + route)
        if status != 200 or "text/html" not in mime:
            raise RuntimeError(f"Route smoke failed: {route} ({status}, {mime})")
        checks.append({"path": route, "status": status})
    # Test the application chunks, not just cached HTML.
    for key in manifest["files"]:
        if key.startswith("_next/static/"):
            status, _, body = fetch(base + "/" + key)
            if status != 200 or hashlib.sha256(body).hexdigest() != manifest["files"][key]:
                raise RuntimeError(f"Static asset smoke failed: {key}")
    status, _, _ = fetch(base + "/__deployment_missing_" + manifest["revision"])
    if status != 404:
        raise RuntimeError(f"Missing route must return 404, got {status}")
    status, _, body = fetch(config["api_base"] + "/health")
    if status != 200 or json.loads(body).get("status") != "ok":
        raise RuntimeError("Existing API health check failed")
    return checks


META_ATTEMPTS, META_RETRY_SECONDS = 3, 5


def api_contract(manifest, config, fetch=get):
    """Compare the site's contract with the live API's GET /meta, before anything is uploaded.

    The site and the API deploy separately. A different major is incompatible (fails). An older API
    minor/patch is reported as "older": the site's newer features then show a "needs the newer API
    release" notice instead of calling routes the API does not have yet.
    """
    site = manifest["contract_version"]
    # A cold or slow API Lambda must not fail every site deploy: retry a few times before failing.
    for attempt in range(META_ATTEMPTS):
        try:
            status, _, body = fetch(config["api_base"] + "/meta")
            problem = None if status == 200 else f"HTTP {status}"
        except (URLError, TimeoutError) as error:
            problem = f"{type(error).__name__}: {error}"
        if problem is None:
            break
        if attempt + 1 < META_ATTEMPTS:
            time.sleep(META_RETRY_SECONDS)
    else:
        raise RuntimeError(f"API /meta preflight failed with {problem} after {META_ATTEMPTS} attempts")
    try:
        api = json.loads(body).get("contractVersion")
    except (ValueError, AttributeError):
        api = None
    parsed_api, parsed_site = parse_version(api), parse_version(site)
    if parsed_api is None or parsed_site is None:
        raise RuntimeError(f"API /meta reports no readable contractVersion ({api!r})")
    if parsed_api[0] != parsed_site[0]:
        raise RuntimeError(f"API contract {api} is incompatible with site contract {site}")
    return {"status": "older" if parsed_api < parsed_site else "ok", "site": site, "api": api}


def contract_preflight(manifest, config, require_current_api=False, fetch=get):
    """api_contract plus the policy: an older API warns by default and fails with --require-current-api."""
    result = api_contract(manifest, config, fetch)
    if result["status"] == "older":
        line = (f"Site contract {result['site']} > API contract {result['api']}; features added since "
                f"{result['api']} will show a 'needs the newer API release' notice")
        if require_current_api:
            raise RuntimeError(f"API older than site (--require-current-api): {line}")
        print(f"::warning title=API older than site::{line}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as stream:
                stream.write(f"**Warning: API older than site.** {line}.\n\n")
    return result


def publish(root, revision, config, clients, require_current_api=False, fetch=get,
            report_path=Path("deployment-report.json")):
    """Validate, check the API contract, then upload, invalidate and smoke test.

    `clients()` returns (s3, cloudfront); it is called only once the contract preflight passed, so an
    incompatible API stops the publish before a single object is written.
    """
    manifest = validate(root, revision, config)
    report = {"revision": revision, "site_url": config["site_url"],
              "started_at": datetime.now(UTC).isoformat(), "objects": [], "status": "started"}
    try:
        report["api_contract"] = contract_preflight(manifest, config, require_current_api, fetch)
        s3, cloudfront = clients()
        upload(root, manifest, config, s3, report)
        invalidation = cloudfront.create_invalidation(
            DistributionId=config["distribution_id"], InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": revision + "-" + os.environ.get("GITHUB_RUN_ID", "manual")
                + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            })["Invalidation"]["Id"]
        report["invalidation_id"] = invalidation
        cloudfront.get_waiter("invalidation_completed").wait(
            DistributionId=config["distribution_id"], Id=invalidation,
            WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        report["checks"] = smoke(manifest, config, fetch)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        save(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--export", type=Path, default=Path("web/out"))
    parser.add_argument("--config", type=Path, default=Path("infra/deploy/site.json"))
    parser.add_argument("--require-current-api", action="store_true",
                        help="fail the publish when the live API's contract is older than the site's")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("A full git commit SHA is required")
    config = json.loads(args.config.read_text())
    if args.command == "prepare":
        manifest = prepare(args.export, args.revision, config)
        print(f"Prepared {len(manifest['files'])} files for {args.revision} "
              f"(contract {manifest['contract_version']})")
        return

    def clients():
        # Import only in the credential-bearing GitHub runner path.
        import boto3
        from botocore.config import Config

        client_config = Config(retries={"mode": "standard", "max_attempts": 3},
                               connect_timeout=10, read_timeout=60)
        return (boto3.client("s3", region_name=config["region"], config=client_config),
                boto3.client("cloudfront", region_name=config["region"], config=client_config))

    report = publish(args.export, args.revision, config, clients, args.require_current_api)
    contract = report["api_contract"]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(f"Deployed `{args.revision}` to {config['site_url']}\n\n"
                         f"Verified {len(report['checks'])} routes, static assets, revision, 404 and API health. "
                         f"Contract check: site {contract['site']}, API {contract['api']} ({contract['status']}).\n")
    print(json.dumps({"status": report["status"], "site_url": config["site_url"],
                      "api_contract": contract["status"]}))


if __name__ == "__main__":
    main()
