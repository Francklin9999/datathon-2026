'use client';
import Link from 'next/link';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import type { Profile } from '../../contracts/types';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { splitLimitations } from '../../lib/limitations';
import { currentHref } from '../../lib/redirect';

/** Reader-facing limitations stay visible; notes written for code sit behind "Technical details" (QA 4.5b). */
function Limitations({ lines }: { lines: readonly string[] }) {
  const { tr } = useApp();
  const { shown, technical } = splitLimitations(lines);
  return <>
    {shown.map(l => <p className="small muted" key={l}>{l}</p>)}
    {technical.length > 0 && <details className="tech-details">
      <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
      {technical.map(l => <p className="small muted mono" key={l}>{l}</p>)}
    </details>}
  </>;
}

export function FocusCandidates({ profile }: { profile: Profile }) {
  const { tr, sessionId } = useApp();
  const query = useQuery(sessionId ? `focus|${sessionId}|${profile.profileId}|${profile.version}` : null, signal => getApiClient().strategicCandidates(profile.profileId, signal));
  return <Card tour="focus-candidates" title={tr({ en: 'Deterministic focus candidates', fr: 'Priorités candidates déterministes' })}>
    <p className="small muted">{tr({ en: 'At most three findings, ranked from measured policy conflicts and explicit goal scenarios. These candidates have local calculation facts; an audited writer must create and verify claims separately.', fr: 'Au plus trois constats classés selon les conflits mesurés et les scénarios d’objectifs explicites. Ces candidats ont des faits de calcul locaux; la rédaction auditée doit créer et vérifier les affirmations séparément.' })}</p>
    {query.loading && <Loading />}{query.error && <ErrorState error={query.error} onRetry={query.reload} />}
    {query.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Focus candidate calculations', fr: 'Calculs des priorités candidates' }, facts: query.data.facts }}>
      {!query.data.candidates.length && <p>{tr({ en: 'No ranked conflict or missing-goal-input finding in this evaluation.', fr: 'Aucun conflit classé ni entrée d’objectif manquante dans cette évaluation.' })}</p>}
      <ol>{query.data.candidates.map(candidate => <li key={candidate.candidateId}><strong>{candidate.label}</strong><p className="small">{candidate.severity} · {candidate.affectedHoldings.join(', ')}</p><p>{candidate.investigation}</p>{!!candidate.missingInputs.length && <p>{tr({ en: 'Missing inputs', fr: 'Entrées manquantes' })}: {candidate.missingInputs.join(', ')}</p>}<div className="row-actions">{candidate.factIds.map(id => <FactChip key={id} factId={id} display={id} />)}<Link className="btn ghost btn-sm" href={candidate.navigationTarget.startsWith('/') && !candidate.navigationTarget.startsWith('//') ? currentHref(candidate.navigationTarget) : '/portfolio/'}>{tr({ en: 'Investigate', fr: 'Examiner' })}</Link></div></li>)}</ol>
      <p className="small muted">{query.data.asOf}</p><Limitations lines={query.data.limitations} />
    </FactScopeProvider>}
  </Card>;
}
