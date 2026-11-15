'use client';
import { useMemo, useState } from 'react';
import sources from '../../data/source-directory.json';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ExternalLink } from '../../components/common/ExternalLink';

const categories = [...new Set(sources.map(s => s.category))];
const accessLabels: Record<string, { en: string; fr: string }> = {
  A: { en: 'Public / generally keyless', fr: 'Public / généralement sans clé' },
  F: { en: 'Signup / free tier', fr: 'Inscription / offre gratuite' },
  D: { en: 'Bulk dataset', fr: 'Jeu de données téléchargeable' },
  M: { en: 'Mixed paid/free', fr: 'Offre mixte payante/gratuite' },
  S: { en: 'Account / approval', fr: 'Compte / autorisation' },
  T: { en: 'Trial / credits', fr: 'Essai / crédits' },
  P: { en: 'Paid / licensed', fr: 'Payant / sous licence' },
  R: { en: 'Restricted', fr: 'Accès restreint' },
  U: { en: 'Unofficial', fr: 'Non officiel' },
};

export function SourceDirectory() {
  const { tr } = useApp();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [access, setAccess] = useState('');
  const matches = useMemo(() => sources.filter(s => (!category || s.category === category)
    && (!access || s.access === access)
    && `${s.name} ${s.use} ${s.category}`.toLowerCase().includes(query.trim().toLowerCase())), [query, category, access]);
  return <Card id="worldwide-directory" title={tr({ en: 'Worldwide source research directory', fr: 'Répertoire mondial des sources candidates' })}>
    <p>{tr({ en: '243 researched API and dataset entries. These are candidate sources; access codes do not establish current availability, integration, or redistribution rights. Loaded datasets and their evidence appear in the passports above.', fr: '243 entrées de recherche. Ce sont des sources candidates; les codes d’accès ne prouvent ni disponibilité, ni intégration, ni droits de redistribution. Les jeux chargés et leurs preuves figurent dans les passeports ci-dessus.' })}</p>
    <div className="form-grid">
      <div className="field"><label htmlFor="source-search">{tr({ en: 'Search sources and uses', fr: 'Rechercher une source ou un usage' })}</label><input id="source-search" type="search" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <div className="field"><label htmlFor="source-category">{tr({ en: 'Category', fr: 'Catégorie' })}</label><select id="source-category" value={category} onChange={e => setCategory(e.target.value)}><option value="">{tr({ en: 'All categories', fr: 'Toutes les catégories' })}</option>{categories.map(c => <option key={c}>{c}</option>)}</select></div>
      <div className="field"><label htmlFor="source-access">{tr({ en: 'Access research', fr: 'Accès documenté' })}</label><select id="source-access" value={access} onChange={e => setAccess(e.target.value)}><option value="">{tr({ en: 'All access types', fr: 'Tous les accès' })}</option>{Object.entries(accessLabels).map(([k, label]) => <option key={k} value={k}>{tr(label)}</option>)}</select></div>
    </div>
    <p className="small muted" role="status">{matches.length} / {sources.length} · {tr({ en: 'Research compiled 2026-11-15; provider terms require verification.', fr: 'Recherche du 2026-11-15; conditions à vérifier auprès des fournisseurs.' })}</p>
    <div className="table-scroll" role="region" aria-label={tr({ en: 'Worldwide candidate sources', fr: 'Sources candidates mondiales' })} tabIndex={0} style={{ maxHeight: 560 }}>
      <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Source', fr: 'Source' })}</th><th scope="col">{tr({ en: 'Data / purpose', fr: 'Données / usage' })}</th><th scope="col">{tr({ en: 'Access', fr: 'Accès' })}</th></tr></thead><tbody>
        {matches.map(s => <tr key={s.sourceId}><th scope="row"><ExternalLink href={s.url}>{s.name}</ExternalLink><span className="block small muted">{s.category}</span></th><td>{s.use}</td><td>{tr(accessLabels[s.access]!)}<span className="block small muted">{tr({ en: 'Candidate · reuse unverified', fr: 'Candidate · réutilisation non vérifiée' })}</span></td></tr>)}
      </tbody></table>
      {matches.length === 0 && <p>{tr({ en: 'No matching candidates.', fr: 'Aucune source correspondante.' })}</p>}
    </div>
  </Card>;
}
