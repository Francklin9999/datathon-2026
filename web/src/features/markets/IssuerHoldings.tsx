'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Card } from '../../components/common/Page';
import { Loading, Unavailable } from '../../components/common/States';
import { useApp } from '../../state/app';

type Clause = { label: string; quote: string };
type Review = {
  issuer: string; source_ids: string[]; dataset: string; dataset_url: string; terms_url: string;
  checked_at: string | null; checked_in_this_review: boolean; terms_page_sha256: string | null;
  status: string; decision: string; clauses: Clause[]; unblock_requires: string; limitations: string[];
};
type Rights = { checked_at: string; issuers: Review[]; permitted_alternative: { source: string; note: string } };
type FundResult = { status: string; requested_fund_ticker: string; network_request_sent: boolean; holdings: null; review: Review };

const ISSUERS = [
  { key: 'spdr', label: 'State Street SPDR' },
  { key: 'vanguard', label: 'Vanguard' },
  { key: 'ishares', label: 'BlackRock iShares' },
];

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object';
const isStr = (v: unknown): v is string => typeof v === 'string';

function isReview(v: unknown): v is Review {
  return isObj(v) && isStr(v.issuer) && Array.isArray(v.source_ids) && v.source_ids.every(isStr)
    && isStr(v.terms_url) && isStr(v.dataset_url) && isStr(v.status) && isStr(v.decision)
    && Array.isArray(v.clauses) && v.clauses.every(c => isObj(c) && isStr(c.label) && isStr(c.quote))
    && Array.isArray(v.limitations) && v.limitations.every(isStr) && isStr(v.unblock_requires)
    && (v.checked_at === null || isStr(v.checked_at)) && (v.terms_page_sha256 === null || isStr(v.terms_page_sha256));
}

function ReviewView({ review }: { review: Review }) {
  const { tr } = useApp();
  const blocked = review.status !== 'permitted';
  return <section>
    <h3>{review.issuer} <span className="small muted">({review.source_ids.join(', ')})</span></h3>
    <p><strong>{blocked ? tr({ en: 'Blocked by provider terms', fr: 'Bloqué par les conditions du fournisseur' }) : review.status}</strong>
      {' · '}{review.checked_at ? `${tr({ en: 'Terms read', fr: 'Conditions lues' })} ${review.checked_at}` : tr({ en: 'Terms not re-read in this review', fr: 'Conditions non relues dans cet examen' })}</p>
    <p>{review.decision}</p>
    {review.clauses.length > 0 && <ul>{review.clauses.map(c => <li key={c.label}><span className="small muted">{c.label}:</span> <q>{c.quote}</q></li>)}</ul>}
    <p className="small">{tr({ en: 'Unblocking requires', fr: 'Déblocage nécessaire' })}: {review.unblock_requires}</p>
    <p className="small"><ExternalLink href={review.terms_url}>{tr({ en: 'Official terms', fr: 'Conditions officielles' })}</ExternalLink>{' · '}<ExternalLink href={review.dataset_url}>{review.dataset}</ExternalLink>
      {review.terms_page_sha256 && <span className="block small muted mono">SHA-256 {review.terms_page_sha256}</span>}</p>
    {review.limitations.length > 0 && <ul className="small muted">{review.limitations.map(l => <li key={l}>{l}</li>)}</ul>}
  </section>;
}

