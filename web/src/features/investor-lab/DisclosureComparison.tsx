'use client';

import { useId, useState } from 'react';
import type { Profile } from '../../contracts/types';
import { researchFetch } from '../../api';
import { ApiRequestError } from '../../api/errors';
import { researchJson } from '../../api/research';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { fmtDate, fmtPct } from '../../lib/format';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';

interface Filing {
  filingId: string;
  manager: string;
  reportDate: string;
  filingDate: string;
  retrievedAt: string;
  modeledCoveragePct: number;
  holdingCount: number;
  secUrl: string;
  sourceUrl: string;
  limitations: string[];
}
interface Holding { ticker: string | null; valueUsd: number; optionType: 'put' | 'call' | null }
interface Capture extends Filing { holdings: Holding[] }

const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
function validFiling(value: unknown): value is Filing {
  return object(value)
    && ['filingId', 'manager', 'reportDate', 'filingDate', 'retrievedAt', 'secUrl', 'sourceUrl'].every(key => typeof value[key] === 'string')
    && typeof value.modeledCoveragePct === 'number' && Number.isFinite(value.modeledCoveragePct)
    && typeof value.holdingCount === 'number' && Number.isInteger(value.holdingCount)
    && Array.isArray(value.limitations) && value.limitations.every(item => typeof item === 'string');
}
function invalid(): never {
  throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'The disclosure response could not be validated.' });
}
function safeLink(value: string): string | undefined {
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : undefined; } catch { return undefined; }
}

/** Optional, read-only comparison: no disclosure or reflection changes profile settings. */
export function DisclosureComparison({ profile }: { profile: Profile }) {
  const { sessionId, lang } = useApp();
  const [expanded, setExpanded] = useState(false);
  const [filingId, setFilingId] = useState('');
  const selectId = useId();
  const filings = useQuery<Filing[]>(expanded && sessionId ? `lab-disclosures|${sessionId}` : null, async signal => {
    const value = await researchJson(await researchFetch('/research/13f', { signal }), '/research/13f');
    if (!object(value) || !Array.isArray(value.items) || !value.items.every(validFiling)) return invalid();
    return value.items;
  });
  const capture = useQuery<Capture>(expanded && sessionId && filingId ? `lab-disclosure|${sessionId}|${filingId}` : null, async signal => {
    const route = `/research/13f/${encodeURIComponent(filingId)}`;
    const value = await researchJson(await researchFetch(route, { signal }), route);
    if (!validFiling(value) || !object(value) || !Array.isArray(value.holdings)
      || !value.holdings.every(item => object(item)
        && (item.ticker === null || typeof item.ticker === 'string')
        && typeof item.valueUsd === 'number' && Number.isFinite(item.valueUsd) && item.valueUsd >= 0
        && (item.optionType === null || item.optionType === 'put' || item.optionType === 'call'))) return invalid();
    return value as unknown as Capture;
  });
  const data = capture.data;
  const longs = data?.holdings.filter(holding => holding.optionType === null) ?? [];
  const total = longs.reduce((sum, holding) => sum + holding.valueUsd, 0);
  const weights = new Map<string, number>();
  for (const holding of longs) {
    if (holding.ticker && total > 0) weights.set(holding.ticker, (weights.get(holding.ticker) ?? 0) + holding.valueUsd / total * 100);
  }
  const common = profile.portfolio.positions.filter(position => weights.has(position.ticker));
  return <Card title="Optional: compare a manager's disclosed holdings">
    <p className="small muted">Compare specific holdings with dates and coverage in view. A disclosure is evidence, not a personality label or the manager's complete strategy.</p>
    <button type="button" className="btn ghost btn-sm" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      {expanded ? 'Close 13F comparison' : 'Open 13F comparison'}
    </button>
    {expanded && <div className="lab-disclosure">
      {filings.loading && <Loading label="Loading dated disclosures…" />}
      {filings.error && <ErrorState error={filings.error} onRetry={filings.reload} />}
      {filings.data && !filings.data.length && <p className="small muted">No documented 13F captures are available in this session.</p>}
      {!!filings.data?.length && <div className="field">
        <label htmlFor={selectId}>Manager and reporting date</label>
        <select id={selectId} value={filingId} onChange={event => setFilingId(event.target.value)}>
          <option value="">Choose a dated disclosure</option>
          {filings.data.map(filing => <option key={filing.filingId} value={filing.filingId}>{filing.manager} · {filing.reportDate}</option>)}
        </select>
      </div>}
      {capture.loading && <Loading label="Reading disclosed holdings…" />}
      {capture.error && <ErrorState error={capture.error} onRetry={capture.reload} />}
      {data && <>
        <p className="small"><strong>{data.manager}</strong> · Holdings at {fmtDate(data.reportDate, lang)} · Filed {fmtDate(data.filingDate, lang)}</p>
        <p className="small muted">Captured {fmtDate(data.retrievedAt.slice(0, 10), lang)}. {data.holdingCount} indexed rows; {fmtPct(data.modeledCoveragePct, lang)} of indexed value has price coverage. These third-party transcriptions have not been verified against the original SEC tables.</p>
        {common.length > 0 ? <div className="lab-chart-data"><table className="data-table">
          <caption>Shared holdings: current hypothetical portfolio versus the captured long book</caption>
          <thead><tr><th>Holding</th><th>Your allocation</th><th>Disclosed long-book allocation</th></tr></thead>
          <tbody>{common.map(position => <tr key={position.ticker}><td>{position.ticker}</td><td>{fmtPct(position.weightPct, lang)}</td><td>{fmtPct(weights.get(position.ticker)!, lang)}</td></tr>)}</tbody>
        </table></div> : <p>No mapped holdings are shared with your current hypothetical portfolio.</p>}
        <p className="small muted">The disclosure percentages use the sum of captured non-option rows, including rows without a mapped ticker. Options, short positions, cash and later trades are not represented as a full portfolio.</p>
        <p className="small">Would knowing this allocation change your intended position size? <a href="#playbook">Record your reasoning in your playbook</a> before confirming any change.</p>
        <p className="small">{safeLink(data.secUrl) && <a href={safeLink(data.secUrl)} target="_blank" rel="noreferrer">SEC filing</a>}{' · '}
          {safeLink(data.sourceUrl) && <a href={safeLink(data.sourceUrl)} target="_blank" rel="noreferrer">Source transcription</a>}</p>
        {data.limitations.length > 0 && <details><summary>Disclosure coverage limitations</summary><ul className="bullets small">{data.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></details>}
      </>}
    </div>}
  </Card>;
}
