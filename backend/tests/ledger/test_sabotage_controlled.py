"""Controlled audit checks: deterministic test templates, scripted review, no model invocation."""

import pytest
from aplomb.contracts.models import ReviewFinding
from aplomb.ledger import DocumentRef, Relation, ReviewResult, audit_and_sign, sabotage_caught
from tests.ledger.test_ledger import draft, evidence, fact, ledger


@pytest.mark.parametrize("kind,expected", [("number", "A02"), ("comparison", "A03"), ("interpretation", "A09")])
def test_controlled_attacks_are_struck(kind, expected):
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    book.add_evidence(evidence(), DocumentRef("doc-abc", "Revenue was 12 percent.",
                                              "https://example.com/source", book.run_id))
    attempts = {
        "number": "Observed value is 999 {{fact:F-001}}.",
        "comparison": "{{fact:F-001}} is higher than {{fact:F-002}}.",
        "interpretation": "The source proves all future returns are safe {{evidence:E-001}}.",
    }
    injected = {"id": "S-attack", "template": attempts[kind]}

    def scripted_review(sections, view):
        if kind == "comparison":
            return ReviewResult("scripted-test-review", relations=[Relation("S-attack", "F-001", ">", "F-002")])
        if kind == "interpretation":
            finding = ReviewFinding(sentence_id="S-attack", code="A09", issue="Unsupported source interpretation")
            return ReviewResult("scripted-test-review", findings=[finding])
        return ReviewResult("scripted-test-review")

    result = audit_and_sign(book, draft(injected), lang="en", model="scripted-test-writer",
                            review=scripted_review)
    assert sabotage_caught(result.audit, result.sections, {"S-attack"})
    assert any(not check.ok and check.code == expected and "S-attack" in check.sentence_ids
               for check in result.audit.checks)
    assert next(s for sec in result.sections for s in sec.sentences if s.id == "S-attack").audit.status == "struck"


def test_true_extracted_relation_cannot_hide_reversed_plain_statement():
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    attempted = draft({"id": "S-attack", "template": "{{fact:F-001}} is higher than {{fact:F-002}}."})
    # The review mistakenly extracts a true lower-than relation, opposite to the prose.
    result = audit_and_sign(book, attempted, lang="en", model="scripted-test-writer",
                            review=lambda s, v: ReviewResult("scripted-test-review", relations=[
                                Relation("S-attack", "F-001", "<", "F-002")]))
    assert sabotage_caught(result.audit, result.sections, {"S-attack"})
    assert any(c.code == "A03" and not c.ok for c in result.audit.checks)


def test_swapping_extracted_operands_cannot_hide_false_plain_statement():
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    attempted = draft({"id": "S-attack", "template": "{{fact:F-001}} is higher than {{fact:F-002}}."})
    result = audit_and_sign(book, attempted, lang="en", model="scripted-test-writer",
                            review=lambda s, v: ReviewResult("scripted-test-review", relations=[
                                Relation("S-attack", "F-002", ">", "F-001")]))
    assert sabotage_caught(result.audit, result.sections, {"S-attack"})
