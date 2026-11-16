'use client';
import { useEffect, useRef, useState } from 'react';
import { getApiClient } from '../../api/index';
import { ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import type { MarketConnection, MarketObservationResponse } from '../../contracts/types';
import { useApp } from '../../state/app';

const chainProviders=new Set(['coinmarketcap','blockscout','alchemy','goldrush']);
const identifierHints:Record<string,string>={coinmarketcap:'Numeric asset ID, e.g. 1 for Bitcoin',blockscout:'Exact Ethereum address: 0x…',alchemy:'ethereum',goldrush:'chains or an exact Ethereum address',eodhd:'Provider code and exchange, e.g. AAPL.US'};

// Generated contract types (1.6.0, research#7); the snake_case keys are the routes' own.
type Connection = MarketConnection;
type Result = MarketObservationResponse;

/** The provider's failure reason (details.reason), or a generic code; a body off the contract is invalid_source_response. */
function failureReason(error: unknown): string {
  if (!(error instanceof ApiRequestError)) return 'provider_unavailable';
  if (typeof error.details?.reason === 'string') return error.details.reason;
  return error.code === 'invalid_response' && error.status < 400 ? 'invalid_source_response' : 'provider_unavailable';
}

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
    getApiClient().marketConnections(controller.signal)
      .then(body=>setConnections(body.providers)).catch(()=>setConnections([]));
    return ()=>controller.abort();
  },[sessionId]);
  function reset(){generation.current++;setResult(null);setMessage('');}
  const ready=connections.filter(item=>item.credential_present&&item.rights_confirmed);
  async function load(event:React.FormEvent){
    event.preventDefault();const current=++generation.current;setBusy(true);setMessage('');setResult(null);
    const identifier=chainProviders.has(provider)?symbol.trim():symbol.trim().toUpperCase();
    const query:{symbol:string;kind?:string;mic?:string}={symbol:identifier};
    if(provider==='alpha-vantage')query.kind=kind;
    if(provider==='twelve-data')query.mic=mic.trim().toUpperCase();
    const end=new Date().toISOString().slice(0,10);
    const start=new Date(Date.now()-30*86400000).toISOString().slice(0,10);
    try{
      const client=getApiClient();
      const body=provider==='tiingo'?await client.tiingoHistory(symbol.trim().toUpperCase(),{start,end}):await client.marketObservation(provider,query);
      if(generation.current===current)setResult(body);
    }catch(error){if(generation.current===current)setMessage(failureReason(error));}
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
      <label htmlFor="keyed-provider">{tr({en:'Provider',fr:'Fournisseur'})}</label><select id="keyed-provider" value={selected?provider:''} disabled={busy} onChange={e=>{setProvider(e.target.value);setSymbol(e.target.value==='alchemy'?'ethereum':e.target.value==='goldrush'?'chains':'');reset();}}><option value="" disabled>{tr({en:'Choose a connected source',fr:'Choisir une source connectée'})}</option>{ready.map(item=><option key={item.id} value={item.id}>{item.id} — {item.supported_operation}</option>)}</select>
      {provider==='alpha-vantage'&&<><label htmlFor="keyed-kind">{tr({en:'Report',fr:'Rapport'})}</label><select id="keyed-kind" value={kind} disabled={busy} onChange={e=>{setKind(e.target.value);reset();}}>{[['quote','Quote'],['overview','Company overview'],['income','Income statement'],['balance','Balance sheet'],['cashflow','Cash flow']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></>}
      <label htmlFor="keyed-symbol">{tr({en:'Provider symbol or exact identifier',fr:'Symbole ou identifiant exact du fournisseur'})}</label><input id="keyed-symbol" value={symbol} placeholder={identifierHints[provider]} maxLength={120} disabled={busy} required onChange={e=>{setSymbol(e.target.value);reset();}} />
      {provider==='twelve-data'&&<><label htmlFor="keyed-mic">MIC</label><input id="keyed-mic" value={mic} minLength={4} maxLength={4} required disabled={busy} onChange={e=>{setMic(e.target.value);reset();}} /></>}
      <button className="btn" disabled={!sessionId||busy||!selected}>{busy?tr({en:'Loading…',fr:'Chargement…'}):tr({en:'Fetch from provider',fr:'Charger depuis la source'})}</button>
    </form>
    {message&&<p role="alert">{tr({en:'Provider response',fr:'Réponse du fournisseur'})}: {message.replaceAll('_',' ')}</p>}
    {result&&<div aria-live="polite">
      <p>{result.provider} — {result.status}</p>
      <dl className="kv-list">{Object.entries(result.observation).filter(([key,value])=>key!=='price'&&key!=='method'&&(typeof value==='string'||typeof value==='number')).map(([key,value])=><div className="kv" key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{String(value)}</dd></div>)}</dl>
      {['chains','balances'].map(key=>{const rows=result.observation[key];return Array.isArray(rows)&&rows.length>0?<div className="table-scroll" tabIndex={0} role="region" aria-label={key} key={key}><table className="data-table"><thead><tr><th scope="col">{key}</th><th scope="col">Details</th></tr></thead><tbody>{rows.map((row:Record<string,unknown>,i:number)=><tr key={i}><th scope="row">{String(row.name??row.contract_name??row.chain_id??i+1)}</th><td>{Object.entries(row).filter(([name,value])=>name!=='name'&&value!=null&&typeof value!=='object').map(([name,value])=><span className="block" key={name}>{name.replaceAll('_',' ')}: {String(value)}</span>)}</td></tr>)}</tbody></table></div>:null;})}
      {result.observation.price!=null&&<p>{String(result.observation.provider_symbol??result.observation.asset_symbol??'')}: {scalar('price')} · {scalar('price_unit')} · {String(result.observation.observed_date??result.observation.last_updated??result.retrieved_at??'')}</p>}
      {company!=null&&typeof company==='object'&&<dl className="kv-list">{Object.entries(company).map(([key,value])=><div className="kv" key={key}><dt>{key}</dt><dd>{typeof value==='string'?value:'—'}</dd></div>)}</dl>}
      {Array.isArray(bars)&&<div className="table-scroll" tabIndex={0} role="region" aria-label={tr({en:'Provider daily bars',fr:'Cours quotidiens de la source'})}><table className="data-table"><thead><tr><th scope="col">{tr({en:'Date',fr:'Date'})}</th><th scope="col">{tr({en:'Close',fr:'Clôture'})}</th><th scope="col">{tr({en:'Adjusted close',fr:'Clôture ajustée'})}</th><th scope="col">{tr({en:'Volume',fr:'Volume'})}</th></tr></thead><tbody>{bars.map((bar:Record<string,unknown>,i:number)=><tr key={String(bar.date??i)}><th scope="row">{String(bar.date??'—')}</th><td>{String(bar.close??'—')} {scalar('currency')}</td><td>{String(bar.adj_close??'—')}</td><td>{String(bar.volume??'—')}</td></tr>)}</tbody></table></div>}
      {Array.isArray(statements)&&<div className="table-scroll" tabIndex={0} role="region" aria-label={tr({en:'Financial statements',fr:'États financiers'})}><table className="data-table"><thead><tr><th scope="col">Period</th><th scope="col">Frequency</th><th scope="col">Concept</th><th scope="col">Value</th></tr></thead><tbody>{statements.map((row:Record<string,unknown>,i:number)=><tr key={i}><th scope="row">{String(row.period_end)}</th><td>{String(row.frequency)}</td><td>{String(row.concept)}</td><td>{row.value==null?'—':String(row.value)} {String(row.unit)}</td></tr>)}</tbody></table></div>}
      {((result.sources??(result.source_url?[{url:result.source_url,sha256:result.source_sha256??'',retrieved_at:result.retrieved_at??''}]:[])) as {url:string;sha256:string;retrieved_at:string}[]).map(source=><p className="small break" key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{result.provider}</a> · {source.retrieved_at}<br /><span className="mono">SHA-256 {source.sha256}</span></p>)}
      <ul className="small muted">{result.limitations.map(note=><li key={note}>{note}</li>)}</ul>
    </div>}
  </Card>;
}
