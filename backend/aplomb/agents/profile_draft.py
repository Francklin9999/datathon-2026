"""Deterministic grounding of a profile draft (agents SPEC "Profile draft").

The model proposes a ``Partial<Profile>``; code keeps a field only when the investor's own text
states it (or the client sent the same value as an already confirmed field). Everything else is
withheld and becomes a bilingual question that names the field, the proposed value and the reason.
Model output is never trusted on its own, and rules and holdings are never filled from text.
"""

from __future__ import annotations

import re

from aplomb.contracts import models as m
from aplomb.datastore.constants import CURRENCIES

# Never filled from text, whatever the model returns (rules/holdings are derived or entered).
NEVER_FROM_TEXT = frozenset({
    "rules", "portfolio", "profileId", "version", "origin", "isDefault", "archived", "initial",
    "objectiveText", "blurb", "personaTest", "quantityHistory", "accounts", "activeAccountId",
    "createdAt", "updatedAt",
})
# The investorContext keys grounded from text; any other key is withheld.
CONTEXT_FROM_TEXT = ("country", "riskCapacity")
REQUIRED = ("riskLevel", "horizonYears")
# Unresolved questions come first in this order, then the rest as found.
PRIORITY = (
    "investorContext.riskCapacity", "reportingCurrency", "horizonYears", "riskLevel", "objective",
    "investorContext.country",
)

_LABEL = {
    "name": ("name", "nom"),
    "occupation": ("occupation", "profession"),
    "age": ("age", "âge"),
    "riskLevel": ("risk tolerance", "tolérance au risque"),
    "horizonYears": ("investment horizon", "horizon de placement"),
    "objective": ("objective", "objectif"),
    "experience": ("experience", "expérience"),
    "reportingCurrency": ("reporting currency", "devise de présentation"),
    "preferences": ("preferences", "préférences"),
    "rules": ("policy rules", "règles du plan"),
    "portfolio": ("holdings", "positions"),
    "investorContext": ("investor context", "contexte de l’investisseur"),
    "investorContext.country": ("country", "pays"),
    "investorContext.riskCapacity": ("risk capacity", "capacité de risque"),
    "investorContext.objectives": ("goals", "objectifs"),
    "investorContext.horizons": ("horizons", "horizons"),
    "investorContext.requirements": ("requirements", "exigences"),
    "investorContext.targetAllocations": ("target allocations", "allocations cibles"),
    "investorContext.investorType": ("investor type", "type d’investisseur"),
    "investorContext.language": ("language", "langue"),
    "investorContext.liquidityNotes": ("liquidity notes", "notes sur la liquidité"),
    "investorContext.riskCapacityNotes": ("risk capacity notes", "notes sur la capacité de risque"),
    "investorContext.permittedAssetClasses": ("permitted asset classes", "catégories d’actifs permises"),
    "investorContext.customThemes": ("custom themes", "thèmes personnalisés"),
    "investorContext.rebalancing": ("rebalancing", "rééquilibrage"),
}
_RISK = {
    "low": ("low", "faible"),
    "low_moderate": ("low to moderate", "faible à modérée"),
    "moderate": ("moderate", "modérée"),
    "moderate_high": ("moderate to high", "modérée à élevée"),
    "high": ("high", "élevée"),
}
_OBJECTIVE = {
    "preserve": ("capital preservation", "préservation du capital"),
    "balanced": ("balanced", "équilibré"),
    "growth": ("growth", "croissance"),
}

# Risk levels as words. Compound levels are matched (and removed) before the single ones, so
# "low to moderate" is never read as "low" or "moderate".
_SEP = r"(?:[\s\-–/_]+(?:(?:to|à|a)[\s\-–/_]+)?)"  # "low to moderate", "low-to-moderate", "low/moderate"
_MOD = r"(?:moderate|mod[ée]r[ée]e?s?)"
_COMPOUND_LEVELS = (
    ("low_moderate", re.compile(rf"\b(?:low|faible){_SEP}{_MOD}\b")),
    ("moderate_high", re.compile(rf"\b{_MOD}{_SEP}(?:high|[ée]lev[ée]e?s?|haute?s?|forte?s?)\b")),
)
_SIMPLE_LEVELS = (
    ("low", re.compile(r"\b(?:low|faible)\b")),
    ("moderate", re.compile(rf"\b(?:{_MOD}|medium|moyen(?:ne)?s?)\b")),
    ("high", re.compile(r"\b(?:high|[ée]lev[ée]e?s?|haute?s?|forte?s?)\b")),
)
_TOLERANCE_CUE = re.compile(r"\b(?:risks?|risques?|tol[ée]rance|appetite|app[ée]tit)\b")
_CAPACITY_CUE = re.compile(r"\bcapacit(?:y|ies|[ée]s?)\b")
_CLAUSE_SPLIT = re.compile(r"[.;,!?\n]|\b(?:and|et|but|mais)\b")

