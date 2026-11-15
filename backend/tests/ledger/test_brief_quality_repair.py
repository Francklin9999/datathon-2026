"""Optional quality rewrite preserves the same audit controls and a strict single retry."""
from aplomb.ledger import ReviewResult, audit_and_sign
from tests.ledger.test_ledger import draft, fact, ledger


def test_struck_optional_sentence_can_be_rewritten_with_full_reaudit():
    book = ledger()
    book.add_fact(fact(12))
    attempts = []
    reviews = []

    def review(sections, view):
        reviews.append(view.digest())
        return ReviewResult("scripted-quality-review")

    def rewrite(raw, report):
        attempts.append(report)
        return draft({"id": "S-repaired", "template": "The measured figure is {{fact:F-001}}."})

    result = audit_and_sign(book, draft({"id": "S-bad", "template": "A figure is 999 {{fact:F-001}}."}),
                            lang="en", model="scripted-writer", review=review, rewrite=rewrite, repair_struck=True)
    assert len(attempts) == 1 and len(reviews) == 2
    assert reviews[0] == reviews[1] == result.audit.ledger_hash
    assert result.audit.rewrites == 1 and result.audit.sentences_struck == 0
    assert result.audit.status == "passed"


def test_remaining_optional_strikes_are_disclosed_after_single_quality_retry():
    book = ledger()
    book.add_fact(fact(12))
    calls = []

    def rewrite(raw, report):
        calls.append(report)
        return draft({"id": "S-still-bad", "template": "Still 999 {{fact:F-001}}."})

    result = audit_and_sign(book, draft({"id": "S-bad", "template": "Bad 999 {{fact:F-001}}."}),
                            lang="en", model="scripted-writer", review=lambda s, v: ReviewResult("scripted-review"),
                            rewrite=rewrite, repair_struck=True)
    assert len(calls) == 1 and result.audit.rewrites == 1
    assert result.audit.status == "passed_with_strikes" and result.audit.sentences_struck == 1
    assert next(s for section in result.sections for s in section.sentences if s.id == "S-still-bad").audit.status == "struck"
