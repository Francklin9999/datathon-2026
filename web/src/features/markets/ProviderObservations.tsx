'use client';
import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/index';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';

export function ProviderObservations({ secAvailable = false }: { secAvailable?: boolean }) {
  const { sessionId, tr } = useApp();
  const [asset, setAsset] = useState('btc');
  const [price, setPrice] = useState('');
  const [priceSource, setPriceSource] = useState<{source_url: string; source_sha256: string; retrieved_at: string} | null>(null);
  const [feed, setFeed] = useState('');
  const [library, setLibrary] = useState<{title: string; url: string}[]>([]);
  const generation = useRef(0);
  useEffect(() => { generation.current++; setPrice(''); setPriceSource(null); setFeed(''); setLibrary([]); }, [sessionId]);
  async function loadPrice() {
    const current = ++generation.current;
    setPriceSource(null);
    setPrice(tr({en:'Loading…',fr:'Chargement…'}));
    try {
      const r = await fetch(`${API_BASE}/intelligence/coinmetrics/${asset}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!r.ok) throw new Error();
      const value: unknown = await r.json();
      if (!value || typeof value !== 'object' || !('value' in value) || typeof value.value !== 'string' || !('observed_at' in value) || typeof value.observed_at !== 'string') throw new Error();
      if (current !== generation.current) return;
      setPrice(`${asset.toUpperCase()} · ${value.value} USD · ${value.observed_at}`);
      if ('source_url' in value && typeof value.source_url === 'string' && 'source_sha256' in value && typeof value.source_sha256 === 'string' && 'retrieved_at' in value && typeof value.retrieved_at === 'string') setPriceSource({source_url:value.source_url, source_sha256:value.source_sha256, retrieved_at:value.retrieved_at});
    } catch { if (current === generation.current) setPrice(tr({en:'Unavailable: source access or noncommercial permission has not been configured.',fr:'Indisponible : accès à la source ou permission non commerciale non configurés.'})); }
  }
  async function loadFeed() {
    setFeed(tr({en:'Loading…',fr:'Chargement…'}));
    try {
      const r = await fetch(`${API_BASE}/intelligence/sec-structured`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!r.ok) throw new Error();
      const value: unknown = await r.json();
      if (!value || typeof value !== 'object' || !('items' in value) || !Array.isArray(value.items)) throw new Error();
      setFeed(`${value.items.length} ${tr({en:'recent SEC entries',fr:'entrées récentes de la SEC'})}`);
    } catch { setFeed(tr({en:'SEC feed unavailable or operator contact not configured.',fr:'Flux SEC indisponible ou contact de l’opérateur non configuré.'})); }
  }
  async function loadLibrary() {
    setFeed(tr({en:'Loading…',fr:'Chargement…'})); setLibrary([]);
    try {
      const r = await fetch(`${API_BASE}/intelligence/sec-data-library`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!r.ok) throw new Error();
      const value: unknown = await r.json();
      if (!value || typeof value !== 'object' || !('items' in value) || !Array.isArray(value.items)) throw new Error();
      const items = value.items.filter((item: unknown): item is {title: string; url: string} => !!item && typeof item === 'object' && 'title' in item && typeof item.title === 'string' && 'url' in item && typeof item.url === 'string' && item.url.startsWith('https://www.sec.gov/'));
      setLibrary(items); setFeed(`${items.length} ${tr({en:'dataset links',fr:'liens de données'})}`);
    } catch { setFeed(tr({en:'SEC Data Library unavailable or contact not configured.',fr:'Bibliothèque SEC indisponible ou contact non configuré.'})); }
  }
  return <Card title={tr({en:'Provider observations',fr:'Observations des fournisseurs'})}>
    <p>{tr({en:'Coin Metrics daily USD aggregate is not an executable exchange price. Community data is licensed for noncommercial use; the feed requires explicit operator configuration.',fr:'Le prix quotidien agrégé en dollars de Coin Metrics n’est pas un prix d’exécution. Les données communautaires sont réservées à un usage non commercial et nécessitent une configuration explicite.'})} <a href="https://docs.coinmetrics.io/service-and-support/coverage" target="_blank" rel="noreferrer">Coin Metrics</a></p>
    <label htmlFor="crypto-asset">{tr({en:'Asset',fr:'Actif'})}</label>{' '}<select id="crypto-asset" value={asset} onChange={e => { generation.current++; setAsset(e.target.value); setPrice(''); setPriceSource(null); }}><option value="btc">Bitcoin</option><option value="eth">Ether</option></select>{' '}<button className="btn" type="button" onClick={loadPrice} disabled={!sessionId}>{tr({en:'Load daily observation',fr:'Charger l’observation quotidienne'})}</button>
    <p role="status">{price}</p>
    {priceSource && <p className="small break"><a href={priceSource.source_url} target="_blank" rel="noreferrer">Coin Metrics Community, CC BY-NC</a> · {priceSource.retrieved_at}<br /><span className="mono">SHA-256 {priceSource.source_sha256}</span></p>}
    {secAvailable && <><p>{tr({en:'The SEC structured-disclosure feed is a recent discovery index, not a complete filing history.',fr:'Le flux structuré de la SEC est un index récent, non un historique complet.'})}</p>
    <button className="btn" type="button" onClick={loadFeed} disabled={!sessionId}>{tr({en:'Inspect SEC feed',fr:'Consulter le flux SEC'})}</button><button className="btn" type="button" onClick={loadLibrary} disabled={!sessionId}>{tr({en:"Browse SEC Data Library",fr:"Consulter la bibliothèque SEC"})}</button><p role="status">{feed}</p><ul>{library.map(item => <li key={item.url}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a></li>)}</ul></>}
  </Card>;
}
