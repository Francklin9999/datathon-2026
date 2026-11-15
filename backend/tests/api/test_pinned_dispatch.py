from types import SimpleNamespace

import pytest
from aplomb.api.dispatcher import LambdaDispatcher
from aplomb.api.errors import ServiceError

BASE = "arn:aws:lambda:us-east-1:010526248118:function:Aplomb-worker"


class Client:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return {"StatusCode": 202}


def test_resumed_run_uses_its_original_numeric_worker_version():
    client = Client()
    repository = SimpleNamespace(_read=lambda _: SimpleNamespace(private={"workerFunction": BASE + ":3"}))
    LambdaDispatcher(client, BASE + ":7", repository).dispatch("run-test", 2)
    assert client.calls[0]["FunctionName"] == BASE + ":3"
    assert client.calls[0]["InvocationType"] == "Event"


@pytest.mark.parametrize("target", [BASE, BASE + ":$LATEST", BASE + ":alias", BASE.replace("Aplomb", "Other") + ":3"])
def test_pinned_dispatch_cannot_escape_the_project_or_invoke_mutable_code(target):
    client = Client()
    repository = SimpleNamespace(_read=lambda _: SimpleNamespace(private={"workerFunction": target}))
    with pytest.raises(ServiceError):
        LambdaDispatcher(client, BASE + ":7", repository).dispatch("run-test", 1)
    assert client.calls == []
