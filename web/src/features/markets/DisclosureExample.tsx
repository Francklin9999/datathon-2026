'use client';
import { useState } from 'react';
import { API_BASE } from '../../api/index';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';

export function DisclosureExample() {
  const { sessionId, tr } = useApp();
  const [asOf, setAsOf] = useState('2026-11-15');
  const [text, setText] = useState('');
  async function load(e: React.FormEvent) {
    e.preventDefault(); setText(tr({en:'Loading…', fr:'Chargement…'}));
    try {
      const url = `${API_BASE}/intelligence/disclosures/aapu?${new URLSearchParams({ as_of: asOf })}`;
      const response = await fetch(url, { headers: { 'X-Aplomb-Session': sessionId ?? '' } });
      if (!response.ok) throw new Error('unavailable');
      const data: unknown = await response.json();
      if (!data || typeof data !== 'object' || !('exposures' in data) || !Array.isArray(data.exposures)) throw new Error('invalid');
      if (!data.exposures.length) setText(tr({en:'No disclosure is available at this cutoff.', fr:'Aucune divulgation disponible à cette date.'}));
      else {
        const first = data.exposures[0] as { security_id?: unknown; weight_pct?: unknown };
        if (typeof first.security_id !== 'string' || typeof first.weight_pct !== 'number' || !('unresolved_portfolio_weight_pct' in data) || typeof data.unresolved_portfolio_weight_pct !== 'number') throw new Error('invalid');
        setText(`${first.security_id}: ${first.weight_pct.toFixed(4)}% · ${tr({en:'unresolved',fr:'non résolu'})}: ${data.unresolved_portfolio_weight_pct.toFixed(4)}%. ${tr({en:'Swaps and leverage are not measured here.',fr:'Les swaps et l’effet de levier ne sont pas mesurés.'})}`);
      }
    } catch { setText(tr({en:'Disclosure unavailable.',fr:'Divulgation indisponible.'})); }
  }
  return <Card title={tr({en:'Dated fund disclosure example',fr:'Exemple de divulgation datée d’un fonds'})}>
    <p>{tr({en:'A partial SEC filing for Direxion Daily AAPL Bull 2X Shares, linked to its listing identifier through documented records. This is a leveraged fund, so direct equity is not its total economic exposure.',fr:'Extrait partiel d’un dépôt SEC pour Direxion Daily AAPL Bull 2X Shares, lié à son identifiant de cotation par des documents. Ce fonds est à effet de levier : les actions détenues ne représentent pas son exposition économique totale.'})}</p>
    <form onSubmit={load}><label htmlFor="disclosure-date">{tr({en:'Information cutoff',fr:'Date limite de l’information'})}</label>{' '}<input id="disclosure-date" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} required />{' '}<button className="btn" disabled={!sessionId}>{tr({en:'Inspect disclosure',fr:'Consulter la divulgation'})}</button></form>
    <p role="status">{text}</p>
    <a href="https://www.sec.gov/Archives/edgar/data/1424958/000119312526137665/primary_doc.xml" target="_blank" rel="noreferrer">SEC N-PORT</a>{' · '}
    <a href="https://www.sec.gov/Archives/edgar/data/1424958/000119312525145523/0001193125-25-145523-index.htm" target="_blank" rel="noreferrer">SEC class mapping</a>{' · '}
    <a href="https://documents.bvl.com.pe/pubdif/boldia/20251205.pdf" target="_blank" rel="noreferrer">BVL ISIN mapping</a>
  </Card>;
}
