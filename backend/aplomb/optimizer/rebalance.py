"""Deterministic complete target allocations. Constant capital, no order or tax/cost model."""
import math

from aplomb.api.errors import Conflict, NotFound, ServiceError
from aplomb.contracts import api as a
from aplomb.quant import LocalLedger, QuantEngine, Unavailable
from aplomb.rules.engine import RuleEngine, RuleInputs, verdict_of


def check_targets(profiles, snapshot, session_id, request: a.RebalanceRequest, now):
    profile = profiles.get(session_id, request.profile_id)
    if profile.version != request.profile_version:
        raise Conflict('Profile changed; refresh before comparing target allocations')
    positions = request.positions
    if len({p.ticker for p in positions}) != len(positions):
        raise ServiceError('validation_error', 'Each target security may appear only once')
    total = math.fsum(p.weight_pct for p in positions)
    if not math.isclose(total, 100, rel_tol=0, abs_tol=1e-9):
        raise ServiceError('validation_error', 'Final target weights must sum to 100%', {'sum': total})
    gate = snapshot.gate(snapshot.data_as_of, 'current')
    universe = gate.universe()
    for position in positions:
        if position.ticker not in universe:
            raise NotFound(f'Unsupported target security: {position.ticker}')
    before = {p.ticker: p.weight_pct / 100 for p in profile.portfolio.positions if p.weight_pct > 0}
    after = {p.ticker: p.weight_pct / 100 for p in positions if p.weight_pct > 0}
    ledger = LocalLedger()
    window = request.window.to_wire() if request.window else {'code': 'full'}
    engine = QuantEngine(gate, ledger, currency=profile.reporting_currency, subject_id=profile.profile_id,
                         created_at=now, window=window)
    try:
        engine.window(window)
    except Unavailable as exc:
        raise ServiceError('insufficient_data', exc.detail) from exc
    views = [engine.view(before, 'before', profile.portfolio.total_value, window=window),
             engine.view(after, 'target', profile.portfolio.total_value, window=window, after_move=True)]
    increased = tuple(t for t, w in after.items() if w > before.get(t, 0) + 1e-12)
    outcomes = [RuleEngine(ledger, engine.ctx).check_rules(profile.rules,
        RuleInputs(view, profile.profile_id, () if i == 0 else increased)) for i, view in enumerate(views)]
    verdicts = [verdict_of(outcome) for outcome in outcomes]
    snapshots = [view.snapshot() for view in views]
    changes = [{'ticker': ticker, 'beforePct': before.get(ticker, 0) * 100,
                'targetPct': after.get(ticker, 0) * 100,
                'changePct': (after.get(ticker, 0) - before.get(ticker, 0)) * 100}
               for ticker in sorted(set(before) | set(after))]
    assumptions = [
        {'en': 'Weights are final target percentages, including all retained assets. Omitted securities have a zero target. Capital is unchanged; no financing or leverage is assumed.',
         'fr': 'Les poids sont les pourcentages cibles finaux, incluant tous les actifs conservés. Un titre omis a une cible nulle. Capital inchangé; aucun financement ni levier supposé.'},
        {'en': 'Frictionless hypothetical rebalance: transaction costs, spreads, taxes, market impact, lot sizes and liquidity are not modeled. No orders are placed.',
         'fr': 'Rééquilibrage hypothétique sans friction : frais, écarts, fiscalité, impact de marché, lots et liquidité ne sont pas modélisés. Aucun ordre transmis.'},
        {'en': 'Deterministic calculations and policy checks only. No research agent or independent model review ran; missing controversy and external evidence remain insufficient.',
         'fr': 'Calculs et règles déterministes seulement. Aucun agent de recherche ni examen indépendant par modèle; les controverses et preuves externes manquantes restent insuffisantes.'},
    ]
    return a.RebalanceResponse.model_validate({'profileId': profile.profile_id, 'profileVersion': profile.version,
        'currency': profile.reporting_currency, 'totalValue': profile.portfolio.total_value,
        'dataVersion': snapshot.data_version, 'asOf': snapshot.data_as_of, 'window': window,
        'changes': changes, 'portfolioBefore': snapshots[0].to_wire(), 'portfolioAfter': snapshots[1].to_wire(),
        'verdictBefore': verdicts[0][0], 'verdictAfter': verdicts[1][0],
        'countsBefore': verdicts[0][1].to_wire(), 'countsAfter': verdicts[1][1].to_wire(),
        'ruleChecksBefore': [c.to_wire() for c in outcomes[0]],
        'ruleChecksAfter': [c.to_wire() for c in outcomes[1]], 'facts': ledger.wire(), 'assumptions': assumptions})
