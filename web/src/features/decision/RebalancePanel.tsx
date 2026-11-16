'use client';
/**
 * The instant target check inside the Decision Desk "Target allocation" card: final target weights
 * (entered in the card) checked by code with /target-funding and /rebalance, one point at a time on
 * the path from today's weights, or five points 0 to 100% side by side. No AI is involved.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Profile, RebalanceResponse, WindowSpec } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { ErrorState } from '../../components/common/States';
import { Note } from '../../components/common/Note';
import { FactScopeProvider } from '../../components/common/FactDrawer';
import { SnapshotCompare } from '../../components/run/Results';
import { RuleTable } from '../../components/run/RuleTable';
import { VERDICT, labelOf } from '../../lib/labels';
import { blendFinalTargets, parseFinalTargets } from '../../lib/targetAllocation';
import { fmtMoney, fmtPct, fmtPts } from '../../lib/format';

type TargetFunding = Awaited<ReturnType<ReturnType<typeof getApiClient>['targetFunding']>>;
/** Errors thrown before any request by parseFinalTargets/blendFinalTargets or the flow check: the user's input, not the network. */
const LOCAL_INPUT_ERRORS = ['invalid_target', 'invalid_target_sum', 'invalid_progress', 'too_many_blended_holdings', 'invalid_weight_sum', 'invalid_flow'];
const isLocalInputError = (e: unknown) => e instanceof Error && LOCAL_INPUT_ERRORS.includes(e.message);
const STEPS = [0, 25, 50, 75, 100] as const;

