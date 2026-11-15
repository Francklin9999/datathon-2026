'use client';
/**
 * Point-in-time disclosure calibration for the Time Machine. Rebuilds, from SEC EDGAR captures
 * retrieved today, which company-reported values and filings were already public at the cutoff
 * (EDGAR acceptance time), and lists the withheld set with reasons. Read-only and separate from
 * replay runs: nothing shown here is an input of a run, and the reveal comparison never changes a
 * signed run.
 */
import { useEffect, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { Loading } from '../../components/common/States';
import { useApp } from '../../state/app';
import { fmtDate } from '../../lib/format';
import { readySource, useSourceCapabilities } from '../markets/SourceAvailability';

type Basis = 'edgar_acceptance' | 'filing_date_end_of_day' | 'unknown';
type FactRow = {
  record_id: string; concept: string; label: string; unit: string; period_start: string | null; period_end: string;
  value: number; filed: string; form: string | null; accession: string; fiscal_year: number | null; fiscal_period: string | null;
  availability_basis: Basis; available_at: string | null; published_at: string | null;
  reason?: string; value_at_cutoff?: number; value_changed?: boolean; accession_at_cutoff?: string; available_at_cutoff?: string | null;
};
type FilingRow = {
  accession: string; form: string; filing_date: string; report_date: string | null; acceptance: string | null;
  availability_basis: Basis; available_at: string | null; url: string; reason?: string;
};
type Source = { kind: string; url: string; sha256: string; retrieved_at: string };
type Base = {
  status: 'available' | 'partial' | 'unavailable'; reason?: string; message?: string;
  cik?: string; name?: string | null; cutoff?: string; boundary?: string; retrieved_at?: string; fact_source?: string | null;
  sources?: Source[]; errors?: { section: string; code: string }[]; notes?: string[]; rejected_source_rows?: number;
  filings_cover_from?: string | null; limitations: string[];
};
type PointInTime = Base & {
  fundamentals?: {
    available: FactRow[]; available_total: number; available_by_basis: Record<string, number>;
    withheld_total: number; withheld_by_reason: Record<string, number>; withheld_revised_values: number;
    withheld: FactRow[]; superseded_before_cutoff: number; excluded_source_rows: Record<string, number>;
    shown_periods_per_concept: number;
  };
  filings?: {
    available_total: number; available_by_form: Record<string, number>; available: FilingRow[];
    withheld_total: number; withheld_by_reason: Record<string, number>; withheld_by_form: Record<string, number>;
    withheld: FilingRow[];
  };
};
type Later = Base & {
  until?: string; statement?: string; new_values_total?: number; new_values?: FactRow[];
  revised_values_total?: number; revised_values?: FactRow[]; filings_total?: number;
  filings_by_form?: Record<string, number>; filings?: FilingRow[];
};
type Candidates = { status: string; candidates?: { cik: string; ticker: string; title: string | null }[]; limitations?: string[] };
type Vintages = { status: string; missing: string[]; reason: string; terms_url: string };

const REASONS: Record<string, { en: string; fr: string }> = {
  published_after_cutoff: { en: 'Published after the cutoff', fr: 'Publié après la date limite' },
  revision_after_cutoff: { en: 'Later revision or re-report of a value known at the cutoff', fr: 'Révision ou nouvelle déclaration ultérieure d’une valeur connue à la date limite' },
  unknown_availability: { en: 'Availability unknown', fr: 'Disponibilité inconnue' },
  observation_after_cutoff: { en: 'Period after the cutoff', fr: 'Période postérieure à la date limite' },
  conflicting_values_in_one_filing: { en: 'Conflicting values in one filing (excluded)', fr: 'Valeurs contradictoires dans un même dépôt (exclues)' },
  ambiguous_same_time_revisions: { en: 'Different values with identical availability (excluded)', fr: 'Valeurs différentes à disponibilité identique (exclues)' },
};
const BASIS: Record<Basis, { en: string; fr: string }> = {
  edgar_acceptance: { en: 'EDGAR acceptance time', fr: 'Heure d’acceptation EDGAR' },
  filing_date_end_of_day: { en: 'Filing date, end of day UTC (date-level)', fr: 'Date de dépôt, fin de journée UTC (au jour près)' },
  unknown: { en: 'Unknown', fr: 'Inconnue' },
};

async function getJson<T>(path: string, sessionId: string | null): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
  if (!response.ok) {
    let message = '';
    try { message = ((await response.json()) as { error?: { message?: string } }).error?.message ?? ''; } catch { /* body is not JSON */ }
    throw new Error(message || `HTTP ${response.status}`);
  }
  return await response.json() as T;
}

