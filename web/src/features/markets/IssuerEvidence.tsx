'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Empty, Loading, Unavailable } from '../../components/common/States';

type EvidenceClass = 'direct' | 'derived' | 'model_inferred' | 'unverified';
type Validity = 'valid' | 'not_valid' | 'unknown' | 'observed';
type Scalar = string | number | boolean | null;
type EdgeSource = { source_id: string; url: string | null; content_sha256: string | null; licence: string; retrieved_at: string; published_at: string | null };
type Edge = {
  id: string; subject: string; relation: string; object: string; evidence_class: EvidenceClass;
  valid_from: string | null; valid_to: string | null; temporal: 'interval' | 'point_observation';
  available_at: string; source: EdgeSource | null; derivation: string | null; path: string[];
  qualifiers: Record<string, Scalar>; validity_on_as_of?: Validity;
};
type Annotation = { type: 'reporting_exception' | 'none_published'; level: 'direct' | 'ultimate'; category?: string; reason?: string; reference?: string | null; source_url?: string; source_sha256?: string };
type GraphNode = { id: string; kind: string; label: string | null; attributes: Record<string, Scalar>; annotations: Annotation[] };
type Entity = { lei: string; legal_name: string | null; jurisdiction: string | null; entity_status: string | null; registration_status?: string | null };
type ParentPart = {
  state: 'reported' | 'exception' | 'none_published';
  exception: { category: string; reason: string; reference: string | null; source_url?: string; source_sha256?: string } | null;
  relationship: { parent_lei: string; relationship_status: string | null; period_start: string | null; period_end: string | null; corroboration_level: string | null; source_url: string; source_sha256: string } | null;
  parent: Entity | null;
};
type Child = { lei: string; legal_name: string | null; jurisdiction: string | null; relationship_status: string | null; period_start: string | null; period_end: string | null; source_url: string | null; source_sha256: string | null };
type Children = { total_reported_by_source: number; truncated: boolean; pages_inspected: number; items: Child[] };
type Tree = {
  status: string; lei?: string; entity?: Entity; direct_parent?: ParentPart; ultimate_parent?: ParentPart;
  direct_children?: Children; ultimate_children?: Children; rejected_rows?: number; reused_capture?: boolean;
  source: { retrieved_at: string; golden_copy_published_at: string | null; licence: string; captures: { url: string; http_status: number; sha256: string | null }[] } | null;
  limitations: string[];
};
type Resolution = { isin: string; candidate_source: string; status: 'verified' | 'unverified' | 'no_candidates' | 'source_unavailable'; checks: { lei: string; status: string; pages_inspected?: number | null }[]; verified_issuer_leis: string[] };
type GraphView = {
  query: { lei: string | null; isin: string | null; as_of: string; knowledge: 'as_of' | 'latest'; include_unverified: boolean };
  issuer_resolution: Resolution | null; corporate_tree: Record<string, Tree>;
  root: string; nodes: GraphNode[]; edges: Edge[]; hidden: Record<string, number>; derivation_notes: string[]; limitations: string[];
};

const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const isView = (v: unknown): v is GraphView => obj(v) && typeof v.root === 'string' && Array.isArray(v.nodes) && Array.isArray(v.edges)
  && obj(v.corporate_tree) && obj(v.hidden) && Array.isArray(v.limitations)
  && v.edges.every(e => obj(e) && typeof e.id === 'string' && typeof e.subject === 'string' && typeof e.object === 'string'
    && ['direct', 'derived', 'model_inferred', 'unverified'].includes(String(e.evidence_class)));
const today = () => new Date().toISOString().slice(0, 10);
const shortHash = (h: string | null | undefined) => (h ? `${h.slice(0, 12)}…` : '—');

