"""GitHub runner entry point for the existing S3/CloudFront static site.

prepare is offline. publish uses the runner's short-lived OIDC credentials.
No backend, data, IAM or CloudFormation resources are changed by this script.
"""

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MIME = {
    ".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".ico": "image/x-icon",
    ".webp": "image/webp", ".woff": "font/woff", ".woff2": "font/woff2",
}
MANIFEST = "deployment.json"


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


def prepare(root, revision, config):
    files = export_files(root)
    # Confirm the compiled client points at the live API, rather than a fixture build.
    if not any(config["api_base"].encode() in (root / key).read_bytes()
               for key in files if key.endswith(".js")):
        raise ValueError("Compiled client is missing the configured live API URL")
    routes = sorted("/" + key.removesuffix("index.html") for key in files
                    if key.endswith("index.html") and not key.startswith("_"))
    manifest = {"revision": revision, "built_at": datetime.now(UTC).isoformat(),
                "api_base": config["api_base"], "fixtures": False,
                "files": files, "routes": routes}
    save(root / MANIFEST, manifest)
    return manifest


def validate(root, revision, config):
    manifest = json.loads((root / MANIFEST).read_text())
    if (manifest["revision"] != revision or manifest["api_base"] != config["api_base"]
            or manifest["fixtures"] is not False or manifest["files"] != export_files(root)):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "publish"])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--export", type=Path, default=Path("web/out"))
    parser.add_argument("--config", type=Path, default=Path("infra/deploy/site.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("A full git commit SHA is required")
    config = json.loads(args.config.read_text())
    if args.command == "prepare":
        manifest = prepare(args.export, args.revision, config)
        print(f"Prepared {len(manifest['files'])} files for {args.revision}")
        return
    # Import only in the credential-bearing GitHub runner path.
    import boto3
    from botocore.config import Config

    manifest = validate(args.export, args.revision, config)
    report = {"revision": args.revision, "site_url": config["site_url"],
              "started_at": datetime.now(UTC).isoformat(), "objects": [], "status": "started"}
    try:
        client_config = Config(retries={"mode": "standard", "max_attempts": 3},
                               connect_timeout=10, read_timeout=60)
        s3 = boto3.client("s3", region_name=config["region"], config=client_config)
        cloudfront = boto3.client("cloudfront", region_name=config["region"], config=client_config)
        upload(args.export, manifest, config, s3, report)
        invalidation = cloudfront.create_invalidation(
            DistributionId=config["distribution_id"], InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": args.revision + "-" + os.environ.get("GITHUB_RUN_ID", "manual")
                + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            })["Invalidation"]["Id"]
        report["invalidation_id"] = invalidation
        cloudfront.get_waiter("invalidation_completed").wait(
            DistributionId=config["distribution_id"], Id=invalidation,
            WaiterConfig={"Delay": 15, "MaxAttempts": 40})
        report["checks"] = smoke(manifest, config)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        save(Path("deployment-report.json"), report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(f"Deployed `{args.revision}` to {config['site_url']}\n\n"
                         f"Verified {len(report['checks'])} routes, static assets, revision, 404 and API health.\n")
    print(json.dumps({"status": report["status"], "site_url": config["site_url"]}))


if __name__ == "__main__":
    main()
