'use client';
/**
 * SEC EDGAR explorer: XBRL company concept time series (every revision kept, filing date as
 * availability), XBRL frames across companies for one concept/unit/period, the EDGAR latest-filings
 * Atom feed, and Form N-CEN fund census filings. Values arrive as exact decimal strings with their
 * unit; entity names and feed titles are labels only. Each tab has its own explicit unavailable state.
 */
import { useState, type FormEvent, type ReactNode } from 'react';
import { API_BASE } from '../../api/index';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Card } from '../../components/common/Page';
import { Loading, Unavailable } from '../../components/common/States';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { useApp } from '../../state/app';

type Tab = 'concept' | 'frames' | 'feed' | 'ncen';
type Source = { url: string; sha256: string; retrieved_at: string; kind?: string };
type Envelope<R> = {
  kind: string; status: 'available' | 'unavailable'; code?: string; http_status?: number | null;
  source?: Source; sources?: Source[]; result?: R; limitations?: string[];
  registrant?: NcenRegistrant; filing?: NcenFiling;
};
type Observation = {
  value: string; unit: string; period_start: string | null; period_end: string; duration_days: number | null;
  fiscal_year: number | null; fiscal_period: string | null; form: string | null; is_amendment_form: boolean;
  filed: string; accession: string; frame: string | null; filing_index_url: string; revision: number;
  revisions_in_period: number; value_changed_from_prior_revision: boolean | null;
};
type PointInTime = { period_start: string | null; period_end: string; value: string; unit: string; filed: string; accession: string; form: string | null; revision: number; revisions_known_as_of: number };
type ConceptUnit = { unit: string; observations: Observation[]; observation_count: number; truncated: boolean; period_count: number; periods_with_multiple_revisions: number; point_in_time: PointInTime[] | null };
type Concept = { cik: string; taxonomy: string; tag: string; label: string | null; description: string | null; entity_name_label: string | null; units: ConceptUnit[]; as_of: string | null };
type FrameRow = { rank: number; cik: string; entity_name_label: string | null; location_label: string | null; value: string; unit: string; period_start: string | null; period_end: string; accession: string; filing_index_url: string };
type Frame = { tag: string; unit: string; period: string; label: string | null; reported_point_count: number | null; statistics: { count: number; min: string | null; max: string | null; median: string | null; method: string }; rows: FrameRow[]; truncated: boolean };
type FeedEntry = { title_label: string; url: string; form: string | null; accession: string | null; filed: string | null; feed_updated_at: string | null; cik_from_link: string | null; role_label: string | null; form_name_label: string | null };
type Feed = { feed_title_label: string | null; feed_updated_at: string | null; entries: FeedEntry[]; skipped_entries: number; filtered_out_entries: number };
type NcenFiling = { form: string; accession: string; filed: string; period_end: string | null; accepted_at: string | null; url: string; index_url: string };
type NcenRegistrant = { cik: string; registrant_name_label: string | null; entity_type_label: string | null; filings: NcenFiling[] };
type Leaf = { path: string; value: string };
type Ncen = { submission_type: string | null; filer_cik_present_in_document: boolean; leaf_count: number; leaves: Leaf[]; leaves_truncated: boolean; series_id: string | null; series_blocks: { container: string; matched_field: string; fields: Leaf[] }[] | null };
type Failure = { status: number | null };

/** Group digits of an exact decimal string without converting it to a binary float. */
function fmtDecimal(value: string, lang: string) {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return value;
  const [, sign, int, frac] = match;
  const group = lang === 'fr' ? ' ' : ',';
  const grouped = (int ?? '').replace(/\B(?=(\d{3})+(?!\d))/g, group);
  return `${sign}${grouped}${frac ? (lang === 'fr' ? ',' : '.') + frac : ''}`;
}

