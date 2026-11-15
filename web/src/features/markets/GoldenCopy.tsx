'use client';
import { useEffect, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Source = { url: string; content_sha256: string; available_at: string; content_as_of: string };
type Result = { status: string; entity: null | { lei: string; legal_name: string; jurisdiction: string; entity_status: string }; source: Source; records_scanned: number };
type Metadata = { content_as_of: string; retrieved_at: string; archives: {kind:string;compressed_bytes:number;record_count:number;within_import_limit:boolean}[] };

export function GoldenCopy() {
  const { sessionId, tr } = useApp();
  const [lei, setLei] = useState('');
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setMetadata(null); setResult(null); setError(''); }, [sessionId]);
  async function loadMeta() {
    setBusy(true); setError('');
    try {
      const r = await fetch(`${API_BASE}/intelligence/gleif-golden/metadata`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!r.ok) throw new Error();
      const body: unknown = await r.json();
      if (!body || typeof body !== 'object' || !('archives' in body) || !Array.isArray(body.archives)) throw new Error();
      setMetadata(body as Metadata);
    } catch { setError(tr({ en: 'GLEIF metadata is unavailable.', fr: 'Les métadonnées GLEIF sont indisponibles.' })); }
    finally { setBusy(false); }
  }
  async function load(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const r = await fetch(`${API_BASE}/intelligence/gleif-golden/delta/${encodeURIComponent(lei.trim().toUpperCase())}`, {
        method: 'POST', headers: { 'X-Aplomb-Session': sessionId ?? '' },
      });
      if (!r.ok) throw new Error();
      const body: unknown = await r.json();
      if (!body || typeof body !== 'object' || !('status' in body) || !('source' in body)) throw new Error();
      setResult(body as Result);
    } catch { setError(tr({ en: 'The delta is unavailable, exceeds the safety limit, or the LEI is invalid.', fr: 'Le delta est indisponible, dépasse la limite de sécurité ou le LEI est invalide.' })); }
    finally { setBusy(false); }
  }
  return <Card title={tr({ en: 'GLEIF Golden Copy updates', fr: 'Mises à jour Golden Copy de GLEIF' })}>
    <p>{tr({ en: 'Search an exact LEI in the latest intraday update. Updates contain recent changes only; no match does not mean the entity is absent. An entity record does not prove a security relationship.', fr: 'Recherchez un LEI exact dans la dernière mise à jour intrajournalière. Une absence ne signifie pas que l’entité est absente. La fiche ne prouve pas un lien avec un titre.' })}</p>
    <button className="btn" type="button" disabled={busy || !sessionId} onClick={() => void loadMeta()}>{tr({ en: 'Inspect archive sizes', fr: 'Consulter la taille des archives' })}</button>
    {metadata && <div className="small"><p>{tr({ en: 'Content as of', fr: 'Contenu au' })} {metadata.content_as_of}; {tr({ en: 'retrieved', fr: 'récupéré' })} {metadata.retrieved_at}</p><ul>{metadata.archives.map(a => <li key={a.kind}>{a.kind}: {a.record_count.toLocaleString()} {tr({ en: 'records', fr: 'enregistrements' })}, {(a.compressed_bytes / 1_000_000).toFixed(2)} MB {a.within_import_limit ? '' : tr({ en: '(not imported)', fr: '(non importé)' })}</li>)}</ul></div>}
    <form onSubmit={load}><label htmlFor="golden-lei">LEI</label>{' '}<input id="golden-lei" required minLength={20} maxLength={20} value={lei} disabled={busy} onChange={e => { setLei(e.target.value); setResult(null); }} />{' '}<button className="btn" disabled={busy || !sessionId}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Inspect intraday update', fr: 'Consulter le delta' })}</button></form>
    {error && <p role="alert">{error}</p>}
    {result && <div role="status"><p>{result.entity ? `${result.entity.legal_name} · ${result.entity.lei} · ${result.entity.jurisdiction} · ${result.entity.entity_status}` : tr({ en: 'This LEI was not present in the latest update.', fr: 'Ce LEI ne figurait pas dans la dernière mise à jour.' })}</p><p className="small break"><a href={result.source.url} target="_blank" rel="noreferrer">GLEIF</a> · {tr({ en: 'capture available', fr: 'capture disponible' })} {result.source.available_at}<br /><span className="mono">SHA-256 {result.source.content_sha256}</span></p></div>}
  </Card>;
}
