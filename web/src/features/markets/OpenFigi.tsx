'use client';
import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Mapping = { figi: string; name: string | null; ticker: string | null; exchCode: string | null; compositeFIGI: string | null; shareClassFIGI: string | null; securityType: string | null };
type Result = { status: string; isin: string; mappings: Mapping[]; source_sha256: string; retrieved_at: string; dataset_version: string };

export function OpenFigi() {
  const { tr, sessionId } = useApp();
  const [isin, setIsin] = useState('');
  const [mic, setMic] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const generation = useRef(0);
  useEffect(() => { generation.current += 1; setResult(null); setError(false); setBusy(false); }, [sessionId]);
  function clear() { generation.current += 1; setResult(null); setError(false); setBusy(false); }
  async function load(event: React.FormEvent) {
    event.preventDefault();
    const current = ++generation.current;
    setBusy(true); setError(false); setResult(null);
    const query = new URLSearchParams({ isin: isin.trim().toUpperCase() });
    if (mic.trim()) query.set('mic', mic.trim().toUpperCase());
    try {
      const response = await fetch(`${API_BASE}/intelligence/openfigi?${query}`, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json() as Result;
      if (!Array.isArray(data.mappings) || typeof data.source_sha256 !== 'string') throw new Error('invalid response');
      if (generation.current === current) setResult(data);
    } catch { if (generation.current === current) setError(true); }
    finally { if (generation.current === current) setBusy(false); }
  }
  return <Card title={tr({ en: 'OpenFIGI instrument mappings', fr: 'Correspondances d’instruments OpenFIGI' })}>
    <p>{tr({ en: 'Map an exact ISIN to provider-assigned instrument, composite and share-class identifiers. Public access requires no API key. Multiple results are preserved; exchange codes are not automatically MICs or proof of issuer ownership.', fr: 'Reliez un ISIN exact aux identifiants d’instrument, composite et de catégorie d’actions du fournisseur. L’accès public ne nécessite aucune clé. Les résultats multiples restent distincts; les codes de place ne sont pas automatiquement des MIC ni une preuve de propriété.' })}</p>
    <form onSubmit={load}>
      <label htmlFor="openfigi-isin">ISIN</label><input id="openfigi-isin" value={isin} required minLength={12} maxLength={12} onChange={e => { setIsin(e.target.value); clear(); }} />
      <label htmlFor="openfigi-mic">{tr({ en: 'Optional MIC filter', fr: 'Filtre MIC facultatif' })}</label><input id="openfigi-mic" value={mic} maxLength={4} onChange={e => { setMic(e.target.value); clear(); }} />
      <button className="btn" disabled={busy || !sessionId}>{busy ? tr({ en: 'Loading…', fr: 'Chargement…' }) : tr({ en: 'Map identifiers', fr: 'Relier les identifiants' })}</button>
    </form>
    {error && <p role="alert">{tr({ en: 'Source unavailable, request limit reached or identifier invalid.', fr: 'Source indisponible, limite de requêtes atteinte ou identifiant invalide.' })}</p>}
    {result && <div aria-live="polite">
      <p>{result.mappings.length} {tr({ en: 'provider mappings; showing up to fifty', fr: 'correspondances du fournisseur; au plus cinquante affichées' })}.</p>
      {result.mappings.length > 0 && <div className="table-scroll" tabIndex={0} role="region" aria-label="OpenFIGI"><table className="data-table"><thead><tr><th scope="col">FIGI</th><th scope="col">{tr({ en: 'Provider label', fr: 'Libellé du fournisseur' })}</th><th scope="col">{tr({ en: 'Exchange code', fr: 'Code de place' })}</th><th scope="col">{tr({ en: 'Composite / share class', fr: 'Composite / catégorie' })}</th></tr></thead><tbody>{result.mappings.slice(0, 50).map(row => <tr key={row.figi}><th scope="row" className="mono">{row.figi}</th><td>{row.name} · {row.ticker}<br />{row.securityType}</td><td>{row.exchCode ?? '—'}</td><td className="mono">{row.compositeFIGI ?? '—'}<br />{row.shareClassFIGI ?? '—'}</td></tr>)}</tbody></table></div>}
      <p className="small break">{tr({ en: 'Captured', fr: 'Capturé' })}: {result.retrieved_at}<br />SHA-256: <span className="mono">{result.source_sha256}</span></p>
      <p className="small">{tr({ en: 'Provider mappings are also available in the session instrument crosswalk. Earlier availability is unknown.', fr: 'Les correspondances sont aussi disponibles dans le référentiel d’instruments de la session. La disponibilité antérieure est inconnue.' })}</p>
    </div>}
    <p className="small"><a href="https://www.openfigi.com/api/documentation" target="_blank" rel="noreferrer">OpenFIGI API</a> · <a href="https://www.openfigi.com/docs/terms-of-service" target="_blank" rel="noreferrer">{tr({ en: 'FIGI public-domain dedication and terms', fr: 'Dédicace FIGI au domaine public et conditions' })}</a></p>
  </Card>;
}
