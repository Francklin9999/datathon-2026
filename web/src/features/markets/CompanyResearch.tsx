'use client';
/**
 * Exact-CIK SEC company research: overview, official reported financials, filings, Form 4 insider
 * transactions and 13F institutional holdings. Each section carries its own source links, filing and
 * acceptance dates, capture time and hashes, and its own unavailable state: one refused or missing
 * source never hides the others, and no value is inferred for a missing section.
 */
import { useState, type ReactNode } from 'react';
import { API_BASE } from '../../api/index';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Card } from '../../components/common/Page';
import { Loading, Unavailable } from '../../components/common/States';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { useApp } from '../../state/app';

type Source = { url: string; sha256: string; retrieved_at: string; published_at?: string | null; section?: string; licence?: string };
type Filing = {
  accession: string; form: string; filed: string; period_end: string | null; url: string;
  accepted_at?: string | null; description?: string | null; index_url?: string; raw_document_url?: string;
};
type Statement = {
  taxonomy?: string; concept: string; label?: string; value: number; unit: string; period_start?: string | null;
  period_end: string; filed: string; form?: string; accession: string; fiscal_year?: number | null;
  fiscal_period?: string | null; source_row_index: number; fact_id?: string; data_class?: string; filing_url?: string;
};
type Owner = { cik: string; name: string; director_reported: string | null; officer_reported: string | null; ten_percent_owner_reported: string | null };
type Transaction = {
  kind: string; security_title: string; transaction_date: string; code: string; code_meaning?: string;
  acquired_or_disposed: string; reported_quantity: string | null; reported_price_per_unit: string | null;
  remaining_reported_quantity: string | null; ownership_nature: string | null; footnote_ids?: string[];
};
type InsiderFiling = {
  accession: string; form: string; filed: string; accepted_at: string | null; report_period: string;
  issuer_name: string; owners: Owner[]; transactions: Transaction[]; footnotes?: Record<string, string>;
  filing_url: string; index_url: string; source_url: string; source: Source; limitations: string[];
};
type SectionError = { section: string; code: string; http_status?: number | null; accession?: string };
type Insiders = {
  status: string; filings: InsiderFiling[]; errors: SectionError[]; coverage: string;
  summary?: { filings: number; transactions: number; by_kind_code_direction: Record<string, number>; method: string };
};
type Holding = {
  issuer_label: string; class_label: string; cusip_as_reported?: string; reported_value_usd: string;
  pct_of_reported_total?: string | null; quantity: string; quantity_type: string; put_call: string | null; discretion: string | null;
};
type HoldingsFiling = {
  accession: string; form: string; filed: string; accepted_at: string | null; report_period: string; report_period_source?: string;
  holdings: Holding[]; row_count: number; rows_shown: number; reported_total_usd: string; value_unit_rule?: string;
  method: string; filing_url: string; index_url: string; source_url: string; source: Source; limitations: string[];
};
type Holdings = { status: string; filing: HoldingsFiling | null; errors: SectionError[]; coverage: string };
type SectionState = { status: string; code?: string | null };
type Detail = {
  status: string; cik: string; as_of: string; retrieved_at: string;
  company: {
    name: string | null; sic?: string | null; sic_description: string | null; entity_type?: string | null; incorporation?: string | null;
    fiscal_year_end?: string | null; filer_category?: string | null; reported_tickers?: string[]; reported_exchanges?: string[];
    ticker_identity_note?: string; filings: Filing[]; is_13f_filer?: boolean; skipped_unrecognized_documents?: number; coverage?: string;
  } | null;
  statements: Statement[];
  facts: Record<string, { verification?: { status?: string } }>;
  sources: Source[];
  sections?: Record<string, SectionState>;
  insider_transactions?: Insiders | null;
  institutional_holdings?: Holdings | null;
  errors: SectionError[]; limitations: string[];
};
type Tab = 'overview' | 'financials' | 'filings' | 'insiders' | 'holdings';
type RequestFailure = { contact: boolean; status: number | null };

const SECTION_KEY: Record<Tab, string> = {
  overview: 'company', financials: 'statements', filings: 'filings', insiders: 'insider_transactions', holdings: 'institutional_holdings',
};