_OBJECTIVE_WORDS = {
    "growth": re.compile(r"\b(?:growth|grow|croissance)\b"),
    "balanced": re.compile(r"\b(?:balanced|[ée]quilibr\w*)\b"),
    "preserve": re.compile(r"\b(?:preserv\w*|pr[ée]serv\w*|capital protection|protect\w* (?:my |the )?capital)\b"),
}
_CURRENCY_NAMES = {
    "JPY": r"\byens?\b",
    "EUR": r"\beuros?\b",
    "GBP": r"\bpounds?(?: sterling)?\b|\bsterling\b|\blivres? sterling\b",
    "CHF": r"\bswiss francs?\b|\bfrancs? suisses?\b",
    "CAD": r"\bcanadian dollars?\b|\bdollars? canadiens?\b",
    "USD": r"\b(?:us|u\.s\.|american) dollars?\b|\bdollars? (?:us|am[ée]ricains?)\b",
    "HKD": r"\bhong kong dollars?\b|\bdollars? de hong kong\b",
    "SGD": r"\bsingapore dollars?\b|\bdollars? de singapour\b",
    "AUD": r"\baustralian dollars?\b|\bdollars? australiens?\b",
}

# Number words up to fifty in steps a description would use ("over ten years", "dix ans").
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8,
    "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15,
    "seize": 16, "dix-sept": 17, "dix-huit": 18, "dix-neuf": 19, "vingt": 20, "vingt-cinq": 25,
    "trente": 30, "quarante": 40, "cinquante": 50,
}
_NUMBER_WORD = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True)) + r")\b"
)
_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"\s*-?\s*(?:years?|yrs?|ans?|ann[ée]es?)\b"
_BETWEEN = re.compile(rf"\b(?:between|entre)\s+{_NUM}\s*(?:and|et)\s*{_NUM}{_UNIT}")
_HORIZON = re.compile(rf"(?<![\d.,]){_NUM}\s*(?:(?:-|–|—|to|à|a)\s*{_NUM}\s*)?(\+)?{_UNIT}")


def _i18n(en: str, fr: str) -> m.I18nText:
    return m.I18nText(en=en, fr=fr)


def _label(field: str) -> tuple[str, str]:
    return _LABEL.get(field, (field, field))


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def _fmt(n: float) -> str:
    return f"{n:g}"


def risk_levels(clause: str) -> set[str]:
    """The risk levels a (casefolded) clause names, compound levels first."""
    found = set()
    for level, pattern in _COMPOUND_LEVELS:
        if pattern.search(clause):
            found.add(level)
            clause = pattern.sub(" ", clause)
    found.update(level for level, pattern in _SIMPLE_LEVELS if pattern.search(clause))
    return found


def _clauses(text: str) -> list[str]:
    return [c for c in _CLAUSE_SPLIT.split(text) if c.strip()]


def tolerance_stated(text: str, level: str) -> bool:
    """A clause names the level with a tolerance cue and no capacity cue."""
    return any(level in risk_levels(c) and _TOLERANCE_CUE.search(c) and not _CAPACITY_CUE.search(c)
               for c in _clauses(text))


def capacity_stated(text: str, level: str) -> bool:
    return any(level in risk_levels(c) and _CAPACITY_CUE.search(c) for c in _clauses(text))


def capacity_mentioned(text: str) -> bool:
    return bool(_CAPACITY_CUE.search(text))


