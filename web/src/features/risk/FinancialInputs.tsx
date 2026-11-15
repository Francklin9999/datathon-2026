'use client';
import { getApiClient } from '../../api/index';
import { useQuery } from '../../state/useQuery';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';

export function FinancialInputs() {
  const { sessionId, tr } = useApp();
  const query = useQuery(sessionId ? `financial-inputs|${sessionId}` : null, signal => getApiClient().sourceInputs(signal));
  return <Card title={tr({ en: 'Captured rate and positioning context', fr: 'Contexte de taux et de positionnement capturé' })}>
    {query.loading && <Loading />}{query.error && <ErrorState error={query.error} onRetry={query.reload} />}
    {query.data && <><p className="small muted">{tr({ en: 'Dated captured observations; no automatic portfolio exposure or forecast is inferred. Capture availability is checked separately from observation dates.', fr: 'Observations capturées et datées; aucune exposition ni prévision du portefeuille n’est déduite. La disponibilité est vérifiée séparément de la date d’observation.' })} · {query.data.knownAt}</p>{query.data.sources.map(source => <details key={source.id}><summary>{source.label ?? source.id} · {source.status.replaceAll('_', ' ')}</summary>
      {source.observation && <dl className="kv-list">{Object.entries(source.observation).map(([key, value]) => <div className="kv" key={key}><dt className="k">{key}</dt><dd className="v">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>}
      <p className="small">{source.limitation}</p>{source.sourceUrl && <ExternalLink href={source.sourceUrl}>{tr({ en: 'Original source', fr: 'Source originale' })}</ExternalLink>}
      <p className="small muted">{source.retrievedAt}</p><p className="small mono" style={{ overflowWrap: 'anywhere' }}>{source.sha256}</p><p className="small muted">{source.rights}</p>
    </details>)}</>}
  </Card>;
}