function useCodeText() {
  const { tr } = useApp();
  return (code: string | null | undefined): string => {
    switch (code) {
      case 'sec_access_denied': return tr({ en: 'SEC refused access (HTTP 403). Access controls are respected: no retry, bypass or substitute source.', fr: 'La SEC a refusé l’accès (HTTP 403). Les contrôles d’accès sont respectés : aucune nouvelle tentative, contournement ni source de remplacement.' });
      case 'rate_limited': return tr({ en: 'SEC rate limit reached; try again later.', fr: 'Limite de débit SEC atteinte; réessayez plus tard.' });
      case 'request_timeout': return tr({ en: 'SEC did not respond in time.', fr: 'La SEC n’a pas répondu à temps.' });
      case 'response_too_large': return tr({ en: 'The SEC document exceeds the bounded capture size; not truncated or partially parsed.', fr: 'Le document SEC dépasse la taille de capture autorisée; il n’est ni tronqué ni analysé partiellement.' });
      case 'submissions_required': return tr({ en: 'Needs the SEC submissions index, which is unavailable.', fr: 'Nécessite l’index des dépôts SEC, qui est indisponible.' });
      case 'disclosure_issuer_cik_mismatch': return tr({ en: 'This Form 4 names a different issuer CIK (this CIK may be the reporting person); not attributed.', fr: 'Ce formulaire 4 désigne un autre CIK émetteur (ce CIK est peut-être la personne déclarante); non attribué.' });
      case 'information_table_not_found': return tr({ en: 'No 13F information table could be identified in the filing index.', fr: 'Aucune table d’information 13F n’a été identifiée dans l’index du dépôt.' });
      case 'unsafe_or_oversized_disclosure_xml': return tr({ en: 'XML rejected: DTD/entity declarations or size limit.', fr: 'XML rejeté : déclarations DTD/entités ou taille limite.' });
      default: return tr({ en: 'Source unavailable or invalid; no values inferred.', fr: 'Source indisponible ou invalide; aucune valeur déduite.' }) + (code ? ` (${code})` : '');
    }
  };
}

function fmtNumber(value: string | number | null | undefined, lang: string, digits = 4): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n.toLocaleString(lang, { maximumFractionDigits: digits }) : String(value);
}

function SourceLine({ source }: { source: Source }) {
  const { tr } = useApp();
  return <p className="small break">
    <ExternalLink href={source.url}>{tr({ en: 'SEC EDGAR source', fr: 'Source SEC EDGAR' })}</ExternalLink>
    {' · '}{tr({ en: 'captured', fr: 'capturé' })} {source.retrieved_at}
    {source.published_at && <> · {tr({ en: 'EDGAR accepted', fr: 'accepté par EDGAR' })} {source.published_at}</>}
    <br /><span className="mono">SHA-256 {source.sha256}</span>
  </p>;
}

function SectionStatus({ state, children }: { state: SectionState | undefined; children?: ReactNode }) {
  const { tr } = useApp();
  const codeText = useCodeText();
  if (!state) return null;
  if (state.status === 'unavailable') {
    return <Unavailable title={tr({ en: 'Section unavailable', fr: 'Section indisponible' })}>{codeText(state.code)}{children}</Unavailable>;
  }
  if (state.status === 'partial') {
    return <p role="status" className="small">{tr({ en: 'Partially available: some filings could not be captured.', fr: 'Partiellement disponible : certains dépôts n’ont pu être capturés.' })} {codeText(state.code)}</p>;
  }
  return null;
}

function ErrorList({ errors }: { errors: SectionError[] }) {
  const codeText = useCodeText();
  if (!errors.length) return null;
  return <ul className="small muted">{errors.map((e, i) => <li key={`${e.accession ?? e.section}-${i}`}>{e.accession && <span className="mono">{e.accession}: </span>}{codeText(e.code)}</li>)}</ul>;
}

