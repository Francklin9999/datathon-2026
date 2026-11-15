'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Candidate = { item_id: string; url: string; asserted_isin: string; evidence_class: string };
type Result = { items: Candidate[]; available_at: string; source_sha256: string; partial: boolean };

export function WikidataCandidates() {
  const { sessionId, tr } = useApp();
  const [isin, setIsin] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  async function search(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setResult(null); setStatus('');
    try {
      const params = new URLSearchParams({ isin: isin.trim().toUpperCase() });
      const response = await fetch(`${API_BASE}/intelligence/wikidata-candidates?${params}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) throw new Error('unavailable');
      const body: unknown = await response.json();
      if (!body || typeof body !== 'object' || !('items' in body) || !Array.isArray(body.items) || !('source_sha256' in body)) throw new Error('invalid response');
      setResult(body as Result);
      setStatus(body.items.length ? tr({en: 'Candidate records found.', fr: 'Correspondances candidates trouvées.'}) : tr({en: 'No candidate found in this capture.', fr: 'Aucun candidat trouvé dans cette capture.'}));
    } catch { setStatus(tr({en: 'Source unavailable, invalid ISIN, or contact configuration missing.', fr: 'Source indisponible, ISIN invalide ou coordonnées non configurées.'})); } finally { setBusy(false); }
  }
  return <Card id="wikidata-candidates" title={tr({en: 'Wikidata candidates', fr: 'Candidats Wikidata'})}>
    <p>{tr({en: 'Discover community records that assert an exact ISIN. These are leads for investigation; they do not prove issuer identity or investment exposure.', fr: 'Découvrez les entrées communautaires indiquant un ISIN exact. Ces pistes ne prouvent ni l’identité de l’émetteur ni l’exposition financière.'})}</p>
    <form onSubmit={search}><label htmlFor="wikidata-isin">ISIN</label>{' '}<input id="wikidata-isin" value={isin} minLength={12} maxLength={12} disabled={busy} onChange={event => { setIsin(event.target.value); setResult(null); }} required />{' '}<button className="btn" disabled={busy || !sessionId}>{busy ? tr({en: 'Loading…', fr: 'Chargement…'}) : tr({en: 'Find candidates', fr: 'Rechercher les candidats'})}</button></form>
    <p className="small"><a href="#instrument-master">{tr({en: 'Record LEI, CIK and exchange statements in the identifier crosswalk', fr: 'Enregistrer LEI, CIK et cotations dans la table de correspondance'})}</a></p>
    <p role="status">{status}</p>
    {result && <><ul>{result.items.map(item => <li key={item.item_id}><a href={item.url} target="_blank" rel="noreferrer">{item.item_id}</a> · {item.asserted_isin} · {tr({en: 'unverified candidate', fr: 'candidat non vérifié'})}</li>)}</ul><p className="small muted">{tr({en: 'Captured', fr: 'Capturé le'})} {result.available_at} · SHA-256 <span className="mono break">{result.source_sha256}</span>{result.partial && tr({en: ' · result limit reached', fr: ' · limite de résultats atteinte'})}</p></>}
  </Card>;
}
