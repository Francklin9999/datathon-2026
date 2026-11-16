"""Static description of every rule family: type, metric, target, unit, bounds and labels
(rules SPEC §3.1, profiles SPEC §3.4). Shared by default profiles, threshold derivation and the
rule engine so a rule is described in exactly one place."""

from __future__ import annotations

from dataclasses import dataclass

from aplomb.quant.engine import slug


@dataclass(frozen=True)
class RuleDef:
    type: str                      # cap | floor | limit | exclude | evidence | flag | sim
    metric: str | None             # MetricCode measured by quant (None for evidence/sim)
    key: str | None                # key passed to PortfolioView.measure
    dimension: str                 # PolicyRule.target.dimension
    target_key: str | None
    comparator: str
    unit: str
    editable: bool
    bounds: dict | None
    counts: bool
    label: dict


def _t(en: str, fr: str) -> dict:
    return {"en": en, "fr": fr}


SECTOR_FR = {
    "Energy": "Énergie", "Materials": "Matériaux", "Industrials": "Industrie", "Consumer Discretionary": "Consommation discrétionnaire",
    "Consumer Staples": "Biens de consommation de base", "Health Care": "Santé", "Financials": "Services financiers",
    "Information Technology": "Technologies de l'information", "Communication Services": "Services de communication",
    "Utilities": "Services publics", "Real Estate": "Immobilier",
}

POSITION_BOUNDS = {"min": 2.0, "max": 50.0, "step": 1.0}
GROWTH_BOUNDS = {"min": 0.0, "max": 100.0, "step": 5.0}
FLOOR_BOUNDS = {"min": 0.0, "max": 100.0, "step": 1.0}

# French wording of the parameterized cap/floor families (rule_def): "Au plus 10 % dans le pays CAN ...".
_DIMENSION_FR = {
    "position": "dans la position", "sector": "dans le secteur", "asset_class": "dans la classe d'actifs",
    "country": "dans le pays", "currency": "dans la devise", "theme": "dans le thème",
}
_QUALIFIER_FR = {"country": " (approximation par le pays de cotation)", "currency": " (approximation par la devise de cotation)"}

FIXED: dict[str, RuleDef] = {
    "cap.position": RuleDef("cap", "weight.position.max_single", None, "position", None, "<=", "pct", True, POSITION_BOUNDS, True,
                            _t("No single stock or crypto asset above {threshold}% of the portfolio",
                               "Aucune action ni cryptoactif au-dessus de {threshold} % du portefeuille")),
    "cap.sector": RuleDef("cap", "weight.sector.max", None, "sector", None, "<=", "pct", True, POSITION_BOUNDS, True,
                          _t("No sector above {threshold}% of the portfolio (directly held stocks)",
                             "Aucun secteur au-dessus de {threshold} % du portefeuille (actions détenues directement)")),
    "cap.growth_assets": RuleDef("cap", "weight.growth_assets", None, "asset_group", "equity+crypto", "<=", "pct", True, GROWTH_BOUNDS, True,
                                 _t("Stocks, equity funds and crypto together at most {threshold}%",
                                    "Actions, fonds d'actions et crypto ensemble à au plus {threshold} %")),
    "floor.fixed_income": RuleDef("floor", "weight.fixed_income", None, "asset_group", "fixed_income+cash", ">=", "pct", True, FLOOR_BOUNDS, True,
                                  _t("Keep bonds and cash at {threshold}% or more", "Garder obligations et encaisse à {threshold} % ou plus")),
    "floor.diversifiers": RuleDef("floor", "weight.diversifiers", None, "asset_group", "fixed_income+cash+commodity", ">=", "pct", True, FLOOR_BOUNDS, True,
                                  _t("Keep bonds, cash and gold together at {threshold}% or more",
                                     "Garder obligations, encaisse et or ensemble à {threshold} % ou plus")),
    "cap.asset_class.crypto": RuleDef("cap", "weight.asset_group", "crypto", "asset_group", "crypto", "<=", "pct", True, POSITION_BOUNDS, True,
                                      _t("Crypto assets at most {threshold}%", "Cryptoactifs à au plus {threshold} %")),
    "limit.volatility": RuleDef("limit", "vol.annualized", None, "portfolio", None, "<=", "pct", True, {"min": 2.0, "max": 40.0, "step": 0.5}, True,
                                _t("Portfolio volatility at most {threshold}% a year", "Volatilité du portefeuille d'au plus {threshold} % par an")),
    "limit.stress_2022": RuleDef("limit", "stress.replay_2022", None, "portfolio", None, "<=", "pct", True, {"min": 1.0, "max": 60.0, "step": 0.5}, True,
                                 _t("A repeat of 2022 may cost at most {threshold}% of the portfolio",
                                    "Une répétition de 2022 peut coûter au plus {threshold} % du portefeuille")),
    "limit.drawdown": RuleDef("limit", "drawdown.max", None, "portfolio", None, "<=", "pct", True, {"min": 2.0, "max": 80.0, "step": 1.0}, True,
                              _t("Largest historical peak-to-trough fall at most {threshold}%",
                                 "Plus forte baisse historique d'un sommet à un creux d'au plus {threshold} %")),
    "exclude.asset_class.crypto": RuleDef("exclude", "weight.asset_class", "crypto", "asset_class", "crypto", "==", "pct", True, None, True,
                                          _t("No crypto assets", "Aucun cryptoactif")),
    "evidence.controversy": RuleDef("evidence", None, None, "none", None, "none", "text", False, None, True,
                                    _t("No company involved in a significant environmental or social controversy (needs outside evidence)",
                                       "Aucune société impliquée dans une controverse environnementale ou sociale importante (exige des preuves externes)")),
    "flag.attention": RuleDef("flag", "attention.pageviews_ratio", None, "position", None, "none", "ratio", False, None, False,
                              _t("Show when the requested asset is drawing unusual public attention",
                                 "Signaler quand l'actif demandé attire une attention publique inhabituelle")),
    "flag.rate_cycle": RuleDef("flag", "stress.rate_cycle", None, "portfolio", None, "none", "pct", False, None, False,
                               _t("Show how the portfolio behaved while interest rates rose",
                                  "Montrer le comportement du portefeuille pendant la hausse des taux")),
    "sim.only": RuleDef("sim", None, None, "none", None, "none", "text", False, None, False,
                        _t("Simulation only: no order is ever placed", "Simulation seulement : aucun ordre n'est jamais passé")),
}


