"""Threshold derivation (optimizer SPEC §2–§3, decisions A-02..A-10). Risk-only inputs: no
historical mean return can influence a threshold."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

from aplomb.contracts import models as m
from aplomb.profiles.defaults import derived_core
from aplomb.profiles.rulebuilder import make_rule, renumber
from aplomb.quant import QuantEngine, Unavailable
from aplomb.quant import metrics as mx
from aplomb.quant.engine import slug
from aplomb.quant.facts import fact_key, make_fact

VOL_BUDGET = {"low": 6.0, "low_moderate": 9.0, "moderate": 12.0, "moderate_high": 16.0, "high": 22.0}  # A-02
DIVERSIFIER_FLOOR = 8.0  # A-10
CAL_REF_MIX = ("XIU.TO", "SPY", "XBB.TO")
REF_MIX_TEXT = "50% XIU.TO + 50% SPY, rest XBB.TO"


def round5(x: float) -> float:
    """Nearest multiple of 5, ties to even (Python ``round``), as in the reference scripts."""
    return 5.0 * round(x / 5.0)


def floor5(x: float) -> float:
    return 5.0 * math.floor(x / 5.0 + 1e-9)


def stress_multiplier(horizon_min: float, horizon_max: float | None) -> tuple[float, float]:
    mid = horizon_min if horizon_max is None else (horizon_min + horizon_max) / 2.0  # open-ended uses min
    return mid, 1.0 if mid <= 5 else (1.25 if mid <= 10 else 1.5)


@dataclass
class Derivation:
    rules: list[dict]
    fact_ids: dict[str, str]
    values: dict[str, float | None]
    issues: list[dict] = field(default_factory=list)


def reference_volatilities(engine: QuantEngine, wr) -> tuple[dict[str, float], dict[str, float], list[str]]:
    """Annualized CAD volatility of starter single stocks and crypto (frozen reference universe)."""
    stocks, crypto, skipped = {}, {}, []
    for a in engine.universe.all():
        if a.tier != "starter" or a.asset_class not in ("equity", "crypto"):
            continue
        try:
            vol = mx.annualized_vol_pct(mx.simple_returns(engine.market.window_levels(a.ticker, wr.i0, wr.i1)))
        except Unavailable:
            skipped.append(a.ticker)
            continue
        (stocks if a.asset_class == "equity" else crypto)[a.ticker] = vol
    return stocks, crypto, skipped


def mix_volatility(engine: QuantEngine, equity_pct: int, wr) -> float:
    e = equity_pct / 100.0
    w = {k: v for k, v in {"XIU.TO": e / 2, "SPY": e / 2, "XBB.TO": 1 - e}.items() if v > 0}
    return mx.annualized_vol_pct(mx.simple_returns(engine.portfolio_levels(w, wr.i0, wr.i1)))


def derive_thresholds(profile: m.Profile, engine: QuantEngine, *, created_at: str, window: dict | None = None) -> Derivation:
    """Derived ``PolicyRule``s (wire dicts, renumbered) and the facts holding their inputs."""
    wr = engine.window(window or {"code": "full"})
    risk = profile.risk_level
    budget = VOL_BUDGET[risk]
    prefs = profile.preferences
    ctx = engine.ctx
    ledger = engine.ledger
    issues: list[dict] = []
    fids: dict[str, str] = {}
    window_spec = wr.spec

    fids["budget.volatility"] = ledger.add_fact(make_fact(
        ctx, key=fact_key("budget.volatility", "portfolio", engine.subject_id, risk, "na"), kind="assumption",
        metric="budget.volatility", label={"en": f"Volatility budget for risk level {risk}", "fr": f"Budget de volatilité, niveau de risque {risk}"},
        value=budget, unit="pct", currency=None, subject={"type": "portfolio", "id": engine.subject_id, "variant": "na"},
        method_id="M_DERIVE_VOL_BUDGET", created_by="optimizer", params={"riskLevel": risk},
        limitations=["LIM_THRESHOLDS_ASSUMED"], checks=[{"code": "lookup", "ok": True, "detail": "A-02 table lookup."}]))

    stocks, crypto, skipped = reference_volatilities(engine, wr)
    if skipped:
        issues.append({"code": "reference_assets_skipped", "detail": ", ".join(sorted(skipped))})
    sigma_stock = statistics.quantiles(sorted(stocks.values()), n=4, method="inclusive")[2] if len(stocks) >= 2 else None
    sigma_crypto = statistics.median(crypto.values()) if crypto else None
    if sigma_stock is not None:
        fids["ref.sigma_single_stock_q3"] = engine.add_series_fact(
            metric="ref.sigma_single_stock_q3", value=sigma_stock, subject={"type": "universe", "id": "starter_single_stocks", "variant": "na"},
            variant_key="na", window_code=wr.code, tickers=sorted(stocks), i0=wr.i0, i1=wr.i1, method_id="M_DERIVE_POSITION_CAP",
            window_spec=window_spec, params={"quantile": "Q3 inclusive", "assets": len(stocks)},
            label={"en": "Upper-quartile volatility of single stocks (starter universe)", "fr": "Volatilité du quartile supérieur des actions (univers de départ)"},
            base_lims=("LIM_SAMPLE_WINDOW", "LIM_SURVIVORSHIP", "LIM_CALENDAR_INTERSECTION", "LIM_THRESHOLDS_ASSUMED"))
    if sigma_crypto is not None:
        fids["ref.sigma_crypto_median"] = engine.add_series_fact(
            metric="ref.sigma_crypto_median", value=sigma_crypto, subject={"type": "universe", "id": "starter_crypto", "variant": "na"},
            variant_key="na", window_code=wr.code, tickers=sorted(crypto), i0=wr.i0, i1=wr.i1, method_id="M_DERIVE_CRYPTO_CAP",
            window_spec=window_spec, params={"statistic": "median", "assets": len(crypto)},
            label={"en": "Median volatility of crypto assets (starter universe)", "fr": "Volatilité médiane des cryptoactifs (univers de départ)"},
            base_lims=("LIM_SAMPLE_WINDOW", "LIM_SURVIVORSHIP", "LIM_CALENDAR_INTERSECTION", "LIM_THRESHOLDS_ASSUMED"))

    # Growth cap: the whole 0..100 grid, because risk can first decrease with equities (A-06).
    growth = None
    try:
        feasible = [e for e in range(0, 101, 5) if mix_volatility(engine, e, wr) <= budget]
        growth = float(max(feasible)) if feasible else None
    except Unavailable as exc:
        issues.append({"code": "reference_mix_unavailable", "detail": exc.detail})
    if growth is None and not any(i["code"] == "reference_mix_unavailable" for i in issues):
        issues.append({"code": "no_feasible_reference_mix",
                       "detail": f"No {REF_MIX_TEXT} mix has volatility within the {budget:g}% budget; growth cap and fixed-income floor not derived."})
    if growth is not None:
        fids["ref.mix_volatility"] = engine.add_series_fact(
            metric="ref.mix_volatility", value=mix_volatility(engine, int(growth), wr),
            subject={"type": "universe", "id": "reference_mix", "variant": f"equity:{int(growth)}"}, variant_key=f"equity:{int(growth)}",
            window_code=wr.code, tickers=list(CAL_REF_MIX), i0=wr.i0, i1=wr.i1, method_id="M_DERIVE_GROWTH_CAP", window_spec=window_spec,
            params={"equityPct": growth, "mix": REF_MIX_TEXT},
            label={"en": f"Volatility of the reference mix at {int(growth)}% equities", "fr": f"Volatilité du mélange de référence à {int(growth)} % d'actions"},
            base_lims=("LIM_SAMPLE_WINDOW", "LIM_BONDS_SAMPLE", "LIM_CONSTANT_WEIGHTS", "LIM_THRESHOLDS_ASSUMED"))

    position = max(5.0, min(25.0, round5(100 * 0.4 * budget / sigma_stock))) if sigma_stock else None
    sector = min(40.0, 2 * position) if position is not None else None
    excluded_crypto = prefs.crypto_interest == "none" or "crypto" in prefs.excluded_asset_classes
    crypto_cap = None
    if not excluded_crypto and sigma_crypto:
        crypto_cap = max(0.0, min(25.0, round5(100 * 0.4 * budget / sigma_crypto)))
        if prefs.crypto_interest == "low" or prefs.avoid_speculative:
            crypto_cap = floor5(crypto_cap / 2)
    mid, mult = stress_multiplier(profile.horizon_years.min, profile.horizon_years.max)
    fi_floor = max(0.0, 100 - growth - 10) if growth is not None and growth < 100 else None
    if position is None:
        issues.append({"code": "reference_stats_unavailable", "detail": "Single-stock reference volatility unavailable; position and sector caps not derived."})

    core = derived_core(risk, budget, mid, mult, position or 0.0, sector or 0.0,
                        growth if growth is not None and growth < 100 else None, fi_floor or None)
    exact_inputs = {
        "cap.position": ("M_DERIVE_POSITION_CAP", "clamp(round5(100 x 0.4 x budgetPct / sigmaStockQ3Pct), 5, 25)",
                         {"budgetPct": budget, "sigmaStockQ3Pct": sigma_stock or 0.0}),
        "cap.sector": ("M_DERIVE_SECTOR_CAP", "min(40, 2 x positionCapPct)", {"positionCapPct": position or 0.0}),
        "cap.growth_assets": ("M_DERIVE_GROWTH_CAP", "max equity share e in 0,5,..,100 with vol(refMix(e)) <= budgetPct",
                              {"budgetPct": budget, "referenceMix": REF_MIX_TEXT}),
        "floor.fixed_income": ("M_DERIVE_GROWTH_CAP", "max(0, 100 - growthCapPct - 10)", {"growthCapPct": growth or 0.0}),
    }

    def deriv(rule_id: str) -> dict:
        base = core[rule_id][1]
        if rule_id in exact_inputs:
            method, formula, inputs = exact_inputs[rule_id]
            base = {**base, "methodId": method, "formula": formula, "inputs": inputs}
        return {**base, "dataVersion": ctx.data_version, "window": window_spec}

    def rule(rule_id: str, threshold, origin: str, rationale: dict, derivation: dict | None) -> dict:
        return make_rule(rule_id, "R1", threshold=threshold, origin=origin, rationale=rationale, derivation=derivation, updated_at=created_at)

    ordered: list[dict] = []
    if position is not None:
        ordered.append(rule("cap.position", position, "derived", core["cap.position"][2], deriv("cap.position")))
        ordered.append(rule("cap.sector", sector, "derived", core["cap.sector"][2], deriv("cap.sector")))
    crypto_rule = None
    if excluded_crypto:
        crypto_rule = rule("exclude.asset_class.crypto", None, "profile_preference",
                           {"en": "The profile shows no interest in crypto assets.", "fr": "Le profil ne montre aucun intérêt pour les cryptoactifs."}, None)
    elif crypto_cap is not None:
        halved = prefs.crypto_interest == "low" or prefs.avoid_speculative
        crypto_rule = rule("cap.asset_class.crypto", crypto_cap, "derived",
                           {"en": "Crypto cap from the volatility budget relative to median crypto volatility" + (", halved for low interest in speculation (A-05)." if halved else " (A-05)."),
                            "fr": "Plafond crypto tiré du budget de volatilité rapporté à la volatilité médiane des cryptos" + (", réduit de moitié faute d'intérêt pour la spéculation (A-05)." if halved else " (A-05).")},
                           {"methodId": "M_DERIVE_CRYPTO_CAP",
                            "formula": "clamp(round5(100 x 0.4 x budgetPct / sigmaCryptoMedianPct), 0, 25)" + (" halved, floor5" if halved else ""),
                            "inputs": {"budgetPct": budget, "sigmaCryptoMedianPct": sigma_crypto, "halved": "true" if halved else "false"},
                            "dataVersion": ctx.data_version, "window": window_spec})
    if growth is not None and growth < 100:
        ordered.append(rule("cap.growth_assets", growth, "derived", core["cap.growth_assets"][2], deriv("cap.growth_assets")))
        if fi_floor:
            ordered.append(rule("floor.fixed_income", fi_floor, "derived", core["floor.fixed_income"][2], deriv("floor.fixed_income")))
    elif growth is not None:  # growth cap 100%: crypto cap and the diversification floor take these slots
        if crypto_rule is not None and crypto_rule["ruleId"] == "cap.asset_class.crypto":
            ordered.append(crypto_rule)
            crypto_rule = None
        if prefs.wants_diversification:
            ordered.append(rule("floor.diversifiers", DIVERSIFIER_FLOOR, "profile_preference",
                                {"en": "The profile wants some diversification; the 8% level is a team assumption (A-10).",
                                 "fr": "Le profil souhaite une certaine diversification; le niveau de 8 % est une hypothèse de l'équipe (A-10)."}, None))
    for rid in ("limit.volatility", "limit.stress_2022", "limit.drawdown"):
        ordered.append(rule(rid, core[rid][0], "derived", core[rid][2], deriv(rid)))
    if crypto_rule is not None:
        ordered.append(crypto_rule)
    for sector_label in prefs.excluded_sectors:
        ordered.append(rule(f"exclude.sector.{slug(sector_label)}", None, "profile_preference",
                            {"en": f"The profile excludes the {sector_label} sector.", "fr": f"Le profil exclut le secteur {sector_label}."}, None))
    if prefs.avoid_controversies:
        ordered.append(rule("evidence.controversy", None, "profile_preference",
                            {"en": "The profile avoids companies with significant controversies; this needs outside evidence.",
                             "fr": "Le profil évite les sociétés aux controverses importantes; cela exige des preuves externes."}, None))
    from aplomb.profiles.defaults import SYSTEM_RATIONALE

    for rid in ("flag.attention", "flag.rate_cycle", "sim.only"):
        ordered.append(rule(rid, None, "system", SYSTEM_RATIONALE[rid], None))
    values = {"budgetPct": budget, "sigmaStockQ3Pct": sigma_stock, "sigmaCryptoMedianPct": sigma_crypto, "positionCapPct": position,
              "sectorCapPct": sector, "cryptoCapPct": crypto_cap, "growthCapPct": growth, "fixedIncomeFloorPct": fi_floor,
              "stressMultiplier": mult, "horizonMidpointYears": mid}
    return Derivation(renumber(ordered), fids, values, issues)
