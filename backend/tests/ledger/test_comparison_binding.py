"""Code checks prose direction even when the required reviewer extracts a true wrong relation.

All model IDs in this file are explicitly scripted test doubles, not live-model evidence.
"""

import pytest
from aplomb.ledger import Relation, ReviewResult, audit_and_sign, sabotage_caught
from tests.ledger.test_ledger import draft, fact, ledger


@pytest.mark.parametrize(
    "template,relation",
    [
        ("{{fact:F-001}} is higher than {{fact:F-002}}.", Relation("S-attack", "F-001", "==", "F-001")),
        ("{{fact:F-001}} is more than {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
        ("{{fact:F-001}} is not lower than {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
        ("{{fact:F-001}} is higher than {{fact:F-002}}.", Relation("S-attack", "F-001", "<", literal_token="{{fact:F-002}}")),
        ("{{fact:F-001}} is equal to {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
        ("{{fact:F-001}} est plus élevée que {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
        ("{{fact:F-001}} est au-dessus de {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
    ],
)
def test_wrong_true_relation_cannot_authenticate_simple_false_prose(template, relation):
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    result = audit_and_sign(
        book, draft({"id": "S-attack", "template": template}), lang="en",
        model="scripted-writer", review=lambda s, v: ReviewResult("scripted-review", relations=[relation]),
    )
    assert sabotage_caught(result.audit, result.sections, {"S-attack"})
    assert any(c.code == "A03" and not c.ok and c.sentence_ids == ["S-attack"] for c in result.audit.checks)


@pytest.mark.parametrize(
    "template,relation",
    [
        ("{{fact:F-001}} is less than {{fact:F-002}}.", Relation("S-attack", "F-001", "<", "F-002")),
        ("{{fact:F-001}} is not higher than {{fact:F-002}}.", Relation("S-attack", "F-001", "<=", "F-002")),
        ("{{fact:F-001}} is lower than or equal to {{fact:F-002}}.", Relation("S-attack", "F-001", "<=", "F-002")),
        ("{{fact:F-001}} is lower than {{fact:F-002}}.", Relation("S-attack", "F-001", "<", literal_token="{{fact:F-002}}")),
        ("{{fact:F-001}} est au-dessous de {{fact:F-002}}.", Relation("S-attack", "F-002", ">", "F-001")),
    ],
)
def test_true_simple_prose_keeps_compatible_typed_relation(template, relation):
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    result = audit_and_sign(
        book, draft({"id": "S-attack", "template": template}), lang="en",
        model="scripted-writer", review=lambda s, v: ReviewResult("scripted-review", relations=[relation]),
    )
    assert result.audit.status == "passed"
