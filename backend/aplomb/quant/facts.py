"""Fact construction, bilingual display formatting and an interim run ledger.

Every number leaving quant, rules or the optimizer becomes a ``Fact`` (schemas.md §6),
validated by T01's Pydantic model. ``LocalLedger`` implements the subset of T10's ``Ledger``
protocol these modules need (``add_fact``, ``get_fact``, ``facts``); T10 can substitute its own
ledger without changing callers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from aplomb.contracts.models import Fact

MINUS = "−"
NBSP = " "  # narrow no-break space used before % and units in French

METHOD_TEXT: dict[str, tuple[str, str]] = {
    "M_PRICE_ADJ_CLOSE": ("Adjusted close (splits and dividends) as published.", "Clôture ajustée (fractionnements et dividendes) telle que publiée."),
    "M_FX_BOC_FFILL": ("Bank of Canada USD/CAD rate of the day, or the last rate published before it.", "Taux USD/CAD de la Banque du Canada du jour, ou le dernier taux publié avant."),
    "M_RET_SIMPLE": ("Simple return: end level divided by start level, minus one.", "Rendement simple : niveau final divisé par le niveau initial, moins un."),
    "M_RET_CALENDAR_YEAR": ("Return from the last observation of the previous year to the last observation of the year.", "Rendement de la dernière observation de l'année précédente à la dernière observation de l'année."),
    "M_VOL_STDEV_252": ("Sample standard deviation of daily returns times the square root of 252.", "Écart-type échantillonnal des rendements quotidiens multiplié par la racine carrée de 252."),
    "M_MDD_PEAK_TROUGH": ("Largest fall from a running peak, as a positive percentage.", "Plus forte baisse depuis un sommet, en pourcentage positif."),
    "M_WORST_ROLLING_252": ("Worst return over any 252 consecutive master-calendar periods.", "Pire rendement sur 252 périodes consécutives du calendrier maître."),
    "M_CORR_PEARSON": ("Pearson correlation of daily returns on the master calendar.", "Corrélation de Pearson des rendements quotidiens sur le calendrier maître."),
    "M_PORT_CONST_WEIGHTS": ("Today's weights applied to past daily returns, rebalanced daily.", "Pondérations actuelles appliquées aux rendements quotidiens passés, rééquilibrées chaque jour."),
    "M_WEIGHTS_AFTER_MOVE": ("Weights after the hypothetical move under the stated funding mode.", "Pondérations après le mouvement hypothétique selon le mode de financement indiqué."),
    "M_STRESS_REPLAY": ("Constant-weight portfolio return over a named historical window.", "Rendement du portefeuille à pondérations constantes sur une période historique nommée."),
    "M_PRICE_MOVE_AFTER_EVENT": ("Simple return over N master-calendar days after the event date.", "Rendement simple sur N jours du calendrier maître après la date de l'événement."),
    "M_CAL_INTERSECTION": ("Days with both a TSX (XIU.TO) and a U.S. (SPY) price.", "Jours avec un prix TSX (XIU.TO) et un prix américain (SPY)."),
    "M_OBSERVED_ROW": ("Value read from one dataset row.", "Valeur lue dans une ligne d'un jeu de données."),
    "M_RULE_COMPARE": ("Comparison of a value with a threshold and the 10% tension band (A-09).", "Comparaison d'une valeur à un seuil et à la zone de tension de 10 % (A-09)."),
    "M_PROFILE_ASSUMPTION": ("Value set in the profile.", "Valeur fixée dans le profil."),
    "M_USER_INPUT": ("Value typed or selected by the user.", "Valeur saisie ou choisie par l'utilisateur."),
    "M_DERIVE_VOL_BUDGET": ("Volatility budget looked up from the risk level (A-02).", "Budget de volatilité tiré du niveau de risque (A-02)."),
    "M_DERIVE_POSITION_CAP": ("clamp(round5(100 x 0.4 x budget / single-stock Q3 volatility), 5, 25) (A-03).", "clamp(arrondi5(100 x 0,4 x budget / volatilité Q3 des actions), 5, 25) (A-03)."),
    "M_DERIVE_SECTOR_CAP": ("min(40, 2 x position cap) (A-04).", "min(40, 2 x plafond par position) (A-04)."),
    "M_DERIVE_CRYPTO_CAP": ("clamp(round5(100 x 0.4 x budget / median crypto volatility), 0, 25), halved when speculation is avoided (A-05).", "clamp(arrondi5(100 x 0,4 x budget / volatilité médiane crypto), 0, 25), réduit de moitié si la spéculation est évitée (A-05)."),
    "M_DERIVE_GROWTH_CAP": ("Largest 5-point equity share of the 50% XIU.TO / 50% SPY / rest XBB.TO mix within the budget (A-06).", "Plus grande part d'actions, par pas de 5 points, du mélange 50 % XIU.TO / 50 % SPY / reste XBB.TO qui respecte le budget (A-06)."),
    "M_DERIVE_STRESS_LIMIT": ("Budget times 1, 1.25 or 1.5 by horizon midpoint (A-07).", "Budget multiplié par 1, 1,25 ou 1,5 selon le milieu de l'horizon (A-07)."),
    "M_DERIVE_DRAWDOWN_LIMIT": ("Two times the volatility budget (A-08).", "Deux fois le budget de volatilité (A-08)."),
    "M_MAXSIZE_GRID": ("Last 0.5-point size before the first rule conflict (A-18).", "Dernière taille, par pas de 0,5 point, avant le premier conflit de règle (A-18)."),
    "M_FRONTIER_MINVAR": ("Long-only minimum-variance portfolios per equity target (risk only).", "Portefeuilles à variance minimale sans vente à découvert, par cible d'actions (risque seulement)."),
    "M_FRONTIER_HIST_MV": ("Long-only mean-variance with historical mean returns (illustration only).", "Moyenne-variance sans vente à découvert avec rendements moyens historiques (illustration seulement)."),
}


def _num(value: float, decimals: int, lang: str) -> str:
    text = f"{abs(value):,.{decimals}f}"
    if lang == "fr":
        text = text.replace(",", NBSP).replace(".", ",")
    return (MINUS if value < 0 and round(abs(value), decimals) != 0 else "") + text


def display(value, unit: str, currency: str | None = None, decimals: int | None = None) -> dict[str, str]:
    """Bilingual display string for a fact value (code-formatted, never by a model)."""
    if value is None:
        return {"en": "unavailable", "fr": "indisponible"}
    if isinstance(value, bool):
        return {"en": "yes" if value else "no", "fr": "oui" if value else "non"}
    if isinstance(value, str):
        return {"en": value, "fr": value}
    if unit == "pct":
        d = 2 if decimals is None else decimals
        return {"en": _num(value, d, "en") + "%", "fr": _num(value, d, "fr") + NBSP + "%"}
    if unit == "pts":
        d = 1 if decimals is None else decimals
        return {"en": _num(value, d, "en") + " pts", "fr": _num(value, d, "fr") + " pts"}
    if unit in ("cad", "usd"):
        d = 0 if decimals is None else decimals
        ccy = currency or unit.upper()
        return {"en": f"{_num(value, d, 'en')} {ccy}", "fr": f"{_num(value, d, 'fr')}{NBSP}{ccy}"}
    if unit == "count":
        return {"en": _num(value, 0 if float(value).is_integer() else 2, "en"),
                "fr": _num(value, 0 if float(value).is_integer() else 2, "fr")}
    d = 2 if decimals is None else decimals
    return {"en": _num(value, d, "en"), "fr": _num(value, d, "fr")}


class FactSink(Protocol):
    """Subset of T10's ``Ledger`` used by quant, rules and the optimizer."""

    def add_fact(self, fact: dict) -> str: ...
    def get_fact(self, fact_id: str) -> Fact: ...


