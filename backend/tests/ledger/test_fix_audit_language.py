"""Audit lexicon regressions: French prose survives, hostile prose is still struck (EN and FR)."""

import pytest
from aplomb.contracts.models import RuleCheck
from aplomb.ledger import (
    AuditFailure,
    Ledger,
    Relation,
    ReviewResult,
    audit_and_sign,
    has_literal,
    parse_draft,
    render_text,
)
from aplomb.ledger.audit import BANNED, COMPARISON, normalized

NOW = "2026-11-14T20:00:00Z"
PERIOD = {"start": "2021-11-12", "end": "2026-11-12"}


def ledger():
    return Ledger("run-language", "2026-11-13", clock=lambda: NOW)


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
        "window": None,
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
        "limitations": [],
        "createdBy": "user",
        **extra,
    }


def rule(status, rule_id="cap.position", code="R1"):
    return RuleCheck.model_validate(
        {
            "ruleId": rule_id,
            "code": code,
            "status": status,
            "value": 12,
            "threshold": 10,
            "unit": "pct",
            "comparator": "<=",
            "headroom": -2,
            "worst": None,
            "valueFactId": "F-001",
            "thresholdFactId": None,
            "detail": {"en": "Detail", "fr": "Détail"},
            "neeReason": None,
            "evidenceIds": [],
        }
    )


def draft(facts, assumptions=("Le seuil est supposé.",), limits=("La simulation reste limitée.",)):
    def section(name, prefix, templates):
        sentences = [{"id": f"{prefix}{i}", "template": t} for i, t in enumerate(templates, 1)]
        return {"id": name, "title": {"en": "-", "fr": "-"}, "sentences": sentences}

    return {
        "sections": [
            section("facts", "S-F", facts),
            section("assumptions", "S-A", assumptions),
            section("limits", "S-L", limits),
        ]
    }


def sign(book, d, *, lang="en", relations=(), **kw):
    return audit_and_sign(
        book,
        d,
        lang=lang,
        model="actual-writer",
        review=lambda sections, view: ReviewResult("actual-review", relations=list(relations)),
        **kw,
    )


def outcome(brief):
    return {
        s.id: (s.audit.status, sorted(set(s.audit.failed_checks)))
        for sec in brief.sections
        for s in sec.sentences
    }


def has_comparison(text):
    return bool(COMPARISON.search(normalized(text)))


# Number words (A02) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Ceci est une simulation et non un conseil.",
        "Il s'agit d'un portefeuille prudent.",
        "Le portefeuille présente une volatilité de .",
        "La règle est en conflit selon un seuil supposé.",
        "Une fois le seuil atteint, la règle est en tension.",
        "This is a simulation and not advice.",
    ],
)
def test_articles_are_not_number_words(text):
    assert not has_literal(text)


@pytest.mark.parametrize(
    "text",
    [
        "deux",
        "vingt",
        "la moitié du portefeuille",
        "un quart",
        "un tiers du portefeuille",
        "une demie",
        "un pour cent",
        "un million",
        "un dixième",
        "une seule position",
        "un point de pourcentage",
        "dix-sept",
        "quatre-vingt",
        "La baisse est de 12",
        "environ 5 %",
        "one position",
        "twenty",
        "half of the portfolio",
    ],
)
def test_numeric_claims_in_prose_are_still_literals(text):
    assert has_literal(text)


# Comparison wording (A03 lexical backstop) --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "La plus forte baisse observée est de .",
        "Les plus grandes positions sont et .",
        "Sa plus forte baisse est de .",
        "De plus, la règle est respectée.",
        "Le portefeuille ne respecte plus la limite.",
        "Au moins une règle reste en tension.",
        "Cette limite ne s'applique pas non plus.",
        "Le portefeuille est également diversifié.",
    ],
)
def test_ordinary_french_adverbs_are_not_comparisons(text):
    assert not has_comparison(text)


@pytest.mark.parametrize(
    "text",
    [
        "La volatilité est plus élevée que le seuil.",
        " vaut moins que .",
        " vaut plus que .",
        "La position pèse plus de .",
        "La position représente plus d'un tiers.",
        "La volatilité est plus élevée après le changement.",
        "La volatilité est supérieure à .",
        "Le poids est inférieur à .",
        "La volatilité dépasse .",
        "Les pertes dépassent .",
        "La volatilité est au-dessus de la limite de .",
        "Le poids est égal à .",
        " is lower than .",
        "Volatility is above the limit of .",
        " is more than .",
        " exceeds .",
    ],
)
def test_genuine_comparisons_are_still_detected(text):
    assert has_comparison(text)