function period(row: FactRow) {
  return row.period_start ? `${row.period_start} → ${row.period_end}` : row.period_end;
}

function fmtValue(value: number, unit: string, lang: 'en' | 'fr') {
  return `${new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', { maximumFractionDigits: 4 }).format(value)} ${unit}`;
}

/** The fixed caveat: restricting tools is not the same as a model that does not know the future. */
export function ModelKnowledgeCaveat() {
  const { tr } = useApp();
  return <p className="stale-note" role="note">{tr({
    en: 'Restricting tools and data to what was available at the cutoff does not erase what a language model learned in pretraining. This panel is deterministic calibration of which disclosures were public; it is not evidence that any model predicted history.',
    fr: 'Limiter les outils et les données à ce qui était disponible à la date limite n’efface pas ce qu’un modèle de langage a appris lors de son préentraînement. Ce panneau est un calibrage déterministe des publications alors publiques; il ne prouve pas qu’un modèle a prédit l’histoire.',
  })}</p>;
}

function Counts({ counts, labels }: { counts: Record<string, number>; labels?: Record<string, { en: string; fr: string }> }) {
  const { tr } = useApp();
  const entries = Object.entries(counts);
  if (entries.length === 0) return <span className="muted">—</span>;
  return <>{entries.map(([key, count], i) => <span key={key}>{i > 0 && ' · '}{labels?.[key] ? tr(labels[key]) : key}: <strong>{count}</strong></span>)}</>;
}

