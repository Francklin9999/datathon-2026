"""Test-only model gateway: deterministic typed replies built from the prompt it receives.

It stands in for Bedrock in offline integration tests so the real workflow, code controls,
ledger and auditor run end to end. It is never imported by the application; its model ID says
what it is. Number-free prose plus ``{{fact:...}}`` tokens, like a compliant writer would produce.
"""

from __future__ import annotations

from aplomb.agents.models import Generation

MODEL_ID = "scripted-test-gateway (no LLM)"


class ScriptedGateway:
    def __init__(self, plan: dict | None = None, parsed: dict | None = None, draft_profile: dict | None = None,
                 writer=None, fail_role: str | None = None) -> None:
        self.plan = plan or {"interpretation": "Test the confirmed hypothetical request against the plan."}
        self.parsed, self.draft_profile, self.writer = parsed, draft_profile, writer
        self.fail_role = fail_role
        self.roles: list[str] = []
        self.prompts: list[tuple[str, dict]] = []

    def generate(self, role, schema, messages, tools, limits):
        limits.take("llm_calls")
        self.roles.append(role)
        self.prompts.append((role, messages[0]))
        if role == self.fail_role:
            raise RuntimeError(f"scripted failure in role {role}")
        if role == "planner":
            output = self.plan
        elif role == "writer":
            output = (self.writer or default_draft)(messages[0])
        elif role == "auditor":
            output = {"findings": [], "relations": []}
        elif role == "parser":
            output = self.parsed
        elif role == "profile_draft":
            output = self.draft_profile
        else:
            raise ValueError(f"unexpected role {role}")
        return Generation(schema.model_validate(output), MODEL_ID, 11, 7, 1)


def default_draft(message: dict) -> dict:
    """A compliant brief: facts cite ledger IDs, assumptions name every conflicting/tension rule."""
    facts = message.get("facts", {})
    checks = message.get("checks", [])
    cited = [fid for fid, fact in facts.items() if isinstance(fact.get("value"), (int, float))
             and not isinstance(fact.get("value"), bool)][:3]
    fact_sentences = [{"id": f"S-F{i}", "template": f"A computed figure of this simulation is {{{{fact:{fid}}}}}."}
                      for i, fid in enumerate(cited, 1)]
    flagged = [c for c in checks if c["status"] in ("conflict", "tension")]
    assumptions = [{"id": f"S-A{i}", "template": f"{{{{rule:{c['ruleId']}}}}} is {{{{status:{c['ruleId']}}}}} under an assumed threshold."}
                   for i, c in enumerate(flagged, 1)]
    if not assumptions:
        assumptions = [{"id": "S-A0", "template": "The thresholds are assumptions derived from the stated profile."}]
    title = {"en": "-", "fr": "-"}
    return {"sections": [
        {"id": "facts", "title": title, "sentences": fact_sentences},
        {"id": "assumptions", "title": title, "sentences": assumptions},
        {"id": "limits", "title": title,
         "sentences": [{"id": "S-L1", "template": "This is a simulation and the figures describe a historical sample only."}]},
    ]}
