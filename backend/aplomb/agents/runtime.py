"""Identity of the frozen inputs that cross the API/worker boundary (never clients).

The application composition itself lives in ``aplomb.api.runtime`` (``build_run_services``,
``build_agent_services``, ``default_agent_services``); these digests are what it pins into a
prepared run and what the worker and the brief cache compare against.
"""

import hashlib
import json


def manifest_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot.manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _runtime_context(settings) -> dict:
    """What can change how a run is written: models (and the configured fallback), Guardrail,
    feature flags, limits and the data prefix. The build revision is not part of it."""
    context = {"runtime": "2026-11-14.2", "strongModel": settings.model_strong, "fastModel": settings.model_fast,
               "guardrail": [settings.guardrail_id, settings.guardrail_version], "features": settings.features,
               "limits": [settings.run_hard_seconds, settings.max_llm_calls, settings.max_research_calls, settings.max_revise],
               "dataPrefix": settings.data_prefix}
    from .models import configured_fallback

    fallback = configured_fallback((settings.model_strong or "", settings.model_fast or ""))
    if fallback:
        # A configured fallback can change which model wrote a cached brief.
        context["fallbackModel"] = fallback
    return context


def _digest(context: dict) -> str:
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def runtime_signature(settings):
    """Pinned into every run; the worker refuses a run prepared under another signature. In AWS it
    includes the build revision, so a worker of another release never resumes the run."""
    context = _runtime_context(settings)
    if settings.build_revision:
        context["buildRevision"] = settings.build_revision
    return _digest(context)


def brief_runtime_identity(settings):
    """Brief-cache identity: the runtime signature without the build revision. A code-only redeploy
    keeps serving the briefs already written; a model, fallback, Guardrail, flag, limit or data-prefix
    change makes them stale."""
    return _digest(_runtime_context(settings))
