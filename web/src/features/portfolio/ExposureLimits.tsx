'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { ProxyNote } from '../../components/common/Note';
import { ProfileWriteError } from '../../components/common/States';

export function ExposureLimits({ profile }: { profile: Profile }) {
  const { tr, applyProfile, feature } = useApp();
  const [dimension, setDimension] = useState<'country' | 'currency'>('currency');
  const [key, setKey] = useState('USD');
  const [threshold, setThreshold] = useState('50');
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  // This form only adds limits (a profile_creator write); saved limits are profile rules, read by the Rules card.
  // It renders inside the Add a rule card, which handles default profiles.
  if (!feature('profile_creator')) return null;
  const save = async () => { setBusy(true); setError(null); try {
    applyProfile(await getApiClient().addExposureLimit(profile.profileId, dimension, key, Number(threshold), profile.version));
  } catch (e) { setError(asApiError(e)); } finally { setBusy(false); } };
  return <div className="add-rule-form">
    <p className="small muted">{tr({ en: 'Set the most this portfolio may hold in one quote currency or listing country.', fr: 'Fixez le maximum que ce portefeuille peut détenir dans une devise de cotation ou un pays de cotation.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void save(); }}><div className="form-grid">
      <div className="field"><label htmlFor="limit-dimension">{tr({ en: 'Measure by', fr: 'Mesurer par' })}</label><select id="limit-dimension" value={dimension} onChange={e => { setDimension(e.target.value as 'country' | 'currency'); setKey(e.target.value === 'country' ? 'USA' : 'USD'); }}><option value="currency">{tr({ en: 'Quote currency', fr: 'Devise de cotation' })}</option><option value="country">{tr({ en: 'Listing country', fr: 'Pays de cotation' })}</option></select></div>
      <div className="field"><label htmlFor="limit-key">{dimension === 'country' ? tr({ en: 'Country code', fr: 'Code de pays' }) : tr({ en: 'Currency code', fr: 'Code de devise' })}</label><input id="limit-key" maxLength={3} pattern="[A-Z]{3}" value={key} onChange={e => setKey(e.target.value.toUpperCase())} aria-describedby="limit-key-hint" /><span id="limit-key-hint" className="hint">{dimension === 'country' ? tr({ en: 'Three letters, for example USA or CAN', fr: 'Trois lettres, par exemple USA ou CAN' }) : tr({ en: 'Three letters, for example USD or EUR', fr: 'Trois lettres, par exemple USD ou EUR' })}</span></div>
      <div className="field"><label htmlFor="limit-max">{tr({ en: 'Maximum weight (%)', fr: 'Poids maximal (%)' })}</label><input id="limit-max" type="number" min={0} max={100} step="any" value={threshold} onChange={e => setThreshold(e.target.value)} /></div>
    </div><button className="btn" disabled={busy || !/^[A-Z]{3}$/.test(key) || threshold === '' || !Number.isFinite(Number(threshold)) || Number(threshold) < 0 || Number(threshold) > 100}>{tr({ en: 'Save cap', fr: 'Enregistrer le plafond' })}</button></form>
    <ProxyNote />
    {error && <ProfileWriteError error={error} />}
  </div>;
}