function useCodeText() {
  const { tr } = useApp();
  const known: Record<string, { en: string; fr: string }> = {
    sec_contact_unconfigured: { en: 'SEC contact (APLOMB_SEC_CONTACT) is not configured; no request was sent.', fr: 'Le contact SEC (APLOMB_SEC_CONTACT) n’est pas configuré; aucune requête envoyée.' },
    sec_access_denied: { en: 'SEC refused access (HTTP 403). It was not retried or bypassed.', fr: 'La SEC a refusé l’accès (HTTP 403). Aucune nouvelle tentative ni contournement.' },
    rate_limited: { en: 'SEC rate limit reached; try again later.', fr: 'Limite de débit SEC atteinte; réessayez plus tard.' },
    request_timeout: { en: 'SEC did not answer in time.', fr: 'La SEC n’a pas répondu à temps.' },
    source_unavailable: { en: 'SEC source unavailable or not found for this request.', fr: 'Source SEC indisponible ou introuvable pour cette requête.' },
    response_too_large: { en: 'SEC response exceeded the size limit.', fr: 'La réponse SEC dépasse la taille permise.' },
    no_ncen_filing_in_recent_submissions: { en: 'No N-CEN filing in this registrant’s recent submissions.', fr: 'Aucun dépôt N-CEN dans les dépôts récents de ce déclarant.' },
    unsafe_or_oversized_xml: { en: 'Rejected XML (DTD/entity declaration or oversized).', fr: 'XML rejeté (DTD/entité ou taille excessive).' },
  };
  return (code?: string) => code && known[code] ? tr(known[code]) : tr({ en: `Unavailable (${code ?? 'unknown'}).`, fr: `Indisponible (${code ?? 'inconnu'}).` });
}

