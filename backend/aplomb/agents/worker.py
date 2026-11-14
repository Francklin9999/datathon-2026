"""Lambda/local composition boundary, with no environment or AWS reads on import."""

from .workflow import AgentServices, execute_run

_factory = None


def configure(factory):
    """Application composition injects a lazy AgentServices factory once at startup."""
    global _factory
    _factory = factory


def make_handler(services: AgentServices):
    def worker(event, context=None):
        if set(event) != {"runId", "generation"}:
            raise ValueError("Worker event requires only runId and generation")
        if not isinstance(event["runId"], str) or type(event["generation"]) is not int:
            raise ValueError("Invalid worker identity")
        execute_run(event["runId"], event["generation"], services)
        return {"accepted": True}

    return worker


def handler(event, context=None):
    if _factory is None:
        raise RuntimeError("Worker AgentServices factory is not configured")
    return make_handler(_factory())(event, context)
