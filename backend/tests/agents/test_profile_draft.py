"""Deterministic grounding of profile drafts (QA t2: Apply kept only name and risk level)."""

import pytest
from aplomb.agents.profile_draft import (
    audit_profile_draft,
    capacity_stated,
    horizon_stated,
    risk_levels,
    tolerance_stated,
)
from aplomb.contracts import models as m

KENJI = ("Kenji Sato is a fictional investor living in JP who reports in JPY. Horizon: 10-15 years. "
         "Objective: growth. Risk tolerance: moderate. Risk capacity: low.")
BEST = {
    "name": "Kenji Sato", "riskLevel": "moderate", "horizonYears": {"min": 10, "max": 15},
    "objective": "growth", "reportingCurrency": "JPY",
    "investorContext": {"country": "JP", "riskCapacity": "low"},
}


def draft(profile, unresolved=(), explanations=()):
    return m.ProfileDraftResult.model_validate(
        {"profile": profile, "unresolved": list(unresolved), "explanations": list(explanations)})


def audit(text, profile, confirmed=None, **kw):
    return audit_profile_draft(draft(profile, **kw), text, confirmed or {})


def fields(result):
    return [item.field for item in result.unresolved]


def test_tester_text_keeps_every_stated_field():
    result = audit(KENJI, BEST)
    assert result.profile.to_wire() == BEST
    assert result.unresolved == []


def test_second_wording_keeps_every_stated_field():
    text = ("Kenji Sato, a fictional investor in JP reporting in yen, has a 10 to 15 year horizon, a growth "
            "objective, moderate risk tolerance and low risk capacity.")
    assert audit(text, BEST).profile.to_wire() == BEST


def test_capacity_word_is_not_a_tolerance():
    result = audit(KENJI, {**BEST, "riskLevel": "low"})
    assert "riskLevel" not in result.profile.to_wire()
    assert fields(result)[0] == "riskLevel"
    question = result.unresolved[0].question
    assert "low" in question.en and "faible" in question.fr and question.en != question.fr
    assert not tolerance_stated("risk capacity: low", "low")
    assert capacity_stated("risk capacity: low", "low")


def test_compound_levels_are_not_read_as_single_levels():
    assert risk_levels("low to moderate risk") == {"low_moderate"}
    assert risk_levels("risque modéré à élevé") == {"moderate_high"}
    assert risk_levels("moderate risk") == {"moderate"}
    assert not tolerance_stated("a low-to-moderate risk tolerance", "low")


def test_currency_not_in_text_is_withheld_with_a_bilingual_question():
    result = audit("A fictional teacher with moderate risk over 10 years.", {"reportingCurrency": "USD"})
    assert "reportingCurrency" not in result.profile.to_wire()
    item = next(i for i in result.unresolved if i.field == "reportingCurrency")
    assert "USD" in item.question.en and "USD" in item.question.fr and item.question.en != item.question.fr


def test_unsupported_currency_lists_the_catalog():
    result = audit("I report in BRL.", {"reportingCurrency": "BRL"})
    item = next(i for i in result.unresolved if i.field == "reportingCurrency")
    assert "not a supported reporting currency" in item.question.en
    assert "AUD, CAD, CHF, EUR, GBP, HKD, JPY, SGD, USD" in item.question.fr


@pytest.mark.parametrize("text,code", [
    ("reports in euros", "EUR"), ("en livres sterling", "GBP"), ("in Swiss francs", "CHF"),
    ("en dollars canadiens", "CAD"), ("reporting currency usd", "USD"), ("in yen", "JPY"),
])
def test_currency_names(text, code):
    assert audit(text, {"reportingCurrency": code}).profile.to_wire() == {"reportingCurrency": code}


def test_other_investor_context_keys_are_withheld_per_key():
    profile = {"investorContext": {"country": "JP", "riskCapacity": "low",
                                   "objectives": [{"name": "Retire", "horizonYears": 10, "priority": 1}]}}
    result = audit(KENJI, profile)
    assert result.profile.to_wire() == {"investorContext": {"country": "JP", "riskCapacity": "low"}}
    item = next(i for i in result.unresolved if i.field == "investorContext.objectives")
    assert "never filled from text" in item.question.en and item.question.en != item.question.fr


def test_country_needs_the_iso_code_in_the_text():
    result = audit("A fictional investor living in Japan.", {"investorContext": {"country": "JP"}})
    assert "investorContext" not in result.profile.to_wire()
    item = next(i for i in result.unresolved if i.field == "investorContext.country")
    assert "JP" in item.question.en and "JP" in item.question.fr
    # "US" in "US dollars" is a currency, not a country of residence.
    assert "investorContext" not in audit("I report in US dollars.", {"investorContext": {"country": "US"}}).profile.to_wire()


def test_unresolved_order_puts_capacity_currency_horizon_first():
    text = "A fictional investor. Risk capacity is something I have not decided."
    result = audit(text, {"reportingCurrency": "USD", "objective": "growth", "horizonYears": {"min": 5, "max": None}})
    assert fields(result)[:4] == ["investorContext.riskCapacity", "reportingCurrency", "horizonYears", "riskLevel"]
    for item in result.unresolved:
        assert item.question.en != item.question.fr, item.field


@pytest.mark.parametrize("text,value,ok", [
    ("10-15 years", {"min": 10, "max": 15}, True),
    ("10 to 15 years", {"min": 10, "max": 15}, True),
    ("10 à 15 ans", {"min": 10, "max": 15}, True),
    ("between 10 and 15 years", {"min": 10, "max": 15}, True),
    ("between 10 and 15 years", {"min": 15, "max": None}, False),
    ("15+ years", {"min": 15, "max": None}, True),
    ("15+ years", {"min": 15, "max": 15}, False),
    ("over ten years", {"min": 10, "max": None}, True),
    ("un horizon de dix ans", {"min": 10, "max": 10}, True),
    ("a 20-year horizon", {"min": 20, "max": None}, True),
    ("12 years", {"min": 10, "max": 15}, False),
    ("10-15 years", {"min": 15, "max": None}, False),
])
def test_horizon_variants(text, value, ok):
    assert horizon_stated(text, value) is ok


def test_confirmed_fields_are_kept_and_not_asked_again():
    confirmed = {"riskLevel": "moderate", "horizonYears": {"min": 5, "max": None}, "reportingCurrency": "CAD"}
    result = audit("I am a teacher.", {"occupation": "teacher", "reportingCurrency": "CAD"}, confirmed)
    assert result.profile.to_wire() == {"occupation": "teacher", "reportingCurrency": "CAD"}
    assert result.unresolved == [], "already confirmed required fields are not reported missing"


def test_missing_required_fields_use_bilingual_questions():
    result = audit("I am a teacher.", {"occupation": "teacher"},
                   unresolved=[{"field": "riskLevel", "question": {"en": "Confirm riskLevel", "fr": "Confirm riskLevel"}}])
    by_field = {i.field: i.question for i in result.unresolved}
    assert by_field["riskLevel"].fr == "Votre description n’indique pas de tolérance au risque. Choisissez-en une."
    assert by_field["horizonYears"].en == "Your description does not state an investment horizon in years. Enter it."


def test_explanations_follow_kept_fields_including_nested_keys():
    explanations = [{"field": "investorContext.country", "text": {"en": "JP stated", "fr": "JP indiqué"}},
                    {"field": "objective", "text": {"en": "x", "fr": "x"}}]
    result = audit("I live in JP.", {"investorContext": {"country": "JP"}, "objective": "growth"},
                   explanations=explanations)
    assert [e.field for e in result.explanations] == ["investorContext.country"]
