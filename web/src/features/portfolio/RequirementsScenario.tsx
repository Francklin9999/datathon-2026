'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtMoney } from '../../lib/format';
import { labelOf } from '../../lib/labels';
import { REQUIREMENT_STATE } from './portfolioLabels';

export function RequirementsScenario({ profile }: { profile: Profile }) {
  const { tr, lang } = useApp();
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [capital, setCapital] = useState('');
  const [rate, setRate] = useState('');
  const [flows, setFlows] = useState('');
  const [result, setResult] = useState<Awaited<ReturnType<ReturnType<typeof getApiClient>['requirementsScenario']>> | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const clear = () => { setResult(null); setInvalid(false); };
  const calculate = async () => {
    const cashflows = [];
    for (const line of flows.split('\n').map(x => x.trim()).filter(Boolean)) {
      const [date, amount, extra] = line.split(/\s+/);
      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || amount === undefined || !Number.isFinite(Number(amount)) || extra) { setInvalid(true); return; }
      cashflows.push({ date, amount: Number(amount) });
    }
    setBusy(true); setError(null); clear();
    try { setResult(await getApiClient().requirementsScenario(profile.profileId, { asOf: start, through: end, liquidCapital: Number(capital), annualReturnPct: Number(rate), cashflows })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Spending and liquidity scenario', fr: 'Scénario de dépenses et de liquidité' })}>
    <p>{tr({ en: 'Use the requirements entered in Profiles. Supply available liquid capital separately from total wealth and state the return assumption. Spending and liabilities consume cash; liquidity requirements reserve a minimum balance. Empty cash flows explicitly assume no additional flows. This nominal scenario does not establish investment or tax advice.', fr: 'Utilisez les besoins saisis dans Profils. Indiquez le capital liquide disponible séparément du patrimoine total et le rendement supposé. Dépenses et passifs consomment le capital; les besoins de liquidité imposent un solde minimum. Des flux vides supposent explicitement aucun flux supplémentaire. Ce scénario nominal ne constitue pas un conseil financier ou fiscal.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void calculate(); }}><fieldset disabled={busy}><div className="form-grid">
      <div className="field"><label htmlFor="requirements-start">{tr({ en: 'Scenario start', fr: 'Début du scénario' })}</label><input id="requirements-start" type="date" required value={start} onChange={e => { setStart(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="requirements-end">{tr({ en: 'Scenario end', fr: 'Fin du scénario' })}</label><input id="requirements-end" type="date" required value={end} onChange={e => { setEnd(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="requirements-capital">{tr({ en: 'Available liquid capital', fr: 'Capital liquide disponible' })} ({profile.reportingCurrency})</label><input id="requirements-capital" type="number" min={0} required step="any" value={capital} onChange={e => { setCapital(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="requirements-rate">{tr({ en: 'Assumed annual return (%)', fr: 'Rendement annuel supposé (%)' })}</label><input id="requirements-rate" type="number" min={-99.99} max={100} required step="any" value={rate} onChange={e => { setRate(e.target.value); clear(); }} /></div>
      <div className="field"><label htmlFor="requirements-flows">{tr({ en: 'Additional cash flows: DATE SIGNED_AMOUNT per line', fr: 'Flux supplémentaires : DATE MONTANT_SIGNÉ par ligne' })}</label><textarea id="requirements-flows" rows={4} maxLength={20000} value={flows} onChange={e => { setFlows(e.target.value); clear(); }} /><p className="small muted">{tr({ en: 'Example format: 2027-01-31 500. Positive adds liquid capital; negative withdraws. Do not duplicate spending already in the requirements.', fr: 'Format : 2027-01-31 500. Positif ajoute du capital; négatif retire. Ne dupliquez pas les dépenses déjà saisies.' })}</p></div>
    </div><button className="btn" type="submit">{tr({ en: 'Calculate entered requirements', fr: 'Calculer les besoins saisis' })}</button></fieldset></form>
    {invalid && <p role="alert">{tr({ en: 'Each cash-flow line needs an ISO date and finite signed amount.', fr: 'Chaque flux exige une date ISO et un montant signé fini.' })}</p>}{error && <ErrorState error={error} />}
    {result && <div role="status"><p><strong>{labelOf(REQUIREMENT_STATE, result.state, lang)}</strong> · {result.currency}</p>{!!result.missingInputs.length && <p>{tr({ en: 'Missing inputs', fr: 'Entrées manquantes' })}: {result.missingInputs.join('; ')}</p>}{result.endingValue !== null && <p>{tr({ en: 'Modeled ending liquid value', fr: 'Valeur liquide finale modélisée' })}: {fmtMoney(result.endingValue, result.currency, lang)}</p>}{result.shortfallDate && <p>{tr({ en: 'First shortfall', fr: 'Premier déficit' })}: {result.shortfallDate} · {fmtMoney(result.shortfall ?? 0, result.currency, lang)}</p>}
      {!!result.events.length && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Requirement scenario events', fr: 'Événements du scénario' })}><table><thead><tr><th>Date</th><th>{tr({ en: 'Requirements', fr: 'Besoins' })}</th><th>{tr({ en: 'Liquid balance', fr: 'Solde liquide' })}</th><th>{tr({ en: 'Minimum reserve', fr: 'Réserve minimale' })}</th></tr></thead><tbody>{result.events.map((event, i) => <tr key={i}><td>{event.date}</td><td>{event.requirements.join(', ')}</td><td>{fmtMoney(event.balance, result.currency, lang)}</td><td>{fmtMoney(event.reserve, result.currency, lang)}</td></tr>)}</tbody></table></div>}
      {result.assumptions.map(a => <p className="small muted" key={a}>{a}</p>)}
    </div>}
  </Card>;
}
