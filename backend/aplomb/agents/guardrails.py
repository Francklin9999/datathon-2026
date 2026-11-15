"""Frozen Bedrock output policy. Any transport or intervention fails signing closed."""

from aplomb.ledger import GuardrailResult


class BedrockOutputPolicy:
    def __init__(self, settings, client=None):
        self.settings, self.client = settings, client

    def __call__(self, text):
        if self.client is None:
            import boto3
            from botocore.config import Config
            self.client = boto3.client("bedrock-runtime", region_name=self.settings.region,
                                       config=Config(connect_timeout=2, read_timeout=5,
                                                     retries={"total_max_attempts": 1}))
        response = self.client.apply_guardrail(
            guardrailIdentifier=self.settings.guardrail_id,
            guardrailVersion=self.settings.guardrail_version,
            source="OUTPUT", content=[{"text": {"text": text}}],
        )
        action = response.get("action")
        if action not in {"NONE", "GUARDRAIL_INTERVENED"}:
            raise ValueError("Invalid Bedrock Guardrail response")
        return GuardrailResult(self.settings.guardrail_id, "none" if action == "NONE" else "blocked")
