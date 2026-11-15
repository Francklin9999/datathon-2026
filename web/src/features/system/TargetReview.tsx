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

/** Separate adapter so Decision Desk can embed the same reviewed target workflow. */
export function TargetReview({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec } = useApp();
  const requestSequence = useRef(0);
  const [text, setText] = useState(() => profile.portfolio.positions.map(p => `${p.ticker} ${p.weightPct}`).join('\n'));
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const { run, error: runError } = useRun(runId);
  const start = async () => {
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
        <textarea id="review-targets" rows={6} maxLength={4000} value={text} disabled={busy} onChange={event => { requestSequence.current++; setText(event.target.value); setRunId(null); setError(null); }} /></div>
      {invalid && <p role="alert">{tr({ en: 'Enter up to 40 unique tickers and valid percentages totaling 100%.', fr: 'Saisissez au plus 40 symboles uniques et des pourcentages valides totalisant 100 %.' })}</p>}
      <button className="btn" disabled={busy}>{tr({ en: 'Run reviewed analysis', fr: 'Lancer l’analyse vérifiée' })}</button>
    </form>
    {(error || runError) && <ErrorState error={(error || runError)!} />}
    {run && <><p><RunStatusBadge status={run.status} />{' '}<Link href={`/agents-system/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Inspect execution', fr: 'Examiner l’exécution' })}</Link></p>
      {run.status === 'failed' && <p role="alert">{run.error?.message} <Link href="/decision-desk/">{tr({ en: 'Open the deterministic comparison in Decision Desk', fr: 'Ouvrir la comparaison déterministe dans le Centre de décision' })}</Link></p>}
      <RunTimeline run={run} />
      {run.result?.kind === 'rebalance' && <FactScopeProvider scope={{ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }}>
        <SnapshotCompare before={run.result.rebalance.portfolioBefore} after={run.result.rebalance.portfolioAfter} />
        <RuleTable checks={run.result.rebalance.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
        <BriefView brief={run.result.rebalance.brief} />
      </FactScopeProvider>}</>}
  </Card>;
}