function Overview({ result }: { result: Detail }) {
  const { tr } = useApp();
  const c = result.company;
  if (!c) return null;
  const rows: [string, ReactNode][] = [
    [tr({ en: 'Registrant name (SEC)', fr: 'Nom du déclarant (SEC)' }), c.name ?? '—'],
    ['CIK', <span key="cik" className="mono">{result.cik}</span>],
    [tr({ en: 'Industry (SIC)', fr: 'Secteur (SIC)' }), [c.sic, c.sic_description].filter(Boolean).join(' · ') || '—'],
    [tr({ en: 'Entity type', fr: 'Type d’entité' }), c.entity_type ?? '—'],
    [tr({ en: 'Incorporation', fr: 'Constitution' }), c.incorporation ?? '—'],
    [tr({ en: 'Fiscal year end (MMDD)', fr: 'Fin d’exercice (MMJJ)' }), c.fiscal_year_end ?? '—'],
    [tr({ en: 'Filer category', fr: 'Catégorie de déposant' }), c.filer_category ?? '—'],
    [tr({ en: 'SEC-reported tickers', fr: 'Symboles déclarés à la SEC' }), (c.reported_tickers ?? []).map((t, i) => `${t}${c.reported_exchanges?.[i] ? ` (${c.reported_exchanges[i]})` : ''}`).join(', ') || '—'],
    [tr({ en: '13F filer in recent submissions', fr: 'Déposant 13F dans les dépôts récents' }), c.is_13f_filer ? tr({ en: 'Yes', fr: 'Oui' }) : tr({ en: 'No', fr: 'Non' })],
  ];
  return <div>
    <dl>{rows.map(([k, v]) => <div key={k} className="kv"><dt className="k">{k}</dt><dd className="v">{v}</dd></div>)}</dl>
    <p className="small muted">{tr({ en: 'Tickers are labels reported to the SEC; the CIK is the identity key. A CIK identifies a disclosure registrant, not an exchange listing.', fr: 'Les symboles sont des libellés déclarés à la SEC; le CIK est la clé d’identité. Un CIK identifie un déclarant, pas une cotation.' })}</p>
  </div>;
}

function Financials({ result }: { result: Detail }) {
  const { tr, lang } = useApp();
  if (!result.statements.length) return null;
  return <div>
    <p className="small"><strong>{tr({ en: 'Official reported values', fr: 'Valeurs officielles déclarées' })}</strong>{' — '}{tr({ en: 'company-reported XBRL facts from SEC companyfacts. These are not estimates or consensus forecasts; none are shown. Current captures can include restatements.', fr: 'faits XBRL déclarés par la société (SEC companyfacts). Ce ne sont pas des estimations ni des prévisions consensuelles; aucune n’est affichée. Les captures actuelles peuvent inclure des retraitements.' })}</p>
    <div className="table-scroll" tabIndex={0} role="region" aria-label={tr({ en: 'Reported financial statement lines', fr: 'Postes financiers déclarés' })}>
      <table className="data-table"><thead><tr>
        <th scope="col">{tr({ en: 'Line', fr: 'Poste' })}</th><th scope="col">{tr({ en: 'Reported value', fr: 'Valeur déclarée' })}</th>
        <th scope="col">{tr({ en: 'Fiscal period', fr: 'Période fiscale' })}</th><th scope="col">{tr({ en: 'Period', fr: 'Période' })}</th>
        <th scope="col">{tr({ en: 'Form', fr: 'Formulaire' })}</th><th scope="col">{tr({ en: 'Filed', fr: 'Déposé' })}</th>
        <th scope="col">{tr({ en: 'Ledger check', fr: 'Contrôle du registre' })}</th>
      </tr></thead><tbody>{result.statements.map(row => {
        const verification = row.fact_id ? result.facts[row.fact_id]?.verification?.status : undefined;
        return <tr key={`${row.taxonomy ?? 'us-gaap'}-${row.concept}-${row.unit}-${row.source_row_index}`}>
          <th scope="row">{row.label ?? row.concept}<br /><span className="small muted mono">{row.taxonomy ?? 'us-gaap'}:{row.concept}</span></th>
          <td>{fmtNumber(row.value, lang)} {row.unit}</td>
          <td>{[row.fiscal_year, row.fiscal_period].filter(Boolean).join(' ') || '—'}</td>
          <td>{row.period_start ? `${row.period_start} → ` : ''}{row.period_end}</td>
          <td>{row.filing_url ? <ExternalLink href={row.filing_url}>{row.form ?? '—'}</ExternalLink> : row.form ?? '—'}<br /><span className="small mono">{row.accession}</span></td>
          <td>{row.filed}</td>
          <td>{row.fact_id ? `${row.fact_id} · ${verification ?? tr({ en: 'unknown', fr: 'inconnu' })}` : tr({ en: 'Not ledger-registered (unit outside USD/CAD check)', fr: 'Non enregistré (unité hors contrôle USD/CAD)' })}</td>
        </tr>;
      })}</tbody></table>
    </div>
  </div>;
}

