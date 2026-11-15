'use client';
import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Constituent = {
  security_id: string; isin: string; weight_pct: number; value_usd: string; reported_names: string[];
  leis: string[]; asset_categories: string[]; direct_equity: boolean;
};
type Warning = { code: string; message: string; kinds?: string[] };
type Filing = {
  capture_id: string; dataset_version: string; series_id: string; series_name: string | null;
  registrant_name: string | null; registrant_cik: string; fund_isin: string | null; accession: string;
  form: string | null; filing_date: string | null; report_date: string; net_assets_usd: string | null;
  available_at: string; availability_basis: 'sec_acceptance_datetime' | 'retrieval_time'; retrieved_at: string;
  source_url: string; filing_index_url: string; source_sha256: string; position_count: number;
  fund_isin_mapping: { sources: string[] } | null;
};
type View = {
  status: 'available' | 'not_visible' | 'not_ingested'; reason?: string; series_id: string; as_of?: string;
  filing?: Filing; constituents?: Constituent[]; constituent_count?: number; covered_pct?: number;
  direct_equity_pct?: number; unknown_remainder_pct?: number;
  unknown_remainder_breakdown?: { unidentified_long_pct: number; derivatives_fair_value_pct: number; short_positions_pct: number; positions_without_weight: number; unexplained_pct: number };
  derivative_count?: number; unidentified_count?: number; warnings?: Warning[]; limitations?: string[];
};
type Summary = { capture_id: string; series_id: string; series_name: string | null; fund_isin: string | null; report_date: string; available_at: string; accession: string; position_count: number };

const pct = (value: number | undefined) => value === undefined ? '—' : `${value.toFixed(2)}%`;
const SERIES = /^S\d{9}$/;

