'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';

type Dimension = 'position' | 'sector' | 'asset_class' | 'country' | 'currency' | 'theme';
export function CustomPolicies({ profile }: { profile: Profile }) {
  const { tr, applyProfile } = useApp();
  const [dimension, setDimension] = useState<Dimension>('position');
  const [key, setKey] = useState('');
  const [operation, setOperation] = useState<'cap' | 'floor'>('cap');
  const [threshold, setThreshold] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().addCustomRule(profile.profileId, { dimension, key, operation, threshold: Number(threshold), version: profile.version })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Custom allocation conditions', fr: 'Conditions de répartition personnalisées' })}>
    <p className="small muted">{tr({ en: 'Typed user limits are evaluated by code in portfolio and decision checks. A floor sets a minimum; a cap sets a maximum. Country limits use ISO three-letter listing-country proxies; currency limits use quotation currency, with economic exposure and hedges unknown. These inputs are user policies, never official regulation.', fr: 'Les limites typées sont évaluées par code dans le portefeuille et les décisions. Un plancher définit un minimum; un plafond un maximum. Pays : code ISO à trois lettres du pays de cotation. Devise : devise de cotation, exposition économique et couverture inconnues. Ce sont des règles utilisateur, jamais une réglementation.' })}</p>
    {profile.isDefault ? <p>{tr({ en: 'Duplicate this seed profile to add custom rules.', fr: 'Dupliquez ce modèle pour ajouter des règles.' })}</p> : <form onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy}><div className="form-grid">
      <div className="field"><label htmlFor="custom-policy-dimension">{tr({ en: 'Dimension', fr: 'Dimension' })}</label><select id="custom-policy-dimension" value={dimension} onChange={e => { setDimension(e.target.value as Dimension); setKey(''); }}>{['position', 'sector', 'asset_class', 'country', 'currency', 'theme'].map(d => <option key={d} value={d}>{d.replaceAll('_', ' ')}</option>)}</select></div>
      <div className="field"><label htmlFor="custom-policy-key">{tr({ en: 'Exact ticker, sector, class, ISO code or theme', fr: 'Symbole, secteur, catégorie, code ISO ou thème exact' })}</label><input id="custom-policy-key" required maxLength={120} value={key} onChange={e => setKey(e.target.value)} /></div>
      <div className="field"><label htmlFor="custom-policy-operation">{tr({ en: 'Condition', fr: 'Condition' })}</label><select id="custom-policy-operation" value={operation} onChange={e => setOperation(e.target.value as typeof operation)}><option value="cap">≤ {tr({ en: 'Maximum', fr: 'Maximum' })}</option><option value="floor">≥ {tr({ en: 'Minimum', fr: 'Minimum' })}</option></select></div>
      <div className="field"><label htmlFor="custom-policy-threshold">{tr({ en: 'Weight threshold (%)', fr: 'Seuil de pondération (%)' })}</label><input id="custom-policy-threshold" required type="number" min={0} max={100} step="any" value={threshold} onChange={e => setThreshold(e.target.value)} /></div>
    </div><button className="btn" type="submit">{tr({ en: 'Save and evaluate condition', fr: 'Enregistrer et évaluer la condition' })}</button></fieldset></form>}
    {error && <ErrorState error={error} />}
  </Card>;
}
