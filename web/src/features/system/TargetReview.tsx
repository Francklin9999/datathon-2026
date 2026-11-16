'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import type { Position, Profile } from '../../contracts/types';
import { getApiClient } from '../../api';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useRun } from '../../state/useRun';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { FactScopeProvider } from '../../components/common/FactDrawer';
import { RunStatusBadge } from '../../components/common/Badges';
import { BriefView } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import { SnapshotCompare } from '../../components/run/Results';
import { RuleTable } from '../../components/run/RuleTable';
import { VERDICT, labelOf } from '../../lib/labels';
import { fmtPct, fmtPts } from '../../lib/format';
import { checkTickers, targetLineTickers } from '../../lib/tickerCoverage';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { SupportedUniverse } from '../../components/common/SupportedUniverse';

/** Separate adapter so Decision Desk can embed the same reviewed target workflow. */
export function TargetReview({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec, feature } = useApp();
  const requestSequence = useRef(0);
  const [text, setText] = useState(() => profile.portfolio.positions.map(p => `${p.ticker} ${p.weightPct}`).join('\n'));
  // Target tickers are checked against the snapshot before the run is created (the server refuses them after).
  const universe = useAssetUniverse();
  const tickerCheck = checkTickers(targetLineTickers(text), universe, feature('on_demand_tickers'));
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const { run, error: runError } = useRun(runId);
  const start = async () => {
    if (tickerCheck.blocking) return;
    const positions: Position[] = [];
    const seen = new Set<string>();
    for (const line of text.split('\n').map(s => s.trim()).filter(Boolean)) {
      const [ticker, amount, extra] = line.toUpperCase().split(/\s+/);
      const weightPct = Number(amount);
      if (!ticker || !amount || extra || seen.has(ticker) || !Number.isFinite(weightPct) || weightPct < 0 || weightPct > 100) {
        setInvalid(true); return;
      }
      seen.add(ticker); positions.push({ ticker, weightPct });
    }
    if (!positions.length || positions.length > 40 || Math.abs(positions.reduce((sum, p) => sum + p.weightPct, 0) - 100) > 1e-9) {
      setInvalid(true); return;
    }
    setInvalid(false); setBusy(true); setError(null); setRunId(null);
    const sequence = ++requestSequence.current;
    try {
      const queued = await getApiClient().createRun({ kind: 'rebalance', profileId: profile.profileId,
        profileVersion: profile.version, lang, positions: positions as [Position, ...Position[]], window: windowSpec }, `target-${crypto.randomUUID()}`);
      if (requestSequence.current === sequence) setRunId(queued.runId);
    } catch (cause) { if (requestSequence.current === sequence) setError(asApiError(cause)); }
    finally { if (requestSequence.current === sequence) setBusy(false); }
  };
  return <Card title={tr({ en: 'Review complete target allocation', fr: 'Examiner une répartition cible complète' })}>
    <p>{tr({ en: 'Enter each final holding and percentage. Include retained holdings; omitted holdings have a zero target. Total must be 100%.', fr: 'Saisissez chaque position finale et son pourcentage. Incluez les positions conservées; les positions omises ont une cible nulle. Le total doit être de 100 %.' })}</p>
    <form onSubmit={event => { event.preventDefault(); void start(); }}>
      <div className="field"><label htmlFor="review-targets">{tr({ en: 'Ticker and final percentage, one per line', fr: 'Symbole et pourcentage final, un par ligne' })}</label>
        <textarea id="review-targets" rows={6} maxLength={4000} value={text} disabled={busy} onChange={event => { requestSequence.current++; setText(event.target.value); setRunId(null); setError(null); }}
          aria-invalid={tickerCheck.blocking} aria-describedby={`${tickerCheck.message ? 'review-targets-issue ' : ''}review-targets-universe`} />
        {tickerCheck.message && <span id="review-targets-issue" className={tickerCheck.blocking ? 'field-error' : 'hint'}>{tr(tickerCheck.message)}</span>}
        <SupportedUniverse id="review-targets-universe" /></div>
      {invalid && <p role="alert">{tr({ en: 'Enter up to 40 unique tickers and valid percentages totaling 100%.', fr: 'Saisissez au plus 40 symboles uniques et des pourcentages valides totalisant 100 %.' })}</p>}
      <button className="btn" disabled={busy || tickerCheck.blocking}>{tr({ en: 'Run reviewed analysis', fr: 'Lancer l’analyse vérifiée' })}</button>
    </form>
    {(error || runError) && <ErrorState error={(error || runError)!} />}
    {run && <><p><RunStatusBadge status={run.status} />{' '}<Link href={`/agents-system/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Inspect execution', fr: 'Examiner l’exécution' })}</Link></p>
      {run.status === 'failed' && <p role="alert">{run.error?.message} <Link href="/decision-desk/">{tr({ en: 'Open the deterministic comparison in Decision Desk', fr: 'Ouvrir la comparaison déterministe dans le Centre de décision' })}</Link></p>}
      <RunTimeline run={run} />
      {run.result?.kind === 'rebalance' && <FactScopeProvider scope={{ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }}>
        <p>{tr({ en: 'Current plan', fr: 'Plan actuel' })}: {labelOf(VERDICT, run.result.rebalance.verdictBefore, lang)} → <strong>{tr({ en: 'Target plan', fr: 'Plan cible' })}: {labelOf(VERDICT, run.result.rebalance.verdictAfter, lang)}</strong></p>
        <SnapshotCompare before={run.result.rebalance.portfolioBefore} after={run.result.rebalance.portfolioAfter} />
        <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Target weight changes', fr: 'Variations des poids cibles' })}><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th><th>{tr({ en: 'Before', fr: 'Avant' })}</th><th>{tr({ en: 'Final target', fr: 'Cible finale' })}</th><th>{tr({ en: 'Change', fr: 'Variation' })}</th></tr></thead><tbody>{run.result.rebalance.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtPct(row.beforePct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{fmtPts(row.changePct, lang)}</td></tr>)}</tbody></table></div>
        <RuleTable checks={run.result.rebalance.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
        {run.result.rebalance.assumptions.map((note, i) => <p className="small muted" key={i}>{tr(note)}</p>)}
        <BriefView brief={run.result.rebalance.brief} />
      </FactScopeProvider>}</>}
  </Card>;
}