export function FundHoldings() {
  const { tr, sessionId } = useApp();
  const [series, setSeries] = useState('');
  const [cik, setCik] = useState('');
  const [accession, setAccession] = useState('');
  const [asOf, setAsOf] = useState(() => new Date().toISOString().slice(0, 10));
  const [view, setView] = useState<View | null>(null);
  const [funds, setFunds] = useState<Summary[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const reasonText = useCallback((reason: string | undefined) => {
    const map: Record<string, { en: string; fr: string }> = {
      operator_contact_unconfigured: { en: 'SEC access is unavailable: the operator contact (APLOMB_SEC_CONTACT) is not configured.', fr: 'Accès SEC indisponible : le contact de l’opérateur (APLOMB_SEC_CONTACT) n’est pas configuré.' },
      source_forbidden: { en: 'SEC refused access (HTTP 403). No workaround is attempted.', fr: 'La SEC a refusé l’accès (HTTP 403). Aucun contournement n’est tenté.' },
      source_rate_limited: { en: 'SEC rate limit reached. Try again later.', fr: 'Limite de requêtes SEC atteinte. Réessayez plus tard.' },
      no_filing_found: { en: 'No N-PORT-P filing whose document names this series was found.', fr: 'Aucun dépôt N-PORT-P désignant cette série n’a été trouvé.' },
      fund_isin_mapping_undocumented: { en: 'This ISIN has no documented series mapping.', fr: 'Cet ISIN n’a pas de correspondance documentée avec une série.' },
      fund_not_ingested_in_session: { en: 'This fund has not been ingested in this session.', fr: 'Ce fonds n’a pas été importé dans cette session.' },
      no_capture_available_at_cutoff: { en: 'No captured report was available at this cutoff.', fr: 'Aucun rapport capturé n’était disponible à cette date.' },
      fund_isin_mapping_not_available_at_cutoff: { en: 'The fund ISIN mapping was not documented yet at this cutoff.', fr: 'La correspondance ISIN du fonds n’était pas encore documentée à cette date.' },
    };
    const text = reason ? map[reason] : undefined;
    return text ? tr(text) : tr({ en: 'SEC EDGAR N-PORT is unavailable.', fr: 'SEC EDGAR N-PORT est indisponible.' }) + (reason ? ` (${reason})` : '');
  }, [tr]);

  const headers = useCallback(() => ({ 'X-Aplomb-Session': sessionId ?? '' }), [sessionId]);

  const refresh = useCallback(async () => {
    if (!sessionId) return;
    try {
      const response = await fetch(`${API_BASE}/intelligence/funds`, { headers: headers() });
      if (!response.ok) return;
      const data: { items?: Summary[] } = await response.json();
      setFunds(Array.isArray(data.items) ? data.items : []);
    } catch { /* listing is optional */ }
  }, [sessionId, headers]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function errorReason(response: Response) {
    try {
      const body: { error?: { details?: { reason?: string } } } = await response.json();
      return body.error?.details?.reason;
    } catch { return undefined; }
  }

  async function show(fundId: string) {
    if (!sessionId) return;
    setBusy(true); setMessage('');
    try {
      const query = new URLSearchParams({ as_of: asOf, limit: '50' });
      const response = await fetch(`${API_BASE}/intelligence/funds/${encodeURIComponent(fundId)}?${query}`, { headers: headers() });
      if (!response.ok) { setView(null); setMessage(reasonText(await errorReason(response))); return; }
      const data: View = await response.json();
      setView(data);
      if (data.status !== 'available') setMessage(reasonText(data.reason));
    } catch { setMessage(reasonText(undefined)); } finally { setBusy(false); }
  }

  async function ingest(e: React.FormEvent) {
    e.preventDefault();
    const id = series.trim().toUpperCase();
    if (!sessionId || !SERIES.test(id)) return;
    setBusy(true); setMessage(tr({ en: 'Requesting SEC EDGAR…', fr: 'Requête auprès de SEC EDGAR…' })); setView(null);
    try {
      const query = new URLSearchParams();
      if (cik.trim()) query.set('cik', cik.trim());
      if (cik.trim() && accession.trim()) query.set('accession', accession.trim());
      const qs = query.toString();
      const response = await fetch(`${API_BASE}/intelligence/funds/${id}${qs ? `?${qs}` : ''}`, { method: 'POST', headers: headers() });
      if (!response.ok) { setMessage(reasonText(await errorReason(response))); return; }
      setMessage('');
      await refresh();
      setBusy(false);
      await show(id);
    } catch { setMessage(reasonText(undefined)); } finally { setBusy(false); }
  }

  const filing = view?.filing;
  const breakdown = view?.unknown_remainder_breakdown;
  return <Card title={tr({ en: 'Fund holdings look-through (SEC N-PORT)', fr: 'Transparence des fonds (SEC N-PORT)' })}>
    <p className="small">{tr({ en: 'Enter an SEC series ID (S + 9 digits). The latest public N-PORT-P report is fetched from SEC EDGAR, checked to name that series, and stored for this session only. Constituents are identified only by the ISIN reported in the filing.', fr: 'Saisissez un identifiant de série SEC (S + 9 chiffres). Le dernier rapport public N-PORT-P est récupéré sur SEC EDGAR, vérifié pour cette série et conservé pour cette session uniquement. Les composantes sont identifiées seulement par l’ISIN déclaré dans le dépôt.' })}</p>
    <form onSubmit={ingest}>
      <div className="field"><label htmlFor="fund-series">{tr({ en: 'SEC series ID', fr: 'Identifiant de série SEC' })}</label><input id="fund-series" value={series} maxLength={10} placeholder="S000076233" disabled={busy} onChange={e => setSeries(e.target.value.toUpperCase())} /></div>
      <div className="field"><label htmlFor="fund-cik">{tr({ en: 'Registrant CIK (optional)', fr: 'CIK du déclarant (facultatif)' })}</label><input id="fund-cik" value={cik} maxLength={10} inputMode="numeric" disabled={busy} onChange={e => setCik(e.target.value.replace(/\D/g, ''))} /></div>
      <div className="field"><label htmlFor="fund-accession">{tr({ en: 'Exact accession number (optional, requires CIK)', fr: 'Numéro d’accès exact (facultatif, exige le CIK)' })}</label><input id="fund-accession" value={accession} maxLength={20} placeholder="0001193125-26-137665" pattern="\d{10}-\d{2}-\d{6}" disabled={busy || !cik} onChange={e => setAccession(e.target.value.trim())} /></div>
      <div className="field"><label htmlFor="fund-asof">{tr({ en: 'Information cutoff', fr: 'Date limite de l’information' })}</label><input id="fund-asof" type="date" value={asOf} disabled={busy} required onChange={e => setAsOf(e.target.value)} /></div>
      <button className="btn" disabled={busy || !sessionId || !SERIES.test(series.trim())}>{tr({ en: 'Fetch latest filing', fr: 'Récupérer le dernier dépôt' })}</button>{' '}
      <button className="btn" type="button" disabled={busy || !sessionId || !SERIES.test(series.trim())} onClick={() => void show(series.trim())}>{tr({ en: 'View stored', fr: 'Voir la capture' })}</button>
    </form>
    {busy && <p role="status">{tr({ en: 'Loading…', fr: 'Chargement…' })}</p>}
    {message && <p role="alert">{message}</p>}
    {funds.length > 0 && <details><summary>{tr({ en: `Ingested in this session (${funds.length})`, fr: `Importés dans cette session (${funds.length})` })}</summary>
      <ul className="small">{funds.map(f => <li key={f.capture_id}><button className="btn" type="button" disabled={busy} onClick={() => { setSeries(f.series_id); void show(f.series_id); }}>{f.series_id}</button>{' '}{f.series_name ?? ''} · {tr({ en: 'report', fr: 'rapport' })} {f.report_date} · {f.position_count} {tr({ en: 'positions', fr: 'positions' })}</li>)}</ul>
    </details>}
    {view?.status === 'available' && filing && <div>
      <p className="small"><strong>{filing.series_name ?? filing.series_id}</strong> · {filing.series_id}{filing.fund_isin ? ` · ISIN ${filing.fund_isin}` : ''} · {filing.registrant_name ?? `CIK ${filing.registrant_cik}`}</p>
      <dl className="small">
        <dt>{tr({ en: 'Report date', fr: 'Date du rapport' })}</dt><dd>{filing.report_date}</dd>
        <dt>{tr({ en: 'Available from', fr: 'Disponible depuis' })}</dt><dd>{filing.available_at} · {filing.availability_basis === 'sec_acceptance_datetime' ? tr({ en: 'SEC acceptance (conservative upper bound)', fr: 'Acceptation SEC (borne supérieure prudente)' }) : tr({ en: 'retrieval time — acceptance not established', fr: 'heure de capture — acceptation non établie' })}</dd>
        <dt>{tr({ en: 'Filing', fr: 'Dépôt' })}</dt><dd>{filing.form ?? 'N-PORT'} {filing.accession}{filing.filing_date ? ` · ${tr({ en: 'filed', fr: 'déposé' })} ${filing.filing_date}` : ''}</dd>
        <dt>{tr({ en: 'Net assets (USD)', fr: 'Actif net (USD)' })}</dt><dd>{filing.net_assets_usd ?? '—'}</dd>
      </dl>
      <p><strong>{tr({ en: 'Covered by exact ISIN', fr: 'Couvert par ISIN exact' })}:</strong> {pct(view.covered_pct)} ({view.constituent_count} {tr({ en: 'constituents', fr: 'composantes' })}; {tr({ en: 'direct equity', fr: 'actions directes' })} {pct(view.direct_equity_pct)}) · <strong>{tr({ en: 'Unknown remainder', fr: 'Reste inconnu' })}:</strong> {pct(view.unknown_remainder_pct)}</p>
      {breakdown && <p className="small">{tr({ en: 'Remainder includes', fr: 'Le reste comprend' })}: {tr({ en: 'long positions without ISIN', fr: 'positions longues sans ISIN' })} {pct(breakdown.unidentified_long_pct)} ({view.unidentified_count}) · {tr({ en: 'derivatives at fair value', fr: 'dérivés à la juste valeur' })} {pct(breakdown.derivatives_fair_value_pct)} ({view.derivative_count}) · {tr({ en: 'shorts', fr: 'positions courtes' })} {pct(breakdown.short_positions_pct)} · {tr({ en: 'unexplained (cash, other assets/liabilities)', fr: 'non expliqué (liquidités, autres actifs/passifs)' })} {pct(breakdown.unexplained_pct)}. {tr({ en: 'Unknown is not zero exposure.', fr: 'Inconnu ne signifie pas exposition nulle.' })}</p>}
      {view.warnings?.map(w => <p key={w.code} role="note"><strong>{tr({ en: 'Warning', fr: 'Avertissement' })}:</strong> {w.code === 'derivatives_present' ? tr({ en: 'This fund holds derivatives (e.g. swaps). They are reported at fair value, not notional, so the holdings below are not its economic exposure and leverage is not measured.', fr: 'Ce fonds détient des dérivés (p. ex. swaps). Ils sont déclarés à la juste valeur, non au notionnel : les avoirs ci-dessous ne sont pas son exposition économique et l’effet de levier n’est pas mesuré.' }) : w.code === 'covered_exceeds_net_assets' ? tr({ en: 'Resolved long positions exceed 100% of net assets; the remainder is negative and is not cash.', fr: 'Les positions longues résolues dépassent 100 % de l’actif net ; le reste est négatif et ne représente pas des liquidités.' }) : tr({ en: 'Short positions are excluded from constituent weights.', fr: 'Les positions courtes sont exclues des pondérations.' })}{w.kinds?.length ? ` (${w.kinds.join(', ')})` : ''}</p>)}
      {view.constituents && view.constituents.length > 0 && <div className="table-scroll"><table className="data-table">
        <caption className="small">{tr({ en: `Top ${view.constituents.length} of ${view.constituent_count} constituents by % of net assets`, fr: `${view.constituents.length} principales composantes sur ${view.constituent_count}, en % de l’actif net` })}</caption>
        <thead><tr><th>ISIN</th><th>{tr({ en: 'Reported name', fr: 'Nom déclaré' })}</th><th>{tr({ en: 'Category', fr: 'Catégorie' })}</th><th>{tr({ en: '% net assets', fr: '% actif net' })}</th><th>{tr({ en: 'Value (USD)', fr: 'Valeur (USD)' })}</th></tr></thead>
        <tbody>{view.constituents.map(c => <tr key={c.isin}><td>{c.isin}</td><td>{c.reported_names[0] ?? '—'}</td><td>{c.asset_categories.join(', ') || '—'}</td><td>{c.weight_pct.toFixed(4)}</td><td>{c.value_usd}</td></tr>)}</tbody>
      </table></div>}
      <p className="small">
        <a href={filing.source_url} target="_blank" rel="noreferrer">{tr({ en: 'N-PORT primary document', fr: 'Document N-PORT principal' })}</a>{' · '}
        <a href={filing.filing_index_url} target="_blank" rel="noreferrer">{tr({ en: 'Filing index', fr: 'Index du dépôt' })}</a>
        {filing.fund_isin_mapping?.sources.map((url, i) => <span key={url}>{' · '}<a href={url} target="_blank" rel="noreferrer">{tr({ en: `ISIN mapping source ${i + 1}`, fr: `Source de correspondance ISIN ${i + 1}` })}</a></span>)}
      </p>
      <p className="small">SHA-256 {filing.source_sha256} · {tr({ en: 'dataset', fr: 'jeu de données' })} {filing.dataset_version} · {tr({ en: 'captured', fr: 'capturé' })} {filing.retrieved_at}</p>
      {view.limitations && <ul className="small">{view.limitations.map(item => <li key={item}>{item}</li>)}</ul>}
    </div>}
  </Card>;
}