def stated_horizons(text: str) -> list[tuple[float, float | None, bool]]:
    """(min, max, open-ended) for every horizon the text states in years; max None for a single number."""
    text = _NUMBER_WORD.sub(lambda match: str(_NUMBER_WORDS[match.group(1)]), text)
    found = [(_number(a), _number(b), False) for a, b in _BETWEEN.findall(text)]
    # "between 10 and 15 years" is one range, not also a single "15 years".
    for a, b, plus in _HORIZON.findall(_BETWEEN.sub(" ", text)):
        found.append((_number(a), _number(b) if b else None, bool(plus)))
    return found


def horizon_stated(text: str, value) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("min"), (int, float)):
        return False
    low, high = float(value["min"]), value.get("max")
    for a, b, plus in stated_horizons(text):
        if b is not None:  # a stated range must match both ends
            if high is not None and (a, b) == (low, float(high)):
                return True
        elif a == low and (high is None or (not plus and float(high) == low)):
            return True  # "15 years" -> {15, null} or {15, 15}; "15+ years" -> {15, null}
    return False


def objective_stated(text: str, value) -> bool:
    pattern = _OBJECTIVE_WORDS.get(value) if isinstance(value, str) else None
    return bool(pattern and pattern.search(text))


def currency_stated(text: str, value) -> bool:
    if value not in CURRENCIES:
        return False
    return bool(re.search(rf"\b{value.casefold()}\b", text) or re.search(_CURRENCY_NAMES[value], text))