@pytest.mark.parametrize(
    "text,banned",
    [
        ("Le rapport est publié vendredi.", False),
        ("Vendez la position.", True),
        ("Il faut vendre.", True),
        ("Achetez ce titre.", True),
        ("Sell the position.", True),
        ("You should buy.", True),
    ],
)
def test_friday_is_not_an_instruction_to_sell(text, banned):
    assert bool(BANNED.search(text)) is banned


def test_french_brief_with_articles_and_superlative_passes_the_audit():
    book = ledger()
    book.add_fact(fact())
    flagged = rule("conflict")
    signed = sign(
        book,
        draft(
            facts=[
                "Le portefeuille présente une volatilité de {{fact:F-001}}.",
                "La plus forte baisse observée est de {{fact:F-001}}.",
            ],
            assumptions=["La règle {{rule:cap.position}} est {{status:cap.position}} selon un seuil supposé."],
            limits=["Ceci est une simulation fondée sur un échantillon historique."],
        ),
        lang="fr",
        rule_checks=(flagged,),
    )
    assert signed.audit.status == "passed" and signed.audit.sentences_struck == 0
    assert "La règle R1 est en conflit selon un seuil supposé." in render_text(signed.sections)


def test_french_conflict_run_no_longer_fails_on_the_article():
    """Before the fix the only sentence naming the rule was struck A02, so A12 failed the run."""
    book = ledger()
    book.add_fact(fact())
    d = draft(
        facts=["Une valeur calculée est {{fact:F-001}}."],
        assumptions=["La règle {{rule:cap.position}} est {{status:cap.position}} selon un seuil supposé."],
    )
    try:
        signed = sign(book, d, lang="fr", rule_checks=(rule("tension"),))
    except AuditFailure as failure:  # pragma: no cover - the regression itself
        pytest.fail(f"French brief failed the audit: {failure}")
    assert next(c for c in signed.audit.checks if c.code == "A12").ok


@pytest.mark.parametrize(
    "lang,template,code",
    [
        ("fr", "La volatilité atteint vingt pour cent {{fact:F-001}}.", "A02"),
        ("fr", "La moitié du portefeuille est exposée {{fact:F-001}}.", "A02"),
        ("fr", "La baisse est de 12 {{fact:F-001}}.", "A02"),
        ("fr", "Un tiers du portefeuille est exposé {{fact:F-001}}.", "A02"),
        ("fr", "Vendez la position {{fact:F-001}}.", "A07"),
        ("fr", "Le titre va augmenter {{fact:F-001}}.", "A07"),
        ("fr", "La valeur est {{fact:F-404}}.", "A01"),
        ("fr", "{{fact:F-001}} vaut moins que {{fact:F-002}}.", "A03"),
        ("fr", "{{fact:F-001}} est supérieure à {{fact:F-002}}.", "A03"),
        ("en", "Volatility reaches twenty percent {{fact:F-001}}.", "A02"),
        ("en", "The drop is 12 {{fact:F-001}}.", "A02"),
        ("en", "Sell the position {{fact:F-001}}.", "A07"),
        ("en", "The value is {{fact:F-404}}.", "A01"),
        ("en", "{{fact:F-001}} is lower than {{fact:F-002}}.", "A03"),
    ],
)
def test_hostile_sentences_are_still_struck(lang, template, code):
    book = ledger()
    book.add_fact(fact(12))
    book.add_fact(fact(20, variant="after"))
    signed = sign(book, draft(["Valeur {{fact:F-001}}.", template]), lang=lang)
    assert outcome(signed)["S-F1"] == ("verified", [])
    status, failed = outcome(signed)["S-F2"]
    # An unresolved reference also leaves a factual sentence without a citation (A04).
    assert status == "struck" and code in failed and set(failed) <= {code, "A04"}


# Relations between a figure and its threshold (A03) -----------------------------------------


def threshold_book():
    """A windowed, dated figure and the timeless threshold the rules engine compares it with."""
    book = ledger()
    book.add_fact(fact(16.96, period=PERIOD, window={"code": "full"}))
    book.add_fact(
        fact(9.0, variant="na", metric="threshold.rule", subject={"type": "rule", "id": "limit.volatility", "variant": "na"})
    )
    return book