function Filings({ result }: { result: Detail }) {
  const { tr } = useApp();
  const c = result.company;
  if (!c) return null;
  if (!c.filings.length) return <p className="muted">{tr({ en: 'No filings of the listed forms in recent submissions on or before the as-of date.', fr: 'Aucun dépôt des formulaires suivis dans les dépôts récents à la date de référence.' })}</p>;
  return <div>
    <div className="table-scroll" tabIndex={0} role="region" aria-label={tr({ en: 'Latest SEC filings', fr: 'Derniers dépôts SEC' })}>
      <table className="data-table"><thead><tr>
        <th scope="col">{tr({ en: 'Form', fr: 'Formulaire' })}</th><th scope="col">{tr({ en: 'Filing date', fr: 'Date de dépôt' })}</th>
        <th scope="col">{tr({ en: 'EDGAR acceptance (publication)', fr: 'Acceptation EDGAR (publication)' })}</th>
        <th scope="col">{tr({ en: 'Report period', fr: 'Période du rapport' })}</th><th scope="col">{tr({ en: 'Documents', fr: 'Documents' })}</th>
      </tr></thead><tbody>{c.filings.map(f => <tr key={f.accession}>
        <th scope="row">{f.form}{f.description && <><br /><span className="small muted">{f.description}</span></>}</th>
        <td>{f.filed}</td><td>{f.accepted_at ?? tr({ en: 'not reported', fr: 'non déclarée' })}</td><td>{f.period_end ?? '—'}</td>
        <td><ExternalLink href={f.url}>{tr({ en: 'Primary document', fr: 'Document principal' })}</ExternalLink>{f.index_url && <> · <ExternalLink href={f.index_url}>{tr({ en: 'Filing index', fr: 'Index du dépôt' })}</ExternalLink></>}<br /><span className="small mono">{f.accession}</span></td>
      </tr>)}</tbody></table>
    </div>
    <p className="small muted">{c.coverage}{c.skipped_unrecognized_documents ? ` ${tr({ en: 'Rows skipped for unrecognized document names:', fr: 'Lignes ignorées (nom de document non reconnu) :' })} ${c.skipped_unrecognized_documents}.` : ''}</p>
  </div>;
}

function relationship(owner: Owner, tr: (t: { en: string; fr: string }) => string): string {
  const yes = (v: string | null) => v === '1' || v?.toLowerCase() === 'true';
  return [yes(owner.director_reported) && tr({ en: 'director', fr: 'administrateur' }), yes(owner.officer_reported) && tr({ en: 'officer', fr: 'dirigeant' }),
    yes(owner.ten_percent_owner_reported) && tr({ en: '10% owner', fr: 'détenteur de 10 %' })].filter(Boolean).join(', ') || tr({ en: 'relationship not flagged', fr: 'relation non indiquée' });
}

