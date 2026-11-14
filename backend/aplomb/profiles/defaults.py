"""The three default personas (profiles SPEC §3) and their rule sets (§3.4, controls §7).

``defaults.json`` is generated from this module (``python -m aplomb.profiles.defaults``) and
checked for drift by tests. Portfolios, capital and thresholds are fictional team assumptions
(A-13, A-02..A-12); persona text follows the organizer brief (pages 5–7).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aplomb.contracts.models import Profile

from .rulebuilder import RISK_EN, RISK_FR, make_rule, renumber

DEFAULTS_PATH = Path(__file__).with_name("defaults.json")
CREATED_AT = "2026-11-14T00:00:00Z"
DATA_VERSION = "snap-20261113-starter"
FULL = {"code": "full"}
# Reference statistics as printed in contracts/controls.md §5 (starter snapshot, CAD, full window).
SIGMA_STOCK_Q3 = 31.22
SIGMA_CRYPTO_MEDIAN = 59.97
REF_MIX = "50% XIU.TO + 50% SPY, rest XBB.TO"


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


def _deriv(method: str, formula: str, inputs: dict) -> dict:
    return {"methodId": method, "formula": formula, "inputs": inputs, "dataVersion": DATA_VERSION, "window": dict(FULL)}


def derived_core(risk: str, budget: float, horizon_mid: float, multiplier: float, position: float, sector: float,
                 growth: float | None, fi_floor: float | None) -> dict[str, tuple[float, dict, dict]]:
    """Threshold, derivation and rationale of each derived rule (A-02..A-08)."""
    r_en, r_fr = RISK_EN[risk], RISK_FR[risk]
    out = {
        "cap.position": (position, _deriv("M_DERIVE_POSITION_CAP", "clamp(round5(100 x 0.4 x budgetPct / sigmaStockQ3Pct), 5, 25)",
                                           {"budgetPct": budget, "sigmaStockQ3Pct": SIGMA_STOCK_Q3}),
                         _t(f"Sized from the {r_en} volatility budget relative to the upper-quartile volatility of single stocks (A-03).",
                            f"Établi à partir du budget de volatilité {r_fr} rapporté à la volatilité du quartile supérieur des actions (A-03).")),
        "cap.sector": (sector, _deriv("M_DERIVE_SECTOR_CAP", "min(40, 2 x positionCapPct)", {"positionCapPct": position}),
                       _t("At least two names per sector at the position cap (A-04).",
                          "Au moins deux titres par secteur au plafond par position (A-04).")),
        "limit.volatility": (budget, _deriv("M_DERIVE_VOL_BUDGET", "budget(riskLevel)", {"riskLevel": risk, "budgetPct": budget}),
                             _t(f"Volatility budget for a {r_en} risk level (A-02).", f"Budget de volatilité d'un niveau de risque {r_fr} (A-02).")),
        "limit.stress_2022": (budget * multiplier,
                              _deriv("M_DERIVE_STRESS_LIMIT", "budgetPct x m(horizonMidpointYears)",
                                     {"budgetPct": budget, "horizonMidpointYears": horizon_mid, "multiplier": multiplier}),
                              _t("A shorter horizon leaves less time to recover from a 2022-like year (A-07).",
                                 "Un horizon plus court laisse moins de temps pour se remettre d'une année comme 2022 (A-07).")),
        "limit.drawdown": (2.0 * budget, _deriv("M_DERIVE_DRAWDOWN_LIMIT", "2 x budgetPct", {"budgetPct": budget}),
                           _t("Largest tolerated fall set at twice the volatility budget (A-08).",
                              "Plus forte baisse tolérée fixée au double du budget de volatilité (A-08).")),
    }
    if growth is not None:
        out["cap.growth_assets"] = (growth, _deriv("M_DERIVE_GROWTH_CAP", "max equity share e in 0,5,..,100 with vol(refMix(e)) <= budgetPct",
                                                   {"budgetPct": budget, "referenceMix": REF_MIX}),
                                    _t("Largest equity share of a broad reference mix that stays within the volatility budget (A-06).",
                                       "Plus grande part d'actions d'un mélange de référence large qui respecte le budget de volatilité (A-06)."))
    if fi_floor is not None:
        out["floor.fixed_income"] = (fi_floor, _deriv("M_DERIVE_GROWTH_CAP", "max(0, 100 - growthCapPct - 10)", {"growthCapPct": growth}),
                                     _t("Bonds and cash complement the growth-assets cap (A-06).",
                                        "Obligations et encaisse complètent le plafond des actifs de croissance (A-06)."))
    return out


SYSTEM_RATIONALE = {
    "flag.attention": _t("Public attention is context, never a verdict on its own (A-19).",
                         "L'attention du public est un contexte, jamais un verdict à elle seule (A-19)."),
    "flag.rate_cycle": _t("The rate-hiking cycle is replayed for information only (A-23).",
                          "Le cycle de hausse des taux est rejoué à titre informatif seulement (A-23)."),
    "sim.only": _t("Aplomb is a simulation with fictional profiles; it never places orders.",
                   "Aplomb est une simulation avec des profils fictifs; il ne passe jamais d'ordres."),
}


def _rules(order: list[str], core: dict, prefs: dict[str, tuple[float | None, dict, str]]) -> list[dict]:
    rules = []
    for rule_id in order:
        if rule_id in core:
            threshold, derivation, rationale = core[rule_id]
            rules.append(make_rule(rule_id, "R1", threshold=threshold, origin="derived", rationale=rationale,
                                   derivation=derivation, updated_at=CREATED_AT))
        elif rule_id in prefs:
            threshold, rationale, origin = prefs[rule_id]
            rules.append(make_rule(rule_id, "R1", threshold=threshold, origin=origin, rationale=rationale,
                                   derivation=None, updated_at=CREATED_AT))
        else:
            rules.append(make_rule(rule_id, "R1", threshold=None, origin="system", rationale=SYSTEM_RATIONALE[rule_id],
                                   derivation=None, updated_at=CREATED_AT))
    return renumber(rules)


def _portfolio(total: float, weights: list[tuple[str, float]]) -> dict:
    return {"isFictional": True, "totalValue": total, "currency": "CAD",
            "positions": [{"ticker": t, "weightPct": w} for t, w in weights], "updatedAt": CREATED_AT}


def _prefs(**kw) -> dict:
    base = {"themesOfInterest": [], "excludedSectors": [], "excludedAssetClasses": [], "esgFocus": False,
            "avoidControversies": False, "avoidSpeculative": False, "cryptoInterest": "open", "wantsDiversification": False,
            "notes": ""}
    base.update(kw)
    return base


def build_defaults() -> list[dict]:
    robert_core = derived_core("low_moderate", 9.0, 4.0, 1.0, 10.0, 20.0, 55.0, 35.0)
    robert = {
        "profileId": "robert", "isDefault": True, "origin": "brief", "name": "Robert", "initial": "R", "age": 59,
        "occupation": "Healthcare professional", "riskLevel": "low_moderate", "horizonYears": {"min": 3.0, "max": 5.0},
        "objective": "preserve",
        "objectiveText": _t("Preserve capital while keeping some growth potential.",
                            "Préserver le capital tout en conservant un certain potentiel de croissance."),
        "experience": "advanced", "reportingCurrency": "CAD",
        "preferences": _prefs(cryptoInterest="none", avoidSpeculative=True, wantsDiversification=True, excludedAssetClasses=["crypto"],
                              notes="Prefers established companies and business models he understands; values stability and quality; "
                                    "may be tempted by a highly publicized company even when riskier than he would normally prefer."),
        "blurb": _t("59, healthcare professional. Low-to-moderate risk over 3 to 5 years; values stability and quality, little interest in crypto.",
                    "59 ans, professionnel de la santé. Risque faible à modéré sur 3 à 5 ans; privilégie la stabilité et la qualité, peu d'intérêt pour la crypto."),
        "personaTest": _t("Aplomb must challenge a request that conflicts with the profile, explain the risks and avoid simply agreeing.",
                          "Aplomb doit contester une demande qui va à l'encontre du profil, expliquer les risques et éviter de simplement acquiescer."),
        "portfolio": _portfolio(600000.0, [("XBB.TO", 30.0), ("ZST.TO", 15.0), ("AGG", 5.0), ("XIU.TO", 15.0), ("SPY", 10.0), ("RY.TO", 5.0),
                                           ("FTS.TO", 5.0), ("ENB.TO", 4.0), ("JNJ", 4.0), ("PG", 4.0), ("GLD", 3.0)]),
        "rules": _rules(
            ["cap.position", "cap.sector", "cap.growth_assets", "floor.fixed_income", "limit.volatility", "limit.stress_2022",
             "limit.drawdown", "exclude.asset_class.crypto", "flag.attention", "flag.rate_cycle", "sim.only"],
            robert_core,
            {"exclude.asset_class.crypto": (None, _t("Robert has little interest in crypto assets (brief p.7; A-12, editable).",
                                                     "Robert a peu d'intérêt pour les cryptoactifs (énoncé p. 7; A-12, modifiable)."), "profile_preference")},
        ),
    }
    mateo_core = derived_core("moderate", 12.0, 10.0, 1.25, 15.0, 30.0, 80.0, 10.0)
    mateo = {
        "profileId": "mateo", "isDefault": True, "origin": "brief", "name": "Mateo", "initial": "M", "age": 41,
        "occupation": "Operations manager", "riskLevel": "moderate", "horizonYears": {"min": 8.0, "max": 12.0},
        "objective": "balanced",
        "objectiveText": _t("Balanced capital growth over the medium and long term.",
                            "Croissance équilibrée du capital à moyen et long terme."),
        "experience": "intermediate", "reportingCurrency": "CAD",
        "preferences": _prefs(esgFocus=True, avoidControversies=True, avoidSpeculative=True, cryptoInterest="low",
                              excludedSectors=["Energy"], wantsDiversification=True,
                              notes="High importance on ESG factors; avoids companies involved in significant environmental or social "
                                    "controversies; open to emerging technologies that fit his risk profile."),
        "blurb": _t("41, operations manager. Moderate risk over 8 to 12 years; ESG matters and he avoids companies with significant controversies.",
                    "41 ans, gestionnaire des opérations. Risque modéré sur 8 à 12 ans; les facteurs ESG comptent et il évite les sociétés aux controverses importantes."),
        "personaTest": _t("Aplomb must use more than return and risk: financial factors and personal preferences together.",
                          "Aplomb doit aller au-delà du rendement et du risque : facteurs financiers et préférences personnelles ensemble."),
        "portfolio": _portfolio(250000.0, [("ESGV", 28.0), ("XBB.TO", 25.0), ("AGG", 7.0), ("ZST.TO", 5.0), ("MSFT", 5.0), ("CNR.TO", 5.0),
                                           ("RY.TO", 5.0), ("FTS.TO", 4.0), ("ATD.TO", 4.0), ("JNJ", 4.0), ("PG", 4.0), ("GLD", 4.0)]),
        "rules": _rules(
            ["cap.position", "cap.sector", "cap.growth_assets", "floor.fixed_income", "limit.volatility", "limit.stress_2022",
             "limit.drawdown", "cap.asset_class.crypto", "exclude.sector.energy", "evidence.controversy", "flag.attention",
             "flag.rate_cycle", "sim.only"],
            mateo_core,
            {
                "cap.asset_class.crypto": (5.0, _t("Formula cap of 10% halved because Mateo has little interest in speculative assets (A-05).",
                                                   "Plafond calculé de 10 % réduit de moitié, car Mateo s'intéresse peu aux actifs spéculatifs (A-05)."), "derived"),
                "exclude.sector.energy": (None, _t("Our reading of his wish to avoid environmental controversies: no direct Energy holdings (A-11, editable).",
                                                   "Notre lecture de son souhait d'éviter les controverses environnementales : aucune action du secteur Énergie (A-11, modifiable)."), "profile_preference"),
                "evidence.controversy": (None, _t("He avoids companies with significant controversies (brief p.6); this needs outside evidence.",
                                                  "Il évite les sociétés aux controverses importantes (énoncé p. 6); cela exige des preuves externes."), "profile_preference"),
            },
        ),
    }
    for r in mateo["rules"]:
        if r["ruleId"] == "cap.asset_class.crypto":
            r["derivation"] = _deriv("M_DERIVE_CRYPTO_CAP", "floor5(clamp(round5(100 x 0.4 x budgetPct / sigmaCryptoMedianPct), 0, 25) / 2)",
                                     {"budgetPct": 12.0, "sigmaCryptoMedianPct": SIGMA_CRYPTO_MEDIAN, "halved": "true"})
    amira_core = derived_core("high", 22.0, 15.0, 1.5, 25.0, 40.0, None, None)
    amira = {
        "profileId": "amira", "isDefault": True, "origin": "brief", "name": "Amira", "initial": "A", "age": 26,
        "occupation": "Software engineer", "riskLevel": "high", "horizonYears": {"min": 15.0, "max": None},
        "objective": "growth",
        "objectiveText": _t("Grow her capital over the long term.", "Faire croître son capital à long terme."),
        "experience": "intermediate", "reportingCurrency": "CAD",
        "preferences": _prefs(themesOfInterest=["ai", "semiconductors", "software", "crypto"], cryptoInterest="open",
                              wantsDiversification=True,
                              notes="Very interested in AI and emerging technologies; open to high-growth companies and significant "
                                    "volatility; still wants some diversification and not only technology."),
        "blurb": _t("26, software engineer. High risk over 15 years or more; drawn to AI and crypto but wants some diversification.",
                    "26 ans, ingénieure logicielle. Risque élevé sur 15 ans ou plus; attirée par l'IA et la crypto, mais souhaite une certaine diversification."),
        "personaTest": _t("An aggressive profile that must not read high risk as anything goes, while respecting her wish for diversification.",
                          "Un profil audacieux qui ne doit pas confondre risque élevé et absence de limites, tout en respectant son souhait de diversification."),
        "portfolio": _portfolio(60000.0, [("NVDA", 8.0), ("MSFT", 8.0), ("GOOGL", 6.0), ("SHOP.TO", 5.0), ("AMZN", 5.0), ("QQQ", 12.0),
                                          ("SPY", 12.0), ("XIU.TO", 10.0), ("BTC-USD", 6.0), ("ETH-USD", 3.0), ("JPM", 4.0), ("CNR.TO", 4.0),
                                          ("ATD.TO", 4.0), ("JNJ", 3.0), ("XBB.TO", 5.0), ("GLD", 5.0)]),
        "rules": _rules(
            ["cap.position", "cap.sector", "cap.asset_class.crypto", "floor.diversifiers", "limit.volatility", "limit.stress_2022",
             "limit.drawdown", "flag.attention", "flag.rate_cycle", "sim.only"],
            amira_core,
            {
                "cap.asset_class.crypto": (15.0, _t("Crypto cap from her high volatility budget relative to median crypto volatility (A-05).",
                                                    "Plafond crypto tiré de son budget de volatilité élevé rapporté à la volatilité médiane des cryptos (A-05)."), "derived"),
                "floor.diversifiers": (8.0, _t("She still wants some diversification (brief p.5); the 8% level is our assumption (A-10).",
                                               "Elle souhaite tout de même une certaine diversification (énoncé p. 5); le niveau de 8 % est notre hypothèse (A-10)."), "profile_preference"),
            },
        ),
    }
    for r in amira["rules"]:
        if r["ruleId"] == "cap.asset_class.crypto":
            r["derivation"] = _deriv("M_DERIVE_CRYPTO_CAP", "clamp(round5(100 x 0.4 x budgetPct / sigmaCryptoMedianPct), 0, 25)",
                                     {"budgetPct": 22.0, "sigmaCryptoMedianPct": SIGMA_CRYPTO_MEDIAN, "halved": "false"})
    out = []
    for p in (robert, amira, mateo):  # GET /profiles order: Robert, Amira, Mateo
        p.update({"version": 1, "createdAt": CREATED_AT, "updatedAt": CREATED_AT})
        Profile.model_validate(p)
        out.append(p)
    return out


def render_json() -> str:
    return json.dumps(build_defaults(), indent=2, ensure_ascii=False) + "\n"


def load_defaults() -> list[Profile]:
    data = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    return [Profile.model_validate(p) for p in data]


if __name__ == "__main__":  # pragma: no cover
    DEFAULTS_PATH.write_text(render_json(), encoding="utf-8", newline="\n")
    print(f"wrote {DEFAULTS_PATH}", file=sys.stderr)
