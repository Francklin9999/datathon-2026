"""Lambda/local composition boundary, with no environment or AWS reads on import."""

import json
import time

from .workflow import AgentServices, execute_run


def make_handler(services: AgentServices):
    def worker(event, context=None):
        if set(event) != {"runId", "generation"}:
            raise ValueError("Worker event requires only runId and generation")
        if not isinstance(event["runId"], str) or type(event["generation"]) is not int:
            raise ValueError("Invalid worker identity")
        executed = execute_run(event["runId"], event["generation"], services)
        if executed:
            run = services.repository._read(event["runId"]).run
            # EMF: low-cardinality dimensions; bearer sessions/prompts never enter logs.
            print(json.dumps({
                "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
                    "Namespace": "Aplomb/Workflows", "Dimensions": [["RunKind"]],
                    "Metrics": [{"Name": "Succeeded", "Unit": "Count"}, {"Name": "Failed", "Unit": "Count"},
                                {"Name": "DurationMs", "Unit": "Milliseconds"},
                                {"Name": "InputTokens", "Unit": "Count"}, {"Name": "OutputTokens", "Unit": "Count"}]}]},
                "RunKind": run.kind, "runId": run.run_id, "status": run.status,
                "workerVersion": getattr(context, "function_version", "local"),
                "runtimeSignature": services.runtime_signature,
                "Succeeded": int(run.status == "succeeded"), "Failed": int(run.status == "failed"),
                "DurationMs": run.usage.duration_ms, "InputTokens": run.usage.input_tokens,
                "OutputTokens": run.usage.output_tokens,
            }))
        return {"accepted": True}

    return worker


_services = None


def handler(event, context=None):
    """Lambda entry point. Builds the application composition lazily on the first invocation,
    from the process environment (``aplomb.api.runtime.default_agent_services``)."""
    global _services
    if _services is None:
        from aplomb.api.runtime import default_agent_services

        _services = default_agent_services()
    return make_handler(_services)(event, context)
