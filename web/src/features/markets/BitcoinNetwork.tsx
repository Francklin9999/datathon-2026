'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Observation = { kind: string; chain: string; data: Record<string, unknown>; retrieved_at: string;
  source_url: string; source_sha256: string; dataset_version: string };
type NetworkResult = { status: string; observations: Record<string, Observation>; errors: Record<string, string>; limitations: string[] };

export function BitcoinNetwork() {
  const { sessionId, tr } = useApp();
  const [result, setResult] = useState<NetworkResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  async function load() {
    setBusy(true); setError(false); setResult(null);
    try {
      const response = await fetch(`${API_BASE}/intelligence/chains/bitcoin`, {
        headers: { 'X-Aplomb-Session': sessionId ?? '' },
      });
      if (!response.ok) throw new Error('unavailable');
      const body: unknown = await response.json();
      if (!body || typeof body !== 'object' || !('observations' in body) || !('errors' in body)) throw new Error('invalid');
      setResult(body as NetworkResult);
    } catch { setError(true); } finally { setBusy(false); }
  }
  return <Card title={tr({ en: 'Bitcoin network conditions', fr: 'État du réseau Bitcoin' })}>
    <p>{tr({ en: 'Inspect recent block height, unconfirmed transaction volume, and the provider’s estimated fees. These describe network conditions.', fr: 'Consultez la hauteur récente, le volume de transactions non confirmées et les frais estimés par le fournisseur. Ces valeurs décrivent l’état du réseau.' })}</p>
    <button type="button" className="btn" disabled={busy || !sessionId} onClick={() => void load()}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Load network snapshot', fr: 'Charger l’état du réseau' })}</button>
    {error && <p role="alert">{tr({ en: 'Source unavailable or hosted-data reuse rights are not configured.', fr: 'Source indisponible ou droits de réutilisation des données non configurés.' })}</p>}
    {result && <div aria-live="polite">
      <p>{result.status}</p>
      {Object.entries(result.errors).map(([kind]) => <p key={kind}>{kind}: {tr({ en: 'Source unavailable or invalid.', fr: 'Source indisponible ou invalide.' })}</p>)}
      {Object.values(result.observations).map(item => <details key={item.kind} className="fold">
        <summary>{item.chain} · {item.kind} · {item.retrieved_at}</summary>
        <dl>{Object.entries(item.data).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'object' && value !== null ? Object.entries(value).map(([k, v]) => `${k}: ${String(v)}`).join(', ') : String(value)}</dd></div>)}</dl>
        <p className="small break"><a href={item.source_url} target="_blank" rel="noreferrer">Mempool REST API</a> · {item.dataset_version}<br /><span className="mono">SHA-256 {item.source_sha256}</span></p>
      </details>)}
      <ul className="small muted">{result.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </div>}
  </Card>;
}
