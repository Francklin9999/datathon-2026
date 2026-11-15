'use client';
import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../api/index';
import { Card } from '../../components/common/Page';
import { useApp } from '../../state/app';

type Connection = { id: string; credential_present: boolean; rights_confirmed: boolean; signup_url: string; supported_operation: string };
type Result = { status: string; provider: string; observation: Record<string, unknown>; source_url?: string; source_sha256?: string; retrieved_at?: string; sources?: {url:string;sha256:string;retrieved_at:string}[]; limitations:string[] };

export function KeyedMarkets() {
  const { sessionId,tr }=useApp();
  const [connections,setConnections]=useState<Connection[]>([]);
  const [provider,setProvider]=useState('tiingo');
  const [symbol,setSymbol]=useState('');
  const [kind,setKind]=useState('quote');
  const [mic,setMic]=useState('XNGS');
  const [result,setResult]=useState<Result|null>(null);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const generation=useRef(0);
  useEffect(()=>{
    generation.current++;setResult(null);setMessage('');setBusy(false);
    if(!sessionId)return;
    const controller=new AbortController();
    fetch(`${API_BASE}/research/market-connections`,{signal:controller.signal,headers:{'X-Aplomb-Session':sessionId}})
      .then(r=>r.ok?r.json():Promise.reject()).then(body=>{if(Array.isArray(body.providers))setConnections(body.providers);}).catch(()=>setConnections([]));
    return ()=>controller.abort();
  },[sessionId]);
  function reset(){generation.current++;setResult(null);setMessage('');}
  const ready=connections.filter(item=>item.credential_present&&item.rights_confirmed);
  async function load(event:React.FormEvent){
    event.preventDefault();const current=++generation.current;setBusy(true);setMessage('');setResult(null);
    const query=new URLSearchParams({symbol:symbol.trim().toUpperCase()});
    if(provider==='alpha-vantage')query.set('kind',kind);
    if(provider==='twelve-data')query.set('mic',mic.trim().toUpperCase());
    const end=new Date().toISOString().slice(0,10);
    const start=new Date(Date.now()-30*86400000).toISOString().slice(0,10);
    const path=provider==='tiingo'?`/research/tiingo/${encodeURIComponent(symbol.trim().toUpperCase())}?${new URLSearchParams({start,end})}`:`/research/market-provider/${provider}?${query}`;
    try{
      const response=await fetch(`${API_BASE}${path}`,{headers:{'X-Aplomb-Session':sessionId??''}});
      const body=await response.json();
      if(!response.ok)throw new Error(typeof body.error?.details?.reason==='string'?body.error.details.reason:'provider_unavailable');
      if(!body.observation||typeof body.observation!=='object')throw new Error('invalid_source_response');
      if(generation.current===current)setResult(body as Result);
    }catch(error){if(generation.current===current)setMessage(error instanceof Error?error.message:'provider_unavailable');}
    finally{if(generation.current===current)setBusy(false);}
  }
  if(!ready.length)return null;
  const selected=ready.some(item=>item.id===provider);
  const bars=result?.observation.bars;
  const company=result?.observation.company;
  const statements=result?.observation.statements;
  const scalar=(key:string)=>{const value=result?.observation[key];return typeof value==='string'||typeof value==='number'?String(value):'—';};
  return <Card title={tr({en:'Connected market data',fr:'Données de marché connectées'})}>
    <p>{tr({en:'Use your configured provider accounts. Provider symbols remain source-specific; Twelve Data also requires an exact exchange MIC. Prices and company reports retain source attribution and capture times.',fr:'Utilisez vos comptes configurés. Les symboles restent propres à chaque fournisseur; Twelve Data exige aussi un MIC exact. Les résultats conservent leurs sources et dates de capture.'})}</p>
    <form onSubmit={load}>
      <label htmlFor="keyed-provider">{tr({en:'Provider',fr:'Fournisseur'})}</label><select id="keyed-provider" value={selected?provider:''} disabled={busy} onChange={e=>{setProvider(e.target.value);reset();}}><option value="" disabled>{tr({en:'Choose a connected source',fr:'Choisir une source connectée'})}</option>{ready.map(item=><option key={item.id} value={item.id}>{item.id} — {item.supported_operation}</option>)}</select>
      {provider==='alpha-vantage'&&<><label htmlFor="keyed-kind">{tr({en:'Report',fr:'Rapport'})}</label><select id="keyed-kind" value={kind} disabled={busy} onChange={e=>{setKind(e.target.value);reset();}}>{[['quote','Quote'],['overview','Company overview'],['income','Income statement'],['balance','Balance sheet'],['cashflow','Cash flow']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></>}
      <label htmlFor="keyed-symbol">{tr({en:'Exact provider symbol',fr:'Symbole exact du fournisseur'})}</label><input id="keyed-symbol" value={symbol} maxLength={40} disabled={busy} required onChange={e=>{setSymbol(e.target.value);reset();}} />
      {provider==='twelve-data'&&<><label htmlFor="keyed-mic">MIC</label><input id="keyed-mic" value={mic} minLength={4} maxLength={4} required disabled={busy} onChange={e=>{setMic(e.target.value);reset();}} /></>}
      <button className="btn" disabled={!sessionId||busy||!selected}>{busy?tr({en:'Loading…',fr:'Chargement…'}):tr({en:'Fetch from provider',fr:'Charger depuis la source'})}</button>
    </form>
    {message&&<p role="alert">{tr({en:'Provider response',fr:'Réponse du fournisseur'})}: {message.replaceAll('_',' ')}</p>}
    {result&&<div aria-live="polite">
      <p>{result.provider} — {result.status}</p>
      {result.observation.price!=null&&<p>{scalar('provider_symbol')}: {scalar('price')} · {scalar('price_unit')} · {scalar('observed_date')}</p>}
      {company!=null&&typeof company==='object'&&<dl className="kv-list">{Object.entries(company).map(([key,value])=><div className="kv" key={key}><dt>{key}</dt><dd>{typeof value==='string'?value:'—'}</dd></div>)}</dl>}
      {Array.isArray(bars)&&<div className="table-scroll" tabIndex={0} role="region" aria-label={tr({en:'Provider daily bars',fr:'Cours quotidiens de la source'})}><table className="data-table"><thead><tr><th scope="col">{tr({en:'Date',fr:'Date'})}</th><th scope="col">{tr({en:'Close',fr:'Clôture'})}</th><th scope="col">{tr({en:'Adjusted close',fr:'Clôture ajustée'})}</th><th scope="col">{tr({en:'Volume',fr:'Volume'})}</th></tr></thead><tbody>{bars.map((bar:Record<string,unknown>,i:number)=><tr key={String(bar.date??i)}><th scope="row">{String(bar.date??'—')}</th><td>{String(bar.close??'—')} {scalar('currency')}</td><td>{String(bar.adj_close??'—')}</td><td>{String(bar.volume??'—')}</td></tr>)}</tbody></table></div>}
      {Array.isArray(statements)&&<div className="table-scroll" tabIndex={0} role="region" aria-label={tr({en:'Financial statements',fr:'États financiers'})}><table className="data-table"><thead><tr><th scope="col">Period</th><th scope="col">Frequency</th><th scope="col">Concept</th><th scope="col">Value</th></tr></thead><tbody>{statements.map((row:Record<string,unknown>,i:number)=><tr key={i}><th scope="row">{String(row.period_end)}</th><td>{String(row.frequency)}</td><td>{String(row.concept)}</td><td>{row.value==null?'—':String(row.value)} {String(row.unit)}</td></tr>)}</tbody></table></div>}
      {(result.sources??(result.source_url?[{url:result.source_url,sha256:result.source_sha256??'',retrieved_at:result.retrieved_at??''}]:[])).map(source=><p className="small break" key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{result.provider}</a> · {source.retrieved_at}<br /><span className="mono">SHA-256 {source.sha256}</span></p>)}
      <ul className="small muted">{result.limitations.map(note=><li key={note}>{note}</li>)}</ul>
    </div>}
  </Card>;
}