export function RebalancePanel({ profile, text, blocked, onBusy }: {
  profile: Profile;
  /** The final targets typed in the card, one "TICKER PERCENT" line per holding. */
  text: string;
  /** The target tickers failed the snapshot check: nothing is sent. */
  blocked: boolean;
  /** Told while the five-point comparison runs, so the card can lock the targets meanwhile. */
  onBusy?: (busy: boolean) => void;
}) {
  const { tr, lang, windowSpec } = useApp();
  const currency = profile.reportingCurrency;
  const [progress, setProgress] = useState(100);
  const [autoPreview, setAutoPreview] = useState(false);
  const [sizes, setSizes] = useState<{ progress: number; result: RebalanceResponse; funding: TargetFunding }[]>([]);
  const [sizesBusy, setSizesBusy] = useState(false);
  const sequence = useRef(0);
  const windowKey = JSON.stringify(windowSpec);
  const [flow, setFlow] = useState('0');
  const [funding, setFunding] = useState<TargetFunding | null>(null);
  const [result, setResult] = useState<RebalanceResponse | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  // Edited targets drop the figures computed for the previous ones.
  const [shownFor, setShownFor] = useState(text);
  if (shownFor !== text) {
    setShownFor(text);
    setResult(null); setFunding(null); setSizes([]); setInvalid(false); setError(null);
  }
  const clear = () => { setResult(null); setFunding(null); setSizes([]); };
  const calculate = useCallback(async (pct: number, signal?: AbortSignal) => {
    const positions = blendFinalTargets(profile.portfolio.positions, parseFinalTargets(text), pct);
    if (!flow.trim() || !Number.isFinite(Number(flow))) throw new Error('invalid_flow');
    const financed = await getApiClient().targetFunding({ totalValue: profile.portfolio.totalValue,
      before: Object.fromEntries(profile.portfolio.positions.map(p => [p.ticker, p.weightPct / 100])),
      target: Object.fromEntries(positions.map(p => [p.ticker, p.weightPct / 100])), externalFlow: Number(flow) });
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const checked = await getApiClient().rebalance({ profileId: profile.profileId, profileVersion: profile.version,
      positions, window: JSON.parse(windowKey) as WindowSpec }, signal);
    return { financed, checked };
  }, [profile, text, flow, windowKey]);
  const check = useCallback(async (signal?: AbortSignal) => {
    const request = ++sequence.current;
    setInvalid(false); setError(null); setResult(null); setBusy(true);
    try {
      const { financed, checked } = await calculate(progress, signal);
      if (request === sequence.current && !signal?.aborted) { setFunding(financed); setResult(checked); }
    } catch (e) {
      if (request === sequence.current && !signal?.aborted) {
        if (isLocalInputError(e)) setInvalid(true);
        else setError(asApiError(e));
      }
    } finally { if (request === sequence.current) setBusy(false); }
  }, [calculate, progress]);
  useEffect(() => {
    if (!autoPreview || blocked) return;
    const controller = new AbortController();
    const timer = setTimeout(() => { void check(controller.signal); }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [autoPreview, blocked, check]);
  useEffect(() => { onBusy?.(sizesBusy); }, [onBusy, sizesBusy]);
  const compareSizes = async () => {
    if (blocked) return;
    setSizesBusy(true); setInvalid(false); setError(null); setSizes([]);
    try {
      const compared = [];
      for (const pct of STEPS) { const { financed, checked } = await calculate(pct); compared.push({ progress: pct, result: checked, funding: financed }); }
      setSizes(compared);
    } catch (e) { if (isLocalInputError(e)) setInvalid(true); else setError(asApiError(e)); } finally { setSizesBusy(false); }
  };
  const money = (value: number) => fmtMoney(value, currency, lang);
  return (
    <section className="target-section" aria-labelledby="target-check-title">
      <h3 className="h4" id="target-check-title">{tr({ en: 'Instant check', fr: 'Vérification instantanée' })}</h3>
      <p className="small muted">{tr({ en: 'Computed by code against the plan’s rules. No AI is involved.', fr: 'Calculée par le code selon les règles du plan. Aucune IA n’intervient.' })}</p>
      <form onSubmit={e => { e.preventDefault(); if (blocked) return; if (autoPreview) void check(); else setAutoPreview(true); }}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="rebalance-flow">{tr({ en: `Money added or withdrawn (${currency})`, fr: `Argent ajouté ou retiré (${currency})` })}</label>
            <input id="rebalance-flow" disabled={sizesBusy} required type="number" step="any" value={flow} aria-describedby="rebalance-flow-hint"
              onChange={e => { setFlow(e.target.value); clear(); }} />
            <span id="rebalance-flow-hint" className="hint">{tr({ en: 'Positive adds new money, negative withdraws, 0 funds the change from the holdings.', fr: 'Positif ajoute du capital, négatif retire, 0 finance le changement à partir des positions.' })}</span>
          </div>
          <div className="field">
            <label htmlFor="rebalance-progress">{tr({ en: 'How far toward the targets', fr: 'Avancement vers les cibles' })}: {progress}%</label>
            <input id="rebalance-progress" type="range" min={0} max={100} step={1} disabled={sizesBusy} value={progress} aria-describedby="rebalance-progress-hint"
              aria-valuetext={`${progress}%`}
              onChange={e => { setProgress(Number(e.target.value)); setResult(null); setFunding(null); setAutoPreview(true); }} />
            <span id="rebalance-progress-hint" className="hint">{tr({ en: '0% keeps today’s weights, 100% uses the targets. Each change is checked again by code.', fr: '0 % garde les poids actuels, 100 % applique les cibles. Chaque changement est revérifié par le code.' })}</span>
          </div>
        </div>
        {invalid && <p className="field-error" role="alert">{tr({ en: 'Use unique supported tickers and percentages from 0 to 100 that total exactly 100%, at most 40 holdings, and a number for the money added or withdrawn.', fr: 'Utilisez des symboles uniques pris en charge et des pourcentages de 0 à 100 totalisant exactement 100 %, au plus 40 positions, et un nombre pour l’argent ajouté ou retiré.' })}</p>}
        <div className="row-actions">
          <button className="btn" disabled={busy || sizesBusy || blocked}>{busy ? tr({ en: 'Checking…', fr: 'Vérification…' }) : tr({ en: 'Check this allocation', fr: 'Vérifier cette allocation' })}</button>
          <button type="button" className="btn ghost" disabled={sizesBusy || busy || blocked} onClick={() => void compareSizes()}>
            {sizesBusy ? tr({ en: 'Comparing…', fr: 'Comparaison…' }) : tr({ en: 'Compare 0 to 100%', fr: 'Comparer de 0 à 100 %' })}
          </button>
        </div>
      </form>
      {error && <ErrorState error={error} />}
      {!!sizes.length && <>
        <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Five points from today’s weights to the targets', fr: 'Cinq points des poids actuels aux cibles' })}>
          <table className="data-table"><thead><tr>
            <th scope="col">{tr({ en: 'Toward targets', fr: 'Vers les cibles' })}</th><th scope="col">{tr({ en: 'Verdict', fr: 'Verdict' })}</th>
            <th scope="col">{tr({ en: 'Volatility', fr: 'Volatilité' })}</th><th scope="col">{tr({ en: 'Drawdown', fr: 'Baisse maximale' })}</th>
            <th scope="col">{tr({ en: 'Modeled purchases', fr: 'Achats modélisés' })} ({currency})</th><th scope="col">{tr({ en: 'Modeled sales', fr: 'Ventes modélisées' })} ({currency})</th>
          </tr></thead><tbody>{sizes.map(row => <tr key={row.progress}>
            <th scope="row">{row.progress}%</th><td>{labelOf(VERDICT, row.result.verdictAfter, lang)}</td>
            <td>{row.result.portfolioAfter.metrics.volatilityPct === null ? '—' : fmtPct(row.result.portfolioAfter.metrics.volatilityPct, lang)}</td>
            <td>{row.result.portfolioAfter.metrics.maxDrawdownPct === null ? '—' : fmtPct(row.result.portfolioAfter.metrics.maxDrawdownPct, lang)}</td>
            <td>{money(row.funding.purchases)}</td><td>{money(row.funding.sales)}</td>
          </tr>)}</tbody></table>
        </div>
        <Note>{tr({ en: 'These are five checked points, not a limit: compatibility can change in either direction along the path.', fr: 'Ce sont cinq points vérifiés, pas une limite : la compatibilité peut varier dans les deux sens le long du chemin.' })}</Note>
      </>}

      {result && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic target allocation comparison', fr: 'Comparaison déterministe des cibles' }, facts: result.facts }}>
        <p>{tr({ en: 'Current plan', fr: 'Plan actuel' })}: {labelOf(VERDICT, result.verdictBefore, lang)} → <strong>{tr({ en: 'Target plan', fr: 'Plan cible' })}: {labelOf(VERDICT, result.verdictAfter, lang)}</strong></p>
        <SnapshotCompare before={result.portfolioBefore} after={result.portfolioAfter} />
        <RuleTable checks={result.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
        <details className="fold">
          <summary>{tr({ en: 'Weights and money per holding', fr: 'Poids et montants par position' })}</summary>
          <div className="fold-body">
            <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Target weight changes', fr: 'Variations des poids cibles' })}>
              <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Holding', fr: 'Position' })}</th><th scope="col">{tr({ en: 'Before', fr: 'Avant' })}</th><th scope="col">{tr({ en: 'Final target', fr: 'Cible finale' })}</th><th scope="col">{tr({ en: 'Change', fr: 'Variation' })}</th></tr></thead>
                <tbody>{result.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtPct(row.beforePct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{fmtPts(row.changePct, lang)}</td></tr>)}</tbody></table>
            </div>
            {funding && <>
              <dl className="kv-list">{([
                [tr({ en: 'Capital before', fr: 'Capital initial' }), funding.beforeValue],
                [tr({ en: 'Capital after the flow', fr: 'Capital après flux' }), funding.afterValue],
                [tr({ en: 'Money added or withdrawn', fr: 'Argent ajouté ou retiré' }), funding.externalFlow],
                [tr({ en: 'Modeled purchases', fr: 'Achats modélisés' }), funding.purchases],
                [tr({ en: 'Modeled sales', fr: 'Ventes modélisées' }), funding.sales],
              ] as const).map(([label, value]) => <div className="kv" key={label}><dt className="k">{label}</dt><dd className="v">{money(value)}</dd></div>)}</dl>
              {!!funding.changes.length && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Modeled money change per holding after the flow', fr: 'Variation monétaire modélisée par position après le flux' })}>
                <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Holding', fr: 'Position' })}</th><th scope="col">{tr({ en: 'Value before', fr: 'Valeur initiale' })} ({currency})</th><th scope="col">{tr({ en: 'Target value after the flow', fr: 'Valeur cible après flux' })} ({currency})</th><th scope="col">{tr({ en: 'Modeled change', fr: 'Variation modélisée' })} ({currency})</th></tr></thead>
                  <tbody>{funding.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{money(row.beforeValue)}</td><td>{money(row.targetValue)}</td><td>{money(row.changeValue)}</td></tr>)}</tbody></table>
              </div>}
              {funding.assumptions.map((note, i) => <p className="small muted" key={`funding-${i}`}>{note}</p>)}
              <p className="small muted">{tr({ en: 'Sales plus deposits equal purchases plus withdrawals. The rule check uses the final weights at today’s capital; the money above values the holdings after the flow. No plan or order is changed.', fr: 'Ventes plus apports égalent achats plus retraits. La vérification des règles utilise les poids finaux au capital actuel ; les montants ci-dessus valorisent les positions après le flux. Aucun plan ni ordre n’est modifié.' })}</p>
            </>}
            {result.assumptions.map((note, i) => <p className="small muted" key={i}>{tr(note)}</p>)}
          </div>
        </details>
      </FactScopeProvider>}
    </section>
  );
}
