'use client';
import { useEffect, useRef, useState } from 'react';
import { researchFetch } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Result = { status: string; provider: string; lei: string; reference_period?: string; rows: Record<string, string | null>[];
  available_at: string; source_url: string; source_sha256: string; source_licence: string; limitations: string[];
  partial?: boolean; total_reported?: number };

export function EURegulatory() {
  const { tr, sessionId } = useApp();
  const [lei, setLei] = useState('');
  const [period, setPeriod] = useState('202506');
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  useEffect(() => { generation.current++; setResult(null); setError(''); setBusy(false); }, [sessionId]);
  async function load(source: 'eba-market-risk' | 'esma-entity') {
    const current = ++generation.current;
    setBusy(true); setResult(null); setError('');
    try {
      const query = source === 'eba-market-risk' ? `?${new URLSearchParams({ period })}` : '';
      const response = await researchFetch(`/intelligence/eu/${source}/${encodeURIComponent(lei.trim().toUpperCase())}${query}`);
      if (!response.ok) throw new Error();
      const value = await response.json() as Result;
      if (!value || !Array.isArray(value.rows) || !Array.isArray(value.limitations)) throw new Error();
      if (current === generation.current) setResult(value);
    } catch { if (current === generation.current) setError(tr({ en: 'Source unavailable or LEI invalid.', fr: 'Source indisponible ou LEI invalide.' })); }
    finally { if (current === generation.current) setBusy(false); }
  }
  return <Card title={tr({ en: 'European regulatory records', fr: 'Registres réglementaires européens' })}>
    <p>{tr({ en: 'Look up an exact legal entity identifier in EBA market-risk disclosures and ESMA authorization records. EBA reporting is historical and source availability starts at capture.', fr: 'Recherchez un identifiant d’entité juridique exact dans les données de risque de marché de l’ABE et les autorisations de l’AEMF. Les données de l’ABE sont historiques et leur disponibilité commence à la capture.' })}</p>
    <div className="field"><label htmlFor="eu-lei">LEI</label><input id="eu-lei" minLength={20} maxLength={20} value={lei} disabled={busy} onChange={e => { setLei(e.target.value); setResult(null); setError(''); }} /></div>
    <div className="field"><label htmlFor="eu-period">{tr({ en: 'EBA reporting period', fr: 'Période de déclaration ABE' })}</label>
      <select id="eu-period" value={period} disabled={busy} onChange={e => { setPeriod(e.target.value); setResult(null); }}>
        <option value="202506">2025-06</option><option value="202503">2025-03</option><option value="202412">2024-12</option><option value="202409">2024-09</option>
      </select></div>
    <div className="row-actions"><button type="button" className="btn" disabled={busy || !sessionId || lei.trim().length !== 20} onClick={() => void load('eba-market-risk')}>{tr({ en: 'EBA market risk', fr: 'Risque de marché ABE' })}</button>
      <button type="button" className="btn" disabled={busy || !sessionId || lei.trim().length !== 20} onClick={() => void load('esma-entity')}>{tr({ en: 'ESMA records', fr: 'Registres AEMF' })}</button></div>
    {busy && <p role="status">{tr({ en: 'Loading…', fr: 'Chargement…' })}</p>}{error && <p role="alert">{error}</p>}
    {result && <div aria-live="polite"><p>{result.provider} · {result.lei} · {result.status} · {result.available_at}</p>
      {result.partial && <p>{tr({ en: `Showing ${result.rows.length} of ${result.total_reported} registry records.`, fr: `${result.rows.length} dossiers affichés sur ${result.total_reported}.` })}</p>}
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Regulatory observations', fr: 'Observations réglementaires' })}><table className="data-table"><thead><tr>
        {result.provider === 'European Banking Authority' ? <><th scope="col">{tr({ en: 'Measure', fr: 'Mesure' })}</th><th scope="col">{tr({ en: 'Amount', fr: 'Montant' })}</th><th scope="col">{tr({ en: 'Codes / source row', fr: 'Codes / ligne source' })}</th></> : <><th scope="col">{tr({ en: 'Entity', fr: 'Entité' })}</th><th scope="col">{tr({ en: 'Reported status', fr: 'Statut déclaré' })}</th><th scope="col">{tr({ en: 'Authority / country', fr: 'Autorité / pays' })}</th></>}
      </tr></thead><tbody>{result.rows.map((row, i) => <tr key={i}>
        {result.provider === 'European Banking Authority' ? <><th scope="row">{row.label}</th><td>{row.amount} {row.unit}</td><td className="mono">{row.portfolio_code} / {row.product_code} / {row.market_risk_code} · {row.source_row}</td></> : <><th scope="row">{row.ae_entityName}</th><td>{row.ae_status} · {row.ae_entityTypeCode}</td><td>{row.ae_competentAuthority} · {row.ae_homeMemberState}</td></>}
      </tr>)}</tbody></table></div>
      <p className="small break"><a href={result.source_url} target="_blank" rel="noreferrer">{result.provider} · {tr({ en: 'Source, available free of charge', fr: 'Source, disponible gratuitement' })}</a><br /><span className="mono">SHA-256 {result.source_sha256}</span><br /><a href={result.source_licence} target="_blank" rel="noreferrer">{tr({ en: 'Source terms', fr: 'Conditions de la source' })}</a></p>
      <ul className="small muted">{result.limitations.map(note => <li key={note}>{note}</li>)}</ul></div>}
  </Card>;
}
