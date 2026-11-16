'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { DraftRestoredNote, ProfileWriteError } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { SupportedUniverse } from '../../components/common/SupportedUniverse';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { checkTickers } from '../../lib/tickerCoverage';
import { fmtMoney, fmtNumber } from '../../lib/format';
import { dropDraft, stashDraft } from '../../lib/draftStore';
import { useRestoredDraft } from '../../state/useDraft';

interface AccountsDraft { name: string; capital: string; currency: string; ticker: string; asOf: string; source: string; destination: string; amount: string }

export function Accounts({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile: apply, feature, meta } = useApp();
  const draftKey = `accounts|${profile.profileId}`;
  // Every successful write here forgets a stashed draft, so the remount it causes starts from the saved profile.
  const applyProfile = (saved: Profile) => { dropDraft(draftKey); apply(saved); };
  // Input typed before a conflict reload; a transfer account the reloaded profile no longer has is not reselected.
  const restored = useRestoredDraft<AccountsDraft>(draftKey, profile.version);
  const known = (id: string | undefined) => (id && profile.accounts?.some(a => a.accountId === id) ? id : '');
  const [name, setName] = useState(restored?.name ?? '');
  const [capital, setCapital] = useState(restored?.capital ?? '');
  const [currency, setCurrency] = useState(restored?.currency ?? profile.reportingCurrency);
  const [ticker, setTicker] = useState(restored?.ticker ?? '');
  const [asOf, setAsOf] = useState(restored?.asOf ?? '');
  const [source, setSource] = useState(known(restored?.source));
  const [destination, setDestination] = useState(known(restored?.destination));
  const [amount, setAmount] = useState(restored?.amount ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  // The initial holding is checked against the snapshot before the write (the server refuses it after).
  const universe = useAssetUniverse();
  const tickerCheck = checkTickers([ticker], universe, feature('on_demand_tickers'));
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
  const refresh = async (accountId: string) => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().refreshAccount(profile.profileId, accountId, profile.version, asOf || undefined)); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  const transfer = async () => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().transferAccount(profile.profileId, source, destination, Number(amount), profile.version)); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card id="accounts" section={tr({ en: 'Accounts', fr: 'Comptes' })} title={tr({ en: 'Accounts', fr: 'Comptes' })}
    info={tr({ en: 'Accounts share this profile’s policy. Native-currency capital is converted once using the pinned FX snapshot; all analyses and aggregation use the reporting currency. Conversion receipts retain the source inputs and quotes. Refresh is explicit and keeps earlier receipts. This is fictional capital, not a live account valuation or a currency trade. Editing an account’s capital in reporting currency replaces its earlier native-value receipt.', fr: 'Les comptes partagent le plan du profil. Le capital en devise native est converti une fois avec les taux de l’instantané; analyses et agrégation utilisent la devise de présentation. Le reçu conserve les entrées et taux. Capital fictif, sans valorisation en direct ni opération de change. Modifier le capital dans la devise de présentation remplace le reçu natif antérieur.' })}>
    <p className="small muted">{tr({ en: `Choose which account to analyze. Every figure is shown in ${profile.reportingCurrency}; this is fictional capital.`, fr: `Choisissez le compte à analyser. Tous les chiffres sont en ${profile.reportingCurrency} ; il s’agit de capital fictif.` })}</p>
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
        <button type="button" className="btn ghost btn-sm" disabled={busy} onClick={() => void refresh(account.accountId)}>{tr({ en: 'Refresh conversion', fr: 'Actualiser la conversion' })}</button>
      </> : <span className="small muted">{tr({ en: 'User-entered reporting-currency value; no FX receipt', fr: 'Valeur saisie en devise de présentation; sans reçu de change' })}</span>}
      {!!account.valuationHistory?.length && <details><summary>{tr({ en: 'Previous valuation receipts', fr: 'Reçus de valorisation antérieurs' })} ({account.valuationHistory.length})</summary><ul>{account.valuationHistory.map((old, i) => <li key={i}>{old.valuationDate} · {fmtMoney(old.nativeValue, old.nativeCurrency, lang)} → {fmtMoney(old.reportingValue, old.reportingCurrency, lang)} · {old.dataVersion}</li>)}</ul></details>}
      </td></tr>;
    })}</tbody></table></div>}
    <div className="field"><label htmlFor="account-refresh-asof">{tr({ en: 'Conversion date for a refresh (optional)', fr: 'Date de conversion pour une actualisation (facultative)' })}</label><input id="account-refresh-asof" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} aria-describedby="account-refresh-asof-hint" /><p className="small muted" id="account-refresh-asof-hint">{tr({ en: 'Empty uses the current pinned snapshot. Historical requests require quotes actually available at that date. Refresh retains the original receipt; unavailable rates leave the account unchanged.', fr: 'Vide : instantané figé actuel. Une date historique exige des taux disponibles à cette date. Les anciens reçus sont conservés; sans taux, le compte reste inchangé.' })}</p></div>
    {(profile.accounts?.length ?? 0) > 1 && <details><summary>{tr({ en: 'Transfer modeled assets between accounts', fr: 'Transférer des actifs modélisés entre comptes' })}</summary>
      <p className="small muted">{tr({ en: 'Transfers move a proportional slice of source holdings at their reporting-currency values. Combined capital is conserved; no purchase, FX trade, fees or tax is modeled. The source must retain positive capital. Earlier FX receipts become historical evidence after this cash flow.', fr: 'Le transfert déplace une part proportionnelle des positions à leur valeur de présentation. Le capital total est conservé, sans achat, change, frais ni impôts modélisés. Le compte source doit rester positif. Les reçus FX antérieurs deviennent historiques.' })}</p>
      <div className="form-grid">{([['transfer-source', source, setSource, tr({ en: 'From account', fr: 'Compte source' })], ['transfer-destination', destination, setDestination, tr({ en: 'To account', fr: 'Compte cible' })]] as const).map(([id, value, setter, label]) => <div className="field" key={id}><label htmlFor={id}>{label}</label><select id={id} value={value} disabled={busy} onChange={e => setter(e.target.value)}><option value="">—</option>{profile.accounts?.map(a => <option key={a.accountId} value={a.accountId}>{a.name}</option>)}</select></div>)}
      <div className="field"><label htmlFor="transfer-amount">{tr({ en: 'Transfer value', fr: 'Valeur transférée' })} ({profile.reportingCurrency})</label><input id="transfer-amount" type="number" min="0.01" step="any" value={amount} disabled={busy} onChange={e => setAmount(e.target.value)} /></div></div>
      <button type="button" className="btn" disabled={busy || !source || !destination || source === destination || !Number.isFinite(Number(amount)) || Number(amount) <= 0} onClick={() => void transfer()}>{tr({ en: 'Transfer and conserve total value', fr: 'Transférer et conserver le total' })}</button>
    </details>}
    <details><summary>{tr({ en: 'Add a fictional account', fr: 'Ajouter un compte fictif' })}</summary>
      <p className="small muted">{tr({ en: 'Enter a supported initial holding and fictional capital explicitly. Edit the active account’s allocation in Profiles afterward. Creating an account represents additional assets, not a transfer from an existing account.', fr: 'Indiquez un titre initial pris en charge et un capital fictif. Modifiez ensuite la répartition active dans Profils. Un nouveau compte représente des actifs supplémentaires et non un transfert.' })}</p>
      <div className="form-grid">
        <div className="field"><label htmlFor="account-name">{tr({ en: 'Account label', fr: 'Libellé du compte' })}</label><input id="account-name" maxLength={80} value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-capital">{tr({ en: 'Fictional native capital', fr: 'Capital fictif en devise native' })} · {currency}</label><input id="account-capital" type="number" min={.01} step="any" value={capital} onChange={e => setCapital(e.target.value)} /></div>
        <div className="field"><label htmlFor="account-currency">{tr({ en: 'Native account currency', fr: 'Devise native du compte' })}</label><select id="account-currency" value={currency} onChange={e => setCurrency(e.target.value)}>{(meta?.reportingCurrencies ?? [profile.reportingCurrency]).map(c => <option key={c} value={c}>{c}</option>)}</select></div>
        <div className="field"><label htmlFor="account-ticker">{tr({ en: 'Initial holding (100%)', fr: 'Position initiale (100 %)' })}</label>
          <input id="account-ticker" value={ticker} onChange={e => setTicker(e.target.value)} aria-invalid={tickerCheck.blocking}
            aria-describedby={`${tickerCheck.message ? 'account-ticker-issue ' : ''}account-ticker-universe`} />
          {tickerCheck.message && <span id="account-ticker-issue" className={tickerCheck.blocking ? 'field-error' : 'hint'}>{tr(tickerCheck.message)}</span>}
          <SupportedUniverse id="account-ticker-universe" />
        </div>
      </div>
      <button className="btn" type="button" disabled={busy || !name.trim() || !ticker.trim() || tickerCheck.blocking || !Number.isFinite(Number(capital)) || Number(capital) <= 0} onClick={() => void create()}>{tr({ en: 'Create and select account', fr: 'Créer et sélectionner le compte' })}</button>
    </details>
    {busy && <p role="status">{tr({ en: 'Saving…', fr: 'Enregistrement…' })}</p>}
    {restored && <DraftRestoredNote />}
    {error && <ProfileWriteError error={error} onReload={() => stashDraft(draftKey, profile.version, { name, capital, currency, ticker, asOf, source, destination, amount } satisfies AccountsDraft)} />}
  </Card>;
}
