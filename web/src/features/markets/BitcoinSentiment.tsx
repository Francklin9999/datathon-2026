'use client';
import { useEffect, useRef, useState } from 'react';
import { researchFetch } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Observation = { value: number; classification: string; observed_at: string };
type Sentiment = { observations: Observation[]; source: { retrieved_at: string; sha256: string } };

export function BitcoinSentiment() {
  const { sessionId, tr } = useApp();
  const [result, setResult] = useState<Sentiment | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const currentSession = useRef(sessionId);
  currentSession.current = sessionId;
  useEffect(() => { setResult(null); setError(false); }, [sessionId]);
  async function load() {
    const expected = sessionId;
    setBusy(true); setError(false); setResult(null);
    try {
      const response = await researchFetch('/intelligence/bitcoin-sentiment');
      if (!response.ok) throw new Error('unavailable');
      const data: Sentiment = await response.json();
      if (!Array.isArray(data.observations) || !data.observations.length || !data.source?.sha256) throw new Error('invalid response');
      if (currentSession.current === expected) setResult(data);
    } catch { if (currentSession.current === expected) setError(true); } finally { setBusy(false); }
  }
  return <Card title={tr({ en: 'Bitcoin sentiment', fr: 'Sentiment Bitcoin' })}>
    <p>{tr({ en: 'Alternative.me combines market indicators into a Bitcoin sentiment index from zero to one hundred. It is a provider methodology and does not predict returns.', fr: 'Alternative.me combine des indicateurs de marché en un indice de sentiment Bitcoin de zéro à cent. Il reflète la méthode du fournisseur et ne prédit pas les rendements.' })}</p>
    <button className="btn" type="button" onClick={() => void load()} disabled={!sessionId || busy}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Load sentiment', fr: 'Charger le sentiment' })}</button>
    {error && <p role="alert">{tr({ en: 'The sentiment source is unavailable.', fr: 'La source de sentiment est indisponible.' })}</p>}
    {result && result.observations[0] && <div role="status">
      <p><strong>{result.observations[0].value} / 100 — {result.observations[0].classification}</strong><br />{tr({ en: 'Index observation', fr: 'Observation de l’indice' })}: {result.observations[0].observed_at}</p>
      <p>{tr({ en: 'Data from', fr: 'Données de' })} <a href="https://alternative.me/crypto/fear-and-greed-index/" target="_blank" rel="noreferrer">Alternative.me — Crypto Fear &amp; Greed Index</a>.</p>
      <p className="small muted">{tr({ en: 'Captured', fr: 'Capturé' })}: {result.source.retrieved_at}. {tr({ en: 'Historical publication and revision times are unknown.', fr: 'Les dates de publication et de révision historiques sont inconnues.' })}<br /><span className="mono break">SHA-256 {result.source.sha256}</span></p>
      <details><summary>{tr({ en: 'Recent reported observations', fr: 'Observations récentes' })}</summary><ul>{result.observations.map(row => <li key={row.observed_at}>{row.observed_at}: {row.value} / 100 — {row.classification}</li>)}</ul></details>
    </div>}
  </Card>;
}
