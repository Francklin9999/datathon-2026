'use client';
import {useState} from 'react';
import type {Profile} from '../../contracts/types';
import {getApiClient} from '../../api/index';
import {asApiError,type ApiRequestError} from '../../api/errors';
import {useApp} from '../../state/app';
import {Card} from '../../components/common/Page';
import {DraftRestoredNote,ProfileWriteError} from '../../components/common/States';
import {parseFinalTargets} from '../../lib/targetAllocation';
import {SupportedUniverse} from '../../components/common/SupportedUniverse';
import {useAssetUniverse} from '../../state/useAssetUniverse';
import {checkTickers,targetLineTickers} from '../../lib/tickerCoverage';
import {dropDraft,stashDraft} from '../../lib/draftStore';
import {useRestoredDraft} from '../../state/useDraft';

interface AccountEditDraft{id:string;name:string;editAllocation:boolean;capital:string;text:string}
export function AccountEditor({profile}:{profile:Profile}){
  const {tr,applyProfile,feature}=useApp();const draftKey=`account-edit|${profile.profileId}`;
  // Input typed before a conflict reload is kept only while the edited account still exists.
  const stashed=useRestoredDraft<AccountEditDraft>(draftKey,profile.version);const restored=stashed&&profile.accounts?.some(a=>a.accountId===stashed.id)?stashed:null;
  const initial=profile.accounts?.find(a=>a.accountId===profile.activeAccountId)??profile.accounts?.[0];
  const [id,setId]=useState(restored?.id??initial?.accountId??'');const [name,setName]=useState(restored?.name??initial?.name??'');const [editAllocation,setEditAllocation]=useState(restored?.editAllocation??false);const [capital,setCapital]=useState(restored?.capital??String(initial?.portfolio.totalValue??''));const [text,setText]=useState(restored?.text??initial?.portfolio.positions.map(p=>`${p.ticker} ${p.weightPct}`).join('\n')??'');const [error,setError]=useState<ApiRequestError|null>(null);const [invalid,setInvalid]=useState(false);const [busy,setBusy]=useState(false);
  // Final-weight tickers are checked against the snapshot before the write (the server refuses them after).
  const universe=useAssetUniverse();const tickerCheck=checkTickers(editAllocation?targetLineTickers(text):[],universe,feature('on_demand_tickers'));
  const choose=(next:string)=>{const a=profile.accounts?.find(p=>p.accountId===next);setId(next);setName(a?.name??'');setCapital(String(a?.portfolio.totalValue??''));setText(a?.portfolio.positions.map(p=>`${p.ticker} ${p.weightPct}`).join('\n')??'');setEditAllocation(false);setError(null);setInvalid(false);};
  const save=async()=>{if(tickerCheck.blocking)return;setError(null);setInvalid(false);let portfolio:unknown;
    if(editAllocation)try{if(!capital.trim()||!Number.isFinite(Number(capital))||Number(capital)<=0)throw new Error();portfolio={totalValue:Number(capital),positions:parseFinalTargets(text)};}catch{setInvalid(true);return;}
    setBusy(true);try{applyProfile(await getApiClient().editAccount(profile.profileId,id,{version:profile.version,name,...(editAllocation?{portfolio}:{})}));dropDraft(draftKey);}catch(e){setError(asApiError(e));}finally{setBusy(false);}
  };
  if(!feature('profile_creator')||!profile.accounts?.length)return null;
  return <Card title={tr({en:'Edit an account and modeled allocation',fr:'Modifier un compte et sa répartition modélisée'})}>
    <p className="small muted">{tr({en:'A label-only edit retains valuations. Editing reporting-currency capital or weights is an explicit modeled account replacement, not a transfer, contribution or real trade. Obsolete native and quantity receipts are retired into history. Use the transfer form when combined account value must be conserved.',fr:'Modifier seulement le libellé conserve les valorisations. Modifier le capital ou les poids remplace explicitement le compte modélisé, sans transfert, contribution ni opération réelle. Les anciens reçus de change et de quantité deviennent historiques. Utilisez le formulaire de transfert pour conserver la valeur totale.'})}</p>
    <form onSubmit={e=>{e.preventDefault();void save();}}><fieldset disabled={busy}>{restored&&<DraftRestoredNote/>}<div className="form-grid"><div className="field"><label htmlFor="account-edit-select">{tr({en:'Account to edit',fr:'Compte à modifier'})}</label><select id="account-edit-select" value={id} onChange={e=>choose(e.target.value)}>{profile.accounts.map(a=><option key={a.accountId} value={a.accountId}>{a.name}</option>)}</select></div><div className="field"><label htmlFor="account-edit-name">{tr({en:'Account label',fr:'Libellé du compte'})}</label><input id="account-edit-name" required maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></div></div>
      <label className="checks"><input type="checkbox" checked={editAllocation} onChange={e=>setEditAllocation(e.target.checked)}/> {tr({en:'Replace this account’s modeled capital/allocation',fr:'Remplacer le capital et la répartition modélisés de ce compte'})}</label>
      {editAllocation&&<><div className="field"><label htmlFor="account-edit-capital">{tr({en:'Reporting-currency modeled capital',fr:'Capital modélisé dans la devise de présentation'})} ({profile.reportingCurrency})</label><input id="account-edit-capital" required type="number" min={.01} step="any" value={capital} onChange={e=>setCapital(e.target.value)}/></div><div className="field"><label htmlFor="account-edit-targets">{tr({en:'Complete final weights: TICKER PERCENT per line',fr:'Poids finaux complets : SYMBOLE POURCENTAGE par ligne'})}</label><textarea id="account-edit-targets" required rows={6} value={text} onChange={e=>setText(e.target.value)} aria-invalid={tickerCheck.blocking} aria-describedby={`${tickerCheck.message?'account-edit-targets-issue ':''}account-edit-targets-universe`}/>
        {tickerCheck.message&&<span id="account-edit-targets-issue" className={tickerCheck.blocking?'field-error':'hint'}>{tr(tickerCheck.message)}</span>}
        <SupportedUniverse id="account-edit-targets-universe"/></div></>}
      <button className="btn" type="submit" disabled={tickerCheck.blocking}>{tr({en:'Save account edit',fr:'Enregistrer la modification du compte'})}</button></fieldset></form>{invalid&&<p role="alert">{tr({en:'Use positive finite capital and unique supported final weights totaling 100%.',fr:'Utilisez un capital positif fini et des poids finaux uniques totalisant 100 %.'})}</p>}{error&&<ProfileWriteError error={error} onReload={()=>stashDraft(draftKey,profile.version,{id,name,editAllocation,capital,text} satisfies AccountEditDraft)}/>}
  </Card>;
}