def rule_def(rule_id: str) -> RuleDef:
    """Definition of a rule ID, including parameterized families."""
    if rule_id.startswith("custom.condition."):
        return RuleDef("limit", None, None, "none", None, "none", "pct", True, None, True,
                       _t("User-defined conditional policy", "Règle conditionnelle définie par l'utilisateur"))
    if rule_id in FIXED:
        return FIXED[rule_id]
    parts = rule_id.split(".", 2)
    if len(parts) == 3 and parts[0] in ("cap", "floor") and parts[1] in ("position", "sector", "asset_class", "country", "currency", "theme"):
        operation, dimension, key = parts
        qualifier = " (listing proxy)" if dimension == "country" else " (quotation proxy)" if dimension == "currency" else ""
        comparison = "At most" if operation == "cap" else "At least"
        comparison_fr = "Au plus" if operation == "cap" else "Au moins"
        key_fr = (SECTOR_FR.get(next((k for k in SECTOR_FR if slug(k) == key), key), key)
                  if dimension == "sector" else key)
        return RuleDef(operation, f"weight.{dimension}", key, dimension, key,
                       "<=" if operation == "cap" else ">=", "pct", True, FLOOR_BOUNDS, True,
                       _t(f"{comparison} {{threshold}}% in {dimension} {key}{qualifier}",
                          f"{comparison_fr} {{threshold}} % {_DIMENSION_FR[dimension]} {key_fr}{_QUALIFIER_FR.get(dimension, '')}"))
    if rule_id.startswith("exclude.sector."):
        s = rule_id[len("exclude.sector."):]
        label = next((k for k in SECTOR_FR if slug(k) == s), s.replace("_", " ").title())
        return RuleDef("exclude", "weight.sector", s, "sector", label, "==", "pct", True, None, True,
                       _t(f"No directly held {label}-sector companies",
                          f"Aucune société du secteur {SECTOR_FR.get(label, label)} détenue directement"))
    if rule_id.startswith("exclude.asset_class."):
        c = rule_id[len("exclude.asset_class."):]
        return RuleDef("exclude", "weight.asset_class", c, "asset_class", c, "==", "pct", True, None, True,
                       _t(f"No assets of class {c}", f"Aucun actif de la classe {c}"))
    if rule_id.startswith("exclude.ticker."):
        t = rule_id[len("exclude.ticker."):]
        return RuleDef("exclude", "weight.position", t, "position", t, "==", "pct", True, None, True,
                       _t(f"No position in {t}", f"Aucune position dans {t}"))
    raise KeyError(f"unknown rule {rule_id!r}")
