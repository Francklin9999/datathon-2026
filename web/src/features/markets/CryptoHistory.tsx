'use client';
import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Candle = { open_time: string; close_time: string; open: string; high: string; low: string; close: string; volume: string };
type History = { market: { base: string; quote: string; quote_kind: string }; date: string; candles: Candle[]; complete: boolean;
  checksum: { sha256: string; verified: boolean }; provenance: { attribution: string; available_at: string; terms_url: string; source_last_modified: string | null } };

export function CryptoHistory() {
  const { sessionId, tr } = useApp();
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [day, setDay] = useState(() => new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10));
  const [result, setResult] = useState<History | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  useEffect(() => { generation.current++; setResult(null); setError(false); setBusy(false); }, [sessionId]);
  async function load(event: React.FormEvent) {
    event.preventDefault(); const current = ++generation.current;
    setBusy(true); setError(false); setResult(null);
    try {
      const response = await fetch(`${API_BASE}/intelligence/crypto-markets/vision/${encodeURIComponent(symbol)}/${encodeURIComponent(day)}?interval=1d`,
        { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) throw new Error();
      const data = await response.json() as History;
      if (!data || !Array.isArray(data.candles) || !data.checksum?.verified) throw new Error();
      if (generation.current === current) setResult(data);
    } catch { if (generation.current === current) setError(true); }
    finally { if (generation.current === current) setBusy(false); }
  }
  return <Card title={tr({ en: 'Crypto exchange history', fr: 'Historique de marché crypto' })}>
    <p>{tr({ en: 'Daily Binance Vision spot candles for personal noncommercial research. Stablecoin quotes such as USDT and USDC are distinct assets, not US dollars.', fr: 'Chandelles quotidiennes Binance Vision pour la recherche personnelle non commerciale. Les cours en USDT et USDC utilisent des actifs distincts du dollar américain.' })}</p>
    <form onSubmit={load}>
      <div className="field"><label htmlFor="crypto-history-pair">{tr({ en: 'Exact market', fr: 'Marché exact' })}</label><select id="crypto-history-pair" value={symbol} disabled={busy} onChange={e => { setSymbol(e.target.value); setResult(null); }}>
        {['BTCUSDT','BTCUSDC','BTCEUR','ETHUSDT','ETHUSDC','ETHEUR','SOLUSDT','SOLUSDC'].map(item => <option key={item} value={item}>{item}</option>)}
      </select></div>
      <div className="field"><label htmlFor="crypto-history-date">{tr({ en: 'Completed UTC date', fr: 'Date UTC terminée' })}</label><input id="crypto-history-date" type="date" value={day} disabled={busy} onChange={e => { setDay(e.target.value); setResult(null); }} required /></div>
      <button className="btn" disabled={busy || !sessionId}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Load daily history', fr: 'Charger l’historique quotidien' })}</button>
    </form>
    {error && <p role="alert">{tr({ en: 'Source unavailable, date missing or local research rights not enabled.', fr: 'Source indisponible, date absente ou droits de recherche locale non activés.' })}</p>}
    {result && <div aria-live="polite"><p>{result.market.base}/{result.market.quote} · {result.date} · {result.complete ? tr({ en: 'complete daily file', fr: 'fichier quotidien complet' }) : tr({ en: 'incomplete daily file', fr: 'fichier quotidien incomplet' })}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Daily market history', fr: 'Historique quotidien' })}><table className="data-table"><thead><tr><th scope="col">UTC</th><th scope="col">{tr({ en: 'Open', fr: 'Ouverture' })}</th><th scope="col">{tr({ en: 'High', fr: 'Plus haut' })}</th><th scope="col">{tr({ en: 'Low', fr: 'Plus bas' })}</th><th scope="col">{tr({ en: 'Close', fr: 'Clôture' })}</th><th scope="col">{tr({ en: 'Base volume', fr: 'Volume de base' })}</th></tr></thead><tbody>{result.candles.map(row => <tr key={row.open_time}><th scope="row">{row.open_time}</th><td>{row.open} {result.market.quote}</td><td>{row.high} {result.market.quote}</td><td>{row.low} {result.market.quote}</td><td>{row.close} {result.market.quote}</td><td>{row.volume} {result.market.base}</td></tr>)}</tbody></table></div>
      <p className="small break"><a href={result.provenance.terms_url} target="_blank" rel="noreferrer">{result.provenance.attribution}</a><br />{tr({ en: 'Captured', fr: 'Capturé' })}: {result.provenance.available_at}<br />SHA-256 {result.checksum.sha256}</p></div>}
  </Card>;
}
