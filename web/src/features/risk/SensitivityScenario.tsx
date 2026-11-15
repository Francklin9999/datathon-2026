'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import type { SensitivityScenarioRequest, SensitivityScenarioResult } from '../../api/riskModels';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtSignedPct } from '../../lib/format';

export function SensitivityScenario({ profile }: { profile: Profile }) {
  const { tr, lang, meta } = useApp();
  const [kind, setKind] = useState<SensitivityScenarioRequest['shock']['kind']>('interest_rate');
  const [key, setKey] = useState('');
  const [change, setChange] = useState('');
  const [assumption, setAssumption] = useState('');
  const [asOf, setAsOf] = useState(meta?.dataAsOf ?? '');
  const [inputs, setInputs] = useState<Record<string, { value: string; source: string }>>({});
  const [result, setResult] = useState<SensitivityScenarioResult | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const rate = kind === 'interest_rate' || kind === 'credit_spread';
  const clear = () => { setResult(null); setError(null); };
  const calculate = async () => {
    setBusy(true); clear();
    const sensitivities = Object.fromEntries(Object.entries(inputs).filter(([, v]) => v.value.trim() && v.source.trim()).map(([ticker, v]) => [ticker, { value: Number(v.value), source: v.source.trim(), asOf }]));
    try { setResult(await getApiClient().sensitivityScenario({ asOf, weights: Object.fromEntries(profile.portfolio.positions.map(p => [p.ticker, p.weightPct / 100])), shock: { kind, key, change: Number(change), assumption }, sensitivities })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Explicit-input sensitivity scenario', fr: 'Scénario de sensibilité à entrées explicites' })}>
    <p>{tr({ en: 'Apply one disclosed linear shock to current weights. Supply signed sensitivities with a source or a clearly stated hypothetical assumption. Blank inputs remain unknown; no full portfolio impact is reported when a holding lacks evidence. For rates/spreads, enter negative modified duration; other models use signed beta. Rate/spread shocks use basis points; others use decimal fractions (0.10 = 10%).', fr: 'Appliquez un choc linéaire aux pondérations actuelles. Indiquez les sensibilités signées avec une source ou une hypothèse explicite. Une entrée vide reste inconnue; aucun impact total n’est présenté si une position manque de données. Pour les taux et écarts, utilisez la duration modifiée négative; les autres modèles utilisent un bêta signé. Chocs de taux en points de base; autres chocs en fractions (0,10 = 10 %).' })}</p>
    <form onSubmit={e => { e.preventDefault(); void calculate(); }}><fieldset disabled={busy}><div className="form-grid">
      <div className="field"><label htmlFor="shock-kind">{tr({ en: 'Shock model', fr: 'Modèle de choc' })}</label><select id="shock-kind" value={kind} onChange={e => { setKind(e.target.value as typeof kind); setInputs({}); clear(); }}>{['interest_rate', 'credit_spread', 'currency', 'commodity', 'factor'].map(k => <option key={k} value={k}>{k.replaceAll('_', ' ')}</option>)}</select></div>
      <div className="field"><label htmlFor="shock-key">{tr({ en: 'Curve, currency, commodity or factor identifier', fr: 'Identifiant de courbe, devise, matière ou facteur' })}</label><input id="shock-key" required maxLength={120} value={key} onChange={e => { setKey(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="shock-change">{tr({ en: 'Shock change', fr: 'Variation du choc' })} ({rate ? 'bp' : tr({ en: 'fraction', fr: 'fraction' })})</label><input id="shock-change" required type="number" step="any" value={change} onChange={e => { setChange(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="shock-asof">{tr({ en: 'Input as-of date', fr: 'Date des entrées' })}</label><input id="shock-asof" required type="date" value={asOf} onChange={e => { setAsOf(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="shock-assumption">{tr({ en: 'Scenario assumption and limitations', fr: 'Hypothèse et limites du scénario' })}</label><textarea id="shock-assumption" required maxLength={1000} value={assumption} onChange={e => { setAssumption(e.target.value); clear(); }} /></div>
    </div><div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Holding sensitivity inputs', fr: 'Sensibilités par position' })}><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th><th>{tr({ en: 'Signed sensitivity', fr: 'Sensibilité signée' })}</th><th>{tr({ en: 'Source or hypothetical assumption', fr: 'Source ou hypothèse' })}</th></tr></thead><tbody>{profile.portfolio.positions.map(p => <tr key={p.ticker}><th scope="row">{p.ticker} · {p.weightPct}%</th><td><input aria-label={`${p.ticker} sensitivity`} type="number" step="any" value={inputs[p.ticker]?.value ?? ''} onChange={e => { setInputs(v => ({ ...v, [p.ticker]: { source: v[p.ticker]?.source ?? '', value: e.target.value } })); clear(); }} /></td><td><input aria-label={`${p.ticker} sensitivity source`} maxLength={1000} value={inputs[p.ticker]?.source ?? ''} onChange={e => { setInputs(v => ({ ...v, [p.ticker]: { value: v[p.ticker]?.value ?? '', source: e.target.value } })); clear(); }} /></td></tr>)}</tbody></table></div>
      <button className="btn" type="submit">{tr({ en: 'Calculate deterministic scenario', fr: 'Calculer le scénario déterministe' })}</button></fieldset></form>
    {error && <ErrorState error={error} />}
    {result && <div role="status"><p><strong>{tr({ en: 'Portfolio modeled impact', fr: 'Impact modélisé du portefeuille' })}: {result.impactFraction === null ? tr({ en: 'Unknown: incomplete sensitivities', fr: 'Inconnu : sensibilités incomplètes' }) : fmtSignedPct(result.impactFraction * 100, lang)}</strong></p>
      <p>{tr({ en: 'Known component only', fr: 'Composante connue seulement' })}: {fmtSignedPct(result.knownImpactFraction * 100, lang)}</p>
      {!!result.missing.length && <p>{tr({ en: 'Missing inputs', fr: 'Entrées manquantes' })}: {result.missing.join(', ')}</p>}
      <ul>{Object.entries(result.contributions).map(([ticker, contribution]) => <li key={ticker}>{ticker}: {fmtSignedPct(contribution * 100, lang)}</li>)}</ul>
      <p className="small muted">{result.asOf} · {result.model}</p>
    </div>}
  </Card>;
}
