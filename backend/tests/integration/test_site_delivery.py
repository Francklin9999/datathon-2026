"""Offline delivery tests: artifact tampering, upload order and false smoke success."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location("deploy_site", ROOT / "scripts/deploy_site.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
CONFIG = {"api_base": "https://example.com/v1", "site_url": "https://site.example.com",
          "bucket": "project-site"}
REVISION = "a" * 40


def artifact(tmp_path):
    files = {"index.html": "Home", "404.html": "Missing", "portfolio/index.html": "Portfolio",
             "_next/static/client.js": CONFIG["api_base"], "index.txt": "Navigation data"}
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return delivery.prepare(tmp_path, REVISION, CONFIG, contract_version=SITE_CONTRACT)


SITE_CONTRACT = "1.5.0"


def test_tampered_export_or_revision_cannot_be_published(tmp_path):
    artifact(tmp_path)
    assert delivery.validate(tmp_path, REVISION, CONFIG)
    with pytest.raises(ValueError, match="integrity"):
        delivery.validate(tmp_path, "b" * 40, CONFIG)
    (tmp_path / "_next/static/client.js").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        delivery.validate(tmp_path, REVISION, CONFIG)


def test_prepare_records_the_generated_contract_version(tmp_path):
    """Without an explicit version, the manifest carries contracts/generated/schema.json's x-contract-version."""
    for name, text in {"index.html": "Home", "404.html": "Missing", "_next/static/client.js": CONFIG["api_base"]}.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    manifest = delivery.prepare(tmp_path, REVISION, CONFIG)
    expected = json.loads((ROOT / "contracts/generated/schema.json").read_text(encoding="utf-8"))["x-contract-version"]
    assert manifest["contract_version"] == expected


def test_manifest_without_contract_version_cannot_be_published(tmp_path):
    artifact(tmp_path)
    marker = json.loads((tmp_path / "deployment.json").read_text())
    del marker["contract_version"]
    (tmp_path / "deployment.json").write_text(json.dumps(marker))
    with pytest.raises(ValueError, match="integrity"):
        delivery.validate(tmp_path, REVISION, CONFIG)


def meta_fetch(api, status=200):
    def fetch(url):
        assert url == CONFIG["api_base"] + "/meta"
        body = json.dumps({} if api is None else {"contractVersion": api}).encode()
        return status, "application/json", body
    return fetch


@pytest.mark.parametrize(("api", "expected"), [("1.5.0", "ok"), ("1.6.0", "ok"), ("1.5.1", "ok"), ("1.4.0", "older")])
def test_api_contract_preflight(tmp_path, api, expected):
    manifest = artifact(tmp_path)
    assert delivery.api_contract(manifest, CONFIG, meta_fetch(api)) == {"status": expected, "site": SITE_CONTRACT, "api": api}


@pytest.mark.parametrize(("api", "status", "match"), [
    ("2.0.0", 200, "incompatible"), ("0.9.0", 200, "incompatible"), ("1.5.0", 503, "HTTP 503"),
    (None, 200, "contractVersion"), ("garbage", 200, "contractVersion"),
])
def test_api_contract_preflight_failures(tmp_path, monkeypatch, api, status, match):
    monkeypatch.setattr(delivery.time, "sleep", lambda seconds: None)
    manifest = artifact(tmp_path)
    with pytest.raises(RuntimeError, match=match):
        delivery.api_contract(manifest, CONFIG, meta_fetch(api, status))


def test_api_contract_preflight_retries_a_slow_or_unreachable_api(tmp_path, monkeypatch):
    """A cold API Lambda (timeout, 503) is retried; only a persistent failure stops the deploy."""
    from urllib.error import URLError

    waits = []
    monkeypatch.setattr(delivery.time, "sleep", waits.append)
    manifest = artifact(tmp_path)
    replies = iter([URLError("timed out"), (504, "", b""), (200, "application/json", b'{"contractVersion": "1.4.0"}')])

    def flaky(url):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    assert delivery.api_contract(manifest, CONFIG, flaky)["status"] == "older"
    assert waits == [delivery.META_RETRY_SECONDS] * 2

    def down(url):
        raise TimeoutError("read timed out")

    with pytest.raises(RuntimeError, match="TimeoutError.*after 3 attempts"):
        delivery.api_contract(manifest, CONFIG, down)


class FakeS3:
    def __init__(self):
        self.keys = []

    def put_object(self, **kwargs):
        self.keys.append(kwargs["Key"])
        return {"VersionId": "v" + str(len(self.keys))}


