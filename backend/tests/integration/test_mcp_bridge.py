"""The live probe charges actual attempts and rejects stale/mismatched replies."""

import importlib.util
import json
import threading
import time
from pathlib import Path

import pytest
from aplomb.agents.limits import Limits
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "live_agents_smoke", ROOT / "scripts/live_agents_smoke.py"
)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class Output(BaseModel):
    value: int


def responder(directory, bodies, *, wrong_model=False):
    for sequence, body in enumerate(bodies, 1):
        request = directory / f"request-{sequence:03d}.json"
        until = time.monotonic() + 3
        while not request.exists() and time.monotonic() < until:
            time.sleep(0.01)
        if not request.exists():
            return
        pending = json.loads(request.read_text())
        bridge.write_json(
            directory / f"response-{sequence:03d}.json",
            {
                "sequence": sequence,
                "modelId": "stale-model" if wrong_model else pending["params"]["modelId"],
                "response": {
                    "stopReason": "end_turn",
                    "usage": {"inputTokens": 10, "outputTokens": 5},
                    "output": {"message": {"content": [{"text": json.dumps(body)}]}},
                },
            },
        )


def test_schema_repair_uses_new_response_and_aggregates_real_attempt_usage(tmp_path):
    directory = tmp_path / "bridge"
    gateway = bridge.McpFileGateway(directory, "strong", "fast")
    thread = threading.Thread(target=responder, args=(directory, [{"value": None}, {"value": 2}]))
    thread.start()
    limits = Limits(hard_seconds=5)
    reply = gateway.generate("profile_draft", Output, [{"text": "Test"}], [], limits)
    thread.join()
    assert reply.output.value == 2
    assert reply.calls == limits.llm_calls == 2
    assert (reply.input_tokens, reply.output_tokens) == (20, 10)


def test_response_from_another_model_cannot_complete_current_request(tmp_path):
    directory = tmp_path / "bridge"
    gateway = bridge.McpFileGateway(directory, "strong", "fast")
    thread = threading.Thread(
        target=responder, args=(directory, [{"value": 2}]), kwargs={"wrong_model": True}
    )
    thread.start()
    with pytest.raises(ValueError, match="does not match"):
        gateway.generate("profile_draft", Output, [], [], Limits(hard_seconds=5))
    thread.join()
