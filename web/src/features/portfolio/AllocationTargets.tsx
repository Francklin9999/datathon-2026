'use client';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import type { Profile } from '../../contracts/types';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { fmtPct, fmtPts } from '../../lib/format';

export function AllocationTargets({ profile }: { profile: Profile }) {
  const { tr, sessionId, lang } = useApp();
  const query = useQuery(sessionId ? `targets|${sessionId}|${profile.profileId}|${profile.version}` : null, signal => getApiClient().allocationTargets(profile.profileId, signal));
  return <Card title={tr({ en: 'Target allocation drift', fr: 'Dérive des cibles de répartition' })}>
    {query.loading && <Loading />}{query.error && <ErrorState error={query.error} onRetry={query.reload} />}
    {query.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Current weights versus user targets', fr: 'Poids actuels et cibles utilisateur' }, facts: query.data.facts }}>
      {!query.data.targets.length ? <p className="small muted">{tr({ en: 'Enter explicit targets and a drift threshold in Profiles to compare with current traded holdings.', fr: 'Saisissez des cibles et un seuil de dérive dans Profils pour les comparer aux positions cotées actuelles.' })}</p> : <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Target allocation drift', fr: 'Dérive des cibles' })}><table><thead><tr><th>{tr({ en: 'Target', fr: 'Cible' })}</th><th>{tr({ en: 'Actual weight', fr: 'Poids actuel' })}</th><th>{tr({ en: 'Target weight', fr: 'Poids cible' })}</th><th>{tr({ en: 'Drift', fr: 'Dérive' })}</th><th>{tr({ en: 'State / origin', fr: 'État / origine' })}</th></tr></thead><tbody>{query.data.targets.map((row, i) => <tr key={i}><th scope="row">{row.dimension}: {row.key}</th><td>{row.actualPct === null ? tr({ en: 'Unknown', fr: 'Inconnu' }) : row.factId ? <FactChip factId={row.factId} display={fmtPct(row.actualPct, lang)} /> : fmtPct(row.actualPct, lang)}</td><td>{fmtPct(row.targetPct, lang)}</td><td>{row.driftPct === null ? '—' : fmtPts(row.driftPct, lang)}{row.driftThresholdPct === null ? '' : ` (±${row.driftThresholdPct})`}</td><td>{row.state.replaceAll('_', ' ')} · {row.origin}{row.unavailableReason ? ` · ${row.unavailableReason}` : ''}</td></tr>)}</tbody></table></div>}
      <p className="small muted">{query.data.asOf} · {tr({ en: 'Review frequency', fr: 'Fréquence de révision' })}: {profile.investorContext?.rebalancing?.frequency ?? tr({ en: 'unspecified', fr: 'non précisée' })}</p>{query.data.limitations.map(l => <p className="small muted" key={l}>{l}</p>)}
    </FactScopeProvider>}
  </Card>;
}
