'use client';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
type Context = NonNullable<Profile['investorContext']>;
type Target = NonNullable<Context['targetAllocations']>[number];
const origins = ['user', 'imported', 'system_default', 'assumption'] as const;

export function AllocationInputs({ value, onChange }: { value: Profile['investorContext']; onChange: (value: Context) => void }) {
  const { tr } = useApp();
  const context = value ?? {};
  const targets = context.targetAllocations ?? [];
  const patch = (next: Partial<Context>) => onChange({ ...context, ...next });
  const update = (i: number, next: Partial<Target>) => patch({ targetAllocations: targets.map((t, j) => i === j ? { ...t, ...next } : t) });
  const rebalance = context.rebalancing ?? { frequency: 'none', customDescription: '', driftThresholdPct: null, origin: 'user' };
  return <fieldset style={{ marginTop: 16 }}><legend>{tr({ en: 'Allocation targets and rebalancing preferences', fr: 'Cibles de répartition et préférences de rééquilibrage' })}</legend>
    <p className="small muted">{tr({ en: 'Targets are compared with current traded weights and the explicit drift threshold. Rebalancing remains a hypothetical decision, with no automatic trades. Listing country and quotation currency are proxies; themes may overlap. Targets within a disjoint dimension must not exceed 100%.', fr: 'Les cibles sont comparées aux poids cotés actuels avec le seuil de dérive explicite. Le rééquilibrage reste hypothétique, sans opération automatique. Pays et devise de cotation sont des approximations; les thèmes peuvent se chevaucher. Les cibles disjointes ne doivent pas dépasser 100 %.' })}</p>
    {targets.map((t, i) => <fieldset key={i}><legend>{tr({ en: 'Target', fr: 'Cible' })} {i + 1}</legend><div className="form-grid">
      <div className="field"><label htmlFor={`target-dimension-${i}`}>{tr({ en: 'Dimension', fr: 'Dimension' })}</label><select id={`target-dimension-${i}`} value={t.dimension} onChange={e => update(i, { dimension: e.target.value as Target['dimension'] })}>{['position', 'sector', 'asset_class', 'country', 'currency', 'theme'].map(d => <option key={d} value={d}>{d.replaceAll('_', ' ')}</option>)}</select></div>
      <div className="field"><label htmlFor={`target-key-${i}`}>{tr({ en: 'Exact ticker, sector, class, ISO code or theme', fr: 'Symbole, secteur, catégorie, code ISO ou thème exact' })}</label><input id={`target-key-${i}`} maxLength={120} required value={t.key} onChange={e => update(i, { key: e.target.value })} /></div>
      <div className="field"><label htmlFor={`target-pct-${i}`}>{tr({ en: 'Target (%)', fr: 'Cible (%)' })}</label><input id={`target-pct-${i}`} type="number" min={0} max={100} required step="any" value={t.targetPct} onChange={e => update(i, { targetPct: Number(e.target.value) })} /></div>
      <div className="field"><label htmlFor={`target-origin-${i}`}>{tr({ en: 'Origin', fr: 'Origine' })}</label><select id={`target-origin-${i}`} value={t.origin ?? 'user'} onChange={e => update(i, { origin: e.target.value as NonNullable<Target['origin']> })}>{origins.map(o => <option key={o} value={o}>{o}</option>)}</select></div>
    </div><button type="button" className="btn ghost btn-sm" onClick={() => patch({ targetAllocations: targets.filter((_, j) => j !== i) })}>{tr({ en: 'Remove target', fr: 'Retirer la cible' })}</button></fieldset>)}
    <button type="button" className="btn ghost" disabled={targets.length >= 100} onClick={() => patch({ targetAllocations: [...targets, { dimension: 'position', key: '', targetPct: 0, origin: 'user' }] })}>{tr({ en: 'Add allocation target', fr: 'Ajouter une cible' })}</button>
    <div className="form-grid">
      <div className="field"><label htmlFor="pf-rebalance-frequency">{tr({ en: 'Rebalancing review frequency', fr: 'Fréquence de révision' })}</label><select id="pf-rebalance-frequency" value={rebalance.frequency ?? 'none'} onChange={e => patch({ rebalancing: { ...rebalance, frequency: e.target.value as NonNullable<NonNullable<Context['rebalancing']>['frequency']> } })}>{['none', 'monthly', 'quarterly', 'semiannual', 'annual', 'custom'].map(f => <option key={f} value={f}>{f}</option>)}</select></div>
      <div className="field"><label htmlFor="pf-rebalance-drift">{tr({ en: 'Absolute drift threshold (percentage points, optional)', fr: 'Seuil de dérive absolue (points de pourcentage, facultatif)' })}</label><input id="pf-rebalance-drift" type="number" min={0} max={100} step="any" value={rebalance.driftThresholdPct ?? ''} onChange={e => patch({ rebalancing: { ...rebalance, driftThresholdPct: e.target.value === '' ? null : Number(e.target.value) } })} /></div>
      <div className="field"><label htmlFor="pf-rebalance-origin">{tr({ en: 'Preference origin', fr: 'Origine de la préférence' })}</label><select id="pf-rebalance-origin" value={rebalance.origin ?? 'user'} onChange={e => patch({ rebalancing: { ...rebalance, origin: e.target.value as NonNullable<NonNullable<Context['rebalancing']>['origin']> } })}>{origins.map(o => <option key={o} value={o}>{o}</option>)}</select></div>
      <div className="field"><label htmlFor="pf-rebalance-description">{tr({ en: 'Review instructions and assumptions', fr: 'Consignes et hypothèses de révision' })}</label><textarea id="pf-rebalance-description" maxLength={1000} value={rebalance.customDescription ?? ''} onChange={e => patch({ rebalancing: { ...rebalance, customDescription: e.target.value } })} /></div>
    </div>
    <div className="field"><label htmlFor="pf-custom-themes">{tr({ en: 'Custom themes (one per line; unverified context)', fr: 'Thèmes personnalisés (un par ligne; contexte non vérifié)' })}</label><textarea id="pf-custom-themes" value={(context.customThemes ?? []).join('\n')} onChange={e => patch({ customThemes: e.target.value.split('\n').map(t => t.trim()).filter(Boolean) })} /></div>
  </fieldset>;
}
