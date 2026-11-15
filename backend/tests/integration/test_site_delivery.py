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
    return delivery.prepare(tmp_path, REVISION, CONFIG)


def test_tampered_export_or_revision_cannot_be_published(tmp_path):
    artifact(tmp_path)
    assert delivery.validate(tmp_path, REVISION, CONFIG)
    with pytest.raises(ValueError, match="integrity"):
        delivery.validate(tmp_path, "b" * 40, CONFIG)
    (tmp_path / "_next/static/client.js").write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        delivery.validate(tmp_path, REVISION, CONFIG)


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
        "repo:Francklin9999/datathon-2026:ref:refs/heads/main")
    grants = props["Policies"][0]["PolicyDocument"]["Statement"]
    assert {action for grant in grants for action in grant["Action"]} == {
        "s3:PutObject", "cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"}
    assert all(grant["Resource"] != "*" for grant in grants)
