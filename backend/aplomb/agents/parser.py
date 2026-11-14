"""Simulation parsing preserves uncertainty and leaves confirmation to the form."""

from aplomb.contracts import models as m

from .limits import Limits


class RequestParser:
    def __init__(self, gateway, profiles=None):
        self.gateway, self.profiles = gateway, profiles

    def parse_request(self, profile, text, lang):
        reply = self.gateway.generate(
            "parser",
            m.ParsedRequest,
            [
                {
                    "text": text,
                    "lang": lang,
                    "profile": profile.to_wire() if profile else None,
                    "instruction": "Parse a hypothetical simulation only. Refuse trade execution or personalized "
                    "advice. Never infer size, funding, risk, or ticker from ambiguity. Unresolved fields must "
                    "appear in missing; request must be null when it cannot be confirmed. Preserve text meaning.",
                }
            ],
            [],
            Limits(),
        )
        parsed = m.ParsedRequest.model_validate(reply.output)
        if parsed.refused is not None or parsed.missing or parsed.confidence == "low":
            parsed = parsed.model_copy(update={"request": None})
        return parsed

    def parse(self, session_id, request):
        profile = self.profiles.get(session_id, request.profile_id) if self.profiles else None
        return self.parse_request(profile, request.text, request.lang)


def parse_request(profile, text, lang, *, gateway):
    return RequestParser(gateway).parse_request(profile, text, lang)
