'use client';
import {useState} from 'react';
import type {Position,Profile} from '../../contracts/types';
import {getApiClient} from '../../api/index';
import {asApiError,type ApiRequestError} from '../../api/errors';
import type {ModelResult} from '../../api/expandedInvestor';
import {useApp} from '../../state/app';
import {Card} from '../../components/common/Page';
import {DraftRestoredNote,ProfileWriteError} from '../../components/common/States';
import {ModelResultView,ResultRows} from '../planning/ModelResult';
import {dropDraft,mergeDraftRows,stashDraft} from '../../lib/draftStore';
import {useRestoredDraft} from '../../state/useDraft';

type Entry={quantity:string;asOf:string;origin:'user'|'imported';source:string};
export function PositionQuantities({profile}:{profile:Profile}){
  const {tr,applyProfile,feature}=useApp();
  const draftKey=`position-quantities|${profile.profileId}`;
  // Input typed before a conflict reload is kept for every holding the reloaded profile still has.
  const restored=useRestoredDraft<Record<string,Entry>>(draftKey,profile.version);
  const [inputs,setInputs]=useState<Record<string,Entry>>(()=>mergeDraftRows(Object.fromEntries(profile.portfolio.positions.map(p=>[p.ticker,{quantity:p.quantity===undefined||p.quantity===null?'':String(p.quantity),asOf:p.quantityAsOf??'',origin:p.quantityOrigin??'user',source:p.quantitySource??''}])),restored));
  const [error,setError]=useState<ApiRequestError|null>(null);const [busy,setBusy]=useState(false);const [result,setResult]=useState<ModelResult|null>(null);
  const patch=(ticker:string,next:Partial<Entry>)=>{setInputs(s=>({...s,[ticker]:{quantity:'',asOf:'',origin:'user',source:'',...s[ticker],...next}}));setResult(null);setError(null);};
  const save=async()=>{setBusy(true);setError(null);try{
    const positions:Position[]=profile.portfolio.positions.map(p=>{const row=inputs[p.ticker]!;const {quantity:old,quantityAsOf,quantityOrigin,quantitySource,...base}=p;void old;void quantityAsOf;void quantityOrigin;void quantitySource;return row.quantity.trim()?{...base,quantity:Number(row.quantity),quantityAsOf:row.asOf,quantityOrigin:row.origin,quantitySource:row.source}:base;});
    applyProfile(await getApiClient().updatePortfolio(profile.profileId,{version:profile.version,totalValue:profile.portfolio.totalValue,positions}));dropDraft(draftKey);
  }catch(e){setError(asApiError(e));}finally{setBusy(false);}};
  const inspect=async()=>{setBusy(true);setError(null);try{setResult(await getApiClient().positionDetails(profile.profileId,{version:profile.version}));}catch(e){setError(asApiError(e));}finally{setBusy(false);}};
  return <Card title={tr({en:'Documented position quantities',fr:'Quantités de positions documentées'})}>
    <p>{tr({en:'Enter actual user/imported quantities only with their original date and source. These quantities are not independently verified and do not replace modeled portfolio weights or imply an executed transaction. Modeled position value remains weight × reported capital. Leave quantity blank to clear a prior current quantity; prior evidence is retained in account history.',fr:'Saisissez les quantités utilisateur/importées avec leur date originale et leur source. Elles ne sont pas vérifiées indépendamment et ne remplacent pas les poids modélisés ni ne prouvent une transaction. Valeur modélisée = poids × capital déclaré. Une quantité vide efface la quantité actuelle; les preuves antérieures restent dans l’historique.'})}</p>
    {/* Saving quantities is a profile_creator write; inspecting saved inputs is not gated. */}
    {!feature('profile_creator')?null:profile.activeAccountId==='aggregate'?<p>{tr({en:'Select an individual account before editing quantities.',fr:'Sélectionnez un compte individuel avant de modifier les quantités.'})}</p>:<form onSubmit={e=>{e.preventDefault();void save();}}><fieldset disabled={busy}>
      {restored&&<DraftRestoredNote/>}
      {profile.portfolio.positions.map(p=>{const row=inputs[p.ticker]!;return <fieldset key={p.ticker}><legend>{p.ticker} · {p.weightPct}%</legend><div className="form-grid"><div className="field"><label htmlFor={`quantity-${p.ticker}`}>{tr({en:'Documented quantity (optional)',fr:'Quantité documentée (facultative)'})}</label><input id={`quantity-${p.ticker}`} type="number" min={0} step="any" value={row.quantity} onChange={e=>patch(p.ticker,{quantity:e.target.value})}/></div><div className="field"><label htmlFor={`quantity-date-${p.ticker}`}>{tr({en:'Quantity as-of date',fr:'Date de la quantité'})}</label><input id={`quantity-date-${p.ticker}`} type="date" required={!!row.quantity.trim()} value={row.asOf} onChange={e=>patch(p.ticker,{asOf:e.target.value})}/></div><div className="field"><label htmlFor={`quantity-origin-${p.ticker}`}>{tr({en:'Origin',fr:'Origine'})}</label><select id={`quantity-origin-${p.ticker}`} value={row.origin} onChange={e=>patch(p.ticker,{origin:e.target.value as Entry['origin']})}><option value="user">user</option><option value="imported">imported</option></select></div><div className="field"><label htmlFor={`quantity-source-${p.ticker}`}>{tr({en:'Quantity source',fr:'Source de la quantité'})}</label><input id={`quantity-source-${p.ticker}`} required={!!row.quantity.trim()} maxLength={1000} value={row.source} onChange={e=>patch(p.ticker,{source:e.target.value})}/></div></div></fieldset>;})}
      <button className="btn" type="submit">{tr({en:'Save documented quantities',fr:'Enregistrer les quantités documentées'})}</button></fieldset></form>}
    <button className="btn ghost" type="button" disabled={busy} onClick={()=>void inspect()}>{tr({en:'Inspect saved position inputs',fr:'Examiner les positions enregistrées'})}</button>{error&&<ProfileWriteError error={error} onReload={()=>stashDraft(draftKey,profile.version,inputs)}/>}{result&&<><ResultRows value={result.positions} label={tr({en:'Position provenance',fr:'Provenance des positions'})} columns={[{key:'ticker',label:tr({en:'Holding',fr:'Position'})},{key:'modeledPositionValue',label:tr({en:'Modeled position value',fr:'Valeur modélisée'})},{key:'quantity',label:tr({en:'Documented quantity input',fr:'Quantité documentée saisie'})}]} /><ModelResultView value={result}/></>}
  </Card>;
}
