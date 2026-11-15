import pytest
from aplomb.agents.guardrails import BedrockOutputPolicy
from aplomb.api.settings import Settings


@pytest.mark.parametrize("action,expected", [("NONE", "none"), ("GUARDRAIL_INTERVENED", "blocked")])
def test_frozen_output_guardrail_actual_response(action, expected):
    calls = []
    class Client:
        def apply_guardrail(self, **kwargs):
            calls.append(kwargs)
            return {"action": action}
    policy = BedrockOutputPolicy(Settings(guardrail_id="example", guardrail_version="1"), Client())
    assert policy("Hypothetical risk").action == expected
    assert calls == [{"guardrailIdentifier": "example", "guardrailVersion": "1", "source": "OUTPUT",
                      "content": [{"text": {"text": "Hypothetical risk"}}]}]


def test_guardrail_does_not_convert_transport_failure_into_pass():
    class Client:
        def apply_guardrail(self, **kwargs):
            raise TimeoutError("unavailable")
    with pytest.raises(TimeoutError):
        BedrockOutputPolicy(Settings(guardrail_id="example", guardrail_version="1"), Client())("text")
