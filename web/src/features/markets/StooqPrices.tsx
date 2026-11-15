'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Card } from '../../components/common/Page';
import { Loading } from '../../components/common/States';
import { useApp } from '../../state/app';

type Evidence = { url: string; http_status: number; observed: string; sha256?: string; content_type?: string };
type Review = {
  source_ids: string[]; provider: string; dataset: string; dataset_url: string; terms_url: string;
  checked_at: string; status: string; terms_verified: boolean; decision: string; evidence: Evidence[];
  unblock_requires: string; unverified: string[];
};
type Result = {
  status: string; network_request_sent: boolean; bars: null;
  request: { symbol: string; start: string; end: string; interval: string } | null; review: Review;
};

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object';
const isStr = (v: unknown): v is string => typeof v === 'string';

function isResult(v: unknown): v is Result {
  if (!isObj(v) || !isStr(v.status) || typeof v.network_request_sent !== 'boolean' || !isObj(v.review)) return false;
  const r = v.review;
  return isStr(r.provider) && isStr(r.terms_url) && isStr(r.dataset_url) && isStr(r.checked_at) && isStr(r.decision)
    && typeof r.terms_verified === 'boolean' && isStr(r.unblock_requires)
    && Array.isArray(r.unverified) && r.unverified.every(isStr)
    && Array.isArray(r.evidence) && r.evidence.every(e => isObj(e) && isStr(e.url) && typeof e.http_status === 'number' && isStr(e.observed))
    && (v.request === null || (isObj(v.request) && isStr(v.request.symbol) && isStr(v.request.start) && isStr(v.request.end)));
}

function isoDaysAgo(days: number) {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
}

export function StooqPrices() {
  const { sessionId, tr } = useApp();
  const [symbol, setSymbol] = useState('aapl.us');
  const [start, setStart] = useState(isoDaysAgo(365));
  const [end, setEnd] = useState(isoDaysAgo(1));
  const [result, setResult] = useState<Result | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function load() {
    setResult(null); setMessage(''); setLoading(true);
    try {
      const q = new URLSearchParams({ symbol: symbol.trim(), start, end });
      const r = await fetch(`${API_BASE}/intelligence/stooq/daily?${q}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (r.status === 400 || r.status === 422) { setMessage(tr({ en: 'Invalid Stooq symbol or date range (maximum about ten years, not in the future).', fr: 'Symbole Stooq ou période invalide (dix ans environ au maximum, pas dans le futur).' })); return; }
      if (!r.ok) throw new Error();
      const v: unknown = await r.json();
      if (!isResult(v)) throw new Error();
      setResult(v);
    } catch { setMessage(tr({ en: 'Stooq service unavailable.', fr: 'Service Stooq indisponible.' })); } finally { setLoading(false); }
  }

  const review = result?.review;
  return <Card title={tr({ en: 'Stooq historical daily prices', fr: 'Cours quotidiens historiques Stooq' })}>
    <p>{tr({ en: 'Daily open, high, low, close and volume by exact Stooq symbol (for example aapl.us). A Stooq symbol is a provider code, not a security identity.', fr: 'Ouverture, plus haut, plus bas, clôture et volume quotidiens par symbole Stooq exact (par exemple aapl.us). Un symbole Stooq est un code fournisseur, pas une identité de titre.' })}</p>
    <div>
      <label htmlFor="stooq-symbol">{tr({ en: 'Stooq symbol', fr: 'Symbole Stooq' })}</label>{' '}
      <input id="stooq-symbol" value={symbol} maxLength={24} onChange={e => setSymbol(e.target.value.toLowerCase())} />{' '}
      <label htmlFor="stooq-start">{tr({ en: 'From', fr: 'Du' })}</label>{' '}
      <input id="stooq-start" type="date" value={start} onChange={e => setStart(e.target.value)} />{' '}
      <label htmlFor="stooq-end">{tr({ en: 'To', fr: 'Au' })}</label>{' '}
      <input id="stooq-end" type="date" value={end} onChange={e => setEnd(e.target.value)} />{' '}
      <button className="btn" type="button" onClick={load} disabled={!sessionId || loading || !symbol.trim() || !start || !end}>{tr({ en: 'Request daily prices', fr: 'Demander les cours quotidiens' })}</button>
    </div>
    {loading && <Loading />}
    {message && <p role="status">{message}</p>}
    {result && review && <div role="status">
      <p><strong>{tr({ en: 'Blocked by provider access control', fr: 'Bloqué par le contrôle d’accès du fournisseur' })}</strong>
        {result.request && <> · <span className="mono">{result.request.symbol}</span> {result.request.start} → {result.request.end}</>}
        {' · '}{result.network_request_sent ? '' : tr({ en: 'No request was sent to Stooq; no prices are shown.', fr: 'Aucune requête n’a été envoyée à Stooq ; aucun cours n’est affiché.' })}</p>
      <p>{review.decision}</p>
      <p className="small">{tr({ en: 'Access checked', fr: 'Accès vérifié' })} {review.checked_at}{' · '}{review.terms_verified ? tr({ en: 'Terms read', fr: 'Conditions lues' }) : tr({ en: 'Terms could not be read', fr: 'Conditions illisibles' })}</p>
      <ul className="small">{review.evidence.map(e => <li key={e.url}><span className="mono">{e.url}</span> · HTTP {e.http_status} · {e.observed}{e.sha256 && <span className="block muted mono">SHA-256 {e.sha256}</span>}</li>)}</ul>
      <p className="small">{tr({ en: 'Unblocking requires', fr: 'Déblocage nécessaire' })}: {review.unblock_requires}</p>
      {review.unverified.length > 0 && <ul className="small muted">{review.unverified.map(u => <li key={u}>{tr({ en: 'Unverified', fr: 'Non vérifié' })}: {u}</li>)}</ul>}
      <p className="small"><ExternalLink href={review.dataset_url}>{review.dataset}</ExternalLink>{' · '}<ExternalLink href={review.terms_url}>{tr({ en: 'Stooq terms', fr: 'Conditions Stooq' })}</ExternalLink></p>
      <p className="small muted">{tr({ en: 'Currency, exchange and adjustment status would be stated per series if acquisition were permitted; none is shown because no data was retrieved.', fr: 'La devise, la place et l’ajustement seraient indiqués par série si l’acquisition était autorisée ; rien n’est affiché car aucune donnée n’a été récupérée.' })}</p>
    </div>}
  </Card>;
}