function Sources({ data }: { data: Base }) {
  const { tr } = useApp();
  return <>
    {(data.errors ?? []).map(item => <p key={item.section} role="status" className="small">{item.section}: {tr({ en: 'source unavailable, absent or invalid; no value inferred.', fr: 'source indisponible, absente ou invalide; aucune valeur déduite.' })}</p>)}
    {(data.notes ?? []).map(note => <p key={note} className="small muted">{note}</p>)}
    <details className="fold">
      <summary className="small">{tr({ en: 'Sources and limitations', fr: 'Sources et limites' })}</summary>
      {(data.sources ?? []).map(source => <p key={source.url} className="small break"><a href={source.url} target="_blank" rel="noreferrer">SEC EDGAR — {source.kind}</a>, {tr({ en: 'retrieved', fr: 'récupéré' })} <span className="mono">{source.retrieved_at}</span><br /><span className="mono">SHA-256 {source.sha256}</span></p>)}
      {typeof data.rejected_source_rows === 'number' && data.rejected_source_rows > 0 && <p className="small">{tr({ en: 'Source rows rejected as malformed', fr: 'Lignes sources rejetées car mal formées' })}: {data.rejected_source_rows}</p>}
      <ul className="small muted">{data.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </details>
  </>;
}

function FactTable({ rows, label, withheld }: { rows: FactRow[]; label: string; withheld?: boolean }) {
  const { tr, lang } = useApp();
  if (rows.length === 0) return <p className="small muted">{tr({ en: 'No row.', fr: 'Aucune ligne.' })}</p>;
  return <div className="table-scroll" tabIndex={0} role="region" aria-label={label}>
    <table className="data-table">
      <thead><tr>
        <th scope="col">{tr({ en: 'Concept', fr: 'Concept' })}</th>
        <th scope="col">{tr({ en: 'Period', fr: 'Période' })}</th>
        <th scope="col">{tr({ en: 'Value', fr: 'Valeur' })}</th>
        {withheld && <th scope="col">{tr({ en: 'Value at cutoff', fr: 'Valeur à la date limite' })}</th>}
        <th scope="col">{tr({ en: 'Form / accession', fr: 'Formulaire / numéro' })}</th>
        <th scope="col">{tr({ en: 'Available at (UTC)', fr: 'Disponible à (UTC)' })}</th>
        {withheld && <th scope="col">{tr({ en: 'Reason', fr: 'Motif' })}</th>}
      </tr></thead>
      <tbody>{rows.map(row => <tr key={`${row.record_id}-${row.accession}`}>
        <th scope="row">{row.concept}</th>
        <td>{period(row)}</td>
        <td>{fmtValue(row.value, row.unit, lang)}</td>
        {withheld && <td>{typeof row.value_at_cutoff === 'number'
          ? <>{fmtValue(row.value_at_cutoff, row.unit, lang)}{row.value_changed ? <strong> ({tr({ en: 'changed', fr: 'modifiée' })})</strong> : null}</>
          : '—'}</td>}
        <td className="small">{row.form ?? '—'} <span className="mono">{row.accession}</span></td>
        <td className="small"><span className="mono">{row.available_at ?? '—'}</span><br /><span className="muted">{tr(BASIS[row.availability_basis] ?? BASIS.unknown)}</span></td>
        {withheld && <td className="small">{row.reason ? tr(REASONS[row.reason] ?? { en: row.reason, fr: row.reason }) : '—'}</td>}
      </tr>)}</tbody>
    </table>
  </div>;
}

function FilingTable({ rows, label, withheld }: { rows: FilingRow[]; label: string; withheld?: boolean }) {
  const { tr } = useApp();
  if (rows.length === 0) return <p className="small muted">{tr({ en: 'No filing of the listed forms.', fr: 'Aucun dépôt des formulaires listés.' })}</p>;
  return <div className="table-scroll" tabIndex={0} role="region" aria-label={label}>
    <table className="data-table">
      <thead><tr>
        <th scope="col">{tr({ en: 'Form', fr: 'Formulaire' })}</th>
        <th scope="col">{tr({ en: 'Report date', fr: 'Date du rapport' })}</th>
        <th scope="col">{tr({ en: 'Filing date', fr: 'Date de dépôt' })}</th>
        <th scope="col">{tr({ en: 'Available at (UTC)', fr: 'Disponible à (UTC)' })}</th>
        {withheld && <th scope="col">{tr({ en: 'Reason', fr: 'Motif' })}</th>}
      </tr></thead>
      <tbody>{rows.map(row => <tr key={row.accession}>
        <th scope="row"><a href={row.url} target="_blank" rel="noreferrer">{row.form}</a> <span className="mono small">{row.accession}</span></th>
        <td>{row.report_date ?? '—'}</td>
        <td>{row.filing_date}</td>
        <td className="small"><span className="mono">{row.available_at ?? '—'}</span><br /><span className="muted">{tr(BASIS[row.availability_basis] ?? BASIS.unknown)}</span></td>
        {withheld && <td className="small">{row.reason ? tr(REASONS[row.reason] ?? { en: row.reason, fr: row.reason }) : '—'}</td>}
      </tr>)}</tbody>
    </table>
  </div>;
}

/** CIK entry with an optional exact-ticker candidate lookup; a ticker never selects a CIK by itself. */
function CikField({ id, cik, setCik, disabled }: { id: string; cik: string; setCik: (value: string) => void; disabled: boolean }) {
  const { tr, sessionId } = useApp();
  const [ticker, setTicker] = useState('');
  const [found, setFound] = useState<Candidates | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function lookup() {
    if (!ticker.trim()) return;
    setBusy(true); setFound(null); setFailed(false);
    try { setFound(await getJson<Candidates>(`/timemachine/sec-ticker-candidates?ticker=${encodeURIComponent(ticker.trim())}`, sessionId)); }
    catch { setFailed(true); } finally { setBusy(false); }
  }
  return <>
    <div className="search-row">
      <label htmlFor={id}>SEC CIK</label>
      <input id={id} inputMode="numeric" pattern="[0-9]{1,10}" maxLength={10} value={cik} disabled={disabled}
        onChange={e => setCik(e.target.value.replace(/[^0-9]/g, ''))} required />
    </div>
    <details className="fold">
      <summary className="small">{tr({ en: 'Find CIK candidates from a ticker', fr: 'Trouver des CIK candidats à partir d’un symbole' })}</summary>
      <div className="search-row">
        <label htmlFor={`${id}-ticker`}>{tr({ en: 'Ticker (exact)', fr: 'Symbole (exact)' })}</label>
        <input id={`${id}-ticker`} maxLength={12} value={ticker} onChange={e => setTicker(e.target.value)} />
        <button type="button" className="btn" disabled={busy || !sessionId || !ticker.trim()} onClick={() => void lookup()}>
          {busy ? tr({ en: 'Looking up…', fr: 'Recherche…' }) : tr({ en: 'Look up', fr: 'Rechercher' })}
        </button>
      </div>
      {failed && <p role="alert" className="small">{tr({ en: 'Lookup failed. Enter an exact CIK instead.', fr: 'La recherche a échoué. Saisissez plutôt un CIK exact.' })}</p>}
      {found && found.status !== 'available' && <p role="status" className="small">{tr({ en: 'SEC lookup unavailable (contact configuration missing or source unavailable).', fr: 'Recherche SEC indisponible (coordonnées non configurées ou source indisponible).' })}</p>}
      {found?.status === 'available' && (found.candidates?.length
        ? <ul className="small">{found.candidates.map(c => <li key={c.cik}>
            <button type="button" className="linklike" onClick={() => setCik(c.cik)}>{c.cik}</button> — {c.ticker} {c.title ?? ''}
          </li>)}</ul>
        : <p className="small muted">{tr({ en: 'No exact current SEC ticker match.', fr: 'Aucune correspondance exacte de symbole SEC actuel.' })}</p>)}
      <p className="small muted">{tr({ en: 'Candidates come from the current SEC ticker list. Tickers are reassigned over time and never establish identity at a past date: confirm the CIK yourself.', fr: 'Les candidats proviennent de la liste actuelle des symboles de la SEC. Les symboles sont réattribués et n’établissent jamais l’identité à une date passée : confirmez le CIK vous-même.' })}</p>
    </details>
  </>;
}

function VintageStatus() {
  const { tr, sessionId } = useApp();
  const [status, setStatus] = useState<Vintages | null>(null);
  useEffect(() => {
    if (!sessionId) return;
    let live = true;
    getJson<Vintages>('/timemachine/vintages/status', sessionId).then(data => { if (live) setStatus(data); }).catch(() => { if (live) setStatus(null); });
    return () => { live = false; };
  }, [sessionId]);
  return <p className="small muted">
    <strong>{tr({ en: 'Macro vintages (ALFRED)', fr: 'Millésimes macro (ALFRED)' })}:</strong>{' '}
    {status?.status === 'rights_confirmed_ingestion_not_wired'
      ? tr({ en: 'operator rights confirmed, but no vintage ingestion exists in this build.', fr: 'droits confirmés par l’opérateur, mais aucune ingestion de millésimes n’existe dans cette version.' })
      : tr({ en: 'unavailable.', fr: 'indisponible.' })}{' '}
    {tr({ en: 'FRED/ALFRED terms restrict use with AI systems, caching and redistribution, so no vintage is fetched or used; revised macro series stay withheld in replays.', fr: 'Les conditions FRED/ALFRED limitent l’usage avec des systèmes d’IA, la mise en cache et la redistribution : aucun millésime n’est récupéré ni utilisé; les séries macro révisées restent retenues dans les rejeux.' })}{' '}
    <a href={status?.terms_url ?? 'https://fred.stlouisfed.org/legal/'} target="_blank" rel="noreferrer">{tr({ en: 'Terms', fr: 'Conditions' })}</a>
  </p>;
}

function Unconfigured({ data }: { data: Base }) {
  const { tr } = useApp();
  return <p role="status">{data.reason === 'sec_contact_unconfigured'
    ? tr({ en: 'Unavailable: the SEC operator contact (APLOMB_SEC_CONTACT) is not configured, so nothing was fetched.', fr: 'Indisponible : le contact opérateur SEC (APLOMB_SEC_CONTACT) n’est pas configuré, rien n’a été récupéré.' })
    : tr({ en: 'Unavailable: the SEC sources could not be read; no value is inferred.', fr: 'Indisponible : les sources SEC n’ont pas pu être lues; aucune valeur n’est déduite.' })}</p>;
}

/** Available vs withheld disclosures at a cutoff (calibration; not an input of any run). */
function PointInTimePanelAvailable({ cutoff }: { cutoff: string }) {
  const { tr, lang, sessionId } = useApp();
  const [cik, setCik] = useState('');
  const [data, setData] = useState<PointInTime | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setData(null); setError(null); }, [cutoff]);
  async function load(event: React.FormEvent) {
    event.preventDefault();
    if (!cutoff || !cik) return;
    setBusy(true); setData(null); setError(null);
    try { setData(await getJson<PointInTime>(`/timemachine/point-in-time/${encodeURIComponent(cik)}?cutoff=${encodeURIComponent(cutoff)}`, sessionId)); }
    catch (e) { setError(e instanceof Error ? e.message : 'error'); } finally { setBusy(false); }
  }
  const f = data?.fundamentals;
  const l = data?.filings;
  return <Card id="tm-point-in-time" section={tr({ en: 'Calibration', fr: 'Calibrage' })}
    title={tr({ en: 'What was public at the cutoff (SEC filings)', fr: 'Ce qui était public à la date limite (dépôts SEC)' })}>
    <p className="small">{tr({ en: 'For one US registrant, rebuild which company-reported figures and filings had been accepted by EDGAR before the end of the cutoff day (UTC), and list what is withheld and why. This is separate from the replay: nothing here is added to a run.', fr: 'Pour un émetteur américain, reconstitue les chiffres déclarés et les dépôts acceptés par EDGAR avant la fin de la date limite (UTC), et liste ce qui est retenu et pourquoi. C’est distinct du rejeu : rien ici n’est ajouté à une exécution.' })}</p>
    <ModelKnowledgeCaveat />
    <VintageStatus />
    <form onSubmit={load}>
      <CikField id="tm-pit-cik" cik={cik} setCik={value => { setCik(value); setData(null); }} disabled={busy} />
      <div className="row-actions">
        <button className="btn" disabled={busy || !sessionId || !cutoff || !cik}>
          {busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Rebuild at cutoff', fr: 'Reconstituer à la date limite' })}
        </button>
        <span className="small">{cutoff
          ? <>{tr({ en: 'Cutoff', fr: 'Date limite' })} <strong>{fmtDate(cutoff, lang)}</strong></>
          : tr({ en: 'Choose a valid cutoff date first.', fr: 'Choisissez d’abord une date limite valide.' })}</span>
      </div>
    </form>
    {busy && <Loading label={tr({ en: 'Reading SEC EDGAR captures…', fr: 'Lecture des captures SEC EDGAR…' })} />}
    {error && <p role="alert">{tr({ en: 'Request refused or failed', fr: 'Requête refusée ou échouée' })}: {error}</p>}
    {data && data.status === 'unavailable' && !f && <Unconfigured data={data} />}
    {data && f && l && <div aria-live="polite">
      <p><strong>{data.name ?? data.cik}</strong> — CIK <span className="mono">{data.cik}</span> — {data.status}</p>
      <p className="small">{tr({ en: 'Gate: available strictly before', fr: 'Barrière : disponible strictement avant' })} <span className="mono">{data.boundary}</span>. {tr({ en: 'Captured', fr: 'Capturé' })} <span className="mono">{data.retrieved_at}</span> ({tr({ en: 'after the cutoff', fr: 'après la date limite' })}).</p>

      <h4 className="h4">{tr({ en: 'Company-reported figures available at the cutoff', fr: 'Chiffres déclarés disponibles à la date limite' })}</h4>
      <p className="small">{tr({ en: 'Total', fr: 'Total' })}: <strong>{f.available_total}</strong> ({tr({ en: `latest ${f.shown_periods_per_concept} periods per concept shown`, fr: `${f.shown_periods_per_concept} dernières périodes par concept affichées` })}). {tr({ en: 'Availability basis', fr: 'Base de disponibilité' })}: <Counts counts={f.available_by_basis} labels={BASIS} />. {tr({ en: 'Superseded by a revision still before the cutoff', fr: 'Remplacées par une révision encore antérieure à la date limite' })}: {f.superseded_before_cutoff}.</p>
      <FactTable rows={f.available} label={tr({ en: 'Figures available at the cutoff', fr: 'Chiffres disponibles à la date limite' })} />

      <h4 className="h4">{tr({ en: 'Withheld figures', fr: 'Chiffres retenus' })}</h4>
      <p className="small">{tr({ en: 'Total', fr: 'Total' })}: <strong>{f.withheld_total}</strong> — <Counts counts={f.withheld_by_reason} labels={REASONS} />. {tr({ en: 'Later revisions with a different value', fr: 'Révisions ultérieures avec une valeur différente' })}: <strong>{f.withheld_revised_values}</strong>.</p>
      {Object.keys(f.excluded_source_rows).length > 0 && <p className="small">{tr({ en: 'Excluded source rows', fr: 'Lignes sources exclues' })}: <Counts counts={f.excluded_source_rows} labels={REASONS} /></p>}
      <FactTable withheld rows={f.withheld} label={tr({ en: 'Withheld figures (sample)', fr: 'Chiffres retenus (échantillon)' })} />

      <h4 className="h4">{tr({ en: 'Filings timeline', fr: 'Chronologie des dépôts' })}</h4>
      <p className="small">
        {tr({ en: 'Accepted on or before the cutoff', fr: 'Acceptés au plus tard à la date limite' })}: <strong>{l.available_total}</strong> · {tr({ en: 'withheld after the cutoff', fr: 'retenus après la date limite' })}: <strong>{l.withheld_total}</strong> (<Counts counts={l.withheld_by_reason} labels={REASONS} />).
        {data.filings_cover_from && <> {tr({ en: 'Fetched submission pages cover filings from', fr: 'Les pages de dépôts récupérées couvrent les dépôts depuis le' })} {data.filings_cover_from}; {tr({ en: 'earlier filings are not counted.', fr: 'les dépôts antérieurs ne sont pas comptés.' })}</>}
      </p>
      <details className="fold">
        <summary className="small">{tr({ en: 'Counts by form', fr: 'Nombres par formulaire' })}</summary>
        <p className="small">{tr({ en: 'Available', fr: 'Disponibles' })}: <Counts counts={l.available_by_form} /></p>
        <p className="small">{tr({ en: 'Withheld', fr: 'Retenus' })}: <Counts counts={l.withheld_by_form} /></p>
      </details>
      <FilingTable rows={l.available} label={tr({ en: 'Filings available at the cutoff', fr: 'Dépôts disponibles à la date limite' })} />
      <p className="small">{tr({ en: 'First filings withheld after the cutoff', fr: 'Premiers dépôts retenus après la date limite' })}</p>
      <FilingTable withheld rows={l.withheld} label={tr({ en: 'Filings withheld after the cutoff', fr: 'Dépôts retenus après la date limite' })} />
      <Sources data={data} />
    </div>}
  </Card>;
}

