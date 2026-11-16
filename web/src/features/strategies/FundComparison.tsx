'use client';

import { useId, useState } from 'react';
import { researchFetch } from '../../api/index';
import { researchJson } from '../../api/research';
import { ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { LineChart, SeriesTable, type Series } from '../../components/common/LineChart';
import type { Profile, StrategyConfig, WindowSpec } from '../../contracts/types';
import { fmtDate, fmtPct, fmtSignedPct } from '../../lib/format';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';

type Filing = {
  filingId: string; manager: string; associatedPerson: string | null; reportDate: string; filingDate: string;
  sourceUrl: string; secUrl: string; holdingCount: number; modeledHoldingCount: number;
  modeledCoveragePct: number; comparisonEligible: boolean; limitations: string[];
};
type Point = { date: string; value: number };
type Comparison = {
  filing: Filing; currency: string; sample: { start: string; end: string; observations: number };
  strategy: { series: Point[]; returnPct: number }; benchmark: { series: Point[]; returnPct: number };
  limitations: string[];
};

const object = (x: unknown): x is Record<string, unknown> => x !== null && typeof x === 'object' && !Array.isArray(x);
const strings = (x: unknown): x is string[] => Array.isArray(x) && x.every(v => typeof v === 'string');
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const filingIsValid = (x: unknown): x is Filing => object(x)
  && ['filingId', 'manager', 'reportDate', 'filingDate', 'sourceUrl', 'secUrl'].every(k => typeof x[k] === 'string')
  && (x.associatedPerson === null || typeof x.associatedPerson === 'string')
  && finite(x.holdingCount) && finite(x.modeledHoldingCount) && finite(x.modeledCoveragePct)
  && typeof x.comparisonEligible === 'boolean' && strings(x.limitations);
const legIsValid = (x: unknown): x is Comparison['strategy'] => object(x) && finite(x.returnPct)
  && Array.isArray(x.series) && x.series.every(p => object(p) && typeof p.date === 'string' && finite(p.value));
function invalidResponse(): never {
  throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid 13F comparison response' });
}
function safeUrl(url: string): string | undefined {
  try { const parsed = new URL(url); return parsed.protocol === 'https:' ? parsed.href : undefined; } catch { return undefined; }
}

/** Public filings are modeled as a subset of disclosed holdings, never as actual fund performance. */
export function FundComparison({ profile, strategy, window }: { profile: Profile; strategy: StrategyConfig; window: WindowSpec }) {
  const app = useApp();
  const { tr, lang, sessionId, meta } = app;
  const selectId = useId();
  const [filingId, setFilingId] = useState('');
  const filings = useQuery<Filing[]>(sessionId && meta ? `13f-filings|${sessionId}|${meta.dataVersion}` : null, async signal => {
    const data = await researchJson(await researchFetch('/research/13f', { signal }), '/research/13f');
    if (!object(data) || !Array.isArray(data.items) || !data.items.every(filingIsValid)) return invalidResponse();
    return data.items;
  });
  const selected = filings.data?.find(filing => filing.filingId === filingId && filing.comparisonEligible);
  const base = profileKey(app);
  const path = `/profiles/${encodeURIComponent(profile.profileId)}/strategies/compare-13f`;
  const comparison = useQuery<Comparison>(base && selected ? `13f-compare|${base}|${JSON.stringify(window)}|${JSON.stringify(strategy)}|${selected.filingId}` : null, async signal => {
    const data = await researchJson(await researchFetch(path, { method: 'POST', signal, body: { filingId: selected!.filingId, strategy, window } }), path);
    if (!object(data) || !filingIsValid(data.filing) || typeof data.currency !== 'string' || !object(data.sample)
      || typeof data.sample.start !== 'string' || typeof data.sample.end !== 'string' || !finite(data.sample.observations)
      || !legIsValid(data.strategy) || !legIsValid(data.benchmark) || !strings(data.limitations)) return invalidResponse();
    return data as Comparison;
  });
  const data = comparison.data;
  const series: Series[] = data ? [
    { label: tr({ en: 'Your strategy', fr: 'Votre stratégie' }), points: data.strategy.series, color: 'var(--chart-1)' },
    { label: tr({ en: 'Modeled filing subset', fr: 'Sous-ensemble modélisé du dépôt' }), points: data.benchmark.series, color: 'var(--chart-4)', dashed: true },
  ] : [];
  const caption = data ? `${fmtDate(data.sample.start, lang)} → ${fmtDate(data.sample.end, lang)} · ${data.sample.observations} ${tr({ en: 'observations', fr: 'observations' })}` : '';
  const officialUrl = selected && safeUrl(selected.secUrl);
  const indexUrl = selected && safeUrl(selected.sourceUrl);
  const limitations = [...new Set([...(selected?.limitations ?? []), ...(data?.limitations ?? [])])];

  return <Card title={tr({ en: 'Compare with a public 13F filing', fr: 'Comparer avec un dépôt 13F public' })}>
    <p className="small muted">{tr({ en: 'This hypothetical benchmark buys and holds the modeled subset of disclosed long holdings. It is not the fund’s actual total performance or a person’s private wealth. Options are excluded.', fr: 'Cet indice hypothétique conserve le sous-ensemble modélisé des positions longues déclarées. Il ne représente ni le rendement total réel du fonds ni la fortune privée d’une personne. Les options sont exclues.' })}</p>
    {filings.loading && <Loading label={tr({ en: 'Loading filings…', fr: 'Chargement des dépôts…' })} />}
    {filings.error && <ErrorState error={filings.error} onRetry={filings.reload} />}
    {filings.data && <>
      <div className="field">
        <label htmlFor={selectId}>{tr({ en: 'Manager and filing', fr: 'Gestionnaire et dépôt' })}</label>
        <select id={selectId} value={filingId} onChange={event => setFilingId(event.target.value)}>
          <option value="">{tr({ en: 'Select a filing', fr: 'Choisir un dépôt' })}</option>
          {filings.data.map(filing => <option key={filing.filingId} value={filing.filingId} disabled={!filing.comparisonEligible}>
            {filing.manager}{filing.associatedPerson ? ` · ${filing.associatedPerson}` : ''} · {filing.reportDate}{!filing.comparisonEligible ? ` — ${tr({ en: 'no supported holdings', fr: 'aucune position prise en charge' })}` : ''}
          </option>)}
        </select>
      </div>
      {filings.data.length === 0 && <p className="small muted">{tr({ en: 'No filings are available.', fr: 'Aucun dépôt disponible.' })}</p>}
    </>}
    {selected && <>
      <p className="small">{tr({ en: `Report: ${fmtDate(selected.reportDate, lang)} · Filed: ${fmtDate(selected.filingDate, lang)}`, fr: `Rapport : ${fmtDate(selected.reportDate, lang)} · Déposé : ${fmtDate(selected.filingDate, lang)}` })}</p>
      <p className="small">{tr({ en: `${fmtPct(selected.modeledCoveragePct, lang)} of disclosed value modeled; ${fmtPct(100 - selected.modeledCoveragePct, lang)} omitted. ${selected.modeledHoldingCount} of ${selected.holdingCount} holdings included.`, fr: `${fmtPct(selected.modeledCoveragePct, lang)} de la valeur déclarée modélisée ; ${fmtPct(100 - selected.modeledCoveragePct, lang)} omis. ${selected.modeledHoldingCount} positions sur ${selected.holdingCount} incluses.` })}</p>
      <p className="small">{officialUrl && <a href={officialUrl} target="_blank" rel="noreferrer">{tr({ en: 'SEC filing', fr: 'Dépôt SEC' })}</a>}{officialUrl && indexUrl && ' · '}{indexUrl && <a href={indexUrl} target="_blank" rel="noreferrer">{tr({ en: 'Filing index', fr: 'Index du dépôt' })}</a>}</p>
      {comparison.loading && <Loading label={tr({ en: 'Comparing on history…', fr: 'Comparaison sur l’historique…' })} />}
      {comparison.error && <ErrorState error={comparison.error} onRetry={comparison.reload} />}
      {data && <>
        <p className="small">{tr({ en: `Strategy return: ${fmtSignedPct(data.strategy.returnPct, lang)} · Modeled subset return: ${fmtSignedPct(data.benchmark.returnPct, lang)}`, fr: `Rendement de la stratégie : ${fmtSignedPct(data.strategy.returnPct, lang)} · Rendement du sous-ensemble modélisé : ${fmtSignedPct(data.benchmark.returnPct, lang)}` })}</p>
        <p className="small muted">{tr({ en: 'Both series start at 100. The strategy return is time-weighted: contributions are removed. The sample starts no earlier than the indexed filing date.', fr: 'Les deux séries commencent à 100. Le rendement de la stratégie est pondéré dans le temps : les versements sont retirés. La période commence au plus tôt à la date du dépôt indiquée par l’index.' })}</p>
        <LineChart series={series} lang={lang} unitLabel={tr({ en: 'Index, start = 100', fr: 'Indice, début = 100' })} caption={caption} digits={1} />
        <details><summary>{tr({ en: 'View chart data', fr: 'Voir les données du graphique' })}</summary><SeriesTable series={series} lang={lang} unitLabel={tr({ en: 'Index', fr: 'Indice' })} caption={caption} digits={1} /></details>
      </>}
      {limitations.length > 0 && <details className="small"><summary>{tr({ en: 'Additional limitations', fr: 'Limites supplémentaires' })}</summary><ul lang="en">{limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
    </>}
  </Card>;
}
