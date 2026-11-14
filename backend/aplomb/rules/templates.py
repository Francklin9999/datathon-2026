"""Detail sentences for rule checks (rules SPEC §5). Built by code, never by a model.

Placeholders: {worst}, {value}, {threshold} (fact display strings) and {what} (category name).
Every (family, status) pair the engine can produce has English and French text (RUL-12).
"""

from __future__ import annotations

T = dict[str, str]


def _t(en: str, fr: str) -> T:
    return {"en": en, "fr": fr}


TEMPLATES: dict[tuple[str, str], T] = {
    ("cap.position", "conflict"): _t("Largest single position would be {worst} at {value}, above the {threshold} cap.",
                                     "La plus grande position serait {worst} à {value}, au-dessus du plafond de {threshold}."),
    ("cap.position", "tension"): _t("Largest single position would be {worst} at {value}, close to the {threshold} cap.",
                                    "La plus grande position serait {worst} à {value}, près du plafond de {threshold}."),
    ("cap.position", "pass"): _t("Largest single position is {worst} at {value}, inside the {threshold} cap.",
                                 "La plus grande position est {worst} à {value}, sous le plafond de {threshold}."),
    ("cap.sector", "conflict"): _t("{worst} would reach {value} of the portfolio, above the {threshold} sector cap.",
                                   "{worst} atteindrait {value} du portefeuille, au-dessus du plafond sectoriel de {threshold}."),
    ("cap.sector", "tension"): _t("{worst} would reach {value} of the portfolio, close to the {threshold} sector cap.",
                                  "{worst} atteindrait {value} du portefeuille, près du plafond sectoriel de {threshold}."),
    ("cap.sector", "pass"): _t("The largest sector is {worst} at {value}, inside the {threshold} sector cap.",
                               "Le plus grand secteur est {worst} à {value}, sous le plafond sectoriel de {threshold}."),
    ("cap.group", "conflict"): _t("{what} would be {value}, above the {threshold} cap.", "{what} serait à {value}, au-dessus du plafond de {threshold}."),
    ("cap.group", "tension"): _t("{what} would be {value}, close to the {threshold} cap.", "{what} serait à {value}, près du plafond de {threshold}."),
    ("cap.group", "pass"): _t("{what}: {value}, inside the {threshold} cap.", "{what} : {value}, sous le plafond de {threshold}."),
    ("floor", "conflict"): _t("{what} would fall to {value}, below the {threshold} floor.", "{what} tomberait à {value}, sous le plancher de {threshold}."),
    ("floor", "tension"): _t("{what} would be {value}, close to the {threshold} floor.", "{what} serait à {value}, près du plancher de {threshold}."),
    ("floor", "pass"): _t("{what}: {value}, above the {threshold} floor.", "{what} : {value}, au-dessus du plancher de {threshold}."),
    ("limit.volatility", "conflict"): _t("Portfolio volatility would be {value} a year, above the {threshold} budget.",
                                         "La volatilité du portefeuille serait de {value} par an, au-dessus du budget de {threshold}."),
    ("limit.volatility", "tension"): _t("Portfolio volatility would be {value} a year, close to the {threshold} budget.",
                                        "La volatilité du portefeuille serait de {value} par an, près du budget de {threshold}."),
    ("limit.volatility", "pass"): _t("Portfolio volatility is {value} a year, inside the {threshold} budget.",
                                     "La volatilité du portefeuille est de {value} par an, sous le budget de {threshold}."),
    ("limit.stress_2022", "conflict"): _t("With these weights, calendar 2022 would have cost {value}, above the {threshold} limit.",
                                          "Avec ces pondérations, l'année 2022 aurait coûté {value}, au-dessus de la limite de {threshold}."),
    ("limit.stress_2022", "tension"): _t("With these weights, calendar 2022 would have cost {value}, close to the {threshold} limit.",
                                         "Avec ces pondérations, l'année 2022 aurait coûté {value}, près de la limite de {threshold}."),
    ("limit.stress_2022", "pass"): _t("With these weights, calendar 2022 would have cost {value}, inside the {threshold} limit.",
                                      "Avec ces pondérations, l'année 2022 aurait coûté {value}, sous la limite de {threshold}."),
    ("limit.drawdown", "conflict"): _t("The largest fall in the window would have been {value}, above the {threshold} ceiling.",
                                       "La plus forte baisse de la période aurait été de {value}, au-dessus du plafond de {threshold}."),
    ("limit.drawdown", "tension"): _t("The largest fall in the window would have been {value}, close to the {threshold} ceiling.",
                                      "La plus forte baisse de la période aurait été de {value}, près du plafond de {threshold}."),
    ("limit.drawdown", "pass"): _t("The largest fall in the window was {value}, inside the {threshold} ceiling.",
                                   "La plus forte baisse de la période a été de {value}, sous le plafond de {threshold}."),
    ("exclude", "conflict"): _t("{worst} belongs to an excluded category ({what}); any size conflicts with this rule.",
                                "{worst} appartient à une catégorie exclue ({what}); toute taille est en conflit avec cette règle."),
    ("exclude", "pass"): _t("No holding belongs to the excluded category ({what}).",
                            "Aucune position n'appartient à la catégorie exclue ({what})."),
    ("evidence", "nee"): _t("No verified controversy evidence was found in the sources searched for {worst}. This is not a clean bill.",
                            "Aucune preuve vérifiée de controverse n'a été trouvée dans les sources consultées pour {worst}. Ce n'est pas un certificat de propreté."),
    ("evidence", "tension"): _t("Verified evidence of a controversy is attached for {worst}; whether it is significant is the investor's judgment.",
                                "Une preuve vérifiée de controverse est jointe pour {worst}; juger de son importance revient à l'investisseur."),
    ("flag.attention", "info"): _t("Public attention to {worst}: {value} of its usual level.",
                                   "Attention publique envers {worst} : {value} de son niveau habituel."),
    ("flag.attention", "info_missing"): _t("No page-view data is loaded for {worst}; attention is not shown.",
                                           "Aucune donnée de consultation n'est chargée pour {worst}; l'attention n'est pas affichée."),
    ("flag.rate_cycle", "info"): _t("During the 2022–2023 rate-hiking cycle these weights returned {value} (informational).",
                                    "Pendant le cycle de hausse des taux de 2022–2023, ces pondérations ont rapporté {value} (à titre informatif)."),
    ("flag.rate_cycle", "info_missing"): _t("The rate-hiking cycle cannot be replayed with the data available.",
                                            "Le cycle de hausse des taux ne peut pas être rejoué avec les données disponibles."),
    ("sim", "info"): _t("Simulation only: no order is ever placed.", "Simulation seulement : aucun ordre n'est jamais passé."),
    ("any", "nee:short_history"): _t("{worst} has too little price history for this figure.",
                                     "{worst} n'a pas assez d'historique de prix pour ce calcul."),
    ("any", "nee:not_visible_at_asof"): _t("The data needed for this figure lies after the selected date.",
                                           "Les données nécessaires à ce calcul sont postérieures à la date choisie."),
    ("any", "nee:asset_unknown"): _t("{worst} could not be found in the data.", "{worst} est introuvable dans les données."),
    ("any", "nee:dataset_missing"): _t("A dataset this rule needs is not loaded.", "Un jeu de données requis par cette règle n'est pas chargé."),
}

WHAT: dict[str, T] = {
    "cap.growth_assets": _t("Stocks, equity funds and crypto", "Actions, fonds d'actions et crypto"),
    "cap.asset_class.crypto": _t("Crypto", "La crypto"),
    "floor.fixed_income": _t("Bonds and cash", "Obligations et encaisse"),
    "floor.diversifiers": _t("Bonds, cash and gold", "Obligations, encaisse et or"),
}


def family(rule_id: str, rule_type: str) -> str:
    if rule_id in ("cap.position", "cap.sector", "limit.volatility", "limit.stress_2022", "limit.drawdown",
                   "flag.attention", "flag.rate_cycle"):
        return rule_id
    if rule_type == "cap":
        return "cap.group"
    if rule_type in ("floor", "exclude", "evidence", "sim"):
        return rule_type
    return rule_id


def render(key: tuple[str, str], values: dict[str, T]) -> T:
    template = TEMPLATES[key]
    return {lang: template[lang].format(**{k: v[lang] for k, v in values.items()}) for lang in ("en", "fr")}