class FakeCloudFront:
    def create_invalidation(self, **_):
        return {"Invalidation": {"Id": "inv-1"}}

    def get_waiter(self, _name):
        return type("Waiter", (), {"wait": lambda self, **_: None})()


def live_fetch(manifest, api):
    def fetch(url):
        if url.endswith("/meta"):
            return 200, "application/json", json.dumps({"contractVersion": api}).encode()
        if url.endswith("deployment.json"):
            return 200, "application/json", json.dumps(manifest).encode()
        if "/__deployment_missing_" in url:
            return 404, "text/html", b"Missing"
        if url.endswith("/health"):
            return 200, "application/json", b'{"status": "ok"}'
        if url.endswith(".js"):
            return 200, "application/javascript", CONFIG["api_base"].encode()
        return 200, "text/html", b"Page"
    return fetch


@pytest.mark.parametrize(("api", "require_current", "outcome"), [
    ("1.5.0", False, "ok"), ("1.4.0", False, "older"), ("1.4.0", True, "blocked"), ("2.0.0", False, "blocked"),
])
def test_publish_checks_the_api_contract_before_uploading(tmp_path, monkeypatch, capsys, api, require_current, outcome):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    site = tmp_path / "site"
    site.mkdir()
    manifest = artifact(site)
    s3, made = FakeS3(), []

    def clients():
        made.append(True)
        return s3, FakeCloudFront()

    report_path = tmp_path / "report.json"

    def run():
        return delivery.publish(site, REVISION, {**CONFIG, "distribution_id": "D1"}, clients, require_current,
                                live_fetch(manifest, api), report_path)

    if outcome == "blocked":
        with pytest.raises(RuntimeError):
            run()
        assert made == [] and s3.keys == []                       # nothing was written
        assert json.loads(report_path.read_text())["status"] == "failed"
        return
    report = run()
    assert report["status"] == "passed" and report["api_contract"]["status"] == outcome
    assert s3.keys[-1] == "deployment.json"
    warned = "::warning title=API older than site::" in capsys.readouterr().out
    assert warned == (outcome == "older")


def test_upload_preserves_versions_and_publishes_dependencies_before_html(tmp_path):
    manifest = artifact(tmp_path)
    calls = []

    class S3:
        def put_object(self, **kwargs):
            calls.append(kwargs)
            return {"VersionId": "version-" + str(len(calls))}

    report = {"objects": []}
    delivery.upload(tmp_path, manifest, CONFIG, S3(), report)
    keys = [call["Key"] for call in calls]
    assert keys[0] == "_next/static/client.js"
    assert keys.index("index.txt") < keys.index("index.html")
    assert keys[-1] == "deployment.json"
    assert "immutable" in calls[0]["CacheControl"]
    assert calls[keys.index("index.html")]["ContentType"].startswith("text/html")
    assert all(item["version_id"] for item in report["objects"])


@pytest.mark.parametrize("broken", [None, "revision", "route", "asset", "404", "health"])
def test_smoke_requires_current_revision_routes_asset_integrity_and_api(tmp_path, broken):
    manifest = artifact(tmp_path)

    def fetch(url):
        if url.endswith("deployment.json"):
            marker = {**manifest, "revision": "old" if broken == "revision" else REVISION}
            return 200, "application/json", json.dumps(marker).encode()
        if "/__deployment_missing_" in url:
            return (200 if broken == "404" else 404), "text/html", b"Missing"
        if url.endswith("/health"):
            return 200, "application/json", json.dumps(
                {"status": "failed" if broken == "health" else "ok"}).encode()
        if url.endswith(".js"):
            return 200, "application/javascript", (
                b"old" if broken == "asset" else CONFIG["api_base"].encode())
        return (500 if broken == "route" else 200), "text/html", b"Page"

    if broken:
        with pytest.raises(RuntimeError):
            delivery.smoke(manifest, CONFIG, fetch)
    else:
        assert len(delivery.smoke(manifest, CONFIG, fetch)) == 2


def test_oidc_role_can_only_publish_the_existing_site_from_main():
    template = json.loads((ROOT / "infra/deploy/github-oidc.template.json").read_text())
    props = template["Resources"]["SitePublisher"]["Properties"]
    trust = props["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]
    assert trust["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert trust["token.actions.githubusercontent.com:sub"] == (
        "repo:Francklin9999@162392919/datathon-2026@1458135970:ref:refs/heads/main")
    grants = props["Policies"][0]["PolicyDocument"]["Statement"]
    assert {action for grant in grants for action in grant["Action"]} == {
        "s3:PutObject", "cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"}
    assert all(grant["Resource"] != "*" for grant in grants)
