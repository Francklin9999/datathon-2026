'use client';
import { useEffect, useRef, useState } from 'react';
import { researchFetch } from '../../api/index';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';

export function ProviderObservations() {
  const { sessionId, tr } = useApp();
  const [asset, setAsset] = useState('btc');
  const [price, setPrice] = useState('');
  const [priceSource, setPriceSource] = useState<{source_url: string; source_sha256: string; retrieved_at: string} | null>(null);
  const generation = useRef(0);
  useEffect(() => { generation.current++; setPrice(''); setPriceSource(null); }, [sessionId]);
  async function loadPrice() {
    const current = ++generation.current;
    setPriceSource(null);
    setPrice(tr({en:'Loading…',fr:'Chargement…'}));
    try {
      const r = await researchFetch(`/intelligence/coinmetrics/${asset}`);
      if (!r.ok) throw new Error();
      const value: unknown = await r.json();
      if (!value || typeof value !== 'object' || !('value' in value) || typeof value.value !== 'string' || !('observed_at' in value) || typeof value.observed_at !== 'string') throw new Error();
      if (current !== generation.current) return;
      setPrice(`${asset.toUpperCase()} · ${value.value} USD · ${value.observed_at}`);
      if ('source_url' in value && typeof value.source_url === 'string' && 'source_sha256' in value && typeof value.source_sha256 === 'string' && 'retrieved_at' in value && typeof value.retrieved_at === 'string') setPriceSource({source_url:value.source_url, source_sha256:value.source_sha256, retrieved_at:value.retrieved_at});
    } catch { if (current === generation.current) setPrice(tr({en:'Unavailable: source access or noncommercial permission has not been configured.',fr:'Indisponible : accès à la source ou permission non commerciale non configurés.'})); }
  }
  return <Card title={tr({en:'Provider observations',fr:'Observations des fournisseurs'})}>
    <p>{tr({en:'Coin Metrics daily USD aggregate is not an executable exchange price. Community data is licensed for noncommercial use; the feed requires explicit operator configuration.',fr:'Le prix quotidien agrégé en dollars de Coin Metrics n’est pas un prix d’exécution. Les données communautaires sont réservées à un usage non commercial et nécessitent une configuration explicite.'})} <a href="https://docs.coinmetrics.io/service-and-support/coverage" target="_blank" rel="noreferrer">Coin Metrics</a></p>
    <label htmlFor="crypto-asset">{tr({en:'Asset',fr:'Actif'})}</label>{' '}<select id="crypto-asset" value={asset} onChange={e => { generation.current++; setAsset(e.target.value); setPrice(''); setPriceSource(null); }}><option value="btc">Bitcoin</option><option value="eth">Ether</option></select>{' '}<button className="btn" type="button" onClick={loadPrice} disabled={!sessionId}>{tr({en:'Load daily observation',fr:'Charger l’observation quotidienne'})}</button>
    <p role="status">{price}</p>
    {priceSource && <p className="small break"><a href={priceSource.source_url} target="_blank" rel="noreferrer">Coin Metrics Community, CC BY-NC</a> · {priceSource.retrieved_at}<br /><span className="mono">SHA-256 {priceSource.source_sha256}</span></p>}
  </Card>;
}
