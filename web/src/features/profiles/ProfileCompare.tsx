'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { FinancialComparison } from './FinancialComparison';
import { fmtMoney } from '../../lib/format';

/** Compare explicit saved inputs. No persona-based ranking or inferred suitability. */
export function ProfileCompare({ profiles }: { profiles: Profile[] }) {
  const { tr, lang } = useApp();
  const [left, setLeft] = useState(profiles[0]?.profileId ?? '');
  const [right, setRight] = useState(profiles[1]?.profileId ?? '');
  const a = profiles.find(p => p.profileId === left);
  const b = profiles.find(p => p.profileId === right);
  const rows: [string, (p: Profile) => string][] = [
    [tr({ en: 'Risk tolerance', fr: 'Tolérance au risque' }), p => p.riskLevel.replaceAll('_', ' ')],
    [tr({ en: 'Horizon (years)', fr: 'Horizon (années)' }), p => `${p.horizonYears.min} – ${p.horizonYears.max ?? '∞'}`],
    [tr({ en: 'Reporting currency', fr: 'Devise de présentation' }), p => p.reportingCurrency],
    [tr({ en: 'Modeled capital', fr: 'Capital modélisé' }), p => fmtMoney(p.portfolio.totalValue, p.reportingCurrency, lang)],
    [tr({ en: 'Country', fr: 'Pays' }), p => p.investorContext?.country ?? '—'],
    [tr({ en: 'Goals', fr: 'Objectifs' }), p => (p.investorContext?.objectives ?? []).map(g => `${g.name}: ${g.horizonYears}y`).join('; ') || '—'],
    [tr({ en: 'Holdings', fr: 'Positions' }), p => p.portfolio.positions.map(h => `${h.ticker} ${h.weightPct}%`).join('; ')],
    [tr({ en: 'Enabled policy limits', fr: 'Limites actives' }), p => p.rules.filter(r => r.enabled).map(r => `${r.ruleId}: ${r.threshold ?? '✓'} (${r.origin})`).join('; ')],
  ];
  return <Card title={tr({ en: 'Compare saved profiles', fr: 'Comparer les profils enregistrés' })}>
    <div className="form-grid">{([['compare-left', left, setLeft], ['compare-right', right, setRight]] as const).map(([id, value, set], i) => <div className="field" key={id}><label htmlFor={id}>{tr({ en: `Profile ${i + 1}`, fr: `Profil ${i + 1}` })}</label><select id={id} value={value} onChange={e => set(e.target.value)}><option value="">—</option>{profiles.map(p => <option key={p.profileId} value={p.profileId}>{p.name}</option>)}</select></div>)}</div>
    {a && b && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Profile input comparison', fr: 'Comparaison des entrées' })}><table><thead><tr><th>{tr({ en: 'Input', fr: 'Entrée' })}</th><th>{a.name} · v{a.version}</th><th>{b.name} · v{b.version}</th></tr></thead><tbody>{rows.map(([name, get]) => <tr key={name}><th scope="row">{name}</th><td>{get(a)}</td><td>{get(b)}</td></tr>)}</tbody></table></div>}
    {a && b && <FinancialComparison key={`${a.profileId}|${a.version}|${b.profileId}|${b.version}`} left={a} right={b} />}
    <p className="small muted">{tr({ en: 'Amounts retain their own currencies. This comparison does not convert capital or infer tax obligations, liabilities or goal feasibility.', fr: 'Chaque montant conserve sa devise. La comparaison ne convertit pas le capital et ne déduit ni fiscalité, ni passifs, ni faisabilité des objectifs.' })}</p>
  </Card>;
}
