"""A08 on a brief that cites no evidence and quotes nothing passes by absence, and says so (QA T3).

The web shows such a check as "No external quotes to verify" from the brief itself
(web/src/lib/evidence.ts); this pins the API's own detail so /runs and /trace readers see the same.
"""

from aplomb.ledger import DocumentRef, Ledger, ReviewResult, audit_and_sign, parse_draft

NOW = "2026-11-14T20:00:00Z"
NOTHING = "No cited evidence or quotations to verify"
CHECKED = "Cited evidence verification and writer quotations checked"


def ledger():
    return Ledger("run-a08", "2026-11-13", clock=lambda: NOW)


def fact():
    return {
        "kind": "assumption",
        "metric": "vol.annualized",
        "label": {"en": "Risk", "fr": "Risque"},
        "value": 12.0,
        "unit": "pct",
        "currency": None,
        "subject": {"type": "portfolio", "id": "robert", "variant": "before"},
        "period": None,
        "window": {"code": "full"},
        "asOf": "2026-11-13",
        "availableAt": None,
        "method": {
            "id": "M_PROFILE_ASSUMPTION",
            "description": {"en": "User threshold", "fr": "Seuil choisi"},
            "params": {},
        },
        "inputs": [],
        "nObs": None,
        "sources": [],
        "limitations": ["LIM_THRESHOLDS_ASSUMED"],
        "createdBy": "user",
    }


def evidence():
    return {
        "type": "official_release",
        "tier": 1,
        "title": "Source title",
        "publisher": "Official",
        "url": "https://example.com/source",
        "publishedAt": "2026-11-12",
        "retrievedAt": NOW,
        "lang": "en",
        "quote": "Revenue was 12 percent.",
        "claim": {"en": "Revenue", "fr": "Revenu"},
        "subject": {"type": "asset", "id": "ABC"},
        "tool": "web.fetch",
        "documentRef": "doc-abc",
        "licence": "unknown",
    }


def draft(*extra):
    return {
        "sections": [
            {
                "id": "facts",
                "title": {"en": "Facts", "fr": "Faits"},
                "sentences": [{"id": "S-a", "template": "Observed value {{fact:F-001}}."}, *extra],
            },
            {
                "id": "assumptions",
                "title": {"en": "Assumptions", "fr": "Hypothèses"},
                "sentences": [{"id": "S-b", "template": "Threshold is assumed."}],
            },
            {
                "id": "limits",
                "title": {"en": "Limits", "fr": "Limites"},
                "sentences": [{"id": "S-c", "template": "Simulation remains limited."}],
            },
        ]
    }


def a08(checks):
    found = [c for c in checks if (c["code"] if isinstance(c, dict) else c.code) == "A08"]
    assert len(found) == 1
    return found[0]


def test_a08_without_evidence_or_quotes_passes_by_absence_with_no_sentences():
    book = ledger()
    book.add_fact(fact())
    _, checks = parse_draft(draft(), book.export(), "en")
    assert a08(checks) == {"code": "A08", "ok": True, "kind": "code", "detail": NOTHING, "sentenceIds": []}
    signed = audit_and_sign(book, draft(), lang="en", model="writer",
                            review=lambda sections, view: ReviewResult("review-model"))
    check = a08(signed.audit.checks)
    assert check.ok and check.detail == NOTHING and check.sentence_ids == []
    assert signed.audit.status == "passed"


def test_a08_with_cited_verified_evidence_keeps_the_checked_detail():
    book = ledger()
    book.add_fact(fact())
    book.add_evidence(evidence(), DocumentRef("doc-abc", "Revenue was 12 percent.",
                                              "https://example.com/source", book.run_id))
    cited = {"id": "S-e", "template": "Revenue was reported {{evidence:E-001}}."}
    _, checks = parse_draft(draft(cited), book.export(), "en")
    check = a08(checks)
    assert check["ok"] and check["detail"] == CHECKED
    assert check["sentenceIds"] == ["S-a", "S-b", "S-c", "S-e"]


def test_a08_prose_quote_without_evidence_still_fails():
    book = ledger()
    book.add_fact(fact())
    quoted = {"id": "S-q", "template": "Management said “growth is strong”."}
    _, checks = parse_draft(draft(quoted), book.export(), "en")
    check = a08(checks)
    assert not check["ok"] and check["sentenceIds"] == ["S-q"]
