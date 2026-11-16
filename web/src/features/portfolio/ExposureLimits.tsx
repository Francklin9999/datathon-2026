'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ProfileWriteError } from '../../components/common/States';

export function ExposureLimits({ profile }: { profile: Profile }) {
  const { tr, applyProfile, feature } = useApp();
  const [dimension, setDimension] = useState<'country' | 'currency'>('currency');
  const [key, setKey] = useState('USD');
  const [threshold, setThreshold] = useState('50');
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  // This card only adds limits (a profile_creator write); saved limits are profile rules, read by the Rules card.
  if (!feature('profile_creator')) return null;
  const save = async () => { setBusy(true); setError(null); try {
    applyProfile(await getApiClient().addExposureLimit(profile.profileId, dimension, key, Number(threshold), profile.version));
  } catch (e) { setError(asApiError(e)); } finally { setBusy(false); } };
  return <Card title={tr({ en: 'Custom exposure policy', fr: 'Règles d’exposition personnalisées' })}>
    <p className="small muted">{tr({ en: 'These are user assumptions. Country limits use listing-country proxies; currency limits use quote currencies. Neither measures revenue geography, ETF holdings, hedges or regulatory requirements.', fr: 'Ce sont des hypothèses utilisateur. Les limites de pays utilisent la cotation; celles de devises utilisent les devises de cotation. Elles ne mesurent ni les revenus, ni les positions des fonds, ni les couvertures, ni des obligations réglementaires.' })}</p>
    {profile.isDefault ? <p>{tr({ en: 'Duplicate a template in Profiles to add custom rules.', fr: 'Dupliquez un modèle dans Profils pour ajouter des règles.' })}</p> : <form onSubmit={e => { e.preventDefault(); void save(); }}><div className="form-grid">
      <div className="field"><label htmlFor="limit-dimension">{tr({ en: 'Dimension', fr: 'Dimension' })}</label><select id="limit-dimension" value={dimension} onChange={e => { setDimension(e.target.value as 'country' | 'currency'); setKey(e.target.value === 'country' ? 'USA' : 'USD'); }}><option value="currency">{tr({ en: 'Quote currency', fr: 'Devise de cotation' })}</option><option value="country">{tr({ en: 'Listing country', fr: 'Pays de cotation' })}</option></select></div>
      <div className="field"><label htmlFor="limit-key">{dimension === 'country' ? 'ISO 3166 alpha-3' : 'ISO 4217'}</label><input id="limit-key" maxLength={3} pattern="[A-Z]{3}" value={key} onChange={e => setKey(e.target.value.toUpperCase())} /></div>
      <div className="field"><label htmlFor="limit-max">{tr({ en: 'Maximum weight (%)', fr: 'Poids maximal (%)' })}</label><input id="limit-max" type="number" min={0} max={100} step="any" value={threshold} onChange={e => setThreshold(e.target.value)} /></div>
    </div><button className="btn" disabled={busy || !/^[A-Z]{3}$/.test(key) || threshold === '' || !Number.isFinite(Number(threshold)) || Number(threshold) < 0 || Number(threshold) > 100}>{tr({ en: 'Save user limit', fr: 'Enregistrer la limite' })}</button></form>}
    {error && <ProfileWriteError error={error} />}
  </Card>;
}
