'use client';
import { useState } from 'react';
import type { EntitySearchResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';

export function EntityResearch() {
  const { tr, sessionId } = useApp();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const result = useQuery<EntitySearchResponse>(sessionId && query ? `gleif|${sessionId}|${query}` : null,
    signal => getApiClient().entityCandidates(query, signal));
  return <Card title={tr({ en: 'Legal entity research', fr: 'Recherche d’entités juridiques' })}>
    <p>{tr({ en: 'Search the official GLEIF directory for legal names and LEIs. Results are candidates: name similarity does not prove that an entity issues a selected security, owns a facility, or belongs to your portfolio.', fr: 'Consultez le répertoire officiel GLEIF pour les raisons sociales et LEI. Les résultats sont des candidats : un nom similaire ne prouve ni l’émetteur d’un titre, ni la propriété d’une installation, ni un lien avec votre portefeuille.' })}</p>
    <form onSubmit={e => { e.preventDefault(); setQuery(text.trim()); }}><div className="field"><label htmlFor="entity-name">{tr({ en: 'Legal entity name', fr: 'Raison sociale' })}</label><input id="entity-name" minLength={2} maxLength={120} value={text} onChange={e => setText(e.target.value)} /></div><button className="btn" disabled={text.trim().length < 2 || result.loading}>{tr({ en: 'Search GLEIF', fr: 'Rechercher dans GLEIF' })}</button></form>
    {result.loading && <Loading />}{result.error && <ErrorState error={result.error} onRetry={result.reload} />}
    {result.data && <>
      <p className="small muted">GLEIF · {result.data.source.licence} · {result.data.source.retrievedAt} · {result.data.returned} / {result.data.total}</p>
      {result.data.truncated && <p>{tr({ en: 'One bounded page is shown; this is not an exhaustive match list.', fr: 'Une seule page limitée est affichée; cette liste n’est pas exhaustive.' })}</p>}
      <ul className="list-plain">{result.data.items.map(entity => <li key={entity.lei}><ExternalLink href={entity.recordUrl}>{entity.legalName}</ExternalLink><span className="block small mono">LEI {entity.lei} · {entity.jurisdiction ?? '—'} · {entity.entityStatus ?? '—'}</span><span className="pill">{tr({ en: 'Unmatched candidate', fr: 'Candidat sans lien établi' })}</span></li>)}</ul>
      <ExternalLink href={result.data.source.licenceUrl}>{tr({ en: 'Source terms', fr: 'Conditions de la source' })}</ExternalLink>
    </>}
  </Card>;
}
