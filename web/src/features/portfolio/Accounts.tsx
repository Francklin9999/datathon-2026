'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtMoney } from '../../lib/format';

export function Accounts({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, feature } = useApp();
  const [name, setName] = useState('');
  const [capital, setCapital] = useState('');
  const [ticker, setTicker] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  if (!feature('profile_creator')) return null;
  const select = async (id: string) => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().selectAccount(profile.profileId, id, profile.version)); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const saved = await getApiClient().createAccount(profile.profileId, name.trim(), profile.version,
        { totalValue: Number(capital), positions: [{ ticker: ticker.trim().toUpperCase(), weightPct: 100 }] });
      applyProfile(saved); setName(''); setCapital(''); setTicker('');
    } catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Portfolio accounts', fr: 'Comptes de portefeuille' })}>
    <p className="small muted">{tr({ en: 'Each account uses this profile’s policy and reporting currency. Selecting an account recalculates all portfolio views and starts a new profile version. Aggregate combines account values and deduplicates securities; it is a read-only analysis view.', fr: 'Chaque compte utilise le plan et la devise de ce profil. La sélection recalcule les vues et crée une nouvelle version. La vue agrégée combine les valeurs et regroupe les titres identiques; elle est en lecture seule.' })}</p>
    {!!profile.accounts?.length && <div className="field"><label htmlFor="account-select">{tr({ en: 'Analyze account', fr: 'Compte à analyser' })}</label>
      <select id="account-select" disabled={busy} value={profile.activeAccountId ?? ''} onChange={e => void select(e.target.value)}>
        {profile.accounts.map(a => <option key={a.accountId} value={a.accountId}>{a.name} · {fmtMoney(a.portfolio.totalValue, a.portfolio.currency, lang)}</option>)}
        <option value="aggregate">{tr({ en: 'All accounts combined', fr: 'Tous les comptes réunis' })}</option>
      </select></div>}
    <details><summary>{tr({ en: 'Add a fictional account', fr: 'Ajouter un compte fictif' })}</summary>
      <p className="small muted">{tr({ en: 'Enter a supported initial holding and fictional capital explicitly. Edit the active account’s allocation in Profiles afterward. Creating an account represents additional assets, not a transfer from an existing account.', fr: 'Indiquez un titre initial pris en charge et un capital fictif. Modifiez ensuite la répartition active dans Profils. Un nouveau compte représente des actifs supplémentaires et non un transfert.' })}</p>
      <div className="form-grid">
        <div className="field"><label htmlFor="account-name">{tr({ en: 'Account label', fr: 'Libellé du compte' })}</label><input id="account-name" maxLength={80} value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-capital">{tr({ en: 'Fictional capital', fr: 'Capital fictif' })} · {profile.reportingCurrency}</label><input id="account-capital" type="number" min={.01} step="any" value={capital} onChange={e => setCapital(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-ticker">{tr({ en: 'Initial holding (100%)', fr: 'Position initiale (100 %)' })}</label><input id="account-ticker" value={ticker} onChange={e => setTicker(e.target.value)} /></div>
      </div>
      <button className="btn" type="button" disabled={busy || !name.trim() || !ticker.trim() || !Number.isFinite(Number(capital)) || Number(capital) <= 0} onClick={() => void create()}>{tr({ en: 'Create and select account', fr: 'Créer et sélectionner le compte' })}</button>
    </details>
    {busy && <p role="status">{tr({ en: 'Saving account selection…', fr: 'Enregistrement de la sélection…' })}</p>}
    {error && <ErrorState error={error} />}
  </Card>;
}
