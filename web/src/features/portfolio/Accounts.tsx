'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { fmtMoney, fmtNumber } from '../../lib/format';

export function Accounts({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, feature, meta } = useApp();
  const [name, setName] = useState('');
  const [capital, setCapital] = useState('');
  const [currency, setCurrency] = useState(profile.reportingCurrency);
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
        { totalValue: Number(capital), positions: [{ ticker: ticker.trim().toUpperCase(), weightPct: 100 }] }, currency);
      applyProfile(saved); setName(''); setCapital(''); setTicker('');
    } catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Portfolio accounts', fr: 'Comptes de portefeuille' })}>
    <p className="small muted">{tr({ en: 'Accounts share this profile’s policy. Native-currency capital is converted once using the pinned FX snapshot; all analyses and aggregation use the reporting currency. Conversion receipts retain the source inputs and quotes. This is fictional capital, not a live account valuation or a currency trade. Editing an account’s capital in reporting currency replaces its earlier native-value receipt.', fr: 'Les comptes partagent le plan du profil. Le capital en devise native est converti une fois avec les taux de l’instantané; analyses et agrégation utilisent la devise de présentation. Le reçu conserve les entrées et taux. Capital fictif, sans valorisation en direct ni opération de change. Modifier le capital dans la devise de présentation remplace le reçu natif antérieur.' })}</p>
    {!!profile.accounts?.length && <div className="field"><label htmlFor="account-select">{tr({ en: 'Analyze account', fr: 'Compte à analyser' })}</label>
      <select id="account-select" disabled={busy} value={profile.activeAccountId ?? ''} onChange={e => void select(e.target.value)}>
        {profile.accounts.map(a => <option key={a.accountId} value={a.accountId}>{a.name} · {fmtMoney(a.portfolio.totalValue, a.portfolio.currency, lang)}</option>)}
        <option value="aggregate">{tr({ en: 'All accounts combined', fr: 'Tous les comptes réunis' })}</option>
      </select></div>}
    {!!profile.accounts?.length && <div className="table-scroll" role="region" aria-label={tr({ en: 'Account conversion receipts', fr: 'Reçus de conversion des comptes' })} tabIndex={0}><table><thead><tr><th>{tr({ en: 'Account', fr: 'Compte' })}</th><th>{tr({ en: 'Entered capital', fr: 'Capital saisi' })}</th><th>{tr({ en: 'Reporting value', fr: 'Valeur de présentation' })}</th><th>{tr({ en: 'Pinned conversion evidence', fr: 'Preuve de conversion figée' })}</th></tr></thead><tbody>{profile.accounts.map(account => {
      const receipt = account.nativeValuation;
      return <tr key={account.accountId}><th scope="row">{account.name}</th><td>{fmtMoney(receipt?.nativeValue ?? account.portfolio.totalValue, receipt?.nativeCurrency ?? account.portfolio.currency, lang)}</td><td>{fmtMoney(account.portfolio.totalValue, profile.reportingCurrency, lang)}</td><td>{receipt ? <>
        <span className="block small muted">{tr({ en: 'Code-checked pinned receipt', fr: 'Reçu figé contrôlé par code' })} · {receipt.verifiedChecks?.length ?? 0} {tr({ en: 'checks', fr: 'contrôles' })}</span>
        <span className="block small">{receipt.valuationDate} · {fmtNumber(receipt.conversionRate, lang, 6)} {receipt.reportingCurrency}/{receipt.nativeCurrency}</span>
        {receipt.quotes.length ? receipt.quotes.map((quote, i) => <span className="block small" key={i}><ExternalLink href={quote.source.sourceUrl ?? ''}>{quote.source.sourceName}</ExternalLink> · {quote.observedOn} · {fmtNumber(quote.cadPerUnit, lang, 6)} CAD/{quote.currency}</span>) : <span className="small muted">{tr({ en: 'Same-currency identity conversion', fr: 'Conversion identité, même devise' })}</span>}
      </> : <span className="small muted">{tr({ en: 'User-entered reporting-currency value; no FX receipt', fr: 'Valeur saisie en devise de présentation; sans reçu de change' })}</span>}</td></tr>;
    })}</tbody></table></div>}
    <details><summary>{tr({ en: 'Add a fictional account', fr: 'Ajouter un compte fictif' })}</summary>
      <p className="small muted">{tr({ en: 'Enter a supported initial holding and fictional capital explicitly. Edit the active account’s allocation in Profiles afterward. Creating an account represents additional assets, not a transfer from an existing account.', fr: 'Indiquez un titre initial pris en charge et un capital fictif. Modifiez ensuite la répartition active dans Profils. Un nouveau compte représente des actifs supplémentaires et non un transfert.' })}</p>
      <div className="form-grid">
        <div className="field"><label htmlFor="account-name">{tr({ en: 'Account label', fr: 'Libellé du compte' })}</label><input id="account-name" maxLength={80} value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-capital">{tr({ en: 'Fictional native capital', fr: 'Capital fictif en devise native' })} · {currency}</label><input id="account-capital" type="number" min={.01} step="any" value={capital} onChange={e => setCapital(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-currency">{tr({ en: 'Native account currency', fr: 'Devise native du compte' })}</label><select id="account-currency" value={currency} onChange={e => setCurrency(e.target.value)}>{(meta?.reportingCurrencies ?? [profile.reportingCurrency]).map(c => <option key={c} value={c}>{c}</option>)}</select></div>
        <div className="field"><label htmlFor="account-ticker">{tr({ en: 'Initial holding (100%)', fr: 'Position initiale (100 %)' })}</label><input id="account-ticker" value={ticker} onChange={e => setTicker(e.target.value)} /></div>
      </div>
      <button className="btn" type="button" disabled={busy || !name.trim() || !ticker.trim() || !Number.isFinite(Number(capital)) || Number(capital) <= 0} onClick={() => void create()}>{tr({ en: 'Create and select account', fr: 'Créer et sélectionner le compte' })}</button>
    </details>
    {busy && <p role="status">{tr({ en: 'Saving account selection…', fr: 'Enregistrement de la sélection…' })}</p>}
    {error && <ErrorState error={error} />}
  </Card>;
}
