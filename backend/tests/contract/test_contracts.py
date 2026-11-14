"""Shared wire cases, fixture round trips, and source-document coverage."""

import json
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from aplomb.contracts import CONTRACT_VERSION
from aplomb.contracts.api import BatchCheckRequest, ProfilesResponse, WorldEventsResponse
from aplomb.contracts.catalog import ERROR_HTTP_STATUS, FEATURE_DEFAULTS, ErrorCode, FeatureFlag
from aplomb.contracts.models import Run
from aplomb.contracts.registry import adapter, export_schema
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "contracts/validation-cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_shared_validation_cases(case):
    validate = adapter(case["contract"])
    payload = json.dumps(case["payload"])
    if case["valid"]:
        validate.validate_json(payload)
    else:
        with pytest.raises(ValidationError):
            validate.validate_json(payload)


@pytest.mark.parametrize(
    "filename,model",
    [
        ("profiles.json", ProfilesResponse),
        ("run.decision.robert-tsla-25.json", Run),
        ("world.events.sample.json", WorldEventsResponse),
    ],
)
def test_fixture_round_trip(filename, model):
    text = (ROOT / "contracts/fixtures" / filename).read_text()
    assert model.model_validate_json(text).to_wire() == json.loads(text)


def test_backend_python_construction_and_wire_aliases():
    text = (ROOT / "contracts/fixtures/profiles.json").read_text()
    profile = ProfilesResponse.model_validate_json(text).items[0]
    assert profile.profile_id == "robert"
    assert profile.reporting_currency == "CAD"
    assert profile.to_wire()["rules"][0]["countsInVerdict"] is True
    assert "profile_id" not in profile.to_wire()


def test_malformed_nested_fixture_cannot_pass():
    run = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    for path, value in [
        (("steps", 0, "type"), "pretend"),
        (("facts", "F-001", "metric"), "invented.metric"),
        (("result", "decision", "counts", "conflict"), -1),
        (("result", "decision", "brief", "audit", "rewrites"), 2),
    ]:
        broken = deepcopy(run)
        target = broken
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValidationError):
            Run.model_validate_json(json.dumps(broken))


@pytest.mark.parametrize("status", ["queued", "running", "waiting_input", "failed", "cancelled"])
def test_non_succeeded_run_envelopes(status):
    run = json.loads((ROOT / "contracts/fixtures/run.decision.robert-tsla-25.json").read_text())
    run.update(status=status, result=None, steps=[], facts={}, evidence={})
    if status == "waiting_input":
        run["question"] = {
            "questionId": "q1",
            "text": {"en": "Size?", "fr": "Taille?"},
            "field": "move.sizePct",
            "options": None,
        }
    if status == "failed":
        run["error"] = {
            "code": "upstream_unavailable",
            "message": "Unavailable",
            "requestId": "req_1",
        }
    assert Run.model_validate_json(json.dumps(run)).to_wire() == run


def test_batch_limit_is_five():
    with pytest.raises(ValidationError):
        BatchCheckRequest.model_validate({"items": [{"profileId": "robert", "move": None}] * 6})


def test_catalog_tables_are_complete():
    assert set(ERROR_HTTP_STATUS) == set(ErrorCode)
    assert set(FEATURE_DEFAULTS) == set(FeatureFlag)
    assert not FEATURE_DEFAULTS[FeatureFlag.GUARDRAILS]
    assert not FEATURE_DEFAULTS[FeatureFlag.RESEARCH_OPEN_WEB]


def test_meta_example_requires_every_feature():
    text = (ROOT / "contracts/api.md").read_text()
    examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.S)]
    meta = next(obj for obj in examples if "contractVersion" in obj)
    adapter("Meta").validate_json(json.dumps(meta))
    del meta["features"]["guardrails"]
    with pytest.raises(ValidationError):
        adapter("Meta").validate_json(json.dumps(meta))


def test_every_documented_type_is_exported():
    text = (ROOT / "contracts/schemas.md").read_text()
    documented = set(re.findall(r"(?:type|interface) (\w+)", text))
    documented |= set(re.findall(r"^\| `(\w+)` \|", text.split("## 2. Primitives")[0], re.M))
    # DatasetId/RuleId and other catalog types are reached through model fields.
    schema = export_schema()
    assert documented <= schema["$defs"].keys()
    assert schema["x-contract-version"] == CONTRACT_VERSION


def test_generators_do_not_drift():
    subprocess.run([sys.executable, "scripts/export_contracts.py", "--check"], cwd=ROOT, check=True)