function InsiderSection({ data }: { data: Insiders }) {
  const { tr, lang } = useApp();
  if (data.status === 'not_applicable') return <p className="muted">{tr({ en: 'No Form 4 filings in recent submissions for this CIK on or before the as-of date.', fr: 'Aucun formulaire 4 dans les dépôts récents de ce CIK à la date de référence.' })}</p>;
  return <div>
    {data.summary && <p className="small">{tr({ en: 'Filings parsed', fr: 'Dépôts analysés' })}: {data.summary.filings} · {tr({ en: 'reported transaction rows', fr: 'lignes de transaction déclarées' })}: {data.summary.transactions}. <span className="muted">{data.summary.method}</span></p>}
    {data.filings.map(f => <section key={f.accession} className="stack" aria-label={`${f.form} ${f.accession}`}>
      <h4>{f.form} · {f.issuer_name} · <span className="mono small">{f.accession}</span></h4>
      <p className="small">{tr({ en: 'Filed', fr: 'Déposé' })} {f.filed} · {tr({ en: 'EDGAR accepted', fr: 'accepté par EDGAR' })} {f.accepted_at ?? tr({ en: 'not reported', fr: 'non déclarée' })} · {tr({ en: 'period of report', fr: 'période du rapport' })} {f.report_period}
        {' · '}<ExternalLink href={f.filing_url}>{tr({ en: 'Rendered filing', fr: 'Dépôt affiché' })}</ExternalLink>{' · '}<ExternalLink href={f.index_url}>{tr({ en: 'Filing index', fr: 'Index du dépôt' })}</ExternalLink></p>
      <ul className="small">{f.owners.map(o => <li key={o.cik}>{o.name} — CIK <span className="mono">{o.cik}</span> ({relationship(o, tr)})</li>)}</ul>
      {f.transactions.length ? <div className="table-scroll" tabIndex={0} role="region" aria-label={tr({ en: 'Reported insider transactions', fr: 'Transactions d’initiés déclarées' })}>
        <table className="data-table"><thead><tr>
          <th scope="col">{tr({ en: 'Date', fr: 'Date' })}</th><th scope="col">{tr({ en: 'Security', fr: 'Titre' })}</th>
          <th scope="col">{tr({ en: 'Code', fr: 'Code' })}</th><th scope="col">{tr({ en: 'Acquired/Disposed', fr: 'Acquis/Cédé' })}</th>
          <th scope="col">{tr({ en: 'Reported quantity', fr: 'Quantité déclarée' })}</th><th scope="col">{tr({ en: 'Reported price per unit', fr: 'Prix unitaire déclaré' })}</th>
          <th scope="col">{tr({ en: 'Held after', fr: 'Détenu ensuite' })}</th><th scope="col">{tr({ en: 'Direct/Indirect', fr: 'Direct/Indirect' })}</th>
        </tr></thead><tbody>{f.transactions.map((t, i) => <tr key={i}>
          <td>{t.transaction_date}</td>
          <th scope="row">{t.security_title}<br /><span className="small muted">{t.kind === 'derivative' ? tr({ en: 'derivative', fr: 'dérivé' }) : tr({ en: 'non-derivative', fr: 'non dérivé' })}</span></th>
          <td><span className="mono">{t.code}</span>{t.code_meaning && <><br /><span className="small muted">{t.code_meaning}</span></>}</td>
          <td>{t.acquired_or_disposed === 'A' ? tr({ en: 'Acquired (A)', fr: 'Acquis (A)' }) : tr({ en: 'Disposed (D)', fr: 'Cédé (D)' })}</td>
          <td>{t.reported_quantity === null ? tr({ en: 'not in field (see footnotes)', fr: 'absent (voir notes)' }) : fmtNumber(t.reported_quantity, lang)}</td>
          <td>{t.reported_price_per_unit === null ? '—' : fmtNumber(t.reported_price_per_unit, lang)}</td>
          <td>{fmtNumber(t.remaining_reported_quantity, lang)}</td>
          <td>{t.ownership_nature ?? '—'}{t.footnote_ids?.length ? <><br /><span className="small muted">{t.footnote_ids.join(', ')}</span></> : null}</td>
        </tr>)}</tbody></table>
      </div> : <p className="small muted">{tr({ en: 'No transaction rows in this filing (holdings only).', fr: 'Aucune ligne de transaction dans ce dépôt (positions seulement).' })}</p>}
      {f.footnotes && Object.keys(f.footnotes).length > 0 && <details className="small"><summary>{tr({ en: 'Filer footnotes (source text, shown as data)', fr: 'Notes du déclarant (texte source, affiché comme donnée)' })}</summary>
        <dl>{Object.entries(f.footnotes).map(([id, text]) => <div key={id}><dt className="mono">{id}</dt><dd>{text}</dd></div>)}</dl></details>}
      <SourceLine source={f.source} />
    </section>)}
    <ErrorList errors={data.errors} />
    <p className="small muted">{data.coverage} {tr({ en: 'Prices have no declared currency in these XML fields; no USD is assumed.', fr: 'Les prix n’ont pas de devise déclarée dans ces champs XML; aucun USD n’est supposé.' })}</p>
    {data.filings[0] && <ul className="small muted">{data.filings[0].limitations.map(n => <li key={n}>{n}</li>)}</ul>}
  </div>;
}

