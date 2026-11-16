'use client';
import { useEffect, useRef, useState } from 'react';
import { researchFetch } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Registry = { status: 'found' | 'not_found'; record: { names: string[]; number: string; jurisdiction: string; status: string | null; governing_act: string | null; registration_date: string | null } | null; source: { sha256: string; retrieved_at: string; attribution: string } };

export function CompanyRegistry() {
  const { sessionId, tr } = useApp();
  const [region, setRegion] = useState('ca');
  const [number, setNumber] = useState('');
  const [result, setResult] = useState<Registry | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const owner = useRef(sessionId); owner.current = sessionId;
  useEffect(() => { generation.current++; setResult(null); setError(false); }, [sessionId]);
  function invalidate() { generation.current++; setResult(null); setError(false); }
  async function load(event: React.FormEvent) {
    event.preventDefault(); invalidate(); const request = generation.current; const expected = sessionId;
    setBusy(true);
    try {
      const response = await researchFetch(`/intelligence/company-registry/${region}/${encodeURIComponent(number)}`);
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json() as Registry;
      if (!data.source?.sha256 || (data.status !== 'found' && data.status !== 'not_found')) throw new Error('invalid');
      if (generation.current === request && owner.current === expected) setResult(data);
    } catch { if (generation.current === request && owner.current === expected) setError(true); } finally { setBusy(false); }
  }
  return <Card title={tr({ en: 'Corporate registry', fr: 'Registre des sociétés' })}>
    <p>{tr({ en: 'Look up an exact official company number. A company record does not establish an exchange listing or ownership of a security.', fr: 'Consultez un numéro officiel exact. Une fiche de société ne prouve ni cotation ni propriété d’un titre.' })}</p>
    <form onSubmit={load}>
      <label htmlFor="registry-region">{tr({ en: 'Registry', fr: 'Registre' })}</label>{' '}
      <select id="registry-region" value={region} disabled={busy} onChange={e => { setRegion(e.target.value); invalidate(); }}><option value="ca">Corporations Canada</option><option value="ie">Ireland CRO open data</option></select>{' '}
      <label htmlFor="registry-number">{tr({ en: 'Company number', fr: 'Numéro de société' })}</label>{' '}
      <input id="registry-number" value={number} inputMode="numeric" pattern="[1-9][0-9]{0,9}" disabled={busy} onChange={e => { setNumber(e.target.value); invalidate(); }} required />{' '}
      <button className="btn" disabled={!sessionId || busy}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Look up', fr: 'Consulter' })}</button>
    </form>
    {error && <p role="alert">{tr({ en: 'Registry unavailable or response could not be verified.', fr: 'Registre indisponible ou réponse invérifiable.' })}</p>}
    {result && <div role="status">
      {result.record ? <p><strong>{result.record.names.join(', ')}</strong> — {result.record.number}<br />{result.record.status} · {result.record.governing_act}<br />{result.record.registration_date}</p> : <p>{tr({ en: 'No exact record found in this registry.', fr: 'Aucune fiche exacte trouvée dans ce registre.' })}</p>}
      <p>{result.source.attribution}: {region === 'ca' ? <a href="https://open.canada.ca/en/open-government-licence-canada" target="_blank" rel="noreferrer">Corporations Canada</a> : <a href="https://opendata.cro.ie/dataset/companies" target="_blank" rel="noreferrer">Ireland Companies Registration Office</a>}</p>
      <p className="small muted">{tr({ en: 'Captured', fr: 'Capturé' })}: {result.source.retrieved_at}. {tr({ en: 'Earlier availability is unknown.', fr: 'La disponibilité antérieure est inconnue.' })}<br /><span className="mono break">SHA-256 {result.source.sha256}</span></p>
      {region === 'ca' && <p className="small muted">{tr({ en: 'The federal registry excludes provincial and certain financial corporations.', fr: 'Le registre fédéral exclut les sociétés provinciales et certaines institutions financières.' })}</p>}
    </div>}
  </Card>;
}