@pytest.mark.parametrize(
    "lang,template",
    [
        ("en", "Annualized volatility would be {{fact:F-001}}, above the limit of {{fact:F-002}}."),
        ("fr", "La volatilité annualisée serait de {{fact:F-001}}, au-dessus de la limite de {{fact:F-002}}."),
        ("fr", "La volatilité {{fact:F-001}} est plus élevée que la limite {{fact:F-002}}."),
    ],
)
def test_true_metric_versus_threshold_relation_is_verified(lang, template):
    signed = sign(
        threshold_book(),
        draft(["Valeur {{fact:F-001}}.", template]),
        lang=lang,
        relations=[Relation("S-F2", "F-001", ">", "F-002")],
    )
    assert signed.audit.status == "passed"
    assert outcome(signed)["S-F2"] == ("verified", [])


@pytest.mark.parametrize(
    "lang,template",
    [
        ("en", "Annualized volatility would be {{fact:F-001}}, below the limit of {{fact:F-002}}."),
        ("fr", "La volatilité {{fact:F-001}} est inférieure à la limite {{fact:F-002}}."),
    ],
)
def test_false_metric_versus_threshold_relation_is_struck(lang, template):
    signed = sign(
        threshold_book(),
        draft(["Valeur {{fact:F-001}}.", template]),
        lang=lang,
        relations=[Relation("S-F2", "F-001", "<", "F-002")],
    )
    assert outcome(signed)["S-F2"] == ("struck", ["A03"])


def test_comparison_without_extracted_relation_is_still_struck():
    template = "Annualized volatility would be {{fact:F-001}}, above the limit of {{fact:F-002}}."
    signed = sign(threshold_book(), draft(["Valeur {{fact:F-001}}.", template]))
    assert outcome(signed)["S-F2"] == ("struck", ["A03"])


@pytest.mark.parametrize(
    "other",
    [
        dict(unit="usd"),
        dict(currency="USD"),
        dict(kind="computed", window={"code": "1y"}, period=PERIOD, inputs=["F-001"]),
        dict(kind="computed", window={"code": "full"}, period={"start": "2022-01-03", "end": "2022-12-30"}, inputs=["F-001"]),
    ],
)
def test_incompatible_operands_are_never_certified(other):
    book = ledger()
    book.add_fact(fact(16.96, period=PERIOD, window={"code": "full"}))
    book.add_fact(fact(9.0, variant="other", **other))
    template = "{{fact:F-001}} is higher than {{fact:F-002}}."
    signed = sign(
        book,
        draft(["Valeur {{fact:F-001}}.", template]),
        relations=[Relation("S-F2", "F-001", ">", "F-002")],
    )
    assert outcome(signed)["S-F2"] == ("struck", ["A03"])


# Loss, gain and impact wording (A14) --------------------------------------------------------


@pytest.mark.parametrize(
    "lang,template",
    [
        ("en", "The portfolio's replayed stress loss would be {{fact:F-001}}."),
        ("en", "The simulated losses stay at {{fact:F-001}}."),
        ("fr", "La perte lors d'une répétition de cette année serait de {{fact:F-001}}."),
        ("fr", "Le gain simulé du portefeuille serait de {{fact:F-001}}."),
    ],
)
def test_cited_loss_figure_is_not_an_impact_claim(lang, template):
    book = ledger()
    book.add_fact(fact())
    signed = sign(book, draft(["Valeur {{fact:F-001}}.", template]), lang=lang)
    assert signed.audit.status == "passed"
    assert outcome(signed)["S-F2"] == ("verified", [])


@pytest.mark.parametrize(
    "lang,template",
    [
        ("en", "This change will produce a gain."),
        ("en", "The impact on the holding is {{fact:F-001}}."),
        ("en", "The event impacted the holding {{fact:F-001}}."),
        ("fr", "Ce changement produira un bénéfice."),
        ("fr", "L'incidence sur le titre est de {{fact:F-001}}."),
        ("fr", "L'impact sur le titre est de {{fact:F-001}}."),
    ],
)
def test_unsupported_impact_is_still_struck_outside_event_briefs(lang, template):
    book = ledger()
    book.add_fact(fact())
    signed = sign(book, draft(["Valeur {{fact:F-001}}."], assumptions=["Le seuil est supposé.", template]), lang=lang)
    assert outcome(signed)["S-A2"] == ("struck", ["A14"])