class LedgerError(ValueError):
    pass


class LocalLedger:
    """Run-local fact store: deterministic ``F-001`` IDs, key de-duplication, input checks.

    Adding a fact whose key already exists returns the existing ID when the value is the same
    and raises when it differs (a FactKey must name one number within a ledger).
    """

    def __init__(self) -> None:
        self._facts: dict[str, Fact] = {}
        self._by_key: dict[str, str] = {}

    def add_fact(self, fact: dict) -> str:
        key = fact["key"]
        existing = self._by_key.get(key)
        if existing is not None:
            old = self._facts[existing].value
            new = fact["value"]
            same = (old == new) or (isinstance(old, float) and isinstance(new, float) and math.isclose(old, new, rel_tol=0, abs_tol=1e-12))
            if not same:
                raise LedgerError(f"fact key {key} already holds {old!r}, not {new!r}")
            return existing
        for ref in fact.get("inputs", []):
            if ref not in self._facts:
                raise LedgerError(f"input {ref} of {key} is not in this ledger")
        fact_id = f"F-{len(self._facts) + 1:03d}"
        model = Fact.model_validate({**fact, "id": fact_id})
        self._facts[fact_id] = model
        self._by_key[key] = fact_id
        return fact_id

    def get_fact(self, fact_id: str) -> Fact:
        return self._facts[fact_id]

    def id_for_key(self, key: str) -> str | None:
        return self._by_key.get(key)

    def facts(self) -> dict[str, Fact]:
        return dict(self._facts)

    def wire(self, ids: list[str] | None = None) -> dict[str, dict]:
        chosen = self._facts if ids is None else {i: self._facts[i] for i in ids}
        return {i: f.to_wire() for i, f in chosen.items()}

    def __len__(self) -> int:
        return len(self._facts)


@dataclass(frozen=True)
class FactContext:
    """What every fact of one computation shares."""

    as_of: str
    created_at: str           # injected clock, ISO UTC
    data_version: str


def make_fact(ctx: FactContext, *, key: str, kind: str, metric: str, label: dict, value, unit: str,
              currency: str | None, subject: dict, method_id: str, created_by: str,
              period: dict | None = None, window: dict | None = None, available_at: str | None = None,
              params: dict | None = None, inputs: list[str] | None = None, n_obs: int | None = None,
              sources: list[dict] | None = None, limitations: list[str] | None = None,
              checks: list[dict] | None = None, decimals: int | None = None) -> dict:
    """Wire-shaped fact (without ``id``) ready for ``FactSink.add_fact``."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{key}: non-finite value")
    en, fr = METHOD_TEXT.get(method_id, (method_id, method_id))
    run_checks = list(checks or [])
    run_checks.append({"code": "finite_value", "ok": True, "detail": "Value is finite or explicitly null."})
    return {
        "key": key, "kind": kind, "metric": metric, "label": label, "value": value, "unit": unit,
        "currency": currency, "display": display(value, unit, currency, decimals), "subject": subject,
        "period": period, "window": window, "asOf": ctx.as_of, "availableAt": available_at,
        "method": {"id": method_id, "description": {"en": en, "fr": fr}, "params": dict(params or {})},
        "inputs": list(inputs or []), "nObs": n_obs, "sources": list(sources or []),
        "limitations": list(dict.fromkeys(limitations or [])),
        "verification": {"status": "verified", "checks": run_checks},
        "createdBy": created_by, "createdAt": ctx.created_at,
    }


def fact_key(metric: str, subject_type: str, subject_id: str, variant: str, window: str) -> str:
    return f"{metric}|{subject_type}:{subject_id}|{variant}|{window}"
