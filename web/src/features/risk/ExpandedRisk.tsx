'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { numeric, record, scalar, texts, type ModelResult } from '../../api/expandedInvestor';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtMoney, fmtNumber } from '../../lib/format';
import { ModelResultView, ResultRows } from '../planning/ModelResult';
import { parseModelInput } from '../../api/investorModels';

export function Covariance({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec } = useApp();
  const [result, setResult] = useState<ModelResult | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const calculate = async () => { setBusy(true); setError(null); try { setResult(await getApiClient().covariance({ profileId: profile.profileId, version: profile.version, window: windowSpec })); } catch(e) { setError(asApiError(e)); } finally { setBusy(false); } };
  const matrix = Array.isArray(result?.dailyCovariance) ? result.dailyCovariance : [];
  const tickers = texts(result?.tickers);
  return <Card title={tr({ en: 'Aligned sample covariance', fr: 'Covariance de l’échantillon aligné' })}>
    <p className="small muted">{tr({ en: 'Daily simple-return covariance with sample denominator n−1. Rows share exactly the same price/FX return calendar; missing prices are never filled. Units are squared fractional daily returns, without annualization.', fr: 'Covariance des rendements simples journaliers avec dénominateur n−1. Même calendrier de prix et de change; aucun prix manquant n’est comblé. Unités : carré des fractions journalières, sans annualisation.' })}</p><button className="btn ghost" type="button" disabled={busy} onClick={() => void calculate()}>{tr({ en: 'Calculate covariance', fr: 'Calculer la covariance' })}</button>
    {error && <ErrorState error={error} />}{result && <>{!!matrix.length && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Covariance matrix', fr: 'Matrice de covariance' })}><table><thead><tr><th>{tr({ en: 'Holding', fr: 'Position' })}</th>{tickers.map(t => <th key={t}>{t}</th>)}</tr></thead><tbody>{matrix.map((row, i) => <tr key={i}><th scope="row">{tickers[i]}</th>{(Array.isArray(row) ? row : []).map((v, j) => <td key={j}>{numeric(v) === null ? '—' : fmtNumber(numeric(v)!, lang, 8)}</td>)}</tr>)}</tbody></table></div>}<p className="small muted">{scalar(record(result.sample).start)} — {scalar(record(result.sample).end)} · n={scalar(record(result.sample).returnObservations)}</p><ModelResultView value={result} /></>}
  </Card>;
}

type LiquidityRow = { dates: string; capacity: string; spread: string; impact: string; source: string };
export function Liquidity({ profile }: { profile: Profile }) {
  const { tr, lang } = useApp();
  const [asOf, setAsOf] = useState(''); const [through, setThrough] = useState(''); const [target, setTarget] = useState('');
  const [inputs, setInputs] = useState<Record<string, LiquidityRow>>({});
  const [result, setResult] = useState<ModelResult | null>(null); const [error, setError] = useState<ApiRequestError | null>(null); const [invalid, setInvalid] = useState(false); const [busy, setBusy] = useState(false);
  const clear = () => { setResult(null); setError(null); setInvalid(false); };
  const update = (ticker: string, key: keyof LiquidityRow, value: string) => { setInputs(s => ({ ...s, [ticker]: { dates:'',capacity:'',spread:'',impact:'',source:'', ...s[ticker], [key]: value } })); clear(); };
  const calculate = async () => {
    clear(); const assumptions = [];
    for (const [ticker, row] of Object.entries(inputs)) {
      if (!Object.values(row).some(s => s.trim())) continue;
      const saleDates = row.dates.split(/[\s,]+/).filter(Boolean);
      if (!saleDates.length || saleDates.some(s => !/^\d{4}-\d{2}-\d{2}$/.test(s)) || !row.source.trim() || [row.capacity,row.spread,row.impact].some(s => !s.trim() || !Number.isFinite(Number(s)))) { setInvalid(true); return; }
      assumptions.push({ ticker, saleDates, dailyCapacity:Number(row.capacity), halfSpreadBps:Number(row.spread), impactBps:Number(row.impact),source:row.source,asOf });
    }
    setBusy(true); try { setResult(await getApiClient().liquidityAnalysis(profile.profileId,{ version:profile.version,asOf,through,targetWithdrawal:target.trim()?Number(target):null,assumptions })); } catch(e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en:'Sale timing and liquidity scenario',fr:'Scénario de calendrier de vente et de liquidité' })}>
    <p>{tr({en:'Supply permitted sale dates, maximum gross value per date, half-spread and fixed impact costs for each modeled holding. Blank holdings remain unknown. No market liquidity, redemption date or sale of private appraisals is inferred. Net proceeds = gross × [1 − (half-spread + impact)/10,000].',fr:'Indiquez les dates de vente permises, la capacité brute par date, la demi-fourchette et l’impact fixe pour chaque position. Les positions vides restent inconnues. Aucune liquidité, date de rachat ou vente d’actif privé n’est déduite. Produit net = brut × [1 − (demi-fourchette + impact)/10 000].'})}</p>
    <form onSubmit={e=>{e.preventDefault();void calculate();}}><fieldset disabled={busy}><div className="form-grid"><div className="field"><label htmlFor="liquidity-start">{tr({en:'Scenario start / input date',fr:'Début du scénario / date des entrées'})}</label><input id="liquidity-start" required type="date" value={asOf} onChange={e=>{setAsOf(e.target.value);clear();}} /></div><div className="field"><label htmlFor="liquidity-end">{tr({en:'Scenario end',fr:'Fin du scénario'})}</label><input id="liquidity-end" required type="date" value={through} onChange={e=>{setThrough(e.target.value);clear();}} /></div><div className="field"><label htmlFor="liquidity-target">{tr({en:'Required withdrawal (optional)',fr:'Retrait requis (facultatif)'})} · {profile.reportingCurrency}</label><input id="liquidity-target" type="number" min={0} step="any" value={target} onChange={e=>{setTarget(e.target.value);clear();}} /></div></div>
      {profile.portfolio.positions.map(p=><fieldset key={p.ticker}><legend>{p.ticker} · {fmtMoney(profile.portfolio.totalValue*p.weightPct/100,profile.reportingCurrency,lang)}</legend><div className="form-grid">{([
        ['dates',tr({en:'Allowed sale dates, comma separated',fr:'Dates de vente permises, séparées par virgules'}),'text'],['capacity',`${tr({en:'Gross capacity per date',fr:'Capacité brute par date'})} (${profile.reportingCurrency})`,'number'],['spread',tr({en:'Half-spread (basis points)',fr:'Demi-fourchette (points de base)'}),'number'],['impact',tr({en:'Fixed impact (basis points)',fr:'Impact fixe (points de base)'}),'number'],['source',tr({en:'Source or explicit assumption',fr:'Source ou hypothèse explicite'}),'text'],
      ] as const).map(([key,label,type])=><div className="field" key={key}><label htmlFor={`liquidity-${p.ticker}-${key}`}>{label}</label><input id={`liquidity-${p.ticker}-${key}`} type={type} {...(type==='number'?{min:0,step:'any'}:{maxLength:1000})} value={inputs[p.ticker]?.[key]??''} onChange={e=>update(p.ticker,key,e.target.value)} /></div>)}</div></fieldset>)}
      <button className="btn" type="submit">{tr({en:'Calculate permitted sale scenario',fr:'Calculer le scénario de vente permis'})}</button></fieldset></form>{invalid&&<p role="alert">{tr({en:'For each included holding provide valid ISO dates, finite capacity/cost values and a source. Enter zero costs explicitly when assumed.',fr:'Pour chaque position incluse, indiquez des dates ISO valides, une capacité et des coûts finis, ainsi qu’une source. Saisissez explicitement zéro si aucun coût n’est supposé.'})}</p>}{error&&<ErrorState error={error}/>}
    {result&&<><p>{tr({en:'Known net proceeds',fr:'Produit net connu'})}: {fmtMoney(numeric(result.knownNetProceeds)??0,profile.reportingCurrency,lang)} · {tr({en:'Whole-portfolio total',fr:'Total de tout le portefeuille'})}: {numeric(result.totalNetProceeds)===null?tr({en:'Unknown',fr:'Inconnu'}):fmtMoney(numeric(result.totalNetProceeds)!,profile.reportingCurrency,lang)}</p><ResultRows value={result.holdings} label={tr({en:'Modeled sale outcomes',fr:'Résultats des ventes modélisées'})} columns={[{key:'ticker',label:tr({en:'Holding',fr:'Position'})},{key:'status',label:tr({en:'State',fr:'État'})},{key:'grossSale',label:tr({en:'Gross sale',fr:'Vente brute'})},{key:'netSale',label:tr({en:'Net proceeds',fr:'Produit net'})},{key:'remainingValue',label:tr({en:'Remaining value',fr:'Valeur restante'})}]} /><ModelResultView value={result}/></>}
  </Card>;
}

export function ActiveFactor({ profile }: { profile: Profile }) {
  const { tr, windowSpec } = useApp();
  const [input, setInput] = useState(''); const [capture, setCapture] = useState(''); const [names, setNames] = useState('market_excess, size, value');
  const [result,setResult]=useState<ModelResult|null>(null);const [error,setError]=useState<ApiRequestError|null>(null);const [invalid,setInvalid]=useState(false);const [busy,setBusy]=useState(false);
  const clear=()=>{setResult(null);setError(null);setInvalid(false);};
  const calculate=async()=>{clear();let supplied:Record<string,unknown>;
    try { supplied=capture.trim()?{captureId:capture.trim(),names:names.split(',').map(n=>n.trim()).filter(Boolean)}:parseModelInput(input); } catch{setInvalid(true);return;}
    setBusy(true);try{setResult(await getApiClient().activeFactorExposure(profile.profileId,{...supplied,version:profile.version,window:windowSpec}));}catch(e){setError(asApiError(e));}finally{setBusy(false);}
  };
  const betas=record(result?.betas);
  return <Card title={tr({en:'Factor exposure of the active portfolio',fr:'Exposition factorielle du portefeuille actif'})}>
    <p>{tr({en:'Portfolio returns are calculated from the actual active holdings, selected window, adjusted prices and reporting-currency FX. Supply exactly aligned factor returns in the same currency, or the ID of a permitted session-owned French factor capture. A captured US factor sample requires a USD-reporting profile. No security matching, currency conversion of factor portfolios or source permission is inferred.',fr:'Les rendements du portefeuille sont calculés à partir des positions actives, de la fenêtre sélectionnée, des prix ajustés et du change. Fournissez des facteurs exactement alignés dans la même devise ou l’identifiant d’une capture French autorisée de cette session. Les facteurs américains capturés exigent un profil en USD. Aucune correspondance de titres, conversion de facteurs ou permission source n’est déduite.'})}</p>
    <form onSubmit={e=>{e.preventDefault();void calculate();}}><fieldset disabled={busy}><div className="form-grid"><div className="field"><label htmlFor="active-factor-capture">{tr({en:'Permitted captured factor ID (optional)',fr:'Identifiant de capture autorisée (facultatif)'})}</label><input id="active-factor-capture" maxLength={72} value={capture} onChange={e=>{setCapture(e.target.value);clear();}} /></div>{capture.trim()&&<div className="field"><label htmlFor="active-factor-names">{tr({en:'Captured factor names',fr:'Noms des facteurs capturés'})}</label><input id="active-factor-names" value={names} onChange={e=>{setNames(e.target.value);clear();}} /></div>}</div>
      {!capture.trim()&&<><details><summary>{tr({en:'Required same-currency factor JSON',fr:'JSON factoriel requis dans la même devise'})}</summary><p className="small">{tr({en:'Provide names, source {origin,description,currency,availableAt,evidence?}, and factors [{start,end,riskFree,factors:{factorName:fraction}}]. Origins are user/imported/source; source origin requires attributed evidence. All returns are decimal fractions. At least 30 exact non-overlapping return periods are needed. Do not include portfolio returns; they come from the active holdings.',fr:'Indiquez names, source {origin,description,currency,availableAt,evidence?} et factors [{start,end,riskFree,factors:{nom:fraction}}]. Origines : user/imported/source; source exige une preuve attribuée. Rendements en fractions décimales. Au moins 30 périodes identiques sans chevauchement. Les rendements du portefeuille proviennent automatiquement des positions actives.'})}</p></details><div className="field"><label htmlFor="active-factor-json">{tr({en:'Attributed factor observations',fr:'Observations factorielles attribuées'})} · {profile.reportingCurrency}</label><textarea id="active-factor-json" required rows={7} maxLength={240000} value={input} onChange={e=>{setInput(e.target.value);clear();}} /></div></>}
      <button type="submit" className="btn">{tr({en:'Calculate active-portfolio factors',fr:'Calculer les facteurs du portefeuille actif'})}</button></fieldset></form>
    {invalid&&<p role="alert">{tr({en:'Provide a valid bounded JSON object or captured factor ID.',fr:'Fournissez un objet JSON valide et borné ou un identifiant de capture.'})}</p>}{error&&<ErrorState error={error}/>}
    {result&&<><p>{scalar(result.firstStart)} — {scalar(result.lastEnd)} · n={scalar(result.observations)}</p><dl className="kv-list">{Object.entries(betas).map(([name,beta])=><div className="kv" key={name}><dt>{name} · β</dt><dd>{scalar(beta)}</dd></div>)}<div className="kv"><dt>α / {tr({en:'period',fr:'période'})}</dt><dd>{scalar(result.alphaPerPeriod)}</dd></div><div className="kv"><dt>R²</dt><dd>{scalar(result.rSquared)}</dd></div></dl><ModelResultView value={result}/></>}
  </Card>;
}

export function NestedFunds() {
  const {tr,lang}=useApp();const [input,setInput]=useState('');const [result,setResult]=useState<ModelResult|null>(null);const [error,setError]=useState<ApiRequestError|null>(null);const [invalid,setInvalid]=useState(false);const [busy,setBusy]=useState(false);
  const clear=()=>{setResult(null);setError(null);setInvalid(false);};
  const calculate=async()=>{clear();let body:Record<string,unknown>;try{body=parseModelInput(input);}catch{setInvalid(true);return;}setBusy(true);try{setResult(await getApiClient().nestedFundExposure(body));}catch(e){setError(asApiError(e));}finally{setBusy(false);}};
  const holdings=(key:string)=>Object.entries(record(result?.[key]));
  return <Card title={tr({en:'Nested fund exposure and unresolved holdings',fr:'Exposition aux fonds imbriqués et positions non résolues'})}>
    <p>{tr({en:'Decompose explicitly supplied fund-of-fund disclosures by exact ISIN, preserving partial weights and evidence dates. Declare known fund ISINs so a missing fund snapshot remains unresolved. Cycles, depth limits and unknown disclosures never become invented direct holdings. These inputs are separate from the active portfolio until a verified security crosswalk is attached.',fr:'Décomposez les compositions explicites de fonds de fonds par ISIN exact, en conservant les poids partiels et les dates de preuve. Déclarez les fonds connus pour qu’une composition manquante reste non résolue. Cycles, limites de profondeur et inconnues ne deviennent jamais des positions directes inventées. Ces données restent distinctes du portefeuille actif sans correspondance vérifiée.'})}</p>
    <details><summary>{tr({en:'Required JSON structure',fr:'Structure JSON requise'})}</summary><p className="small">asOf, historical, positions (ISIN → fraction), knownFunds (ISIN[]), maxDepth (1–8), snapshots ([fundIsin, holdingsDate, evidence, constituents]). {tr({en:'Each constituent has isin and weight. Evidence uses source_id, HTTPS url, content_sha256, available_at, retrieved_at and licence. At most 50 snapshots and 10,000 traversal nodes; unresolved weight is conserved.',fr:'Chaque composant a isin et weight. La preuve utilise source_id, url HTTPS, content_sha256, available_at, retrieved_at et licence. Au plus 50 compositions et 10 000 nœuds; le poids non résolu est conservé.'})}</p></details>
    <form onSubmit={e=>{e.preventDefault();void calculate();}}><fieldset disabled={busy}><div className="field"><label htmlFor="nested-fund-json">{tr({en:'Dated nested disclosure inputs',fr:'Compositions imbriquées datées'})}</label><textarea id="nested-fund-json" required rows={8} maxLength={240000} value={input} onChange={e=>{setInput(e.target.value);clear();}} /></div><button className="btn" type="submit">{tr({en:'Calculate nested fund exposure',fr:'Calculer l’exposition aux fonds imbriqués'})}</button></fieldset></form>{invalid&&<p role="alert">{tr({en:'Provide a valid JSON object.',fr:'Fournissez un objet JSON valide.'})}</p>}{error&&<ErrorState error={error}/>}
    {result&&<><p><strong>{tr({en:'Unresolved portfolio weight',fr:'Poids non résolu du portefeuille'})}: {fmtNumber((numeric(result.unresolvedWeight)??0)*100,lang,3)}%</strong></p>{(['direct','indirect','unresolvedByReason'] as const).map(key=><section key={key}><h3>{key==='direct'?tr({en:'Direct holdings',fr:'Positions directes'}):key==='indirect'?tr({en:'Indirect holdings',fr:'Positions indirectes'}):tr({en:'Unresolved reasons',fr:'Causes de non-résolution'})}</h3><dl className="kv-list">{holdings(key).map(([name,value])=><div className="kv" key={name}><dt>{name}</dt><dd>{fmtNumber((numeric(value)??0)*100,lang,3)}%</dd></div>)}</dl></section>)}<ModelResultView value={result}/></>}
  </Card>;
}
