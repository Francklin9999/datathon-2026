'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { numeric, record, scalar, type ModelResult } from '../../api/expandedInvestor';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtMoney } from '../../lib/format';
import { ModelResultView, ResultRows } from './ModelResult';

export function JointPlan({ profile }: { profile: Profile }) {
  const { tr, lang } = useApp();
  const [asOf, setAsOf] = useState('');
  const [through, setThrough] = useState('');
  const [rate, setRate] = useState('');
  const [inflation, setInflation] = useState('');
  const [basis, setBasis] = useState('nominal');
  const [aggregation, setAggregation] = useState('independent');
  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [outside, setOutside] = useState('');
  const [outsideDescription, setOutsideDescription] = useState('');
  const [outsideAdditional, setOutsideAdditional] = useState(false);
  const [flows, setFlows] = useState('');
  const goals = profile.investorContext?.objectives ?? [];
  const requirements = profile.investorContext?.requirements ?? [];
  const [goalSelection, setGoalSelection] = useState(goals.map((_, i) => i));
  const [requirementSelection, setRequirementSelection] = useState(requirements.map((_, i) => i));
  const [result, setResult] = useState<ModelResult | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const sources = profile.accounts?.length ? profile.accounts.flatMap(a => [
    { kind: 'account', id: a.accountId, name: a.name, value: a.portfolio.totalValue },
    ...(a.privateAssets ?? []).map(p => ({ kind: 'private_asset', id: p.assetId, name: `${a.name} · ${p.name} (${p.valuation.valuationDate})`, value: p.valuation.conversion.reportingValue })),
  ]) : [{ kind: 'portfolio', id: 'active', name: tr({ en: 'Active traded portfolio', fr: 'Portefeuille coté actif' }), value: profile.portfolio.totalValue }];
  const clear = () => { setResult(null); setInvalid(false); setError(null); };
  const calculate = async () => {
    clear();
    const cashflows = [];
    for (const line of flows.split('\n').map(s => s.trim()).filter(Boolean)) {
      const [date, amount, extra] = line.split(/\s+/);
      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || amount === undefined || !Number.isFinite(Number(amount)) || extra) { setInvalid(true); return; }
      cashflows.push({ date, amount: Number(amount), origin: 'user' });
    }
    const capitalSources = sources.filter(s => (amounts[s.id] ?? '').trim() !== '').map(s => ({ kind: s.kind, id: s.id, amount: Number(amounts[s.id]), origin: 'user', sourceDescription: 'User-selected available liquid portion of the saved reporting-currency value' }));
    if (outside.trim()) capitalSources.push({ kind: 'outside', id: 'outside-1', amount: Number(outside), origin: 'user', sourceDescription: outsideDescription });
    setBusy(true);
    try { setResult(await getApiClient().jointPlan(profile.profileId, { profileVersion: profile.version, asOf, through,
      annualReturnPct: Number(rate), annualInflationPct: Number(inflation), amountBasis: basis,
      capitalSources, outsideIsAdditional: outsideAdditional, cashflows,
      goalIndexes: goalSelection, requirementIndexes: requirementSelection,
      liquidityAggregation: aggregation, allocationTreatment: 'shared_pool' })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  const money = (key: string) => { const n = result ? numeric(result[key]) : null; return n === null ? '—' : fmtMoney(n, profile.reportingCurrency, lang); };
  return <Card title={tr({ en: 'Joint goals, spending and liquidity plan', fr: 'Plan conjoint des objectifs, dépenses et liquidités' })}>
    <p>{tr({ en: 'Evaluate selected goals and obligations together against one shared pool. Enter the portion actually available for spending from each saved account or appraisal. The same capital cannot be entered twice. Private appraisals are not assumed liquid. One global cash-flow schedule replaces separate goal-sleeve contributions in this calculation.', fr: 'Évaluez les objectifs et obligations sélectionnés avec une réserve commune. Indiquez la part disponible de chaque compte ou évaluation. Un même capital ne peut être compté deux fois. Les actifs privés ne sont pas supposés liquides. Un calendrier global remplace les contributions séparées par objectif.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void calculate(); }}><fieldset disabled={busy}><div className="form-grid">
      <div className="field"><label htmlFor="joint-start">{tr({ en: 'Plan start', fr: 'Début du plan' })}</label><input id="joint-start" type="date" required value={asOf} onChange={e => { setAsOf(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="joint-through">{tr({ en: 'Plan through', fr: 'Fin du plan' })}</label><input id="joint-through" type="date" required value={through} onChange={e => { setThrough(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="joint-return">{tr({ en: 'Assumed annual effective return (%)', fr: 'Rendement annuel effectif supposé (%)' })}</label><input id="joint-return" type="number" step="any" min={-99.99} max={100} required value={rate} onChange={e => { setRate(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="joint-inflation">{tr({ en: 'Assumed annual inflation (%)', fr: 'Inflation annuelle supposée (%)' })}</label><input id="joint-inflation" type="number" step="any" min={-99.99} max={100} required value={inflation} onChange={e => { setInflation(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="joint-basis">{tr({ en: 'Entered amount basis', fr: 'Base des montants saisis' })}</label><select id="joint-basis" value={basis} onChange={e => { setBasis(e.target.value); clear(); }}><option value="nominal">{tr({ en: 'Nominal at each due date', fr: 'Nominal à chaque échéance' })}</option><option value="as_of_real">{tr({ en: 'Purchasing power at plan start', fr: 'Pouvoir d’achat au début du plan' })}</option></select></div>
      <div className="field"><label htmlFor="joint-reserves">{tr({ en: 'Simultaneous liquidity reserves', fr: 'Réserves de liquidité simultanées' })}</label><select id="joint-reserves" value={aggregation} onChange={e => { setAggregation(e.target.value); clear(); }}><option value="independent">{tr({ en: 'Independent: add all reserves', fr: 'Indépendantes : additionner les réserves' })}</option><option value="overlapping">{tr({ en: 'Overlapping: maximum reserve', fr: 'Chevauchantes : réserve maximale' })}</option></select></div>
    </div>
    <fieldset><legend>{tr({ en: 'Explicit available liquid capital', fr: 'Capital liquide disponible explicite' })} · {profile.reportingCurrency}</legend><p className="small muted">{tr({ en: 'Leave blank to exclude a source. Enter zero explicitly if none of its value is available.', fr: 'Laissez vide pour exclure une source. Saisissez zéro si aucune partie n’est disponible.' })}</p><div className="form-grid">{sources.map(source => <div className="field" key={source.id}><label htmlFor={`joint-capital-${source.id}`}>{source.name} · {tr({ en: 'recorded limit', fr: 'limite enregistrée' })} {fmtMoney(source.value, profile.reportingCurrency, lang)}</label><input id={`joint-capital-${source.id}`} type="number" min={0} max={source.value} step="any" value={amounts[source.id] ?? ''} onChange={e => { setAmounts(a => ({ ...a, [source.id]: e.target.value })); clear(); }} /></div>)}</div>
      <div className="form-grid"><div className="field"><label htmlFor="joint-outside">{tr({ en: 'Additional outside capital (optional)', fr: 'Capital externe supplémentaire (facultatif)' })}</label><input id="joint-outside" type="number" min={0} step="any" value={outside} onChange={e => { setOutside(e.target.value); clear(); }} /></div><div className="field"><label htmlFor="joint-outside-source">{tr({ en: 'Outside capital source', fr: 'Source du capital externe' })}</label><input id="joint-outside-source" required={!!outside.trim()} maxLength={1000} value={outsideDescription} onChange={e => { setOutsideDescription(e.target.value); clear(); }} /></div></div>
      <label><input type="checkbox" checked={outsideAdditional} onChange={e => { setOutsideAdditional(e.target.checked); clear(); }} /> {tr({ en: 'Any outside capital is additional and is not included in another selected source.', fr: 'Le capital externe est supplémentaire et n’est inclus dans aucune autre source sélectionnée.' })}</label>
    </fieldset>
    <fieldset><legend>{tr({ en: 'Selected goals', fr: 'Objectifs sélectionnés' })}</legend>{goals.length === 0 && <p>{tr({ en: 'No entered goals. Add them in Profiles.', fr: 'Aucun objectif saisi. Ajoutez-en dans Profils.' })}</p>}{goals.map((goal, i) => <label className="checks" key={i}><input type="checkbox" checked={goalSelection.includes(i)} onChange={e => { setGoalSelection(s => e.target.checked ? [...s, i] : s.filter(j => j !== i)); clear(); }} /> {goal.name} · {tr({ en: 'priority', fr: 'priorité' })} {goal.priority} · {goal.deadline ?? goal.endDate ?? `${goal.horizonYears}y`} · {goal.origin ?? 'unknown'}</label>)}</fieldset>
    <fieldset><legend>{tr({ en: 'Selected spending, liabilities and reserves', fr: 'Dépenses, passifs et réserves sélectionnés' })}</legend>{requirements.length === 0 && <p>{tr({ en: 'No entered requirements; none will be inferred.', fr: 'Aucun besoin saisi; aucun ne sera déduit.' })}</p>}{requirements.map((r, i) => <label className="checks" key={i}><input type="checkbox" checked={requirementSelection.includes(i)} onChange={e => { setRequirementSelection(s => e.target.checked ? [...s, i] : s.filter(j => j !== i)); clear(); }} /> {r.name} · {r.kind} · {fmtMoney(r.amount, profile.reportingCurrency, lang)} · {r.dueDate ?? tr({ en: 'date unknown', fr: 'date inconnue' })}</label>)}</fieldset>
    <div className="field"><label htmlFor="joint-flows">{tr({ en: 'Shared external cash flows: DATE SIGNED_AMOUNT per line', fr: 'Flux externes communs : DATE MONTANT_SIGNÉ par ligne' })}</label><textarea id="joint-flows" rows={4} maxLength={20000} value={flows} onChange={e => { setFlows(e.target.value); clear(); }} /><p className="small muted">{tr({ en: 'Positive adds capital; negative withdraws. Blank explicitly assumes no additional cash flows. Do not repeat saved spending or goal contributions.', fr: 'Positif ajoute du capital; négatif retire. Vide suppose explicitement aucun flux supplémentaire. Ne répétez pas les dépenses ou contributions par objectif.' })}</p></div>
    <button className="btn" type="submit">{tr({ en: 'Calculate shared plan and priority alternative', fr: 'Calculer le plan commun et la variante prioritaire' })}</button></fieldset></form>
    {invalid && <p role="alert">{tr({ en: 'Cash flows need an ISO date and a finite signed amount on every line.', fr: 'Chaque flux exige une date ISO et un montant signé fini.' })}</p>}{error && <ErrorState error={error} />}
    {result && <><p><strong>{scalar(result.state).replaceAll('_', ' ')}</strong> · {profile.reportingCurrency}</p><dl className="kv-list">{[['capital',tr({ en: 'Selected shared capital', fr: 'Capital commun sélectionné' })],['requiredInitialCapital',tr({ en: 'Required initial capital under these assumptions', fr: 'Capital initial requis selon ces hypothèses' })],['additionalInitialCapital',tr({ en: 'Additional initial capital required', fr: 'Capital initial supplémentaire requis' })],['endingLiquidValue',tr({ en: 'Ending liquid value', fr: 'Valeur liquide finale' })]].map(([key,label]) => <div className="kv" key={key}><dt>{label}</dt><dd>{money(key!)}</dd></div>)}</dl>
      <ResultRows value={result.goals} label={tr({ en: 'Dated goal outcomes', fr: 'Résultats datés des objectifs' })} columns={[{key:'name',label:tr({ en:'Goal',fr:'Objectif' })},{key:'dueDate',label:tr({en:'Due date',fr:'Échéance'})},{key:'targetAtDue',label:`${tr({en:'Target',fr:'Cible'})} (${profile.reportingCurrency})`},{key:'state',label:tr({en:'State',fr:'État'})}]} />
      <h3>{tr({ en: 'Priority alternative preserving essential obligations', fr: 'Variante prioritaire préservant les obligations essentielles' })}</h3><p>{scalar(record(result.priorityPlan).state).replaceAll('_',' ')}</p><ResultRows value={record(result.priorityPlan).goals} label={tr({ en: 'Priority scenario allocation', fr: 'Répartition du scénario prioritaire' })} columns={[{key:'name',label:tr({en:'Goal',fr:'Objectif'})},{key:'priority',label:tr({en:'Priority',fr:'Priorité'})},{key:'paid',label:`${tr({en:'Funded amount',fr:'Montant financé'})} (${profile.reportingCurrency})`},{key:'shortfall',label:`${tr({en:'Shortfall',fr:'Déficit'})} (${profile.reportingCurrency})`}]} />
      <ResultRows value={result.events} label={tr({ en: 'Shared dated cash ledger', fr: 'Registre daté commun' })} columns={[{key:'date',label:'Date'},{key:'openingValue',label:tr({en:'Opening balance',fr:'Solde initial'})},{key:'externalFlow',label:tr({en:'External flow',fr:'Flux externe'})},{key:'closingValue',label:tr({en:'Ending balance',fr:'Solde final'})},{key:'shortfall',label:tr({en:'Shortfall',fr:'Déficit'})}]} /><ModelResultView value={result} /></>}
  </Card>;
}
