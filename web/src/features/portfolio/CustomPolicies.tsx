'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { ProxyNote } from '../../components/common/Note';
import { labelOf } from '../../lib/labels';
import { DIMENSION } from './portfolioLabels';
import { DraftRestoredNote, ProfileWriteError } from '../../components/common/States';
import { dropDraft, stashDraft } from '../../lib/draftStore';
import { useRestoredDraft } from '../../state/useDraft';

type Dimension = 'position' | 'sector' | 'asset_class' | 'country' | 'currency' | 'theme';
interface CustomPolicyDraft { dimension: Dimension; key: string; operation: 'cap' | 'floor'; threshold: string }
export function CustomPolicies({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, feature } = useApp();
  const draftKey = `custom-policies|${profile.profileId}`;
  const restored = useRestoredDraft<CustomPolicyDraft>(draftKey, profile.version);
  const [dimension, setDimension] = useState<Dimension>(restored?.dimension ?? 'position');
  const [key, setKey] = useState(restored?.key ?? '');
  const [operation, setOperation] = useState<'cap' | 'floor'>(restored?.operation ?? 'cap');
  const [threshold, setThreshold] = useState(restored?.threshold ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const save = async () => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().addCustomRule(profile.profileId, { dimension, key, operation, threshold: Number(threshold), version: profile.version })); dropDraft(draftKey); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  // This form only adds conditions (a profile_creator write); saved ones are profile rules, read by the Rules card.
  // It renders inside the Add a rule card, which handles default profiles.
  if (!feature('profile_creator')) return null;
  const keyHint = dimension === 'position' ? { en: 'Ticker, for example AAPL', fr: 'Symbole, par exemple AAPL' }
    : dimension === 'country' ? { en: 'Three-letter country code, for example USA', fr: 'Code de pays à trois lettres, par exemple USA' }
      : dimension === 'currency' ? { en: 'Three-letter currency code, for example USD', fr: 'Code de devise à trois lettres, par exemple USD' }
        : { en: 'Exact name as shown in Holdings', fr: 'Nom exact, comme dans Positions' };
  return <div className="add-rule-form">
    <p className="small muted">{tr({ en: 'Set a maximum (cap) or a minimum (floor) weight for a holding, sector, class, country, currency or theme.', fr: 'Fixez un poids maximal (plafond) ou minimal (plancher) pour une position, un secteur, une catégorie, un pays, une devise ou un thème.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy}>{restored && <DraftRestoredNote />}<div className="form-grid">
      <div className="field"><label htmlFor="custom-policy-dimension">{tr({ en: 'Applies to', fr: 'S’applique à' })}</label><select id="custom-policy-dimension" value={dimension} onChange={e => { setDimension(e.target.value as Dimension); setKey(''); }}>{(['position', 'sector', 'asset_class', 'country', 'currency', 'theme'] as const).map(d => <option key={d} value={d}>{labelOf(DIMENSION, d, lang)}</option>)}</select></div>
      <div className="field"><label htmlFor="custom-policy-key">{tr({ en: 'Which one', fr: 'Lequel' })}</label><input id="custom-policy-key" required maxLength={120} value={key} onChange={e => setKey(e.target.value)} aria-describedby="custom-policy-key-hint" /><span id="custom-policy-key-hint" className="hint">{tr(keyHint)}</span></div>
      <div className="field"><label htmlFor="custom-policy-operation">{tr({ en: 'Condition', fr: 'Condition' })}</label><select id="custom-policy-operation" value={operation} onChange={e => setOperation(e.target.value as typeof operation)}><option value="cap">{tr({ en: 'At most (cap)', fr: 'Au plus (plafond)' })}</option><option value="floor">{tr({ en: 'At least (floor)', fr: 'Au moins (plancher)' })}</option></select></div>
      <div className="field"><label htmlFor="custom-policy-threshold">{tr({ en: 'Weight (%)', fr: 'Poids (%)' })}</label><input id="custom-policy-threshold" required type="number" min={0} max={100} step="any" value={threshold} onChange={e => setThreshold(e.target.value)} /></div>
    </div><button className="btn" type="submit">{tr({ en: 'Save and check', fr: 'Enregistrer et vérifier' })}</button></fieldset></form>
    {(dimension === 'country' || dimension === 'currency') && <ProxyNote />}
    {error && <ProfileWriteError error={error} onReload={() => stashDraft(draftKey, profile.version, { dimension, key, operation, threshold } satisfies CustomPolicyDraft)} />}
  </div>;
}