/** Reveal-only: what SEC published between the cutoff and the reveal date. Never changes the run. */
function PublishedLaterPanelAvailable({ cutoff, until }: { cutoff: string; until: string }) {
  const { tr, lang, sessionId } = useApp();
  const [cik, setCik] = useState('');
  const [data, setData] = useState<Later | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setData(null); setError(null); }, [cutoff, until]);
  async function load(event: React.FormEvent) {
    event.preventDefault();
    if (!cik) return;
    setBusy(true); setData(null); setError(null);
    try { setData(await getJson<Later>(`/timemachine/point-in-time/${encodeURIComponent(cik)}/published-later?cutoff=${encodeURIComponent(cutoff)}&until=${encodeURIComponent(until)}`, sessionId)); }
    catch (e) { setError(e instanceof Error ? e.message : 'error'); } finally { setBusy(false); }
  }
  return <section className="reveal" aria-labelledby="tm-later-title">
    <h4 className="h4" id="tm-later-title">{tr({ en: 'What was published later (SEC, separate comparison)', fr: 'Ce qui a été publié ensuite (SEC, comparaison distincte)' })}</h4>
    <p className="small">{tr({ en: `Company-reported figures and filings accepted by EDGAR after ${cutoff} and up to ${until}. Shown for comparison only: the replay could not see them and the signed run is not modified.`, fr: `Chiffres déclarés et dépôts acceptés par EDGAR après le ${cutoff} et jusqu’au ${until}. Affichés pour comparaison seulement : le rejeu ne pouvait pas les voir et l’exécution signée n’est pas modifiée.` })}</p>
    <form onSubmit={load}>
      <CikField id="tm-later-cik" cik={cik} setCik={value => { setCik(value); setData(null); }} disabled={busy} />
      <div className="row-actions">
        <button className="btn" disabled={busy || !sessionId || !cik}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Compare', fr: 'Comparer' })}</button>
        <span className="small">{fmtDate(cutoff, lang)} → {fmtDate(until, lang)}</span>
      </div>
    </form>
    {busy && <Loading label={tr({ en: 'Reading SEC EDGAR captures…', fr: 'Lecture des captures SEC EDGAR…' })} />}
    {error && <p role="alert">{tr({ en: 'Request refused or failed', fr: 'Requête refusée ou échouée' })}: {error}</p>}
    {data && data.status === 'unavailable' && data.new_values === undefined && <Unconfigured data={data} />}
    {data && data.new_values !== undefined && <div aria-live="polite">
      <p><strong>{data.name ?? data.cik}</strong> — {data.status}</p>
      <p className="small">
        {tr({ en: 'New figures', fr: 'Nouveaux chiffres' })}: <strong>{data.new_values_total ?? 0}</strong> · {tr({ en: 'figures whose value was revised', fr: 'chiffres dont la valeur a été révisée' })}: <strong>{data.revised_values_total ?? 0}</strong> · {tr({ en: 'filings', fr: 'dépôts' })}: <strong>{data.filings_total ?? 0}</strong> (<Counts counts={data.filings_by_form ?? {}} />)
      </p>
      <h5>{tr({ en: 'Values revised after the cutoff', fr: 'Valeurs révisées après la date limite' })}</h5>
      <FactTable withheld rows={(data.revised_values ?? []).map(row => ({ ...row, value_changed: true }))} label={tr({ en: 'Revised values', fr: 'Valeurs révisées' })} />
      <h5>{tr({ en: 'New figures (latest periods per concept)', fr: 'Nouveaux chiffres (dernières périodes par concept)' })}</h5>
      <FactTable rows={data.new_values ?? []} label={tr({ en: 'New figures', fr: 'Nouveaux chiffres' })} />
      <h5>{tr({ en: 'Filings in the window', fr: 'Dépôts dans la fenêtre' })}</h5>
      <FilingTable rows={data.filings ?? []} label={tr({ en: 'Filings published later', fr: 'Dépôts publiés ensuite' })} />
      <ModelKnowledgeCaveat />
      <Sources data={data} />
    </div>}
  </section>;
}


export function PointInTimePanel(props: { cutoff: string }) {
  const source = useSourceCapabilities();
  return readySource(source.data, 'sec') ? <PointInTimePanelAvailable {...props} /> : null;
}

export function PublishedLaterPanel(props: { cutoff: string; until: string }) {
  const source = useSourceCapabilities();
  return readySource(source.data, 'sec') ? <PublishedLaterPanelAvailable {...props} /> : null;
}
