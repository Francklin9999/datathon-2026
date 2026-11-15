'use client';
import { useState } from 'react';
import type { Position, Profile, RebalanceResponse } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { FactScopeProvider } from '../../components/common/FactDrawer';
import { SnapshotCompare } from '../../components/run/Results';
import { RuleTable } from '../../components/run/RuleTable';
import { VERDICT, labelOf } from '../../lib/labels';
import { fmtMoney, fmtPct, fmtPts } from '../../lib/format';

export function RebalancePanel({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec } = useApp();
  const [text, setText] = useState(() => profile.portfolio.positions.map(p => `${p.ticker} ${p.weightPct}`).join('\n'));
  const [flow, setFlow] = useState('0');
  const [funding, setFunding] = useState<Awaited<ReturnType<ReturnType<typeof getApiClient>['targetFunding']>> | null>(null);
  const [result, setResult] = useState<RebalanceResponse | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    const positions: Position[] = [];
    const seen = new Set<string>();
    for (const line of text.split('\n').map(x => x.trim()).filter(Boolean)) {
      const [ticker, value, extra] = line.toUpperCase().split(/\s+/);
      const weightPct = Number(value);
      if (!ticker || !value || extra || seen.has(ticker) || !Number.isFinite(weightPct) || weightPct < 0 || weightPct > 100) { setInvalid(true); return; }
      seen.add(ticker); positions.push({ ticker, weightPct });
    }
    if (!positions.length || positions.length > 40 || Math.abs(positions.reduce((s, p) => s + p.weightPct, 0) - 100) > 1e-9) { setInvalid(true); return; }
    setInvalid(false); setError(null); setResult(null); setBusy(true);
    try {
      const financed = await getApiClient().targetFunding({ totalValue: profile.portfolio.totalValue,
        before: Object.fromEntries(profile.portfolio.positions.map(p => [p.ticker, p.weightPct / 100])),
        target: Object.fromEntries(positions.map(p => [p.ticker, p.weightPct / 100])), externalFlow: Number(flow) });
      setFunding(financed);
      setResult(await getApiClient().rebalance({ profileId: profile.profileId, profileVersion: profile.version, positions, window: windowSpec })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Compare a complete target allocation', fr: 'Comparer une répartition cible complète' })}>
    <p>{tr({ en: 'Enter final target weights, one TICKER PERCENT line per holding. Include every asset you plan to retain; an omitted holding is removed. Targets must total 100%. This supports reductions, complete exits and increases at constant fictional capital.', fr: 'Saisissez les poids cibles finaux, une ligne SYMBOLE POURCENTAGE par titre. Incluez tous les actifs conservés; un titre omis est retiré. Total requis : 100 %. Réductions, sorties complètes et augmentations à capital fictif constant.' })}</p>
    <details><summary>{tr({ en: 'Set final targets', fr: 'Définir les cibles finales' })}</summary>
      <form onSubmit={e => { e.preventDefault(); void check(); }}><div className="field"><label htmlFor="rebalance-targets">{tr({ en: 'Final allocation (%)', fr: 'Répartition finale (%)' })}</label><textarea id="rebalance-targets" disabled={busy} rows={7} maxLength={4000} value={text} onChange={e => { setText(e.target.value); setResult(null); setFunding(null); }} /></div>
      <div className="field"><label htmlFor="rebalance-flow">{tr({ en: 'External capital flow: positive = new money, negative = withdrawal, zero = internal funding', fr: 'Flux externe : positif = nouveau capital, négatif = retrait, zéro = financement interne' })} ({profile.reportingCurrency})</label><input id="rebalance-flow" disabled={busy} required type="number" step="any" value={flow} onChange={e => { setFlow(e.target.value); setFunding(null); setResult(null); }} /></div>
      {invalid && <p role="alert">{tr({ en: 'Use unique supported tickers and finite percentages from 0 to 100, totaling exactly 100%. Maximum 40 holdings.', fr: 'Symboles uniques pris en charge; pourcentages finis de 0 à 100, totalisant exactement 100 %. Maximum 40 positions.' })}</p>}
      <button className="btn" disabled={busy}>{busy ? tr({ en: 'Calculating…', fr: 'Calcul…' }) : tr({ en: 'Check target allocation', fr: 'Vérifier la répartition cible' })}</button></form>
    </details>
    {error && <ErrorState error={error} />}
    {result && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic target allocation comparison', fr: 'Comparaison déterministe des cibles' }, facts: result.facts }}>
      <p>{tr({ en: 'Current plan', fr: 'Plan actuel' })}: {labelOf(VERDICT, result.verdictBefore, lang)} → <strong>{tr({ en: 'Target plan', fr: 'Plan cible' })}: {labelOf(VERDICT, result.verdictAfter, lang)}</strong></p>
      {funding && <><dl className="kv-list">{([
        [tr({ en: 'Before capital', fr: 'Capital initial' }), funding.beforeValue],
        [tr({ en: 'After-flow capital', fr: 'Capital après flux' }), funding.afterValue],
        [tr({ en: 'External flow', fr: 'Flux externe' }), funding.externalFlow],
        [tr({ en: 'Modeled purchases', fr: 'Achats modélisés' }), funding.purchases],
        [tr({ en: 'Modeled sales', fr: 'Ventes modélisées' }), funding.sales],
      ] as const).map(([label, value]) => <div className="kv" key={label}><dt className="k">{label}</dt><dd className="v">{fmtMoney(value, profile.reportingCurrency, lang)}</dd></div>)}</dl>
      <p className="small muted">{tr({ en: 'Sales + deposits = purchases + withdrawals. The risk and policy comparison below uses final weights at the original comparison capital; the funding model above separately values the after-flow holdings. No profile or order is changed.', fr: 'Ventes + apports = achats + retraits. La comparaison du risque ci-dessous utilise les poids finaux au capital initial; le modèle ci-dessus valorise séparément le capital après flux. Aucun profil ni ordre n’est modifié.' })}</p></>}
      <SnapshotCompare before={result.portfolioBefore} after={result.portfolioAfter} />
      <div className="table-scroll"><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th><th>{tr({ en: 'Before', fr: 'Avant' })}</th><th>{tr({ en: 'Final target', fr: 'Cible finale' })}</th><th>{tr({ en: 'Change', fr: 'Variation' })}</th></tr></thead><tbody>{result.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtPct(row.beforePct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{fmtPts(row.changePct, lang)}</td></tr>)}</tbody></table></div>
      <RuleTable checks={result.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
      {result.assumptions.map((note, i) => <p className="small muted" key={i}>{tr(note)}</p>)}
    </FactScopeProvider>}
  </Card>;
}