def country_stated(original: str, value) -> bool:
    """The ISO 3166-1 alpha-2 code itself, upper case, as a word ("US" before "dollar" is a currency)."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{2}", value):
        return False
    return bool(re.search(rf"(?<![A-Za-z]){value}(?![A-Za-z])(?!\s*(?:dollars?|\$))", original))


def _value_text(field: str, value) -> tuple[str, str] | None:
    if field in {"riskLevel", "investorContext.riskCapacity"} and value in _RISK:
        return _RISK[value]
    if field == "objective" and value in _OBJECTIVE:
        return _OBJECTIVE[value]
    if field == "horizonYears" and isinstance(value, dict) and isinstance(value.get("min"), (int, float)):
        low, high = _fmt(value["min"]), value.get("max")
        if high is None:
            return f"{low}+ years", f"{low} ans et plus"
        if float(high) == float(value["min"]):
            return f"{low} years", f"{low} ans"
        return f"{low}–{_fmt(high)} years", f"{low} à {_fmt(high)} ans"
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int, float)):
        shown = str(value)[:80]
        return shown, shown
    return None


def not_in_text(field: str, value) -> m.MissingField:
    en_label, fr_label = _label(field)
    shown = _value_text(field, value)
    if shown is None:
        question = _i18n(
            f"The draft proposed a value for {en_label}, but your description does not state it. "
            "Confirm or correct it.",
            f"Le brouillon propose une valeur pour le champ « {fr_label} », mais votre description "
            "ne l’indique pas. Confirmez ou corrigez cette valeur.",
        )
    else:
        question = _i18n(
            f"The draft proposed {shown[0]} for {en_label}, but your description does not state it. "
            "Confirm or correct it.",
            f"Le brouillon propose « {shown[1]} » pour le champ « {fr_label} », mais votre description "
            "ne l’indique pas. Confirmez ou corrigez cette valeur.",
        )
    return m.MissingField(field=field, question=question)


def unsupported_currency(value) -> m.MissingField:
    shown = str(value)[:12]
    codes = ", ".join(sorted(CURRENCIES))
    return m.MissingField(field="reportingCurrency", question=_i18n(
        f"{shown} is not a supported reporting currency. Choose one of {codes}.",
        f"{shown} n’est pas une devise de présentation prise en charge. Choisissez parmi {codes}.",
    ))


def never_from_text(field: str) -> m.MissingField:
    en_label, fr_label = _label(field)
    return m.MissingField(field=field, question=_i18n(
        f"{en_label[:1].upper()}{en_label[1:]} is never filled from text. Enter it in the form.",
        f"Le champ « {fr_label} » n’est jamais rempli à partir du texte. Saisissez-le dans le formulaire.",
    ))


def missing(field: str) -> m.MissingField:
    if field == "riskLevel":
        question = _i18n("Your description does not state a risk tolerance. Choose one.",
                         "Votre description n’indique pas de tolérance au risque. Choisissez-en une.")
    elif field == "horizonYears":
        question = _i18n("Your description does not state an investment horizon in years. Enter it.",
                         "Votre description n’indique pas d’horizon de placement en années. Indiquez-le.")
    elif field == "investorContext.riskCapacity":
        question = _i18n(
            "Your description mentions risk capacity, but the draft could not map it to low, low to "
            "moderate, moderate, moderate to high or high. Choose one.",
            "Votre description mentionne la capacité de risque, mais le brouillon n’a pas pu la rattacher "
            "à faible, faible à modérée, modérée, modérée à élevée ou élevée. Choisissez-en une.",
        )
    else:
        en_label, fr_label = _label(field)
        question = _i18n(f"Your description does not state the {en_label}. Enter it in the form.",
                         f"Votre description ne précise pas le champ « {fr_label} ». "
                         "Renseignez-le dans le formulaire.")
    return m.MissingField(field=field, question=question)


def _bilingual(question: m.I18nText) -> bool:
    return bool(question.en.strip() and question.fr.strip() and question.en.strip() != question.fr.strip())


def _grounded(field: str, value, text: str, original: str) -> bool:
    if field in {"name", "occupation"}:
        return isinstance(value, str) and bool(value.strip()) and value.casefold() in text
    if field == "riskLevel":
        return isinstance(value, str) and tolerance_stated(text, value)
    if field == "horizonYears":
        return horizon_stated(text, value)
    if field == "objective":
        return objective_stated(text, value)
    if field == "reportingCurrency":
        return currency_stated(text, value)
    if field == "investorContext.country":
        return country_stated(original, value)
    if field == "investorContext.riskCapacity":
        return isinstance(value, str) and capacity_stated(text, value)
    return False


def audit_profile_draft(draft: m.ProfileDraftResult, text: str, confirmed: dict) -> m.ProfileDraftResult:
    """Keep the grounded fields of ``draft``; withhold the rest as bilingual questions."""
    original = text
    text = text.casefold()
    raw = draft.profile.to_wire()
    confirmed_context = confirmed.get("investorContext") or {}
    safe: dict = {}
    kept: set[str] = set()
    withheld: dict[str, m.MissingField] = {}

    def check(field, value, confirmed_value, has_confirmed):
        if has_confirmed and confirmed_value == value:
            return True
        if field == "reportingCurrency" and value not in CURRENCIES:
            withheld[field] = unsupported_currency(value)
            return False
        if _grounded(field, value, text, original):
            return True
        withheld[field] = not_in_text(field, value)
        return False

    for key, value in raw.items():
        if value is None:  # an explicit null proposes nothing
            continue
        if key in NEVER_FROM_TEXT:
            withheld[key] = never_from_text(key)
        elif key == "investorContext" and isinstance(value, dict):
            context = {}
            for sub, sub_value in value.items():
                field = f"investorContext.{sub}"
                if sub_value is None:
                    continue
                if sub not in CONTEXT_FROM_TEXT:
                    if sub in confirmed_context and confirmed_context[sub] == sub_value:
                        context[sub] = sub_value
                    else:
                        withheld[field] = never_from_text(field)
                elif check(field, sub_value, confirmed_context.get(sub), sub in confirmed_context):
                    context[sub] = sub_value
                    kept.add(field)
            if context:
                safe[key] = context
                kept.add(key)
        elif check(key, value, confirmed.get(key), key in confirmed):
            safe[key] = value
            kept.add(key)

    model_questions = {item.field: item for item in draft.unresolved}
    for field in (*REQUIRED, "investorContext.riskCapacity"):
        if field in kept or field in withheld or field in confirmed:
            continue
        if field == "investorContext.riskCapacity" and (
            "riskCapacity" in confirmed_context or not capacity_mentioned(text)
        ):
            continue
        asked = model_questions.get(field)
        withheld[field] = asked if asked is not None and _bilingual(asked.question) else missing(field)
    for field, item in model_questions.items():
        if field in kept or field in withheld or field in confirmed:
            continue
        withheld[field] = item if _bilingual(item.question) else missing(field)

    order = {field: i for i, field in enumerate(PRIORITY)}
    unresolved = sorted(withheld.values(), key=lambda item: order.get(item.field, len(PRIORITY)))
    return m.ProfileDraftResult(
        profile=m.PartialProfile.model_validate(safe),
        explanations=[item for item in draft.explanations if item.field in kept],
        unresolved=unresolved,
    )
