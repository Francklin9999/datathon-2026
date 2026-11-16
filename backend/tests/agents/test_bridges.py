"""Synthetic provider boundary tests; no external evidence is asserted here."""
from types import SimpleNamespace

import pytest
from aplomb.agents.bridges import CandidateFinding, candidate_findings


def test_candidates_require_verified_run_owned_facts():
    verified = SimpleNamespace(verification=SimpleNamespace(status="verified"))
    ledger = SimpleNamespace(export=lambda: SimpleNamespace(facts={"F-002": verified}))
    finding = CandidateFinding("risk", 75, ("F-002",))
    assert candidate_findings(lambda *_: [finding], None, None, ledger) == [finding]
    with pytest.raises(ValueError, match="foreign"):
        candidate_findings(lambda *_: [CandidateFinding("risk", 75, ("F-001",))], None, None, ledger)
