'use client';
import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Source = { id: string; status: string; docs_url: string; terms_url: string };
type RecordResult = {
  provider: string; status: string; source_url: string; source_sha256: string;
  available_at: string; limitations: string[];
  observation: Record<string, unknown> | null;
};

export function DefiResearch() {
  const { sessionId, tr } = useApp();
  const [sources, setSources] = useState<Source[]>([]);
  const [chain, setChain] = useState('ethereum');
  const [pool, setPool] = useState('');
  const [result, setResult] = useState<RecordResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++; setResult(null); setError(''); setSources([]); setBusy(false);
    if (!sessionId) return;
    const controller = new AbortController();
    fetch(`${API_BASE}/intelligence/defi/sources`, { signal: controller.signal, headers: { 'X-Aplomb-Session': sessionId } })
      .then(r => r.ok ? r.json() : Promise.reject()).then(body => { if (Array.isArray(body.providers)) setSources(body.providers); })
      .catch(() => undefined);
    return () => controller.abort();
  }, [sessionId]);
  const isReady = (id: string) => sources.some(source => source.id === id && source.status === 'configured');
  async function request(path: string) {
    const current = ++generation.current;
    setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`${API_BASE}${path}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) throw new Error();
      const body = await response.json() as RecordResult;
      if (!body || typeof body.source_sha256 !== 'string' || !Array.isArray(body.limitations)) throw new Error();
      if (current === generation.current) setResult(body);
    } catch { if (current === generation.current) setError(tr({ en: 'Source unavailable, identity mismatch, or data rights not configured.', fr: 'Source indisponible, identité non correspondante ou droits non configurés.' })); }
    finally { if (current === generation.current) setBusy(false); }
  }
  const field = (key: string) => {
    const value = result?.observation?.[key];
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '—';
  };
  return <Card title={tr({ en: 'On-chain market research', fr: 'Recherche sur les marchés en chaîne' })}>
    <p>{tr({ en: 'Look up one exact pool or provider protocol. Prices, liquidity and total value locked are provider estimates, not verified portfolio values.', fr: 'Recherchez un bassin exact ou un protocole du fournisseur. Les prix, la liquidité et la valeur bloquée sont des estimations, et non des valeurs de portefeuille vérifiées.' })}</p>
    <ul className="small">{sources.map(source => <li key={source.id}><a href={source.docs_url} target="_blank" rel="noreferrer">{source.id}</a> — {source.status.replaceAll('_', ' ')} · <a href={source.terms_url} target="_blank" rel="noreferrer">{tr({ en: 'terms', fr: 'conditions' })}</a></li>)}</ul>
    <form onSubmit={e => { e.preventDefault(); void request(`/intelligence/defi/pair/${encodeURIComponent(chain)}/${encodeURIComponent(pool.trim())}`); }}>
      <div className="field"><label htmlFor="defi-chain">{tr({ en: 'Chain', fr: 'Chaîne' })}</label>
        <select id="defi-chain" value={chain} onChange={e => { setChain(e.target.value); setResult(null); }} disabled={busy}>
          {['ethereum', 'base', 'arbitrum', 'optimism', 'bsc', 'polygon', 'avalanche', 'solana'].map(item => <option value={item} key={item}>{item}</option>)}
        </select>
      </div>
      <div className="field"><label htmlFor="defi-pool">{tr({ en: 'Exact pool address', fr: 'Adresse exacte du bassin' })}</label><input id="defi-pool" value={pool} maxLength={44} onChange={e => { setPool(e.target.value); setResult(null); }} required disabled={busy} /></div>
      <button className="btn" disabled={busy || !sessionId || !isReady('dexscreener')}>{tr({ en: 'Find pool', fr: 'Rechercher le bassin' })}</button>
    </form>
    {busy && <p role="status">{tr({ en: 'Loading…', fr: 'Chargement…' })}</p>}
    {error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite">
      <p>{result.provider} — {result.status} — {result.available_at}</p>
      {result.provider === 'dexscreener' && result.observation && <dl className="kv-list">
        <div className="kv"><dt>Pool</dt><dd className="mono break">{field('pool_address')}</dd></div>
        <div className="kv"><dt>{tr({ en: 'USD price', fr: 'Prix en USD' })}</dt><dd>{field('price_usd')}</dd></div>
        <div className="kv"><dt>{tr({ en: 'Liquidity (USD)', fr: 'Liquidité (USD)' })}</dt><dd>{field('liquidity_usd')}</dd></div>
        <div className="kv"><dt>{tr({ en: '24-hour volume (USD)', fr: 'Volume 24 heures (USD)' })}</dt><dd>{field('volume_24h_usd')}</dd></div>
      </dl>}
      <p className="small break"><a href={result.source_url} target="_blank" rel="noreferrer">{tr({ en: 'Provider source', fr: 'Source du fournisseur' })}</a><br /><span className="mono">SHA-256 {result.source_sha256}</span></p>
      <ul className="small muted">{result.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </div>}
  </Card>;
}