def event_book():
    """An event brief ledger: the event fact says impact is not established; one measured move."""
    book = ledger()
    book.add_fact(fact(3, metric="count.sources", unit="count", limitations=["LIM_IMPACT_NOT_ESTABLISHED"]))
    book.add_fact(fact(25.0, variant="weight", metric="weight.position"))
    move = fact(-4.2, variant="move", metric="return.period")
    move["method"] = {**move["method"], "id": "M_PRICE_MOVE_AFTER_EVENT"}
    book.add_fact(move)
    return book


@pytest.mark.parametrize(
    "lang,template",
    [
        ("en", "The holding's loss after the event was {{fact:F-002}}."),
        ("fr", "La perte du titre après l'événement est de {{fact:F-002}}."),
        ("en", "The holding took a loss after the event."),
    ],
)
def test_event_effect_without_measured_move_is_struck(lang, template):
    signed = sign(event_book(), draft(["Sources {{fact:F-001}}.", template]), lang=lang)
    assert outcome(signed)["S-F2"][0] == "struck"
    assert "A14" in outcome(signed)["S-F2"][1]


def test_event_effect_needs_the_declared_measured_move():
    template = "The holding's loss after the event was {{fact:F-003}}."
    d = draft(["Sources {{fact:F-001}}.", template], limits=["Financial impact not established."])
    signed = sign(event_book(), d, measured_impact_fact_ids=("F-003",))
    assert outcome(signed)["S-F2"] == ("verified", [])
    assert outcome(signed)["S-L1"] == ("verified", [])
    undeclared = sign(event_book(), d)
    assert outcome(undeclared)["S-F2"] == ("struck", ["A14"])


# Status words -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,en,fr",
    [
        ("pass", "fits", "respectée"),
        ("tension", "in tension", "en tension"),
        ("conflict", "in conflict", "en conflit"),
        ("nee", "not enough evidence", "preuve insuffisante"),
        ("info", "information", "information"),
    ],
)
def test_status_segment_shows_a_localized_word(status, en, fr):
    d = draft(["Valeur."], assumptions=["{{rule:cap.position}} {{status:cap.position}}"])
    for lang, word in (("en", en), ("fr", fr)):
        sections, _ = parse_draft(d, ledger().export(), lang, (rule(status),))
        code, shown = [s for s in sections[1].sentences[0].segments if s.t != "text"]
        assert (code.t, code.display) == ("rule", "R1")
        assert (shown.t, shown.rule_id, shown.display) == ("status", "cap.position", word)
        assert not has_literal(word)


def test_identical_writer_templates_are_deduplicated_before_review():
    d = draft(["Observation.", "Observation.", "Different observation."])
    sections, _ = parse_draft(d, ledger().export(), "en")
    facts = next(s for s in sections if s.id == "facts")
    assert [s.id for s in facts.sentences] == ["S-F1", "S-F3"]
    assert all(next(s for s in sections if s.id == name).sentences for name in ("assumptions", "limits"))


# Instructed rule wording (QA 4.5a) ----------------------------------------------------------


@pytest.mark.parametrize(
    "lang,facts,assumption,limits,rendered",
    [
        ("en", "A computed figure is {{fact:F-001}}.", "{{rule:cap.position}}: {{status:cap.position}}.",
         "This is a simulation based on a historical sample.", "R1: in tension."),
        ("fr", "Une valeur calculée est {{fact:F-001}}.", "{{rule:cap.position}} : {{status:cap.position}}.",
         "Ceci est une simulation fondée sur un échantillon historique.", "R1 : en tension."),
    ],
)
def test_the_instructed_rule_status_pattern_passes_every_code_check(lang, facts, assumption, limits, rendered):
    """The writer is told to write '{{rule:ID}}: {{status:ID}}'; that shape satisfies A12 and no check strikes it."""
    book = ledger()
    book.add_fact(fact())
    signed = sign(book, draft([facts], assumptions=[assumption], limits=[limits]), lang=lang,
                  rule_checks=(rule("tension"),))
    assert signed.audit.status == "passed" and signed.audit.sentences_struck == 0
    assert all(check.ok for check in signed.audit.checks)
    assert not has_comparison(assumption)
    assert rendered in render_text(signed.sections)
