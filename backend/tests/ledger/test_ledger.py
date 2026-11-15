from types import SimpleNamespace

import pytest
from aplomb.contracts.models import ReviewFinding, RuleCheck
from aplomb.ledger import (
    AuditFailure,
    DocumentRef,
    GuardrailResult,
    Ledger,
    Relation,
    ReviewResult,
    audit_and_sign,
    fork_for_sabotage,
    has_literal,
    render_html,
    render_text,
    sabotage_caught,
)

NOW = "2026-11-14T20:00:00Z"


def ledger():
    return Ledger("run-parent", "2026-11-13", clock=lambda: NOW)


def fact(value=12.0, variant="before", **extra):
    return {
        "kind": "assumption",
        "metric": "vol.annualized",
        "label": {"en": "Risk", "fr": "Risque"},
        "value": value,
        "unit": "pct",
        "currency": None,
        "subject": {"type": "portfolio", "id": "robert", "variant": variant},
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
        **extra,
    }


def evidence(**extra):
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
        **extra,
    }


def draft(extra=None):
    sections = [
        {
            "id": "facts",
            "title": {"en": "Facts", "fr": "Faits"},
            "sentences": [{"id": "S-a", "template": "Observed value {{fact:F-001}}."}],
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
    if extra:
        sections[0]["sentences"].append(extra)
    return {"sections": sections}


def review(sections, view):
    return ReviewResult("actual-review-model")


def sign(book, d=None, **kw):
    return audit_and_sign(
        book, d or draft(), lang="en", model="actual-writer", review=kw.pop("review", review), **kw
    )


def test_led01_dag_ids_and_defensive_copy():
    book = ledger()
    with pytest.raises(ValueError, match="dependency"):
        book.add_fact(fact(inputs=["F-001"]))
    fid = book.add_fact(fact())
    assert book.add_fact(fact()) == fid
    with pytest.raises(ValueError, match="FactKey"):
        book.add_fact(fact(13))
    with pytest.raises(ValueError):
        book.add_fact(fact(variant="after", inputs=["other/F-001"]))
    book.get_fact(fid).value = 999
    book.export().facts[fid].value = 888
    assert book.get_fact(fid).value == 12
    # IDs expand and never wrap.
    for i in range(1, 1000):
        last = book.add_fact(fact(variant=f"v{i}"))
    assert last == "F-1000"


@pytest.mark.parametrize(
    "text",
    ["−1,2 %", "١٢", "４", "Ⅳ", "half", "quatre-vingt", "dix-sept", "moitié", "zéro", "billion"],
)
def test_led02_unicode_english_french_literals(text):
    assert has_literal(text)


def test_led02_trusted_numeric_dates_and_unknown_token():
    book = ledger()
    book.add_fact(fact("2026-11-13", unit="date"))
    signed = sign(book, draft({"id": "S-bad", "template": "Date ２０２６ {{fact:F-999}}."}))
    assert signed.audit.status == "passed_with_strikes"
    assert "2026-11-13" in render_text(signed.sections)
    assert "２０２６" not in render_text(signed.sections)


@pytest.mark.parametrize(
    "unit,op,ambiguous", [("pct", ">", False), ("usd", "<", False), ("pct", "<", True)]
)
def test_led03_false_incompatible_ambiguous_comparisons(unit, op, ambiguous):
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after", unit=unit))
    d = draft({"id": "S-lie", "template": "{{fact:F-001}} is lower than {{fact:F-002}}."})
    result = sign(
        book,
        d,
        review=lambda s, v: ReviewResult(
            "real-model", relations=[Relation("S-lie", "F-001", op, "F-002", ambiguous=ambiguous)]
        ),
    )
    assert result.sections[0].sentences[1].audit.status == "struck"
    assert any(c.code == "A03" and not c.ok for c in result.audit.checks)


def test_led03_true_comparison():
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    result = sign(
        book,
        draft({"id": "S-relation", "template": "{{fact:F-001}} is lower than {{fact:F-002}}."}),
        review=lambda s, v: ReviewResult(
            "real", relations=[Relation("S-relation", "F-001", "<", "F-002")]
        ),
    )
    assert result.audit.status == "passed"


def test_led04_quotes_document_ownership_and_figures():
    book = ledger()
    with pytest.raises(ValueError, match="Cross-run"):
        book.register_document(DocumentRef("doc", "content", "url", "other"))
    doc = DocumentRef(
        "doc-abc", "Revenue\nwas 12   percent.", "https://example.com/source", book.run_id
    )
    eid = book.add_evidence(evidence(), doc)
    assert book.get_evidence(eid).verification.status == "verified"
    bad = book.add_evidence(evidence(quote="Fabricated statement."))
    assert book.get_evidence(bad).verification.status == "failed"
    source = {
        "datasetId": "edgar_companyfacts",
        "dataVersion": "snap-20261113-starter",
        "sourceName": "Official",
        "sourceUrl": doc.source_url,
        "retrievedOn": "2026-11-14",
        "licence": "unknown",
        "rowsRead": 1,
    }
    # Pick a registered catalog dataset for the fixture.
    source["datasetId"] = "prices_daily"
    fid = book.add_quote_figure(
        fact(metric="quote.figure", sources=[source], availableAt="2026-11-12T00:00:00Z"),
        eid,
        value_text="12",
        unit_text="percent",
    )
    assert book.get_fact(fid).verification.status == "verified"
    with pytest.raises(ValueError, match="differs"):
        book.add_quote_figure(fact(99, sources=[source]), eid, value_text="12", unit_text="percent")


def test_led04_unsupported_quotes_struck():
    book = ledger()
    book.add_fact(fact())
    book.add_evidence(
        evidence(),
        DocumentRef(
            "doc-abc", "Revenue was 12 percent.", "https://example.com/source", book.run_id
        ),
    )
    result = sign(book, draft({"id": "S-quote", "template": "“Fabricated” {{evidence:E-001}}."}))
    assert result.sections[0].sentences[1].audit.status == "struck"


def test_led05_empty_mandatory_one_rewrite_and_ids():
    book = ledger()
    book.add_fact(fact())
    d = draft()
    d["sections"][0]["sentences"][0]["template"] = "999"
    calls = []

    def rewrite_once(d, report):
        calls.append(report)
        return d

    with pytest.raises(AuditFailure) as error:
        sign(book, d, rewrite=rewrite_once)
    assert len(calls) == 1
    assert error.value.report.rewrites == 1
    fixed = draft()
    fixed["sections"][0]["sentences"][0]["id"] = "S-fixed"
    assert sign(book, d, rewrite=lambda d, r: fixed).audit.rewrites == 1


@pytest.mark.parametrize(
    "available,historical,ok",
    [
        ("2026-11-13T23:59:59.999Z", True, True),
        ("2026-11-14T00:00:00Z", False, False),
        (None, True, False),
    ],
)
def test_led06_cutoff_unknown_and_next_day(available, historical, ok):
    book = ledger()
    book.add_fact(fact(kind="observed", availableAt=available))
    if ok:
        # Provenance-struck observed fact would empty facts. Test temporal check independently with a good fact.
        book.add_fact(fact(variant="after"))
        d = draft()
        d["sections"][0]["sentences"][0]["template"] = "{{fact:F-002}}"
        result = sign(book, d, historical=historical)
        assert next(c for c in result.audit.checks if c.code == "A11").ok
    else:
        with pytest.raises(AuditFailure) as error:
            sign(book, historical=historical)
        assert any(c.code == "A11" and not c.ok for c in error.value.report.checks)


def test_led06_max_availability_parsed_timestamp():
    book = ledger()
    a = book.add_fact(fact(availableAt="2026-11-13T10:00:00Z"))
    b = book.add_fact(fact(variant="after", availableAt="2026-11-13T10:00:00.900Z"))
    c = book.add_fact(fact(kind="computed", variant="derived", inputs=[a, b]))
    assert book.get_fact(c).available_at == "2026-11-13T10:00:00.900Z"


def test_led07_hash_unicode_finite_freeze():
    a, b = ledger(), ledger()
    a.add_fact(fact(label={"en": "Québec", "fr": "Québec"}))
    b.add_fact(dict(reversed(list(fact(label={"en": "Québec", "fr": "Québec"}).items()))))
    assert a.export().digest() == b.export().digest()
    assert b"Qu\xc3\xa9bec" in a.export().canonical_bytes()
    c = ledger()
    c.add_fact(fact(13))
    assert c.export().digest() != a.export().digest()
    with pytest.raises(ValueError):
        ledger().add_fact(fact(float("inf")))
    sign(a)
    with pytest.raises(ValueError, match="frozen"):
        a.add_fact(fact(variant="after"))


def test_led08_sabotage_honesty_parent_immutable():
    parent = ledger()
    parent.add_fact(fact())
    sign(parent)
    before = parent.export().digest()
    run = SimpleNamespace(
        status="succeeded",
        kind="decision",
        result=object(),
        run_id=parent.run_id,
        facts=parent.export().facts,
        evidence={},
    )
    child = fork_for_sabotage(run, parent, "run-child")
    result = sign(child, draft({"id": "S-injected", "template": "Guaranteed 999 {{fact:F-001}}."}))
    assert sabotage_caught(result.audit, result.sections, {"S-injected"})
    assert not sabotage_caught(result.audit, result.sections, set())
    assert parent.export().digest() == before
    run.status = "failed"
    with pytest.raises(ValueError):
        fork_for_sabotage(run, parent, "run-other")


def test_led09_every_numeric_segment_resolves_and_xss_escaped():
    book = ledger()
    book.add_fact(fact())
    result = sign(
        book, draft({"id": "S-xss", "template": "<script>alert(payload)</script> {{fact:F-001}}."})
    )
    assert "<script>" not in render_html(result.sections)
    assert "&lt;script&gt;" in render_html(result.sections)
    for sec in result.sections:
        for sentence in sec.sentences:
            for segment in sentence.segments:
                if segment.t == "fact":
                    assert segment.display == book.get_fact(segment.fact_id).display.en


def test_led10_assumptions_limitations_and_required_review():
    book = ledger()
    book.add_fact(fact())
    rc = RuleCheck.model_validate(
        {
            "ruleId": "limit.volatility",
            "code": "R1",
            "status": "conflict",
            "value": 12,
            "threshold": 10,
            "unit": "pct",
            "comparator": "<=",
            "headroom": -2,
            "worst": None,
            "valueFactId": "F-001",
            "thresholdFactId": None,
            "detail": {"en": "Conflict", "fr": "Conflit"},
            "neeReason": None,
            "evidenceIds": [],
        }
    )
    with pytest.raises(AuditFailure) as error:
        sign(book, rule_checks=(rc,))
    assert any(c.code == "A12" and not c.ok for c in error.value.report.checks)
    d = draft()
    d["sections"][1]["sentences"][0]["template"] = (
        "Assumed {{rule:limit.volatility}} {{status:limit.volatility}}."
    )
    result = sign(book, d, rule_checks=(rc,))
    assert "LIM_THRESHOLDS_ASSUMED" in render_text(result.sections)
    fresh = ledger()
    fresh.add_fact(fact())
    with pytest.raises(AuditFailure, match="review unavailable"):
        sign(fresh, review=None)


def test_actual_review_findings_guardrail_and_mutation_block():
    book = ledger()
    book.add_fact(fact())
    d = draft({"id": "S-causal", "template": "Growth follows from {{fact:F-001}}."})
    result = sign(
        book,
        d,
        review=lambda s, v: ReviewResult(
            "review-real",
            [ReviewFinding(sentence_id="S-causal", issue="Unsupported cause", code="A09")],
        ),
    )
    assert result.sections[0].sentences[1].audit.status == "struck"
    book = ledger()
    book.add_fact(fact())
    with pytest.raises(AuditFailure) as error:
        sign(book, guardrail=lambda text: GuardrailResult("guard-actual", "blocked"))
    assert error.value.report.guardrail.id == "guard-actual"
    assert "Observed value" not in render_text(error.value.sections)
    assert error.value.report.status == "failed"

    def mutate(s, v):
        book.add_fact(fact(variant="changed-during-review"))
        return ReviewResult("real-model")

    with pytest.raises(AuditFailure, match="mutated"):
        sign(book, review=mutate)


def test_whitespace_only_mandatory_and_checkpoint():
    book = ledger()
    book.add_fact(fact())
    d = draft()
    d["sections"][1]["sentences"][0]["template"] = "  \n "
    with pytest.raises(AuditFailure) as error:
        sign(book, d)
    assert any(c.code == "A05" and not c.ok for c in error.value.report.checks)
    state = book.checkpoint()
    restored = Ledger.restore(book.run_id, book.as_of, state, clock=lambda: NOW)
    assert restored.export().digest() == book.export().digest()
    assert restored.add_fact(fact(variant="after")) == "F-002"
    state["facts"]["F-001"]["value"] = 777
    with pytest.raises(ValueError, match="integrity"):
        Ledger.restore(book.run_id, book.as_of, state, clock=lambda: NOW)


def test_idempotent_registration_ignores_only_ledger_outputs():
    book = ledger()
    original = fact()
    fid = book.add_fact(original)
    repeated = {
        **original,
        "id": "F-999",
        "display": {"en": "Caller display", "fr": "Affichage"},
        "createdAt": "2026-11-14T23:59:59Z",
        "verification": {
            "status": "verified",
            "checks": [{"code": "fake", "ok": True, "detail": "not run"}],
        },
    }
    assert book.add_fact(repeated) == fid
    assert list(book.export().facts) == [fid]
    assert all(check.code != "fake" for check in book.get_fact(fid).verification.checks)
    variants = [
        {"value": 13.0},
        {"currency": "USD"},
        {"asOf": "2026-11-12"},
        {"method": {**original["method"], "params": {"different": True}}},
        {
            "sources": [
                {
                    "datasetId": "prices_daily",
                    "dataVersion": "snap-20261113-starter",
                    "sourceName": "Changed source",
                    "sourceUrl": "https://example.com",
                    "retrievedOn": "2026-11-13",
                    "licence": "unknown",
                    "rowsRead": 1,
                }
            ]
        },
        {"limitations": []},
        {"availableAt": "2026-11-13T01:00:00Z"},
        {"label": {"en": "Changed", "fr": "Modifié"}},
    ]
    for changed in variants:
        with pytest.raises(ValueError):
            book.add_fact({**original, **changed})
    dependency = book.add_fact(fact(variant="input"))
    with pytest.raises(ValueError, match="FactKey"):
        book.add_fact({**original, "inputs": [dependency]})
    computed = fact(kind="computed", variant="aggregate", inputs=[])
    computed_id = book.add_fact(computed)
    assert (
        book.add_fact({**computed, "verification": {"status": "verified", "checks": []}})
        == computed_id
    )
    assert book.get_fact(computed_id).verification.status == "unverified"


def test_sabotage_document_checkpoint_restores_under_child_identity():
    parent = ledger()
    parent.add_fact(fact())
    parent.add_evidence(evidence(), DocumentRef("doc-abc", "Revenue was 12 percent.",
                                                 "https://example.com/source", parent.run_id))
    sign(parent)
    run = SimpleNamespace(status="succeeded", kind="decision", result=object(), run_id=parent.run_id,
                          facts=parent.export().facts, evidence=parent.export().evidence)
    child = fork_for_sabotage(run, parent, "run-child")
    restored = Ledger.restore("run-child", child.as_of, child.checkpoint())
    assert restored.export().digest() == child.export().digest()