async function getSec<R>(path: string, params: Record<string, string>, sessionId: string | null): Promise<Envelope<R> | Failure> {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== ''));
  try {
    const response = await fetch(`${API_BASE}/research/sec/${path}${query.size ? `?${query}` : ''}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
    if (!response.ok) return { status: response.status };
    const body = await response.json() as Envelope<R>;
    if (!body || (body.status !== 'available' && body.status !== 'unavailable')) return { status: null };
    return body;
  } catch { return { status: null }; }
}

function isFailure<R>(value: Envelope<R> | Failure | null): value is Failure {
  return !!value && !('kind' in value);
}

function Outcome<R>({ value, busy, children }: { value: Envelope<R> | Failure | null; busy: boolean; children: (env: Envelope<R>, result: R) => ReactNode }) {
  const { tr } = useApp();
  const codeText = useCodeText();
  if (busy) return <Loading />;
  if (!value) return null;
  if (isFailure(value)) {
    return <Unavailable title={tr({ en: 'Request not completed', fr: 'Requête non complétée' })}>
      {value.status === 429 ? tr({ en: 'Request limit reached; wait a minute.', fr: 'Limite de requêtes atteinte; patientez une minute.' })
        : value.status === 400 ? tr({ en: 'Input rejected by validation.', fr: 'Saisie rejetée par la validation.' })
          : tr({ en: 'Service unreachable or invalid response.', fr: 'Service injoignable ou réponse invalide.' })}
    </Unavailable>;
  }
  return <div aria-live="polite" className="stack">
    {value.status === 'unavailable' || value.result === undefined
      ? <Unavailable title={tr({ en: 'SEC source unavailable', fr: 'Source SEC indisponible' })}>{codeText(value.code)}</Unavailable>
      : children(value, value.result)}
    {[...(value.source ? [value.source] : []), ...(value.sources ?? [])].map(s => <p key={s.url + s.sha256} className="small break">
      <ExternalLink href={s.url}>{tr({ en: 'SEC source', fr: 'Source SEC' })}</ExternalLink>{s.kind ? ` (${s.kind})` : ''} · {tr({ en: 'captured', fr: 'capturé' })} {s.retrieved_at}<br /><span className="mono">SHA-256 {s.sha256}</span>
    </p>)}
    {value.limitations && value.limitations.length > 0 && <details><summary className="small">{tr({ en: 'Limitations', fr: 'Limites' })}</summary><ul className="small muted">{value.limitations.map(l => <li key={l}>{l}</li>)}</ul></details>}
  </div>;
}

function Period({ start, end }: { start: string | null; end: string }) {
  return <>{start ? `${start} → ${end}` : end}</>;
}

function ConceptPanel() {
  const { sessionId, tr, lang } = useApp();
  const [cik, setCik] = useState('');
  const [taxonomy, setTaxonomy] = useState('us-gaap');
  const [tag, setTag] = useState('Assets');
  const [asOf, setAsOf] = useState('');
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState<Envelope<Concept> | Failure | null>(null);
  const [unitIndex, setUnitIndex] = useState(0);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setValue(null); setUnitIndex(0);
    setValue(await getSec<Concept>(`concept/${encodeURIComponent(cik.trim())}`, { taxonomy, tag: tag.trim(), as_of: asOf }, sessionId));
    setBusy(false);
  }
  return <div className="stack">
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="secx-concept-cik">CIK</label><input id="secx-concept-cik" inputMode="numeric" pattern="[0-9]{1,10}" value={cik} onChange={e => setCik(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-concept-tax">{tr({ en: 'Taxonomy', fr: 'Taxonomie' })}</label><select id="secx-concept-tax" value={taxonomy} onChange={e => setTaxonomy(e.target.value)}>{['us-gaap', 'ifrs-full', 'dei', 'srt'].map(t => <option key={t}>{t}</option>)}</select></div>
      <div className="field"><label htmlFor="secx-concept-tag">{tr({ en: 'Concept tag (exact XBRL name)', fr: 'Concept (nom XBRL exact)' })}</label><input id="secx-concept-tag" value={tag} pattern="[A-Za-z][A-Za-z0-9_]{1,150}" onChange={e => setTag(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-concept-asof">{tr({ en: 'Point-in-time view as of (optional)', fr: 'Vue à date (facultatif)' })}</label><input id="secx-concept-asof" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} /></div>
      <button className="btn" disabled={busy || !sessionId}>{tr({ en: 'Load concept', fr: 'Charger le concept' })}</button>
    </form>
    <Outcome value={value} busy={busy}>{(_env, c) => {
      const unit = c.units[Math.min(unitIndex, Math.max(0, c.units.length - 1))];
      return <>
        <p><strong>{c.label ?? c.tag}</strong> · {c.taxonomy}:{c.tag} · CIK <span className="mono">{c.cik}</span>{c.entity_name_label && <> · <span className="muted">{c.entity_name_label} ({tr({ en: 'label', fr: 'libellé' })})</span></>}</p>
        {c.description && <p className="small muted">{c.description}</p>}
        {c.units.length > 1 && <div className="field"><label htmlFor="secx-concept-unit">{tr({ en: 'Unit', fr: 'Unité' })}</label><select id="secx-concept-unit" value={unitIndex} onChange={e => setUnitIndex(Number(e.target.value))}>{c.units.map((u, i) => <option key={u.unit} value={i}>{u.unit}</option>)}</select></div>}
        {!unit ? <p className="muted">{tr({ en: 'No units reported.', fr: 'Aucune unité déclarée.' })}</p> : <>
          <p className="small" role="status">{tr({ en: 'Unit', fr: 'Unité' })} <strong>{unit.unit}</strong> · {unit.observation_count} {tr({ en: 'observations', fr: 'observations' })} · {unit.period_count} {tr({ en: 'periods', fr: 'périodes' })} · {unit.periods_with_multiple_revisions} {tr({ en: 'periods reported more than once', fr: 'périodes déclarées plusieurs fois' })}{unit.truncated && tr({ en: ' · display limit reached', fr: ' · limite d’affichage atteinte' })}</p>
          {unit.point_in_time && <details open><summary>{tr({ en: `Known as of ${c.as_of}`, fr: `Connu au ${c.as_of}` })} ({unit.point_in_time.length})</summary>
            <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Point-in-time values', fr: 'Valeurs à date' })}><table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Period', fr: 'Période' })}</th><th scope="col">{tr({ en: 'Value', fr: 'Valeur' })} ({unit.unit})</th><th scope="col">{tr({ en: 'Filed', fr: 'Déposé' })}</th><th scope="col">{tr({ en: 'Revision', fr: 'Révision' })}</th></tr></thead><tbody>
              {unit.point_in_time.slice(0, 200).map(p => <tr key={`${p.period_start}-${p.period_end}`}><td><Period start={p.period_start} end={p.period_end} /></td><td className="num">{fmtDecimal(p.value, lang)}</td><td>{p.filed} · {p.form} <span className="mono small">{p.accession}</span></td><td>{p.revision} / {p.revisions_known_as_of}</td></tr>)}
            </tbody></table></div></details>}
          <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'All reported observations', fr: 'Toutes les observations déclarées' })}><table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Period', fr: 'Période' })}</th><th scope="col">{tr({ en: 'Value', fr: 'Valeur' })} ({unit.unit})</th><th scope="col">FY / FP</th><th scope="col">{tr({ en: 'Form', fr: 'Formulaire' })}</th><th scope="col">{tr({ en: 'Filed (available)', fr: 'Déposé (disponible)' })}</th><th scope="col">{tr({ en: 'Revision', fr: 'Révision' })}</th><th scope="col">{tr({ en: 'Accession', fr: 'Numéro d’accès' })}</th></tr></thead><tbody>
            {unit.observations.slice(0, 300).map(o => <tr key={`${o.accession}-${o.period_start}-${o.period_end}-${o.filed}`}>
              <td><Period start={o.period_start} end={o.period_end} />{o.duration_days != null && <span className="block small muted">{o.duration_days} {tr({ en: 'days', fr: 'jours' })}</span>}</td>
              <td className="num">{fmtDecimal(o.value, lang)}</td>
              <td>{o.fiscal_year ?? '—'} / {o.fiscal_period ?? '—'}</td>
              <td>{o.form ?? '—'}{o.is_amendment_form && <span className="block small">{tr({ en: 'amendment', fr: 'modification' })}</span>}</td>
              <td>{o.filed}</td>
              <td>{o.revision} / {o.revisions_in_period}{o.value_changed_from_prior_revision && <span className="block small">{tr({ en: 'value changed', fr: 'valeur modifiée' })}</span>}</td>
              <td><ExternalLink href={o.filing_index_url}><span className="mono small">{o.accession}</span></ExternalLink></td>
            </tr>)}
          </tbody></table></div>
          {unit.observations.length > 300 && <p className="small muted">{tr({ en: 'Showing the 300 most recent periods’ rows.', fr: 'Affichage des 300 lignes les plus récentes.' })}</p>}
        </>}
      </>;
    }}</Outcome>
  </div>;
}

function FramesPanel() {
  const { sessionId, tr, lang } = useApp();
  const [tag, setTag] = useState('Assets');
  const [unit, setUnit] = useState('USD');
  const [period, setPeriod] = useState('CY2023Q4I');
  const [order, setOrder] = useState('desc');
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState<Envelope<Frame> | Failure | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setValue(null);
    setValue(await getSec<Frame>('frames', { taxonomy: 'us-gaap', tag: tag.trim(), unit: unit.trim(), period: period.trim().toUpperCase(), order, limit: '200' }, sessionId));
    setBusy(false);
  }
  return <div className="stack">
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="secx-frame-tag">{tr({ en: 'us-gaap concept tag', fr: 'Concept us-gaap' })}</label><input id="secx-frame-tag" value={tag} pattern="[A-Za-z][A-Za-z0-9_]{1,150}" onChange={e => setTag(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-frame-unit">{tr({ en: 'Unit (USD, shares, USD-per-shares)', fr: 'Unité (USD, shares, USD-per-shares)' })}</label><input id="secx-frame-unit" value={unit} onChange={e => setUnit(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-frame-period">{tr({ en: 'Calendar frame (CY2023, CY2023Q4, CY2023Q4I for instants)', fr: 'Période civile (CY2023, CY2023Q4, CY2023Q4I pour un instant)' })}</label><input id="secx-frame-period" value={period} onChange={e => setPeriod(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-frame-order">{tr({ en: 'Order', fr: 'Ordre' })}</label><select id="secx-frame-order" value={order} onChange={e => setOrder(e.target.value)}><option value="desc">{tr({ en: 'Largest first', fr: 'Plus grandes d’abord' })}</option><option value="asc">{tr({ en: 'Smallest first', fr: 'Plus petites d’abord' })}</option></select></div>
      <button className="btn" disabled={busy || !sessionId}>{tr({ en: 'Load frame', fr: 'Charger la période' })}</button>
    </form>
    <Outcome value={value} busy={busy}>{(_env, f) => <>
      <p><strong>{f.label ?? f.tag}</strong> · {f.period} · {tr({ en: 'unit', fr: 'unité' })} <strong>{f.unit}</strong></p>
      <dl className="kv-list">
        <div className="kv"><dt className="k">{tr({ en: 'Entities', fr: 'Entités' })}</dt><dd className="v">{f.statistics.count}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Median', fr: 'Médiane' })}</dt><dd className="v">{f.statistics.median ? fmtDecimal(f.statistics.median, lang) : '—'}</dd></div>
        <div className="kv"><dt className="k">Min</dt><dd className="v">{f.statistics.min ? fmtDecimal(f.statistics.min, lang) : '—'}</dd></div>
        <div className="kv"><dt className="k">Max</dt><dd className="v">{f.statistics.max ? fmtDecimal(f.statistics.max, lang) : '—'}</dd></div>
      </dl>
      <p className="small muted">{f.statistics.method}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Frame rows', fr: 'Lignes de la période' })}><table className="data-table"><thead><tr><th scope="col">#</th><th scope="col">CIK</th><th scope="col">{tr({ en: 'Entity (label)', fr: 'Entité (libellé)' })}</th><th scope="col">{tr({ en: 'Value', fr: 'Valeur' })} ({f.unit})</th><th scope="col">{tr({ en: 'Period', fr: 'Période' })}</th><th scope="col">{tr({ en: 'Accession', fr: 'Numéro d’accès' })}</th></tr></thead><tbody>
        {f.rows.map(r => <tr key={`${r.cik}-${r.accession}`}><td>{r.rank}</td><td className="mono">{r.cik}</td><td>{r.entity_name_label ?? '—'}{r.location_label && <span className="block small muted">{r.location_label}</span>}</td><td className="num">{fmtDecimal(r.value, lang)}</td><td><Period start={r.period_start} end={r.period_end} /></td><td><ExternalLink href={r.filing_index_url}><span className="mono small">{r.accession}</span></ExternalLink></td></tr>)}
      </tbody></table></div>
      {f.truncated && <p className="small muted">{tr({ en: `Showing ${f.rows.length} of ${f.statistics.count} rows; statistics use all rows.`, fr: `${f.rows.length} lignes sur ${f.statistics.count}; les statistiques utilisent toutes les lignes.` })}</p>}
    </>}</Outcome>
  </div>;
}

function FeedPanel() {
  const { sessionId, tr } = useApp();
  const [form, setForm] = useState('8-K');
  const [cik, setCik] = useState('');
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState<Envelope<Feed> | Failure | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setValue(null);
    setValue(await getSec<Feed>('latest-filings', { form: form.trim(), cik: cik.trim(), count: '40' }, sessionId));
    setBusy(false);
  }
  return <div className="stack">
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="secx-feed-form">{tr({ en: 'Form type (blank for all)', fr: 'Type de formulaire (vide pour tous)' })}</label><input id="secx-feed-form" value={form} maxLength={20} onChange={e => setForm(e.target.value)} /></div>
      <div className="field"><label htmlFor="secx-feed-cik">{tr({ en: 'Company CIK (optional, per-company feed)', fr: 'CIK de la société (facultatif, flux par société)' })}</label><input id="secx-feed-cik" inputMode="numeric" pattern="[0-9]{0,10}" value={cik} onChange={e => setCik(e.target.value)} /></div>
      <button className="btn" disabled={busy || !sessionId}>{tr({ en: 'Load feed', fr: 'Charger le flux' })}</button>
    </form>
    <Outcome value={value} busy={busy}>{(_env, f) => <>
      <p className="small" role="status">{f.entries.length} {tr({ en: 'entries', fr: 'entrées' })}{f.feed_updated_at && <> · {tr({ en: 'feed updated', fr: 'flux mis à jour' })} {f.feed_updated_at}</>}{f.skipped_entries > 0 && <> · {f.skipped_entries} {tr({ en: 'entries skipped (unsafe or incomplete link)', fr: 'entrées ignorées (lien incomplet ou non sûr)' })}</>}{f.filtered_out_entries > 0 && <> · {f.filtered_out_entries} {tr({ en: 'outside the form filter', fr: 'hors du filtre de formulaire' })}</>}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Latest filings', fr: 'Derniers dépôts' })}><table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Form', fr: 'Formulaire' })}</th><th scope="col">{tr({ en: 'Title (label)', fr: 'Titre (libellé)' })}</th><th scope="col">CIK</th><th scope="col">{tr({ en: 'Filed', fr: 'Déposé' })}</th><th scope="col">{tr({ en: 'Feed time (UTC)', fr: 'Heure du flux (UTC)' })}</th><th scope="col">{tr({ en: 'Accession', fr: 'Numéro d’accès' })}</th></tr></thead><tbody>
        {f.entries.map((e, i) => <tr key={`${e.url}-${i}`}><td>{e.form ?? '—'}</td><td>{e.title_label}{e.role_label && <span className="block small muted">{e.role_label}</span>}</td><td className="mono">{e.cik_from_link ?? '—'}</td><td>{e.filed ?? '—'}</td><td>{e.feed_updated_at ?? '—'}</td><td><ExternalLink href={e.url}><span className="mono small">{e.accession ?? tr({ en: 'filing', fr: 'dépôt' })}</span></ExternalLink></td></tr>)}
      </tbody></table></div>
    </>}</Outcome>
  </div>;
}

function NcenPanel() {
  const { sessionId, tr } = useApp();
  const [cik, setCik] = useState('');
  const [series, setSeries] = useState('');
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState<Envelope<Ncen> | Failure | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setValue(null);
    setValue(await getSec<Ncen>(`ncen/${encodeURIComponent(cik.trim())}`, { series: series.trim().toUpperCase() }, sessionId));
    setBusy(false);
  }
  const registrant = value && !isFailure(value) ? value.registrant : undefined;
  return <div className="stack">
    <form onSubmit={submit} className="stack">
      <div className="field"><label htmlFor="secx-ncen-cik">{tr({ en: 'Fund registrant CIK', fr: 'CIK du déclarant (fonds)' })}</label><input id="secx-ncen-cik" inputMode="numeric" pattern="[0-9]{1,10}" value={cik} onChange={e => setCik(e.target.value)} required /></div>
      <div className="field"><label htmlFor="secx-ncen-series">{tr({ en: 'Series ID (optional, e.g. S000000000)', fr: 'Identifiant de série (facultatif, ex. S000000000)' })}</label><input id="secx-ncen-series" pattern="[Ss][0-9]{9}" value={series} onChange={e => setSeries(e.target.value)} /></div>
      <button className="btn" disabled={busy || !sessionId}>{tr({ en: 'Load N-CEN', fr: 'Charger N-CEN' })}</button>
    </form>
    {registrant && <div className="small">
      <p>CIK <span className="mono">{registrant.cik}</span>{registrant.registrant_name_label && <> · {registrant.registrant_name_label} ({tr({ en: 'label', fr: 'libellé' })})</>}</p>
      {registrant.filings.length > 0 && <ul>{registrant.filings.map(f => <li key={f.accession}>{f.form} · {tr({ en: 'filed', fr: 'déposé' })} {f.filed}{f.period_end && <> · {tr({ en: 'period', fr: 'période' })} {f.period_end}</>}{f.accepted_at && <> · {tr({ en: 'accepted', fr: 'accepté' })} {f.accepted_at}</>} · <ExternalLink href={f.index_url}><span className="mono">{f.accession}</span></ExternalLink></li>)}</ul>}
    </div>}
    <Outcome value={value} busy={busy}>{(env, n) => <>
      {env.filing && <p>{tr({ en: 'Showing', fr: 'Affiché' })}: {env.filing.form} <span className="mono">{env.filing.accession}</span> · {n.submission_type ?? tr({ en: 'submission type not tagged', fr: 'type de dépôt non balisé' })}</p>}
      <p className="small">{n.filer_cik_present_in_document ? tr({ en: 'The registrant CIK appears in the filing XML.', fr: 'Le CIK du déclarant figure dans le XML du dépôt.' }) : tr({ en: 'The registrant CIK was not found as a value in the filing XML.', fr: 'Le CIK du déclarant n’apparaît pas comme valeur dans le XML.' })}</p>
      {n.series_id && (n.series_blocks && n.series_blocks.length > 0
        ? n.series_blocks.map((b, i) => <details key={`${b.container}-${i}`} open={i === 0}><summary>{tr({ en: 'Series block', fr: 'Bloc de série' })} {n.series_id} · {b.container} ({b.fields.length})</summary><Leaves leaves={b.fields} /></details>)
        : <Unavailable title={tr({ en: 'Series not found', fr: 'Série introuvable' })}>{tr({ en: 'This exact series identifier does not appear in the filing.', fr: 'Cet identifiant de série exact n’apparaît pas dans le dépôt.' })}</Unavailable>)}
      <details><summary>{tr({ en: 'All tagged fields', fr: 'Tous les champs balisés' })} ({n.leaves.length}{n.leaves_truncated ? ` / ${n.leaf_count}` : ''})</summary><Leaves leaves={n.leaves} /></details>
    </>}</Outcome>
  </div>;
}

function Leaves({ leaves }: { leaves: Leaf[] }) {
  const { tr } = useApp();
  return <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Tagged fields', fr: 'Champs balisés' })}><table className="data-table"><thead><tr><th scope="col">{tr({ en: 'XML path', fr: 'Chemin XML' })}</th><th scope="col">{tr({ en: 'Value (as filed)', fr: 'Valeur (telle que déposée)' })}</th></tr></thead><tbody>
    {leaves.map((l, i) => <tr key={`${l.path}-${i}`}><td className="mono small break">{l.path}</td><td className="break">{l.value}</td></tr>)}
  </tbody></table></div>;
}

export function SecExplorer() {
  const { tr } = useApp();
  const [tab, setTab] = useState<Tab>('concept');
  const tabs: { value: Tab; label: string }[] = [
    { value: 'concept', label: tr({ en: 'Concept', fr: 'Concept' }) },
    { value: 'frames', label: tr({ en: 'Frames', fr: 'Périodes' }) },
    { value: 'feed', label: tr({ en: 'Latest filings', fr: 'Derniers dépôts' }) },
    { value: 'ncen', label: 'N-CEN' },
  ];
  return <Card title={tr({ en: 'SEC EDGAR explorer', fr: 'Explorateur SEC EDGAR' })}>
    <p className="small">{tr({ en: 'Official SEC data by exact CIK. Filing date is the availability date, revisions stay separate, and values are exact decimals in the stated unit. Names and titles are labels only.', fr: 'Données officielles de la SEC par CIK exact. La date de dépôt est la date de disponibilité, les révisions restent distinctes et les valeurs sont des décimales exactes dans l’unité indiquée. Noms et titres ne sont que des libellés.' })}</p>
    <SegmentedControl label={tr({ en: 'SEC explorer sections', fr: 'Sections de l’explorateur SEC' })} value={tab} onChange={setTab} options={tabs} size="sm" />
    <div className="stack" role="region" aria-label={tabs.find(t => t.value === tab)?.label}>
      {tab === 'concept' && <ConceptPanel />}
      {tab === 'frames' && <FramesPanel />}
      {tab === 'feed' && <FeedPanel />}
      {tab === 'ncen' && <NcenPanel />}
    </div>
  </Card>;
}
