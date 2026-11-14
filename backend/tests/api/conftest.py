import copy
import json
from pathlib import Path

import pytest
from aplomb.api.repositories import timestamp
from aplomb.api.services import new_run_id
from aplomb.contracts.models import Run

SID = "s_00000000-0000-4000-8000-000000000001"
OTHER_SID = "s_00000000-0000-4000-8000-000000000002"
FIXTURES = Path(__file__).parents[3] / "contracts" / "fixtures"


@pytest.fixture
def clock():
    class Clock:
        value = 1_800_000_000.0

        def __call__(self):
            return self.value

        def advance(self, seconds):
            self.value += seconds

    return Clock()


@pytest.fixture
def fixture_payload():
    # Explicit test-only schema example, never an application provider.
    return json.loads((FIXTURES / "run.decision.robert-tsla-25.json").read_text())


@pytest.fixture
def queued_run(fixture_payload, clock):
    fixture_payload = copy.deepcopy(fixture_payload)
    fixture_payload.update(
        runId=new_run_id(clock()),
        status="queued",
        steps=[],
        facts={},
        evidence={},
        result=None,
        error=None,
        question=None,
        createdAt=timestamp(clock()),
        updatedAt=timestamp(clock()),
    )
    return Run.model_validate(fixture_payload)