function HoldingsSection({ data }: { data: Holdings }) {
  const { tr, lang } = useApp();
  if (data.status === 'not_applicable') return <p className="muted">{data.coverage}</p>;
  const f = data.filing;
  return <div>
    <ErrorList errors={data.errors} />
    {f && <>
      <p className="small">{f.form} · <span className="mono">{f.accession}</span> · {tr({ en: 'report period', fr: 'période du rapport' })} {f.report_period}
        {' · '}{tr({ en: 'filed', fr: 'déposé' })} {f.filed} · {tr({ en: 'EDGAR accepted', fr: 'accepté par EDGAR' })} {f.accepted_at ?? tr({ en: 'not reported', fr: 'non déclarée' })}
        {' · '}<ExternalLink href={f.index_url}>{tr({ en: 'Filing index', fr: 'Index du dépôt' })}</ExternalLink></p>
      <p className="small">{tr({ en: 'Reported rows', fr: 'Lignes déclarées' })}: {f.row_count} · {tr({ en: 'shown', fr: 'affichées' })}: {f.rows_shown} · {tr({ en: 'sum of reported values', fr: 'somme des valeurs déclarées' })}: {fmtNumber(f.reported_total_usd, lang, 0)} USD</p>
      {f.value_unit_rule && <p className="small muted">{f.value_unit_rule}</p>}
      <div className="table-scroll" tabIndex={0} role="region" aria-label={tr({ en: 'Reported 13F holdings', fr: 'Positions 13F déclarées' })}>
        <table className="data-table"><thead><tr>
          <th scope="col">{tr({ en: 'Issuer (as reported)', fr: 'Émetteur (tel que déclaré)' })}</th><th scope="col">{tr({ en: 'Class', fr: 'Catégorie' })}</th>
          <th scope="col">{tr({ en: 'CUSIP as reported', fr: 'CUSIP tel que déclaré' })}</th><th scope="col">{tr({ en: 'Reported value (USD)', fr: 'Valeur déclarée (USD)' })}</th>
          <th scope="col">{tr({ en: '% of reported total', fr: '% du total déclaré' })}</th><th scope="col">{tr({ en: 'Quantity', fr: 'Quantité' })}</th>
          <th scope="col">{tr({ en: 'Put/Call', fr: 'Put/Call' })}</th><th scope="col">{tr({ en: 'Discretion', fr: 'Discrétion' })}</th>
        </tr></thead><tbody>{f.holdings.map((h, i) => <tr key={`${h.cusip_as_reported ?? ''}-${i}`}>
          <th scope="row">{h.issuer_label}</th><td>{h.class_label}</td><td className="mono">{h.cusip_as_reported ?? '—'}</td>
          <td>{fmtNumber(h.reported_value_usd, lang, 0)}</td><td>{h.pct_of_reported_total ?? '—'}</td>
          <td>{fmtNumber(h.quantity, lang, 0)} {h.quantity_type}</td><td>{h.put_call ?? '—'}</td><td>{h.discretion ?? '—'}</td>
        </tr>)}</tbody></table>
      </div>
      <p className="small muted">{f.method} {tr({ en: 'CUSIPs are shown as reported and never used to join identities without a licence; issuer names are labels.', fr: 'Les CUSIP sont affichés tels que déclarés et jamais utilisés pour joindre des identités sans licence; les noms d’émetteurs sont des libellés.' })}</p>
      <SourceLine source={f.source} />
      <ul className="small muted">{f.limitations.map(n => <li key={n}>{n}</li>)}</ul>
    </>}
    <p className="small muted">{data.coverage}</p>
  </div>;
}

