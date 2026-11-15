'use client';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';

type Family = { id: string; name: string; state: 'available' | 'evidence' | 'aside' | 'removed'; requirement: string; source_ids: string[] };
type Source = { id: string; provider: string; source_url: string; status: string; remaining_work_or_external_blocker: string };
export type CapabilityResponse = { families: Family[]; catalogue: { rows: Source[]; source_count: number }; note: string };

export function useSourceCapabilities() {
  const { sessionId } = useApp();
  return useQuery<CapabilityResponse>(sessionId ? `source-capabilities|${sessionId}` : null, async signal => {
    const response = await fetch(`${API_BASE}/intelligence/source-capabilities`, { signal, headers: { 'X-Aplomb-Session': sessionId ?? '' } });
    if (!response.ok) throw new Error('Source capability inventory unavailable');
    return response.json() as Promise<CapabilityResponse>;
  });
}

export function readySource(data: CapabilityResponse | null | undefined, id: string) {
  return data?.families.some(item => item.id === id && (item.state === 'available')) ?? false;
}

export function SourceAvailability({ value, loading, error, reload }: { value: CapabilityResponse | null; loading: boolean; error: Parameters<typeof ErrorState>[0]['error'] | null; reload: () => void }) {
  const { tr } = useApp();
  const aside = value?.families.filter(item => item.state === 'aside') ?? [];
  const removed = value?.families.filter(item => item.state === 'removed') ?? [];
  const active = value?.families.filter(item => item.state === 'available') ?? [];
  const evidence = value?.families.filter(item => item.state === 'evidence') ?? [];
  return <Card id="source-availability" title={tr({ en: 'Research source availability', fr: 'Disponibilité des sources de recherche' })}>
    <p>{tr({ en: 'Available sources have documented successful captures. Current availability can change, and provider coverage remains limited.', fr: 'Les sources disponibles ont des captures documentées. Leur disponibilité peut changer et leur couverture demeure limitée.' })}</p>
    {loading && <Loading />}{error && <ErrorState error={error} onRetry={reload} />}
    {value && <>
      <h3>{tr({ en: 'Available', fr: 'Disponible' })} ({active.length})</h3>
      <ul>{active.map(item => <li key={item.id}><strong>{item.name}</strong> — {tr({ en: 'capture documented', fr: 'capture documentée' })}<span className="block small muted">{item.requirement}</span></li>)}</ul>
      {evidence.length > 0 && <details><summary>{tr({ en: 'Preserved evidence', fr: 'Preuves conservées' })} ({evidence.length})</summary><ul>{evidence.map(item => <li key={item.id}><strong>{item.name}</strong><span className="block small muted">{item.requirement}</span></li>)}</ul></details>}
      <details><summary>{tr({ en: 'Awaiting access or permission', fr: 'En attente d’accès ou de permission' })} ({aside.length})</summary><ul>{aside.map(item => <li key={item.id}><strong>{item.name}</strong><span className="block small muted">{item.requirement}</span></li>)}</ul></details>
      <details><summary>{tr({ en: 'Removed paid sources', fr: 'Sources payantes retirées' })} ({removed.length})</summary><ul>{removed.map(item => <li key={item.id}>{item.requirement}</li>)}</ul></details>
      <details><summary>{tr({ en: `Assigned source catalogue (${value.catalogue.source_count} rows)`, fr: `Catalogue des sources assignées (${value.catalogue.source_count} entrées)` })}</summary>
        <p className="small muted">{tr({ en: 'Rows include duplicated providers and document branch status, not a current availability test.', fr: 'Les entrées comprennent des fournisseurs en double et décrivent l’état de la branche, sans vérifier leur disponibilité actuelle.' })}</p>
        <ul>{value.catalogue.rows.map(row => <li key={row.id}><span className="mono">{row.id}</span> <a href={row.source_url} target="_blank" rel="noreferrer">{row.provider}</a> — {row.status}<span className="block small muted">{row.remaining_work_or_external_blocker}</span></li>)}</ul>
      </details>
    </>}
  </Card>;
}
