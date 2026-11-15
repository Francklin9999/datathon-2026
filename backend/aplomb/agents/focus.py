"""Code-owned strategic focus areas for the horizon-aware portfolio brief.

Ranking adapts to the investor's own objectives, horizon and exclusions, never to seed names.
Every figure is a verified ledger fact; scores are visible heuristics, not forecasts; holdings
are exact session-portfolio tickers; a candidate provider can only re-rank or attach verified
facts and held tickers (see ``bridges.candidate_findings``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote

MAX_PRIMARY = 3
MAX_OBJECTIVE_CARDS = 2


@dataclass
class Candidate:
    topic: str
    score: int
    rationale: str
    card: dict
    action: tuple[str, str]
    horizon_note: tuple[str, str]
    holdings: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    uncertainty: str = "medium"
    reasons: list[tuple[str, str]] = field(default_factory=list)
    href: str = "/portfolio/"
    horizon_years: float = 0.0
    objective: str | None = None
    basis: str = "built_in"


def band_of(years: float) -> str:
    return "short" if years < 3 else ("medium" if years < 10 else "long")


def _i18n(pair):
    return {"en": pair[0], "fr": pair[1]}


def ranked_objectives(profile) -> list:
    """User-stated order (priority 1 first), then the nearest horizon."""
    context = profile.investor_context
    if not context or not context.objectives:
        return []
    return sorted(context.objectives, key=lambda g: (g.priority, g.horizon_years, g.name))


def _positions(check):
    return [p for p in check.portfolio_before.positions if p.weight_pct > 0]


def _top(check, n=3):
    return [p.ticker for p in sorted(_positions(check), key=lambda p: -p.weight_pct)[:n]]


def _exposure_tickers(check, worst) -> list[str]:
    if worst is None:
        return []
    positions = _positions(check)
    if worst.type == "asset":
        return [p.ticker for p in positions if p.ticker == worst.id]
    if worst.type == "sector":
        return [p.ticker for p in positions if p.sector == worst.id]
    if worst.type == "asset_group":
        return [p.ticker for p in positions if p.asset_group == worst.id]
    return []  # theme membership is not an exact holding attribute here


def excluded_holdings(profile, check) -> list[str]:
    """Holdings whose recorded sector/asset class exactly matches a stated exclusion."""
    prefs = profile.preferences
    sectors = {s.casefold() for s in prefs.excluded_sectors}
    classes = set(prefs.excluded_asset_classes)
    return [p.ticker for p in _positions(check) if p.sector.casefold() in sectors or p.asset_class in classes]


def _dedupe(values):
    return list(dict.fromkeys(v for v in values if v))


def built_in_candidates(*, run_id, profile, check, cards, flagged, base_horizon) -> list[Candidate]:
    risk, concentration, plan_fit, bond = cards["risk"], cards["concentration"], cards["plan"], cards.get("fixed_income")
    by_rule = {c.rule_id: c for c in check.rule_checks}
    audit_href = f"/evidence-audit/?runId={quote(run_id, safe='')}"
    out = []

    metrics = check.portfolio_before.metrics
    missing_metrics = metrics.volatility_pct is None or metrics.max_drawdown_pct is None
    out.append(Candidate(
        "risk", 70 if base_horizon < 10 else 45, "sample risk and horizon", risk,
        ("Investigate historical downside resilience before changing the allocation.",
         "Examiner la résistance aux baisses historiques avant de modifier la répartition."),
        ("Consider whether the sample's drawdowns are tolerable over the investor's horizon.",
         "Examiner si les baisses de l'échantillon sont tolérables à l'horizon de l'investisseur."),
        holdings=_top(check), href="/portfolio/", horizon_years=base_horizon,
        uncertainty="high" if missing_metrics else "medium",
        reasons=[("Historical sample statistics; not a forecast.",
                  "Statistiques d'un échantillon historique; pas une prévision.")]
        + ([("Some risk measures are unavailable with the visible history.",
             "Certaines mesures de risque sont indisponibles avec l'historique visible.")] if missing_metrics else []),
    ))

    position, sector = by_rule.get("cap.position"), by_rule.get("cap.sector")
    held_etf = any(p.asset_class.startswith("etf") for p in _positions(check))
    conc_holdings = _dedupe(_exposure_tickers(check, position.worst if position else None)
                            + _exposure_tickers(check, sector.worst if sector else None)) or _top(check, 1)
    out.append(Candidate(
        "concentration", 60, "direct concentration; ETF look-through remains unknown", concentration,
        ("Investigate issuer overlap inside ETFs; direct positions do not establish underlying diversification.",
         "Examiner les émetteurs communs aux FNB; les positions directes ne prouvent pas la diversification sous-jacente."),
        ("Investigate whether concentrated exposures fit the investor's horizon and capacity for losses.",
         "Examiner si la concentration convient à l'horizon et à la capacité de perte de l'investisseur."),
        holdings=conc_holdings, href="/risk-intelligence/", horizon_years=base_horizon,
        rule_ids=[c.rule_id for c in (position, sector) if c is not None],
        uncertainty="medium" if held_etf else "low",
        reasons=[("ETF constituents are not looked through here.",
                  "Les composantes des FNB ne sont pas examinées ici.")] if held_etf else
                [("Direct weights only; issuer relationships are not established.",
                  "Poids directs seulement; les liens entre émetteurs ne sont pas établis.")],
    ))

    excluded = excluded_holdings(profile, check)
    if flagged or excluded:
        severity = (100 if any(c.status == "conflict" for c in flagged)
                    else 90 if any(c.status == "tension" for c in flagged) else 55)
        if excluded:
            severity = max(severity, 95)
        plan_holdings = _dedupe([t for c in flagged for t in _exposure_tickers(check, c.worst)] + excluded)
        has_nee = any(c.status == "nee" for c in flagged)
        reasons = []
        if has_nee:
            reasons.append(("At least one rule lacks enough evidence to evaluate.",
                            "Au moins une règle manque de preuves pour être évaluée."))
        if excluded:
            reasons.append(("Holdings match a stated exclusion by recorded sector or asset class.",
                            "Des positions correspondent à une exclusion déclarée (secteur ou catégorie enregistrés)."))
        out.append(Candidate(
            "plan", severity, "policy status, stated exclusions or missing evidence", plan_fit,
            ("Inspect the flagged rules and their evidence before testing a move.",
             "Examiner les règles signalées et leurs preuves avant de tester un mouvement."),
            ("Review whether the policy assumptions reflect the investor's horizon.",
             "Examiner si les hypothèses du plan reflètent l'horizon de l'investisseur."),
            holdings=plan_holdings, href=audit_href, horizon_years=base_horizon,
            rule_ids=[c.rule_id for c in flagged[:4]],
            evidence_ids=_dedupe(e for c in flagged for e in c.evidence_ids),
            uncertainty="high" if has_nee else ("medium" if excluded and not flagged else "low"),
            reasons=reasons or [("Deterministic rule evaluation under the plan's assumptions.",
                                 "Évaluation déterministe des règles selon les hypothèses du plan.")],
        ))

    if bond is not None:
        out.append(Candidate(
            "fixed_income", 75 if base_horizon < 10 else 50,
            "fixed-income exposure and horizon; duration unavailable", bond,
            ("Investigate bond duration and credit quality; neither is established by asset-class weight.",
             "Examiner la duration et la qualité du crédit; le poids de la catégorie ne les établit pas."),
            ("Compare bond characteristics with the investor's horizon; duration is not established here.",
             "Comparer les caractéristiques obligataires à l'horizon de l'investisseur; la duration n'est pas établie ici."),
            holdings=[p.ticker for p in _positions(check) if p.asset_group == "fixed_income"],
            href="/markets/", horizon_years=base_horizon, uncertainty="high",
            reasons=[("Duration and credit quality are not established by asset-class weight.",
                      "La duration et la qualité du crédit ne sont pas établies par le poids de la catégorie.")],
        ))

    out.append(Candidate(
        "plan", 10, "baseline policy assessment", plan_fit,
        ("Review policy assumptions and missing evidence before the next investigation.",
         "Revoir les hypothèses du plan et les preuves manquantes avant la prochaine recherche."),
        ("Review whether the policy assumptions reflect the investor's horizon.",
         "Examiner si les hypothèses du plan reflètent l'horizon de l'investisseur."),
        href=audit_href, horizon_years=base_horizon, uncertainty="low",
        reasons=[("Deterministic rule evaluation under the plan's assumptions.",
                  "Évaluation déterministe des règles selon les hypothèses du plan.")],
    ))
    return out


def objective_candidates(*, profile, risk_rows, make_card, include=frozenset()) -> list[Candidate]:
    """One card per leading stated objective, ranked by the user's own order and horizon.

    The card shows the sample's verified downside figures beside the objective's horizon. It never
    computes goal feasibility, earmarks holdings or treats free-text notes as instructions.
    """
    out = []
    context = profile.investor_context
    ranked = ranked_objectives(profile)
    chosen = [g for i, g in enumerate(ranked) if i < MAX_OBJECTIVE_CARDS or g.name in include]
    for index, goal in enumerate(chosen):
        years = float(goal.horizon_years)
        # Earlier user order and a nearer horizon raise investigation priority; capped below a policy conflict.
        score = max(0, min(88, 80 - 8 * index - (0 if years < 3 else 12 if years < 10 else 25)))
        reasons = [("No holdings are earmarked for this objective; the whole portfolio is shown.",
                    "Aucune position n'est affectée à cet objectif; l'ensemble du portefeuille est montré.")]
        if goal.target_amount is None or goal.allocated_value is None:
            reasons.append(("Target or allocated amount is not recorded, so funding progress is unknown.",
                            "Le montant cible ou affecté n'est pas renseigné; l'avancement est inconnu."))
        if goal.origin == "assumption":
            reasons.append(("This objective is recorded as an assumption.",
                            "Cet objectif est enregistré comme une hypothèse."))
        if context and (context.liquidity_notes or context.risk_capacity_notes):
            reasons.append(("Liquidity and risk-capacity notes are shown to you but not evaluated by code.",
                            "Les notes de liquidité et de capacité de risque ne sont pas évaluées par le code."))
        slug = f"OBJ{index + 1}"
        card = make_card(slug, f"Objective: {goal.name}", f"Objectif : {goal.name}", risk_rows)
        out.append(Candidate(
            "objective", score, "stated objective order and horizon", card,
            ("Investigate whether the sample's historical losses would be tolerable before this objective's horizon.",
             "Examiner si les pertes historiques de l'échantillon seraient tolérables avant l'horizon de cet objectif."),
            ("Compare this objective's horizon with the drawdown and recovery seen in the sample.",
             "Comparer l'horizon de cet objectif aux baisses et reprises observées dans l'échantillon."),
            href="/profiles/", horizon_years=years, objective=goal.name,
            uncertainty="high" if len(reasons) > 1 else "medium", reasons=reasons,
        ))
    return out


def apply_provider(candidates: list[Candidate], findings, *, facts, fact_sentence, lang) -> None:
    """Re-rank and enrich built-in candidates from validated provider findings."""
    sep = " : " if lang == "fr" else ": "
    for finding in findings:
        targets = [c for c in candidates if c.topic == finding.topic
                   and (finding.objective is None or c.objective == finding.objective)]
        for candidate in targets:
            if finding.priority > candidate.score or candidate.basis == "built_in":
                candidate.score = finding.priority
            candidate.basis = "candidate_provider"
            candidate.holdings = _dedupe([*candidate.holdings, *finding.tickers])
            shown = set(candidate.card["factIds"])
            for fid in finding.fact_ids:
                if fid in shown or len(candidate.card["body"]) >= 6:
                    continue
                fact = facts[fid]
                label = fact.label.fr if lang == "fr" else fact.label.en
                candidate.card["body"].append(fact_sentence(
                    f"C-PROV-{candidate.topic.upper()}-{len(candidate.card['body']) + 1}", label + sep, fact, lang))
                candidate.card["factIds"].append(fid)
                shown.add(fid)


def select(candidates: list[Candidate], *, lang, text_sentence) -> list[dict]:
    """Highest score first, one card per title, at most three primary focus areas."""
    fr = lang == "fr"
    selected, seen = [], set()
    for c in sorted(candidates, key=lambda x: -x.score):
        title = c.card["title"]["en"]
        if title in seen:
            continue
        seen.add(title)
        priority = len(selected) + 1
        card = c.card
        card["body"].append(text_sentence(f"C-FOCUS-{priority}-ACTION", c.action[1] if fr else c.action[0]))
        card["body"].append(text_sentence(f"C-FOCUS-{priority}-HORIZON", c.horizon_note[1] if fr else c.horizon_note[0]))
        # This explains ordering; it is a code-owned heuristic, not a verified market claim.
        card["body"].append(text_sentence(
            f"C-FOCUS-{priority}-RANK",
            f"Deterministic priority score {c.score}: {c.rationale}." if not fr else
            f"Score heuristique du système : {c.score}; ce classement n'est pas une mesure financière."))
        card["detail"] = {
            "priority": priority, "topic": c.topic, "score": int(c.score), "basis": c.basis,
            "timeHorizon": band_of(c.horizon_years), "horizonYears": min(150.0, max(0.0, float(c.horizon_years))),
            "objective": c.objective, "holdings": c.holdings[:10], "evidenceIds": c.evidence_ids[:10],
            "ruleIds": c.rule_ids[:6], "uncertainty": c.uncertainty,
            "uncertaintyReasons": [_i18n(r) for r in c.reasons], "investigation": _i18n(c.action),
            "href": c.href,
        }
        selected.append(card)
        if len(selected) == MAX_PRIMARY:
            break
    return selected