export function IssuerHoldings() {
  const { sessionId, tr } = useApp();
  const [rights, setRights] = useState<Rights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [issuer, setIssuer] = useState('spdr');
  const [ticker, setTicker] = useState('SPY');
  const [fund, setFund] = useState<FundResult | null>(null);
  const [fundError, setFundError] = useState('');
  const headers = { 'X-Aplomb-Session': sessionId ?? '' };

  async function loadRights() {
    setLoading(true); setError(false);
    try {
      const r = await fetch(`${API_BASE}/intelligence/issuer-holdings/rights`, { headers });
      if (!r.ok) throw new Error();
      const v: unknown = await r.json();
      if (!isObj(v) || !isStr(v.checked_at) || !Array.isArray(v.issuers) || !v.issuers.every(isReview)
        || !isObj(v.permitted_alternative) || !isStr(v.permitted_alternative.source) || !isStr(v.permitted_alternative.note)) throw new Error();
      setRights(v as Rights);
    } catch { setError(true); setRights(null); } finally { setLoading(false); }
  }

  async function requestFund() {
    setFund(null); setFundError('');
    try {
      const r = await fetch(`${API_BASE}/intelligence/issuer-holdings/${encodeURIComponent(issuer)}/${encodeURIComponent(ticker.trim())}`, { headers });
      if (r.status === 400 || r.status === 422) { setFundError(tr({ en: 'Invalid fund ticker.', fr: 'Symbole de fonds invalide.' })); return; }
      if (!r.ok) throw new Error();
      const v: unknown = await r.json();
      if (!isObj(v) || !isStr(v.status) || !isStr(v.requested_fund_ticker) || typeof v.network_request_sent !== 'boolean' || !isReview(v.review)) throw new Error();
      setFund(v as FundResult);
    } catch { setFundError(tr({ en: 'Issuer holdings service unavailable.', fr: 'Service des positions d’émetteurs indisponible.' })); }
  }

  return <Card title={tr({ en: 'Issuer-published ETF holdings', fr: 'Positions d’ETF publiées par les émetteurs' })}>
    <p>{tr({ en: 'Daily holdings files published by fund issuers are used only where the issuer’s own terms permit automated download, storage and display. Each issuer’s terms were reviewed; no holdings are fetched from a blocked issuer.', fr: 'Les fichiers quotidiens de positions publiés par les émetteurs ne sont utilisés que si leurs propres conditions autorisent le téléchargement automatisé, le stockage et l’affichage. Les conditions de chaque émetteur ont été examinées ; aucune position n’est récupérée auprès d’un émetteur bloqué.' })}</p>
    <button className="btn" type="button" onClick={loadRights} disabled={!sessionId || loading}>{tr({ en: 'Show rights review', fr: 'Afficher l’examen des droits' })}</button>
    {loading && <Loading />}
    {error && <Unavailable title={tr({ en: 'Rights review unavailable', fr: 'Examen des droits indisponible' })} />}
    {rights && <div>
      {rights.issuers.map(r => <ReviewView key={r.issuer} review={r} />)}
      <p className="small"><strong>{tr({ en: 'Permitted alternative', fr: 'Alternative autorisée' })}:</strong> {rights.permitted_alternative.source}. {rights.permitted_alternative.note}</p>
    </div>}
    <div>
      <label htmlFor="issuer-select">{tr({ en: 'Issuer', fr: 'Émetteur' })}</label>{' '}
      <select id="issuer-select" value={issuer} onChange={e => setIssuer(e.target.value)}>{ISSUERS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}</select>{' '}
      <label htmlFor="issuer-fund-ticker">{tr({ en: 'Fund ticker', fr: 'Symbole du fonds' })}</label>{' '}
      <input id="issuer-fund-ticker" value={ticker} maxLength={10} onChange={e => setTicker(e.target.value.toUpperCase())} />{' '}
      <button className="btn" type="button" onClick={requestFund} disabled={!sessionId || !ticker.trim()}>{tr({ en: 'Request holdings', fr: 'Demander les positions' })}</button>
    </div>
    {fundError && <p role="status">{fundError}</p>}
    {fund && <div role="status">
      <p><strong>{fund.requested_fund_ticker}</strong> · {tr({ en: 'No holdings: acquisition blocked by issuer terms.', fr: 'Aucune position : acquisition bloquée par les conditions de l’émetteur.' })}{' '}
        {fund.network_request_sent ? '' : tr({ en: 'No request was sent to the issuer.', fr: 'Aucune requête n’a été envoyée à l’émetteur.' })}</p>
      <p className="small muted">{tr({ en: 'A ticker is not an identity; no ISIN or constituent mapping is inferred.', fr: 'Un symbole n’établit pas une identité ; aucun ISIN ni constituant n’est déduit.' })}</p>
      <p className="small"><ExternalLink href={fund.review.terms_url}>{tr({ en: 'Terms that block this source', fr: 'Conditions qui bloquent cette source' })}</ExternalLink></p>
    </div>}
  </Card>;
}
