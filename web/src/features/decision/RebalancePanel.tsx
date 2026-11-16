'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Profile, RebalanceResponse, WindowSpec } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { FactScopeProvider } from '../../components/common/FactDrawer';
import { SnapshotCompare } from '../../components/run/Results';
import { RuleTable } from '../../components/run/RuleTable';
import { VERDICT, labelOf } from '../../lib/labels';
import { blendFinalTargets, parseFinalTargets } from '../../lib/targetAllocation';
import { checkTickers, targetLineTickers } from '../../lib/tickerCoverage';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { SupportedUniverse } from '../../components/common/SupportedUniverse';
import { fmtMoney, fmtPct, fmtPts } from '../../lib/format';

type TargetFunding = Awaited<ReturnType<ReturnType<typeof getApiClient>['targetFunding']>>;
/** Errors thrown before any request by parseFinalTargets/blendFinalTargets or the flow check: the user's input, not the network. */
const LOCAL_INPUT_ERRORS = ['invalid_target', 'invalid_target_sum', 'invalid_progress', 'too_many_blended_holdings', 'invalid_weight_sum', 'invalid_flow'];
const isLocalInputError = (e: unknown) => e instanceof Error && LOCAL_INPUT_ERRORS.includes(e.message);

export function RebalancePanel({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec, feature } = useApp();
  const [text, setText] = useState(() => profile.portfolio.positions.map(p => `${p.ticker} ${p.weightPct}`).join('\n'));
  // Target tickers are checked against the snapshot before any request (/rebalance refuses them after).
  const universe = useAssetUniverse();
  const tickerCheck = checkTickers(targetLineTickers(text), universe, feature('on_demand_tickers'));
  const blocked = tickerCheck.blocking;
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
  const compareSizes = async () => {
    if (blocked) return;
    setSizesBusy(true); setInvalid(false); setError(null); setSizes([]);
    try {
      const compared = [];
      for (const pct of [0, 25, 50, 75, 100]) { const { financed, checked } = await calculate(pct); compared.push({ progress: pct, result: checked, funding: financed }); }
      setSizes(compared);
    } catch (e) { if (isLocalInputError(e)) setInvalid(true); else setError(asApiError(e)); } finally { setSizesBusy(false); }
  };
  return <Card title={tr({ en: 'Compare a complete target allocation', fr: 'Comparer une répartition cible complète' })}>
    <p>{tr({ en: 'Enter final target weights, one TICKER PERCENT line per holding. Include every asset you plan to retain; an omitted holding is removed. Targets must total 100%. This supports reductions, complete exits and increases at constant fictional capital.', fr: 'Saisissez les poids cibles finaux, une ligne SYMBOLE POURCENTAGE par titre. Incluez tous les actifs conservés; un titre omis est retiré. Total requis : 100 %. Réductions, sorties complètes et augmentations à capital fictif constant.' })}</p>
    <details><summary>{tr({ en: 'Set final targets', fr: 'Définir les cibles finales' })}</summary>
      <form onSubmit={e => { e.preventDefault(); if (blocked) return; if (autoPreview) void check(); else setAutoPreview(true); }}><div className="field"><label htmlFor="rebalance-targets">{tr({ en: 'Final allocation (%)', fr: 'Répartition finale (%)' })}</label><textarea id="rebalance-targets" disabled={sizesBusy} rows={7} maxLength={4000} value={text} onChange={e => { setText(e.target.value); setResult(null); setFunding(null); setSizes([]); }}
        aria-invalid={blocked} aria-describedby={`${tickerCheck.message ? 'rebalance-targets-issue ' : ''}rebalance-targets-universe`} />
        {tickerCheck.message && <span id="rebalance-targets-issue" className={blocked ? 'field-error' : 'hint'}>{tr(tickerCheck.message)}</span>}
        <SupportedUniverse id="rebalance-targets-universe" /></div>
      <div className="field"><label htmlFor="rebalance-flow">{tr({ en: 'External capital flow: positive = new money, negative = withdrawal, zero = internal funding', fr: 'Flux externe : positif = nouveau capital, négatif = retrait, zéro = financement interne' })} ({profile.reportingCurrency})</label><input id="rebalance-flow" disabled={sizesBusy} required type="number" step="any" value={flow} onChange={e => { setFlow(e.target.value); setFunding(null); setResult(null); setSizes([]); }} /></div>
      <div className="field"><label htmlFor="rebalance-progress">{tr({ en: 'Progress from current weights to entered targets', fr: 'Progression des poids actuels vers les cibles saisies' })}: {progress}%</label><input id="rebalance-progress" type="range" min={0} max={100} step={1} disabled={sizesBusy} value={progress} onChange={e => { setProgress(Number(e.target.value)); setResult(null); setFunding(null); setAutoPreview(true); }} /></div>
      <p className="small muted">{tr({ en: '0% keeps current weights; 100% uses the complete entered targets. Each slider adjustment recalculates by code without an AI run. External flow applies separately at every point. Compatibility can vary non-monotonically; these are evaluated points, not a maximum compatible-size bound.', fr: '0 % conserve les poids actuels; 100 % utilise toutes les cibles saisies. Chaque ajustement recalcule par code, sans analyse IA. Le flux externe s’applique séparément à chaque point. La compatibilité peut varier de façon non monotone; aucun plafond de taille compatible n’est déduit.' })}</p>
      {invalid && <p role="alert">{tr({ en: 'Use unique supported tickers and finite percentages from 0 to 100, totaling exactly 100%. Maximum 40 holdings.', fr: 'Symboles uniques pris en charge; pourcentages finis de 0 à 100, totalisant exactement 100 %. Maximum 40 positions.' })}</p>}
      <button className="btn" disabled={busy || sizesBusy || blocked}>{busy ? tr({ en: 'Calculating…', fr: 'Calcul…' }) : tr({ en: 'Check target allocation', fr: 'Vérifier la répartition cible' })}</button><button type="button" className="btn ghost" disabled={sizesBusy || busy || blocked} onClick={() => void compareSizes()}>{tr({ en: 'Compare 0 / 25 / 50 / 75 / 100%', fr: 'Comparer 0 / 25 / 50 / 75 / 100 %' })}</button></form>
    </details>
    {error && <ErrorState error={error} />}
    {!!sizes.length && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Deterministic size comparison', fr: 'Comparaison déterministe des tailles' })}><table><thead><tr><th>{tr({ en: 'Target progress', fr: 'Progression vers la cible' })}</th><th>{tr({ en: 'Verdict', fr: 'Verdict' })}</th><th>{tr({ en: 'Volatility', fr: 'Volatilité' })}</th><th>{tr({ en: 'Drawdown', fr: 'Baisse maximale' })}</th><th>{tr({ en: 'Modeled purchases', fr: 'Achats modélisés' })} ({profile.reportingCurrency})</th><th>{tr({ en: 'Modeled sales', fr: 'Ventes modélisées' })} ({profile.reportingCurrency})</th></tr></thead><tbody>{sizes.map(row => <tr key={row.progress}><th scope="row">{row.progress}%</th><td>{labelOf(VERDICT, row.result.verdictAfter, lang)}</td><td>{row.result.portfolioAfter.metrics.volatilityPct === null ? '—' : fmtPct(row.result.portfolioAfter.metrics.volatilityPct, lang)}</td><td>{row.result.portfolioAfter.metrics.maxDrawdownPct === null ? '—' : fmtPct(row.result.portfolioAfter.metrics.maxDrawdownPct, lang)}</td><td>{fmtMoney(row.funding.purchases, profile.reportingCurrency, lang)}</td><td>{fmtMoney(row.funding.sales, profile.reportingCurrency, lang)}</td></tr>)}</tbody></table></div>}

    {result && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic target allocation comparison', fr: 'Comparaison déterministe des cibles' }, facts: result.facts }}>
      <p>{tr({ en: 'Current plan', fr: 'Plan actuel' })}: {labelOf(VERDICT, result.verdictBefore, lang)} → <strong>{tr({ en: 'Target plan', fr: 'Plan cible' })}: {labelOf(VERDICT, result.verdictAfter, lang)}</strong></p>
      {funding && <><dl className="kv-list">{([
        [tr({ en: 'Before capital', fr: 'Capital initial' }), funding.beforeValue],
        [tr({ en: 'After-flow capital', fr: 'Capital après flux' }), funding.afterValue],
        [tr({ en: 'External flow', fr: 'Flux externe' }), funding.externalFlow],
        [tr({ en: 'Modeled purchases', fr: 'Achats modélisés' }), funding.purchases],
        [tr({ en: 'Modeled sales', fr: 'Ventes modélisées' }), funding.sales],
      ] as const).map(([label, value]) => <div className="kv" key={label}><dt className="k">{label}</dt><dd className="v">{fmtMoney(value, profile.reportingCurrency, lang)}</dd></div>)}</dl>
      {!!funding.changes.length && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Modeled money change per holding after the external flow', fr: 'Variation monétaire modélisée par position après le flux externe' })}><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th><th>{tr({ en: 'Before value', fr: 'Valeur initiale' })} ({profile.reportingCurrency})</th><th>{tr({ en: 'After-flow target value', fr: 'Valeur cible après flux' })} ({profile.reportingCurrency})</th><th>{tr({ en: 'Modeled change', fr: 'Variation modélisée' })} ({profile.reportingCurrency})</th></tr></thead><tbody>{funding.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtMoney(row.beforeValue, profile.reportingCurrency, lang)}</td><td>{fmtMoney(row.targetValue, profile.reportingCurrency, lang)}</td><td>{fmtMoney(row.changeValue, profile.reportingCurrency, lang)}</td></tr>)}</tbody></table></div>}
      {funding.assumptions.map((note, i) => <p className="small muted" key={`funding-${i}`}>{note}</p>)}
      <p className="small muted">{tr({ en: 'Sales + deposits = purchases + withdrawals. The risk and policy comparison below uses final weights at the original comparison capital; the funding model above separately values the after-flow holdings. No profile or order is changed.', fr: 'Ventes + apports = achats + retraits. La comparaison du risque ci-dessous utilise les poids finaux au capital initial; le modèle ci-dessus valorise séparément le capital après flux. Aucun profil ni ordre n’est modifié.' })}</p></>}
      <SnapshotCompare before={result.portfolioBefore} after={result.portfolioAfter} />
      <div className="table-scroll"><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th><th>{tr({ en: 'Before', fr: 'Avant' })}</th><th>{tr({ en: 'Final target', fr: 'Cible finale' })}</th><th>{tr({ en: 'Change', fr: 'Variation' })}</th></tr></thead><tbody>{result.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtPct(row.beforePct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{fmtPts(row.changePct, lang)}</td></tr>)}</tbody></table></div>
      <RuleTable checks={result.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
      {result.assumptions.map((note, i) => <p className="small muted" key={i}>{tr(note)}</p>)}
    </FactScopeProvider>}
  </Card>;
}
