"""Goal candidates, alternatives and rebalance (optimizer SPEC §5). Ranking never uses returns.

Every retained scenario is rebuilt with facts and checked by the rule engine against the
profile's own rules; goal limits (``maxLossPct``/``maxVolPct``) only add constraints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from aplomb.contracts import models as m
from aplomb.datastore.constants import CASH_TICKERS, MIN_MASTER_OBS_FOR_RISK
from aplomb.quant import FundingError, QuantEngine, apply_move
from aplomb.quant.engine import slug
from aplomb.rules.definitions import rule_def
from aplomb.rules.engine import RuleEngine, RuleInputs, quick_statuses, verdict_of

from .search import counts, evaluate, max_compatible_size

MAX_SCREEN = 8
MAX_CANDIDATES = 3
REBALANCE_SIZES = (2.0, 5.0, 10.0, 15.0, 25.0)
REBALANCE_MAX_MOVES = 5


def weights_of(profile: m.Profile) -> dict[str, float]:
    return {p.ticker: p.weight_pct / 100.0 for p in profile.portfolio.positions if p.weight_pct > 0}


def excluded_asset(rules: list[m.PolicyRule], asset) -> bool:
    for r in rules:
        if not r.enabled or r.type != "exclude":
            continue
        rid = r.rule_id
        if rid.startswith("exclude.ticker.") and asset.ticker == rid[len("exclude.ticker."):]:
            return True
        if rid.startswith("exclude.asset_class.") and asset.asset_class == rid[len("exclude.asset_class."):]:
            return True
        if rid.startswith("exclude.sector.") and asset.asset_class == "equity" and slug(asset.sector) == rid[len("exclude.sector."):]:
            return True
    return False


def eligible(engine: QuantEngine, rules, ticker: str) -> bool:
    if ticker in CASH_TICKERS or ticker not in engine.universe:
        return False
    a = engine.universe.get(ticker)
    return a.history.n_obs_master >= MIN_MASTER_OBS_FOR_RISK and not excluded_asset(rules, a)


def apply_moves(weights: dict[str, float], moves: list[dict]) -> tuple[dict[str, float], float]:
    """Sequential additive moves, each on the preceding variant and its current denominator."""
    w, factor = dict(weights), 1.0
    for mv in moves:
        f = mv["funding"]
        res = apply_move(w, mv["ticker"], mv["sizePct"], f["mode"], f.get("fromTickers"))
        w, factor = res.weights, factor * res.value_factor
    return w, factor


def build_scenario(engine: QuantEngine, profile: m.Profile, rules, weights, moves: list[dict], sid: str, kind: str,
                   label: dict, rationale: dict, *, themes=(), rank: int = 1, best: bool = False, evidence=()) -> dict:
    after, factor = apply_moves(weights, moves)
    view = engine.view(after, f"scenario:{sid}", profile.portfolio.total_value * factor)
    moved = tuple(dict.fromkeys(mv["ticker"] for mv in moves))
    checks = RuleEngine(engine.ledger, engine.ctx).check_rules(rules, RuleInputs(view, profile.profile_id, moved, tuple(evidence)))
    verdict, cnt = verdict_of(checks)
    exposure, keys = [], []
    for theme in themes:
        before_pct = math.fsum(w * 100 for t, w in weights.items() if theme in engine.universe.get(t).themes)
        meas = view.measure("weight.theme", theme)
        exposure.append({"theme": theme, "beforePct": min(before_pct, 100.0), "afterPct": min(meas.value, 100.0)})
        keys.append(meas.fact_id)
    keys += [c.value_fact_id for c in checks if c.status in ("conflict", "tension") and c.value_fact_id]
    return m.Scenario.model_validate({
        "scenarioId": sid, "kind": kind, "label": label, "moves": moves, "verdict": verdict, "counts": cnt.to_wire(),
        "ruleChecks": [c.to_wire() for c in checks], "portfolioAfter": view.snapshot().to_wire(), "exposure": exposure,
        "rationale": rationale, "isBestFit": best, "rank": rank, "keyFactIds": list(dict.fromkeys(k for k in keys if k)),
    }).to_wire()


def _turnover(before: dict[str, float], after: dict[str, float], factor: float) -> float:
    scaled = {k: v / factor for k, v in before.items()}
    return 50.0 * math.fsum(abs(after.get(t, 0.0) - scaled.get(t, 0.0)) for t in set(after) | set(scaled))


def _num(x: float) -> tuple[str, str]:
    en = f"{x:g}"
    return en, en.replace(".", ",")


@dataclass
class ScenarioSet:
    scenarios: list[dict]
    screened: list[str] = field(default_factory=list)
    notes: list[dict] = field(default_factory=list)


# --- Goals ---------------------------------------------------------------------------------------


def goal_candidates(engine: QuantEngine, profile: m.Profile, goal: m.ExposureGoal, max_candidates: int = MAX_CANDIDATES,
                    evidence=()) -> ScenarioSet:
    rules, weights, universe = profile.rules, weights_of(profile), engine.universe
    themes, classes, named = set(goal.themes), set(goal.asset_classes), list(goal.tickers)

    def matches(asset) -> bool:
        return asset.ticker in named or bool(themes & set(asset.themes)) or asset.asset_class in classes

    def exposure(w: dict[str, float]) -> float:  # union of matched positions: no double counting (OPT-07)
        return math.fsum(x * 100 for t, x in w.items() if t not in CASH_TICKERS and matches(universe.get(t)))

    ordered = [t for t in named if t in universe] + [a.ticker for a in universe.all() if matches(a) and a.ticker not in named]
    screened = [t for t in dict.fromkeys(ordered) if eligible(engine, rules, t)][:MAX_SCREEN]
    notes: list[dict] = []
    unknown = [t for t in named if t not in universe]
    if unknown:
        notes.append({"en": f"Not in the data: {', '.join(unknown)}.", "fr": f"Absents des données : {', '.join(unknown)}."})
    current = exposure(weights)
    target = goal.target_exposure_pct
    needed = None
    if target is not None:
        needed = target - current
        if needed <= 1e-9:
            notes.append({"en": "The portfolio already reaches the target exposure; no candidate is needed.",
                          "fr": "Le portefeuille atteint déjà l'exposition visée; aucun candidat n'est nécessaire."})
            return ScenarioSet([], screened, notes)

    def extra(w: dict[str, float]) -> bool:
        if goal.max_vol_pct is None and goal.max_loss_pct is None:
            return False
        r = engine.risk_values(w)
        vol, stress = r.get("vol"), r.get("stress2022")
        if goal.max_vol_pct is not None and (vol is None or vol > goal.max_vol_pct + 1e-9):
            return True
        if goal.max_loss_pct is not None and (stress is None or max(0.0, -stress) > goal.max_loss_pct + 1e-9):
            return True
        return False

    options = []
    for ticker in screened:
        best = None
        for mode in ("pro_rata", "new_money"):
            search = max_compatible_size(engine, rules, weights, ticker, mode, None, evidence, profile.profile_id,
                                         extra_conflict=extra)
            size = search.max_size_pct
            if size <= 0:
                continue
            if target is not None:  # smallest grid size that reaches the target (funding dilutes holdings)
                k = 1
                while k * 0.5 <= size + 1e-9:
                    if exposure(apply_move(weights, ticker, k * 0.5, mode).weights) >= target - 1e-9:
                        size = k * 0.5
                        break
                    k += 1
            res = apply_move(weights, ticker, size, mode)
            st = evaluate(engine, rules, res.weights, (ticker,), evidence, profile.profile_id)
            c = counts(st)
            after = exposure(res.weights)
            shortfall = max(0.0, target - after) if target is not None else -after
            key = (c["conflict"], c["tension"], c["nee"], round(shortfall, 9), round(_turnover(weights, res.weights, res.value_factor), 9),
                   size if mode == "new_money" else 0.0, ticker, mode)
            if best is None or key < best[0]:
                best = (key, {"ticker": ticker, "sizePct": size, "funding": {"mode": mode}})
        if best:
            options.append(best)
    options.sort(key=lambda kv: kv[0])
    chosen = options[:max_candidates]
    if len(chosen) < max_candidates:
        notes.append({"en": f"Only {len(chosen)} candidate(s) fit the profile's rules and the goal's limits among {len(screened)} screened assets.",
                      "fr": f"Seulement {len(chosen)} candidat(s) respectent les règles du profil et les limites de l'objectif parmi {len(screened)} actifs examinés."})
    scenarios = []
    for i, (_, move) in enumerate(chosen, start=1):
        en, fr = _num(move["sizePct"])
        scenarios.append(build_scenario(
            engine, profile, rules, weights, [move], f"sc_goal_{slug(move['ticker'])}", "goal_candidate",
            {"en": f"Candidate {i}: {en} points into {move['ticker']} ({move['funding']['mode']})",
             "fr": f"Candidat {i} : {fr} points dans {move['ticker']} ({move['funding']['mode']})"},
            {"en": "Largest size before the first conflict with the profile's rules and the goal's own limits; ranked by conflicts, "
                   "tensions, missing evidence, distance to the target exposure and turnover, never by past returns.",
             "fr": "Plus grande taille avant le premier conflit avec les règles du profil et les limites de l'objectif; classé selon les "
                   "conflits, tensions, preuves manquantes, l'écart à l'exposition visée et le roulement, jamais selon les rendements passés."},
            themes=goal.themes, rank=i, best=i == 1, evidence=evidence))
    return ScenarioSet(scenarios, screened, notes)


def no_change(engine: QuantEngine, profile: m.Profile, goal: m.ExposureGoal, notes: list[dict], evidence=()) -> dict:
    """The current portfolio as the goal's only scenario when no candidate exists: it carries the
    measured exposure, the current rule assessment and the reason, and proposes no move."""
    en = " ".join(n["en"] for n in notes) or "No candidate fits the profile's rules and the goal's limits."
    fr = " ".join(n["fr"] for n in notes) or "Aucun candidat ne respecte les règles du profil et les limites de l'objectif."
    return build_scenario(
        engine, profile, profile.rules, weights_of(profile), [], "sc_goal_no_change", "goal_candidate",
        {"en": "No change: keep the current portfolio", "fr": "Aucun changement : garder le portefeuille actuel"},
        {"en": f"{en} No trade is proposed.", "fr": f"{fr} Aucune transaction n'est proposée."},
        themes=goal.themes, rank=1, best=True, evidence=evidence)


# --- Alternatives --------------------------------------------------------------------------------


def alternatives(engine: QuantEngine, profile: m.Profile, ticker: str, size_pct: float, max_candidates: int = MAX_CANDIDATES,
                 evidence=()) -> ScenarioSet:
    rules, weights, universe = profile.rules, weights_of(profile), engine.universe
    if ticker not in universe:
        return ScenarioSet([], [], [{"en": f"{ticker} is not in the data.", "fr": f"{ticker} est absent des données."}])
    tags = set(universe.get(ticker).themes)
    pool = [a.ticker for a in universe.all() if a.ticker != ticker and tags & set(a.themes) and eligible(engine, rules, a.ticker)]
    options = []
    for t in pool[:MAX_SCREEN]:
        search = max_compatible_size(engine, rules, weights, t, "pro_rata", None, evidence, profile.profile_id, max_size=size_pct)
        size = search.max_size_pct
        if size <= 0:
            continue
        res = apply_move(weights, t, size, "pro_rata")
        c = counts(evaluate(engine, rules, res.weights, (t,), evidence, profile.profile_id))
        options.append(((c["conflict"], c["tension"], c["nee"], round(size_pct - size, 9), t),
                        {"ticker": t, "sizePct": size, "funding": {"mode": "pro_rata"}}))
    options.sort(key=lambda kv: kv[0])
    notes = [] if options else [{"en": "No asset sharing a theme tag fits the profile's rules.",
                                 "fr": "Aucun actif partageant une étiquette thématique ne respecte les règles du profil."}]
    scenarios = []
    for i, (_, move) in enumerate(options[:max_candidates], start=1):
        shared = sorted(tags & set(universe.get(move["ticker"]).themes))
        en, fr = _num(move["sizePct"])
        scenarios.append(build_scenario(
            engine, profile, rules, weights, [move], f"sc_alt_{slug(move['ticker'])}", "alternative",
            {"en": f"Alternative {i}: {en} points into {move['ticker']}", "fr": f"Solution de rechange {i} : {fr} points dans {move['ticker']}"},
            {"en": f"Shares the tag(s) {', '.join(shared)} with {ticker}; a shared tag does not make two assets equivalent (LIM_THEME_TAGS).",
             "fr": f"Partage l'étiquette {', '.join(shared)} avec {ticker}; une étiquette commune ne rend pas deux actifs équivalents (LIM_THEME_TAGS)."},
            themes=shared, rank=i, best=False, evidence=evidence))
    return ScenarioSet(scenarios, pool[:MAX_SCREEN], notes)


# --- Rebalance -----------------------------------------------------------------------------------


def _score(engine: QuantEngine, profile: m.Profile, rules, w: dict[str, float], evidence=()) -> tuple[int, float]:
    view = engine.view(w, "rebalance-scan", 1.0, record=False)
    st = quick_statuses(rules, RuleInputs(view, profile.profile_id, (), tuple(evidence)))
    excess = 0.0
    n = 0
    for r in rules:
        if st.get(r.rule_id) != "conflict":
            continue
        n += 1
        d = rule_def(r.rule_id)
        v = view.measure(d.metric, d.key).value or 0.0
        if r.rule_id == "limit.stress_2022":
            v = max(0.0, -v)
        limit = float(r.threshold or 0.0)
        excess += (v - limit if r.type in ("cap", "limit", "exclude") else limit - v) / max(limit, 1.0)
    return n, excess


def rebalance(engine: QuantEngine, profile: m.Profile, evidence=()) -> ScenarioSet:
    """Bounded greedy search for few, small moves that remove every conflict of the current
    portfolio. Finding none within budget is reported as such; it does not prove none exists."""
    rules, weights, universe = profile.rules, weights_of(profile), engine.universe
    score = _score(engine, profile, rules, weights, evidence)
    if score[0] == 0:
        return ScenarioSet([], [], [{"en": "The current portfolio has no rule conflict; no rebalance is needed.",
                                     "fr": "Le portefeuille actuel n'a aucun conflit de règle; aucun rééquilibrage n'est nécessaire."}])
    cash = f"CASH.{profile.reporting_currency}"
    targets = [t for t in ("XBB.TO", "AGG", "GLD", "XIU.TO", "SPY") if t in universe and eligible(engine, rules, t)] + [cash]
    moves: list[dict] = []
    current = dict(weights)
    for _ in range(REBALANCE_MAX_MOVES):
        view = engine.view(current, "rebalance-scan", 1.0, record=False)
        st = quick_statuses(rules, RuleInputs(view, profile.profile_id, (), tuple(evidence)))
        donors = []
        for r in rules:
            if st.get(r.rule_id) == "conflict" and r.type in ("cap", "exclude"):
                d = rule_def(r.rule_id)
                worst = view.measure(d.metric, d.key).worst
                if worst and worst["type"] == "asset":
                    donors.append(worst["id"])
                elif worst and worst["type"] == "sector":
                    donors += [t for t, a in view.assets.items() if a.asset_class == "equity" and a.sector == worst["id"]]
        donors += [t for t in current if excluded_asset(rules, universe.get(t)) if t not in CASH_TICKERS]
        donors = list(dict.fromkeys(donors))
        best = None
        for target in targets:
            fundings = [{"mode": "pro_rata"}] + [{"mode": "from_holdings", "fromTickers": [d]} for d in donors if d != target]
            for funding in fundings:
                for size in REBALANCE_SIZES:
                    move = {"ticker": target, "sizePct": size, "funding": funding}
                    try:
                        w, _ = apply_moves(current, [move])
                    except FundingError:
                        continue
                    sc = _score(engine, profile, rules, w, evidence)
                    key = (sc, size, target, funding["mode"], tuple(funding.get("fromTickers", ())))
                    if best is None or key < best[0]:
                        best = (key, move, w, sc)
        if best is None or best[3] >= score:
            break
        _, move, current, score = best
        moves.append(move)
        if score[0] == 0:
            break
    if not moves or score[0] != 0:
        return ScenarioSet([], targets, [{"en": "No rebalance within the search budget removes every conflict; this does not prove that none exists.",
                                          "fr": "Aucun rééquilibrage dans le budget de recherche ne supprime tous les conflits; cela ne prouve pas qu'il n'en existe aucun."}])
    scenario = build_scenario(
        engine, profile, rules, weights, moves, "sc_rebalance", "rebalance",
        {"en": f"Rebalance in {len(moves)} move(s)", "fr": f"Rééquilibrage en {len(moves)} mouvement(s)"},
        {"en": "Few, small hypothetical moves toward broad funds, bonds, gold or cash that remove every rule conflict (bounded greedy search).",
         "fr": "Quelques petits mouvements hypothétiques vers des fonds larges, des obligations, de l'or ou de l'encaisse qui suppriment tous les conflits (recherche gloutonne bornée)."},
        rank=1, best=False, evidence=evidence)
    return ScenarioSet([scenario], targets, [])