export function CompanyResearch() {
  const { sessionId, tr } = useApp();
  const codeText = useCodeText();
  const [cik, setCik] = useState('');
  const [result, setResult] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [tab, setTab] = useState<Tab>('overview');
  async function load(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setResult(null); setFailure(null);
    try {
      const response = await fetch(`${API_BASE}/research/company/${encodeURIComponent(cik.trim())}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        setFailure({ contact: response.status === 503 && /contact/i.test(text), status: response.status });
        return;
      }
      const data = await response.json() as Detail;
      if (!Array.isArray(data.statements) || !Array.isArray(data.sources)) throw new Error('invalid response');
      setResult(data);
    } catch { setFailure({ contact: false, status: null }); } finally { setBusy(false); }
  }
  const tabs: { value: Tab; label: string }[] = [
    { value: 'overview', label: tr({ en: 'Overview', fr: 'Aperçu' }) },
    { value: 'financials', label: tr({ en: 'Financials', fr: 'États financiers' }) },
    { value: 'filings', label: tr({ en: 'Filings', fr: 'Dépôts' }) },
    { value: 'insiders', label: tr({ en: 'Insider transactions', fr: 'Transactions d’initiés' }) },
    { value: 'holdings', label: tr({ en: 'Institutional holdings', fr: 'Positions institutionnelles' }) },
  ];
  const sectionState = (t: Tab): SectionState | undefined => {
    if (!result) return undefined;
    const declared = result.sections?.[SECTION_KEY[t]];
    if (declared) return declared;
    // Older responses without per-section states: derive only from explicit errors.
    const error = result.errors.find(e => e.section === SECTION_KEY[t] || (t === 'filings' && e.section === 'company'));
    return error ? { status: 'unavailable', code: error.code } : { status: 'available' };
  };
  const sourceFor = (t: Tab) => result?.sources.filter(s => s.section === (t === 'filings' ? 'company' : SECTION_KEY[t]) && (t === 'overview' || t === 'financials' || t === 'filings')) ?? [];
  return <Card title={tr({ en: 'Company reports and filings', fr: 'Rapports et déclarations des sociétés' })}>
    <p>{tr({ en: 'Use an exact SEC CIK for US disclosure research. Filing dates, EDGAR acceptance times and reporting periods stay distinct; current captures can contain restatements.', fr: 'Utilisez un CIK SEC exact pour les déclarations américaines. Dates de dépôt, heures d’acceptation EDGAR et périodes comptables restent distinctes; les captures actuelles peuvent contenir des révisions.' })}</p>
    <form onSubmit={load} className="search-row">
      <label htmlFor="company-cik">SEC CIK</label>
      <input id="company-cik" inputMode="numeric" pattern="[0-9]{1,10}" maxLength={10} value={cik} disabled={busy} onChange={e => { setCik(e.target.value); setResult(null); setFailure(null); }} required />
      <button className="btn" disabled={busy || !sessionId}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Load reports', fr: 'Charger les rapports' })}</button>
    </form>
    {busy && <Loading label={tr({ en: 'Capturing SEC sources (several documents; bounded)…', fr: 'Capture des sources SEC (plusieurs documents, bornée)…' })} />}
    {failure && <div role="alert">
      <Unavailable title={failure.contact
        ? tr({ en: 'SEC access not configured', fr: 'Accès SEC non configuré' })
        : failure.status === 422 || failure.status === 400
          ? tr({ en: 'Invalid SEC CIK', fr: 'CIK SEC invalide' })
          : tr({ en: 'SEC research unavailable', fr: 'Recherche SEC indisponible' })}>
        {failure.contact
          ? tr({ en: 'SEC requires a descriptive operator contact (APLOMB_SEC_CONTACT). None is configured, and none is invented.', fr: 'La SEC exige un contact opérateur descriptif (APLOMB_SEC_CONTACT). Aucun n’est configuré et aucun n’est inventé.' })
          : tr({ en: 'Source unavailable, identifier invalid or request limit reached.', fr: 'Source indisponible, identifiant invalide ou limite de requêtes atteinte.' })}
      </Unavailable>
      <ul className="small muted">{tabs.map(t => <li key={t.value}>{t.label}: {tr({ en: 'unavailable', fr: 'indisponible' })}</li>)}</ul>
    </div>}
    {result && <div aria-live="polite">
      <p><strong>{result.company?.name ?? result.cik}</strong> — {result.status} · {tr({ en: 'as of', fr: 'au' })} {result.as_of} · {tr({ en: 'captured', fr: 'capturé' })} {result.retrieved_at}</p>
      <SegmentedControl label={tr({ en: 'Company research sections', fr: 'Sections de recherche' })} value={tab} onChange={setTab}
        options={tabs.map(t => ({ ...t, label: sectionState(t.value)?.status === 'unavailable' ? `${t.label} ⨯` : t.label }))} size="sm" />
      <div className="stack" role="region" aria-label={tabs.find(t => t.value === tab)?.label}>
        <SectionStatus state={sectionState(tab)} />
        {tab === 'overview' && <Overview result={result} />}
        {tab === 'financials' && <Financials result={result} />}
        {tab === 'filings' && <Filings result={result} />}
        {tab === 'insiders' && result.insider_transactions && <InsiderSection data={result.insider_transactions} />}
        {tab === 'holdings' && result.institutional_holdings && <HoldingsSection data={result.institutional_holdings} />}
        {sourceFor(tab).map(s => <SourceLine key={s.url} source={s} />)}
      </div>
      {result.errors.length > 0 && <details className="small"><summary>{tr({ en: 'Unavailable sources', fr: 'Sources indisponibles' })} ({result.errors.length})</summary>
        <ul>{result.errors.map((e, i) => <li key={`${e.section}-${i}`}>{e.section}: {codeText(e.code)}</li>)}</ul></details>}
      <ul className="small muted">{result.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </div>}
  </Card>;
}