async function call(path: string, sessionId: string | null): Promise<unknown> {
  const r = await fetch(`${API_BASE}${path}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
  const body: unknown = await r.json().catch(() => null);
  if (!r.ok) {
    const message = obj(body) && obj(body.error) && typeof body.error.message === 'string' ? body.error.message : `HTTP ${r.status}`;
    throw new Error(message);
  }
  return body;
}

export function IssuerEvidence() {
  const { sessionId, tr } = useApp();
  const [isin, setIsin] = useState('');
  const [lei, setLei] = useState('');
  const [asOf, setAsOf] = useState(today);
  const [knowledge, setKnowledge] = useState<'as_of' | 'latest'>('as_of');
  const [includeUnverified, setIncludeUnverified] = useState(false);
  const [pages, setPages] = useState(1);
  const [data, setData] = useState<GraphView | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const classLabel = (c: EvidenceClass) => ({
    direct: tr({ en: 'Direct source', fr: 'Source directe' }),
    derived: tr({ en: 'Derived (stated rule)', fr: 'Dérivé (règle explicite)' }),
    model_inferred: tr({ en: 'Model-inferred', fr: 'Inféré par modèle' }),
    unverified: tr({ en: 'Unverified', fr: 'Non vérifié' }),
  })[c];
  const validityLabel = (v: Validity | undefined) => v === 'valid' ? tr({ en: 'Valid on date', fr: 'Valide à la date' })
    : v === 'observed' ? tr({ en: 'Observed (point in time)', fr: 'Observé (ponctuel)' })
    : v === 'unknown' ? tr({ en: 'Start not documented', fr: 'Début non documenté' })
    : v === 'not_valid' ? tr({ en: 'Not valid on date', fr: 'Non valide à la date' }) : '—';
  const relationLabel = (r: string) => ({
    SECURITY_ISSUED_BY: tr({ en: 'Security issued by', fr: 'Titre émis par' }),
    ENTITY_PARENT_OF: tr({ en: 'Direct parent of', fr: 'Société mère directe de' }),
    ENTITY_ULTIMATE_PARENT_OF: tr({ en: 'Ultimate parent of', fr: 'Société mère ultime de' }),
    SECURITY_ISSUER_ULTIMATE_PARENT: tr({ en: 'Issuer’s ultimate parent', fr: 'Société mère ultime de l’émetteur' }),
    SECURITY_HELD_BY_PORTFOLIO: tr({ en: 'Held by portfolio', fr: 'Détenu par le portefeuille' }),
    PORTFOLIO_HOLDS_ISSUER_SECURITY: tr({ en: 'Portfolio holds a security of', fr: 'Le portefeuille détient un titre de' }),
    CLAIM_SUPPORTED_BY_SOURCE: tr({ en: 'Claim supported by', fr: 'Affirmation appuyée par' }),
    FACT_SOURCED_FROM_DATASET: tr({ en: 'Fact sourced from', fr: 'Fait tiré de' }),
  } as Record<string, string>)[r] ?? r;
  const hiddenLabel = (k: string) => ({
    not_yet_available: tr({ en: 'not yet available on the as-of date', fr: 'pas encore disponibles à la date' }),
    outside_validity: tr({ en: 'outside their validity period', fr: 'hors de leur période de validité' }),
    excluded_class: tr({ en: 'model-inferred or unverified (hidden)', fr: 'inférés ou non vérifiés (masqués)' }),
    edge_limit: tr({ en: 'beyond the display limit', fr: 'au-delà de la limite d’affichage' }),
  } as Record<string, string>)[k] ?? k;
  const reasonLabel = (reason: string) => ({
    NATURAL_PERSONS: tr({ en: 'controlled by natural persons', fr: 'contrôlée par des personnes physiques' }),
    NON_CONSOLIDATING: tr({ en: 'parent does not consolidate', fr: 'la mère ne consolide pas' }),
    NO_KNOWN_PERSON: tr({ en: 'no known controlling person', fr: 'aucune personne de contrôle connue' }),
    NON_PUBLIC: tr({ en: 'parent information not public', fr: 'informations non publiques' }),
    BINDING_LEGAL_COMMITMENTS: tr({ en: 'binding legal commitments', fr: 'engagements juridiques contraignants' }),
    LEGAL_OBSTACLES: tr({ en: 'legal obstacles', fr: 'obstacles juridiques' }),
    DISCLOSURE_DETRIMENTAL: tr({ en: 'disclosure detrimental', fr: 'divulgation préjudiciable' }),
    DETRIMENT_NOT_EXCLUDED: tr({ en: 'detriment not excluded', fr: 'préjudice non exclu' }),
    CONSENT_NOT_OBTAINED: tr({ en: 'consent not obtained', fr: 'consentement non obtenu' }),
  } as Record<string, string>)[reason] ?? reason;

  const names = new Map((data?.nodes ?? []).map(n => [n.id, n.label]));
  const nodeName = (id: string) => {
    const label = names.get(id);
    return label ? `${label} (${id})` : id;
  };

  async function load(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams({ as_of: asOf, knowledge, include_unverified: String(includeUnverified), max_pages: String(pages) });
    const i = isin.trim().toUpperCase(); const l = lei.trim().toUpperCase();
    if (i) params.set('isin', i);
    if (l) params.set('lei', l);
    if (!i && !l) { setError(tr({ en: 'Enter an exact ISIN or LEI.', fr: 'Saisissez un ISIN ou un LEI exact.' })); return; }
    setBusy(true); setError(''); setData(null);
    try {
      const body = await call(`/intelligence/relationships?${params}`, sessionId);
      if (!isView(body)) throw new Error('invalid response');
      setData(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'unavailable');
    } finally { setBusy(false); }
  }

  const sourceCell = (url: string | null | undefined, hash: string | null | undefined) => <>
    {url ? <ExternalLink href={url}>{tr({ en: 'GLEIF record', fr: 'Fiche GLEIF' })}</ExternalLink> : '—'}
    <span className="block small mono" title={hash ?? undefined}>sha256 {shortHash(hash)}</span>
  </>;

  const parentItem = (part: ParentPart | undefined, level: 'direct' | 'ultimate') => {
    const heading = level === 'direct' ? tr({ en: 'Direct parent', fr: 'Société mère directe' }) : tr({ en: 'Ultimate parent', fr: 'Société mère ultime' });
    if (!part) return null;
    if (part.state === 'reported' && part.relationship) {
      const r = part.relationship;
      return <li><strong>{heading}:</strong> {part.parent?.legal_name ?? tr({ en: 'name not fetched', fr: 'nom non récupéré' })} <span className="mono">{r.parent_lei}</span>
        <span className="block small muted">{r.relationship_status ?? '—'} · {r.period_start ?? tr({ en: 'start not documented', fr: 'début non documenté' })} → {r.period_end ?? tr({ en: 'open', fr: 'en cours' })} · {r.corroboration_level ?? '—'}</span>
        <span className="block small">{sourceCell(r.source_url, r.source_sha256)}</span></li>;
    }
    if (part.state === 'exception' && part.exception) {
      return <li><strong>{heading}:</strong> {tr({ en: 'not reported', fr: 'non déclarée' })}: {reasonLabel(part.exception.reason)} <span className="small mono">({part.exception.reason})</span>
        <span className="block small">{sourceCell(part.exception.source_url, part.exception.source_sha256)}</span></li>;
    }
    return <li><strong>{heading}:</strong> {tr({ en: 'no relationship or reporting exception published in GLEIF (this does not prove there is none)', fr: 'aucune relation ni exception publiée dans GLEIF (cela ne prouve pas l’absence)' })}</li>;
  };

  const childList = (group: Children | undefined, label: string) => {
    if (!group) return null;
    return <li><strong>{label}</strong>: {group.items.length} / {group.total_reported_by_source} {tr({ en: 'reported by GLEIF', fr: 'déclarées par GLEIF' })}
      {group.truncated && <span className="block small muted">{tr({ en: `Only ${group.pages_inspected} page(s) read; increase pages to see more.`, fr: `Seulement ${group.pages_inspected} page(s) lue(s); augmentez le nombre de pages.` })}</span>}
      {group.items.length > 0 && <details><summary>{tr({ en: 'Show entities', fr: 'Afficher les entités' })}</summary>
        <ul>{group.items.map(c => <li key={c.lei}>{c.legal_name ?? tr({ en: 'name not fetched', fr: 'nom non récupéré' })} <span className="mono">{c.lei}</span>
          <span className="small muted"> · {c.jurisdiction ?? '—'} · {c.relationship_status ?? '—'} · {c.period_start ?? '?'} → {c.period_end ?? tr({ en: 'open', fr: 'en cours' })}</span></li>)}</ul>
      </details>}
    </li>;
  };

  return <Card title={tr({ en: 'Issuer and corporate relationships', fr: 'Émetteur et relations de groupe' })}>
    <p>{tr({ en: 'Enter an exact ISIN and/or LEI. An ISIN alone gives GLEIF candidates, and only an exact ISIN–LEI pair check links the security to an issuer. Parent and subsidiary links come from GLEIF Level 2 (accounting consolidation, not ownership percentage). Names never create links.', fr: 'Saisissez un ISIN et/ou un LEI exacts. Un ISIN seul donne des candidats GLEIF; seule une vérification exacte de la paire ISIN–LEI relie le titre à un émetteur. Les liens mère/filiale proviennent de GLEIF niveau 2 (consolidation comptable, pas un pourcentage de détention). Les noms ne créent jamais de lien.' })}</p>
    <form onSubmit={load}>
      <div className="field"><label htmlFor="rel-isin">ISIN</label><input id="rel-isin" value={isin} maxLength={12} onChange={e => setIsin(e.target.value)} autoComplete="off" /></div>
      <div className="field"><label htmlFor="rel-lei">LEI</label><input id="rel-lei" value={lei} maxLength={20} onChange={e => setLei(e.target.value)} autoComplete="off" /></div>
      <div className="field"><label htmlFor="rel-asof">{tr({ en: 'As of', fr: 'Au' })}</label><input id="rel-asof" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} required /></div>
      <div className="field"><label htmlFor="rel-knowledge">{tr({ en: 'Knowledge', fr: 'Connaissance' })}</label>
        <select id="rel-knowledge" value={knowledge} onChange={e => setKnowledge(e.target.value === 'latest' ? 'latest' : 'as_of')}>
          <option value="as_of">{tr({ en: 'Only what was available on the date', fr: 'Seulement ce qui était disponible à la date' })}</option>
          <option value="latest">{tr({ en: 'What is known now (labelled)', fr: 'Ce qui est connu aujourd’hui (signalé)' })}</option>
        </select></div>
      <div className="field"><label htmlFor="rel-pages">{tr({ en: 'Subsidiary pages (100 each)', fr: 'Pages de filiales (100 chacune)' })}</label>
        <select id="rel-pages" value={pages} onChange={e => setPages(Number(e.target.value))}>{[1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}</select></div>
      <div className="field"><label><input type="checkbox" checked={includeUnverified} onChange={e => setIncludeUnverified(e.target.checked)} /> {tr({ en: 'Include model-inferred and unverified links', fr: 'Inclure les liens inférés ou non vérifiés' })}</label></div>
      <button className="btn" disabled={busy || !sessionId}>{tr({ en: 'Show relationships', fr: 'Afficher les relations' })}</button>
    </form>
    {busy && <Loading label={tr({ en: 'Capturing GLEIF records…', fr: 'Capture des fiches GLEIF…' })} />}
    {error && <Unavailable title={tr({ en: 'Relationships unavailable', fr: 'Relations indisponibles' })}>{error}</Unavailable>}
    {data && <div role="region" aria-label={tr({ en: 'Relationship results', fr: 'Résultats des relations' })}>
      {data.query.knowledge === 'latest' && <p className="small"><strong>{tr({ en: 'Shown with today’s knowledge: some links may not have been knowable on the as-of date.', fr: 'Affiché avec les connaissances actuelles : certains liens n’étaient peut-être pas connaissables à la date.' })}</strong></p>}
      {data.issuer_resolution && <section>
        <h3>{tr({ en: 'Security → issuer', fr: 'Titre → émetteur' })}</h3>
        <p role="status">{data.issuer_resolution.status === 'verified'
          ? tr({ en: `Exact pair verified in GLEIF: ${data.issuer_resolution.verified_issuer_leis.join(', ')}`, fr: `Paire exacte vérifiée dans GLEIF : ${data.issuer_resolution.verified_issuer_leis.join(', ')}` })
          : data.issuer_resolution.status === 'no_candidates' ? tr({ en: 'GLEIF returned no candidate issuer for this ISIN.', fr: 'GLEIF n’a renvoyé aucun émetteur candidat pour cet ISIN.' })
          : data.issuer_resolution.status === 'source_unavailable' ? tr({ en: 'GLEIF candidate lookup unavailable; issuer unresolved.', fr: 'Recherche GLEIF indisponible; émetteur non résolu.' })
          : tr({ en: 'No candidate could be verified as an exact pair; issuer unresolved.', fr: 'Aucun candidat vérifié comme paire exacte; émetteur non résolu.' })}</p>
        {data.issuer_resolution.checks.length > 0 && <ul className="small">{data.issuer_resolution.checks.map(c => <li key={c.lei}><span className="mono">{c.lei}</span>: {c.status}{c.pages_inspected ? ` (${c.pages_inspected} p.)` : ''}</li>)}</ul>}
      </section>}
      {Object.entries(data.corporate_tree).map(([key, tree]) => <section key={key}>
        <h3>{tr({ en: 'Corporate tree', fr: 'Structure du groupe' })}: {tree.entity?.legal_name ?? key} <span className="mono small">{key}</span></h3>
        {tree.status !== 'captured' ? <Unavailable title={tree.status === 'lei_not_found' ? tr({ en: 'LEI not found in GLEIF', fr: 'LEI introuvable dans GLEIF' }) : tr({ en: 'GLEIF Level 2 unavailable', fr: 'GLEIF niveau 2 indisponible' })}>{tree.limitations.join(' ')}</Unavailable>
          : <ul aria-label={tr({ en: 'Corporate tree', fr: 'Structure du groupe' })}>
            {parentItem(tree.ultimate_parent, 'ultimate')}
            {parentItem(tree.direct_parent, 'direct')}
            <li><strong>{tr({ en: 'Entity', fr: 'Entité' })}:</strong> {tree.entity?.legal_name} · {tree.entity?.jurisdiction ?? '—'} · {tree.entity?.entity_status ?? '—'}
              <ul>
                {childList(tree.direct_children, tr({ en: 'Direct subsidiaries', fr: 'Filiales directes' }))}
                {childList(tree.ultimate_children, tr({ en: 'Entities it ultimately consolidates', fr: 'Entités consolidées en dernier ressort' }))}
              </ul></li>
          </ul>}
        {tree.source && <p className="small muted">{tr({ en: 'Captured', fr: 'Capturé' })} {tree.source.retrieved_at} · {tr({ en: 'GLEIF golden copy', fr: 'Copie de référence GLEIF' })} {tree.source.golden_copy_published_at ?? '—'} · {tree.source.licence} · {tree.source.captures.length} {tr({ en: 'requests', fr: 'requêtes' })}{tree.reused_capture ? ` · ${tr({ en: 'reused today’s capture', fr: 'capture du jour réutilisée' })}` : ''}{tree.rejected_rows ? ` · ${tree.rejected_rows} ${tr({ en: 'rows rejected', fr: 'lignes rejetées' })}` : ''}</p>}
      </section>)}
      <h3>{tr({ en: 'Dated relationships', fr: 'Relations datées' })}</h3>
      {data.edges.length === 0 ? <Empty>{tr({ en: 'No relationship is shown for this date and setting. Absence here is not evidence of no relationship.', fr: 'Aucune relation affichée pour cette date et ce réglage. L’absence ici ne prouve pas l’absence de relation.' })}</Empty>
        : <div className="table-scroll" role="region" aria-label={tr({ en: 'Relationship edges', fr: 'Liens de relation' })} tabIndex={0}>
          <table className="data-table"><thead><tr>
            <th scope="col">{tr({ en: 'From', fr: 'De' })}</th><th scope="col">{tr({ en: 'Relationship', fr: 'Relation' })}</th><th scope="col">{tr({ en: 'To', fr: 'Vers' })}</th>
            <th scope="col">{tr({ en: 'Evidence', fr: 'Preuve' })}</th><th scope="col">{tr({ en: 'Valid', fr: 'Validité' })}</th><th scope="col">{tr({ en: 'Available', fr: 'Disponible' })}</th><th scope="col">{tr({ en: 'Source', fr: 'Source' })}</th>
          </tr></thead><tbody>
            {data.edges.map(e => <tr key={e.id}>
              <td className="break">{nodeName(e.subject)}</td>
              <td>{relationLabel(e.relation)}{e.qualifiers.relationship_status ? <span className="block small muted">{String(e.qualifiers.relationship_status)}</span> : null}</td>
              <td className="break">{nodeName(e.object)}</td>
              <td>{classLabel(e.evidence_class)}{e.derivation && <span className="block small muted">{e.derivation} · {tr({ en: 'path', fr: 'chemin' })}: {e.path.join(' → ')}</span>}</td>
              <td>{e.valid_from ?? '?'} → {e.temporal === 'point_observation' ? tr({ en: '(snapshot)', fr: '(instantané)' }) : e.valid_to ?? tr({ en: 'open', fr: 'en cours' })}<span className="block small muted">{validityLabel(e.validity_on_as_of)}</span></td>
              <td className="small">{e.available_at}</td>
              <td>{e.source ? <>{e.source.url ? <ExternalLink href={e.source.url}>{e.source.source_id}</ExternalLink> : e.source.source_id}<span className="block small mono" title={e.source.content_sha256 ?? undefined}>sha256 {shortHash(e.source.content_sha256)}</span><span className="block small muted">{e.source.licence}</span></> : tr({ en: 'Derived from the path', fr: 'Dérivé du chemin' })}</td>
            </tr>)}
          </tbody></table>
        </div>}
      {Object.keys(data.hidden).length > 0 && <p className="small muted">{tr({ en: 'Hidden', fr: 'Masqués' })}: {Object.entries(data.hidden).map(([k, n]) => `${n} ${hiddenLabel(k)}`).join(' · ')}</p>}
      {data.derivation_notes.length > 0 && <ul className="small muted">{data.derivation_notes.map(n => <li key={n}>{n}</li>)}</ul>}
      <ul className="small muted">{data.limitations.map(l => <li key={l}>{l}</li>)}</ul>
    </div>}
  </Card>;
}
