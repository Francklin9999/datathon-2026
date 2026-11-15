'use client';
import { useState } from 'react';
import type { Fact, Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { numeric, record, rows, scalar, texts, type ModelResult } from '../../api/expandedInvestor';
import { useApp } from '../../state/app';
import { ErrorState } from '../../components/common/States';
import { FactChip, FactScopeProvider } from '../../components/common/FactDrawer';
import { fmtMoney, fmtNumber, fmtPct } from '../../lib/format';

export function FinancialComparison({ left, right }: { left: Profile; right: Profile }) {
  const { tr, lang, meta, windowSpec } = useApp();
  const [currency, setCurrency] = useState(left.reportingCurrency);
  const [result, setResult] = useState<ModelResult | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const compare = async () => {
    setBusy(true); setError(null); setResult(null);
    try { setResult(await getApiClient().comparePortfolios({ profiles: [{ profileId: left.profileId, version: left.version }, { profileId: right.profileId, version: right.version }], currency, window: windowSpec })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <section><h3>{tr({ en: 'Compare calculated portfolio outcomes', fr: 'Comparer les résultats calculés des portefeuilles' })}</h3>
    <p className="small muted">{tr({ en: 'Both portfolios use one reporting currency and the selected global history window. Full-history comparisons use a disclosed common contiguous sample; a named/custom period is never silently shortened. All amounts remain modeled, with private appraisals excluded.', fr: 'Les deux portefeuilles utilisent une même devise et la fenêtre historique sélectionnée. L’historique complet utilise un échantillon contigu commun explicite; une période nommée ou personnalisée n’est jamais raccourcie silencieusement. Les valeurs sont modélisées, hors évaluations privées.' })}</p>
    <div className="field"><label htmlFor="comparison-currency">{tr({ en: 'Common reporting currency', fr: 'Devise de comparaison commune' })}</label><select id="comparison-currency" value={currency} disabled={busy} onChange={e => { setCurrency(e.target.value); setResult(null); }}>{(meta?.reportingCurrencies ?? [left.reportingCurrency, right.reportingCurrency]).filter((v, i, a) => a.indexOf(v) === i).map(c => <option key={c} value={c}>{c}</option>)}</select></div>
    <button type="button" className="btn" disabled={busy || left.profileId === right.profileId} onClick={() => void compare()}>{tr({ en: 'Calculate portfolio comparison', fr: 'Calculer la comparaison des portefeuilles' })}</button>
    {error && <ErrorState error={error} />}
    {result && <><p>{tr({ en: 'Same usable return sample', fr: 'Même échantillon de rendements disponible' })}: <strong>{result.sameSample ? tr({ en: 'Yes', fr: 'Oui' }) : tr({ en: 'No — inspect availability before comparing', fr: 'Non — examiner la disponibilité avant de comparer' })}</strong></p><p className="small muted">{scalar(result.sampleRule)}</p>
      <div className="grid-2">{rows(result.portfolios).map(portfolio => {
        const facts = record(portfolio.facts) as unknown as Record<string, Fact>;
        const metrics = record(portfolio.metrics), ids = record(portfolio.factIds), sample = record(portfolio.sample);
        const display = (key: string) => { const n = numeric(metrics[key]); if (n === null) return tr({ en: 'Unavailable', fr: 'Indisponible' }); return key === 'hhi' || key === 'effectiveN' ? fmtNumber(n, lang, 3) : fmtPct(n, lang); };
        return <FactScopeProvider key={scalar(portfolio.profileId)} scope={{ kind: 'local', label: { en: `Comparison: ${scalar(portfolio.name)}`, fr: `Comparaison : ${scalar(portfolio.name)}` }, facts }}><section><h4>{scalar(portfolio.name)} · v{scalar(portfolio.profileVersion)}</h4><p>{tr({ en: 'Converted modeled capital', fr: 'Capital modélisé converti' })}: {numeric(portfolio.capital) === null ? tr({ en: 'Unknown', fr: 'Inconnu' }) : fmtMoney(numeric(portfolio.capital)!, currency, lang)}</p><p className="small">{scalar(sample.start)} — {scalar(sample.end)} · {scalar(sample.returnObservations)} {tr({ en: 'returns', fr: 'rendements' })}</p>
          <dl className="kv-list">{([
            ['returnPct',tr({en:'Period return',fr:'Rendement de la période'})],['volatilityPct',tr({en:'Annualized volatility',fr:'Volatilité annualisée'})],['maxDrawdownPct',tr({en:'Maximum drawdown',fr:'Baisse maximale'})],['stress2022Pct',tr({en:'2022 replay return',fr:'Rendement rejoué 2022'})],['hhi','HHI'],['effectiveN',tr({en:'Effective holdings',fr:'Positions effectives'})],
          ] as const).map(([key,label]) => { const id = scalar(ids[key] ?? ids[key === 'returnPct' ? 'return.period' : key]); return <div className="kv" key={key}><dt>{label}</dt><dd>{id in facts ? <FactChip factId={id} display={display(key)} /> : display(key)}</dd></div>; })}</dl>
          <details><summary>{tr({ en: 'Inspect FX conversion and missing data', fr: 'Examiner la conversion et les données manquantes' })}</summary><pre style={{ whiteSpace:'pre-wrap',overflowWrap:'anywhere' }}>{JSON.stringify({ conversion: portfolio.conversion, missing: portfolio.missing, unavailable: portfolio.unavailable },null,2)}</pre></details></section></FactScopeProvider>;
      })}</div>{texts(result.limitations).map(s => <p className="small muted" key={s}>{s}</p>)}</>}
  </section>;
}
