"""Lambda/local composition boundary, with no environment or AWS reads on import."""

from .workflow import AgentServices, execute_run

_factory = None


def configure(factory):
    """Application composition injects a lazy AgentServices factory once at startup."""
    global _factory, _services
    _factory, _services = factory, None


def make_handler(services: AgentServices):
    def worker(event, context=None):
        if set(event) != {"runId", "generation"}:
            raise ValueError("Worker event requires only runId and generation")
        if not isinstance(event["runId"], str) or type(event["generation"]) is not int:
            raise ValueError("Invalid worker identity")
        execute_run(event["runId"], event["generation"], services)
        return {"accepted": True}

    return worker


_services = None


def handler(event, context=None):
    """Lambda entry point. Uses the configured factory, else the default application composition
    (built lazily on the first invocation, from the process environment)."""
    global _services
    if _services is None:
        if _factory is not None:
            _services = _factory()
        else:
            from aplomb.api.runtime import default_agent_services

            _services = default_agent_services()
    return make_handler(_services)(event, context)
