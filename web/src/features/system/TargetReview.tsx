'use client';
/**
 * The reviewed AI analysis of a complete target allocation (a "rebalance" run), embedded in the
 * Decision Desk "Target allocation" card below the instant check. The targets come from the card.
 */
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { Position, Profile } from '../../contracts/types';
import { getApiClient } from '../../api';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useRun } from '../../state/useRun';
import { ErrorState } from '../../components/common/States';
import { FactScopeProvider } from '../../components/common/FactDrawer';
import { RunStatusBadge } from '../../components/common/Badges';
import { BriefView } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import { SnapshotCompare } from '../../components/run/Results';
import { RuleTable } from '../../components/run/RuleTable';
import { RUN_STATUS, VERDICT, labelOf } from '../../lib/labels';
import { isTerminal } from '../../lib/runs';
import { fmtPct, fmtPts } from '../../lib/format';
import { parseFinalTargets } from '../../lib/targetAllocation';

export function TargetReview({ profile, text, blocked }: {
  profile: Profile;
  /** The final targets typed in the card, one "TICKER PERCENT" line per holding. */
  text: string;
  /** The target tickers failed the snapshot check: no analysis is created. */
  blocked: boolean;
}) {
  const { tr, lang, windowSpec } = useApp();
  const requestSequence = useRef(0);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  // Edited targets abandon the analysis written for the previous ones (and any creation in flight).
  const [shownFor, setShownFor] = useState(text);
  if (shownFor !== text) {
    setShownFor(text);
    setRunId(null); setError(null); setInvalid(false); setBusy(false);
  }
  useEffect(() => { requestSequence.current++; }, [text]);
  const { run, error: runError } = useRun(runId);
  const start = async () => {
    if (blocked) return;
    let positions: Position[];
    try { positions = parseFinalTargets(text); }
    catch { setInvalid(true); return; }
    setInvalid(false); setBusy(true); setError(null); setRunId(null);
    const sequence = ++requestSequence.current;
    try {
      const queued = await getApiClient().createRun({ kind: 'rebalance', profileId: profile.profileId,
        profileVersion: profile.version, lang, positions: positions as [Position, ...Position[]], window: windowSpec }, `target-${crypto.randomUUID()}`);
      if (requestSequence.current === sequence) setRunId(queued.runId);
    } catch (cause) { if (requestSequence.current === sequence) setError(asApiError(cause)); }
    finally { if (requestSequence.current === sequence) setBusy(false); }
  };
  const shownError = error ?? runError;
  const rebalance = run?.result?.kind === 'rebalance' ? run.result.rebalance : null;
  const active = Boolean(busy || (run && !isTerminal(run.status)));
  return (
    <section className="target-section" aria-labelledby="target-review-title">
      <h3 className="h4" id="target-review-title">{tr({ en: 'Reviewed analysis', fr: 'Analyse vérifiée' })}</h3>
      <div className="row-actions">
        <button type="button" className="btn" disabled={active || blocked} onClick={() => void start()} aria-describedby="target-review-hint">
          {tr({ en: 'Analyze this allocation', fr: 'Analyser cette allocation' })}
        </button>
        <span id="target-review-hint" className="small muted">{tr({ en: 'An AI explains the complete targets from the checked figures, then an auditor verifies every sentence.', fr: 'Une IA explique les cibles complètes à partir des chiffres vérifiés, puis un auditeur contrôle chaque phrase.' })}</span>
      </div>
      {invalid && <p className="field-error" role="alert">{tr({ en: 'Enter up to 40 unique tickers and percentages from 0 to 100 that total exactly 100%.', fr: 'Saisissez au plus 40 symboles uniques et des pourcentages de 0 à 100 totalisant exactement 100 %.' })}</p>}
      {shownError && <ErrorState error={shownError} />}
      {run && <>
        <p className="small">
          <RunStatusBadge status={run.status} />{' '}
          <Link href={`/agents-system/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'See how it was produced', fr: 'Voir comment elle a été produite' })}</Link>
        </p>
        {run.status === 'failed' && (
          <p className="field-error" role="alert">
            {run.error?.message ?? labelOf(RUN_STATUS, run.status, lang)}{' '}
            {tr({ en: 'The instant check above still works without AI.', fr: 'La vérification instantanée ci-dessus fonctionne toujours sans IA.' })}
          </p>
        )}
        {rebalance && <FactScopeProvider scope={{ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }}>
          <p>{tr({ en: 'Current plan', fr: 'Plan actuel' })}: {labelOf(VERDICT, rebalance.verdictBefore, lang)} → <strong>{tr({ en: 'Target plan', fr: 'Plan cible' })}: {labelOf(VERDICT, rebalance.verdictAfter, lang)}</strong></p>
          <BriefView brief={rebalance.brief} />
          <SnapshotCompare before={rebalance.portfolioBefore} after={rebalance.portfolioAfter} />
          <RuleTable checks={rebalance.ruleChecksAfter} rules={profile.rules} caption={tr({ en: 'Target policy checks', fr: 'Vérification des règles cibles' })} />
          <details className="fold">
            <summary>{tr({ en: 'Weights per holding', fr: 'Poids par position' })}</summary>
            <div className="fold-body">
              <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Target weight changes', fr: 'Variations des poids cibles' })}>
                <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Holding', fr: 'Position' })}</th><th scope="col">{tr({ en: 'Before', fr: 'Avant' })}</th><th scope="col">{tr({ en: 'Final target', fr: 'Cible finale' })}</th><th scope="col">{tr({ en: 'Change', fr: 'Variation' })}</th></tr></thead>
                  <tbody>{rebalance.changes.map(row => <tr key={row.ticker}><th scope="row">{row.ticker}</th><td>{fmtPct(row.beforePct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{fmtPts(row.changePct, lang)}</td></tr>)}</tbody></table>
              </div>
              {rebalance.assumptions.map((note, i) => <p className="small muted" key={i}>{tr(note)}</p>)}
            </div>
          </details>
        </FactScopeProvider>}
        <details className="fold" open={!rebalance && run.status !== 'failed'}>
          <summary>{tr({ en: 'Steps', fr: 'Étapes' })}, {labelOf(RUN_STATUS, run.status, lang).toLowerCase()}</summary>
          <RunTimeline run={run} />
        </details>
      </>}
    </section>
  );
}
