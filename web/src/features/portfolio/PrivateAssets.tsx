'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { DraftRestoredNote, ProfileWriteError } from '../../components/common/States';
import { fmtMoney } from '../../lib/format';
import { valuationLimitationText, valuationTotals } from '../../lib/portfolioEditors';
import { dropDraft, stashDraft } from '../../lib/draftStore';
import { useRestoredDraft } from '../../state/useDraft';
import { useQuery } from '../../state/useQuery';

interface PrivateAssetDraft {
  accountId: string; assetId: string; name: string; type: string; date: string; value: string;
  currency: string; origin: 'user' | 'imported'; source: string; liquidity: string;
}

export function PrivateAssets({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, meta, feature, sessionId } = useApp();
  const draftKey = `private-assets|${profile.profileId}`;
  const restored = useRestoredDraft<PrivateAssetDraft>(draftKey, profile.version);
  // A restored account or asset that no longer exists in the reloaded profile is not reselected.
  const restoredAccount = restored && profile.accounts?.find(a => a.accountId === restored.accountId);
  const [accountId, setAccountId] = useState(restoredAccount ? restoredAccount.accountId : profile.activeAccountId === 'aggregate' ? '' : profile.activeAccountId ?? '');
  const [assetId, setAssetId] = useState(restored && restoredAccount?.privateAssets?.some(p => p.assetId === restored.assetId) ? restored.assetId : '');
  const [name, setName] = useState(restored?.name ?? '');
  const [type, setType] = useState(restored?.type ?? '');
  const [date, setDate] = useState(restored?.date ?? '');
  const [value, setValue] = useState(restored?.value ?? '');
  const [currency, setCurrency] = useState(restored?.currency ?? profile.reportingCurrency);
  const [origin, setOrigin] = useState<'user' | 'imported'>(restored?.origin ?? 'user');
  const [source, setSource] = useState(restored?.source ?? '');
  const [liquidity, setLiquidity] = useState(restored?.liquidity ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const account = profile.accounts?.find(a => a.accountId === accountId);
  const assets = (profile.accounts ?? []).flatMap(a => (a.privateAssets ?? []).map(asset => ({ ...asset, accountName: a.name })));
  // Server totals (GET /profiles/{id}/account-valuations); the same sums from the loaded profile
  // stand in while they load and when the API cannot answer (fixture mode, an outage).
  const valuations = useQuery(sessionId && meta ? `account-valuations|${sessionId}|${profile.profileId}|v${profile.version}|${meta.dataVersion}` : null,
    signal => getApiClient().accountValuations(profile.profileId, signal));
  const totals = valuationTotals(profile, valuations.data);
  const load = (id: string) => {
    setAssetId(id);
    const a = account?.privateAssets?.find(p => p.assetId === id);
    setName(a?.name ?? ''); setType(a?.assetType ?? ''); setLiquidity(a?.liquidityNotes ?? '');
    setDate(a?.valuation.valuationDate ?? ''); setValue(a ? String(a.valuation.conversion.nativeValue) : '');
    setCurrency(a?.valuation.conversion.nativeCurrency ?? profile.reportingCurrency);
    setSource(a?.valuation.sourceDescription ?? ''); setOrigin(a?.valuation.origin ?? 'user');
  };
  const save = async () => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().savePrivateAsset(profile.profileId, accountId, { version: profile.version, ...(assetId ? { assetId } : {}), name, assetType: type, liquidityNotes: liquidity, valuationDate: date, nativeValue: Number(value), nativeCurrency: currency, origin, sourceDescription: source })); dropDraft(draftKey); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  const keepDraft = () => stashDraft(draftKey, profile.version, { accountId, assetId, name, type, date, value, currency, origin, source, liquidity } satisfies PrivateAssetDraft);
  return <Card title={tr({ en: 'Private and illiquid asset valuations', fr: 'Valorisations des actifs privés et illiquides' })}>
    <p>{tr({ en: 'These are additional user or imported appraisals, separate from traded portfolio capital. Do not enter the same asset twice. Market risk, performance, allocation limits and rebalancing exclude these assets because no traded return or liquidation model is available. An appraisal is not an executable sale price.', fr: 'Ces évaluations supplémentaires, saisies ou importées, sont séparées du capital coté. Ne comptez pas deux fois un actif. Risque, performance, limites et rééquilibrage excluent ces actifs sans série de prix ni modèle de liquidation. Une évaluation n’est pas un prix de vente exécutable.' })}</p>
    <dl className="kv-list"><div className="kv"><dt>{tr({ en: 'All accounts: modeled traded capital', fr: 'Tous comptes : capital coté modélisé' })}</dt><dd>{fmtMoney(totals.traded, totals.currency, lang)}</dd></div><div className="kv"><dt>{tr({ en: 'Additional private appraisals', fr: 'Évaluations privées supplémentaires' })}</dt><dd>{fmtMoney(totals.privateValue, totals.currency, lang)}</dd></div><div className="kv"><dt>{tr({ en: 'Combined reported value', fr: 'Valeur totale déclarée' })}</dt><dd>{fmtMoney(totals.combined, totals.currency, lang)}</dd></div></dl>
    {valuations.error && <p className="small muted" role="note">{tr({ en: 'The API’s valuation summary is unavailable, so these totals were added up in this browser from the loaded profile.', fr: 'Le résumé de valorisation de l’API est indisponible : ces totaux ont été additionnés dans ce navigateur à partir du profil chargé.' })}</p>}
    {totals.rows.length > 1 && <div className="table-scroll" role="region" aria-label={tr({ en: 'Value per account', fr: 'Valeur par compte' })} tabIndex={0}><table className="data-table">
      <thead><tr><th scope="col">{tr({ en: 'Account', fr: 'Compte' })}</th><th scope="col" className="num-col">{tr({ en: 'Modeled traded capital', fr: 'Capital coté modélisé' })}</th><th scope="col" className="num-col">{tr({ en: 'Private appraisals', fr: 'Évaluations privées' })}</th><th scope="col" className="num-col">{tr({ en: 'Combined', fr: 'Total' })}</th></tr></thead>
      <tbody>{totals.rows.map(row => <tr key={row.accountId}><th scope="row">{row.name}</th><td className="num-col num">{fmtMoney(row.modeledTradedValue, totals.currency, lang)}</td><td className="num-col num">{fmtMoney(row.privateValue, totals.currency, lang)}</td><td className="num-col num">{fmtMoney(row.combinedValue, totals.currency, lang)}</td></tr>)}</tbody>
    </table></div>}
    {totals.limitations.length > 0 && <ul className="small muted">{totals.limitations.map(sentence => {
      const known = valuationLimitationText(sentence);
      return <li key={sentence} {...(known ? {} : { lang: 'en' })}>{known ? tr(known) : sentence}</li>;
    })}</ul>}
    {assets.map(a => <details key={a.assetId}><summary>{a.accountName} · {a.name} · {fmtMoney(a.valuation.conversion.reportingValue, profile.reportingCurrency, lang)}</summary><p>{a.assetType} · {a.liquidityNotes}</p><p>{a.valuation.valuationDate} · {a.valuation.origin} · {a.valuation.sourceDescription}</p><p className="small muted">{tr({ en: 'FX receipt date', fr: 'Date du reçu FX' })}: {a.valuation.conversion.valuationDate} · {a.valuation.conversion.dataVersion} · {fmtMoney(a.valuation.conversion.nativeValue, a.valuation.conversion.nativeCurrency, lang)}</p>{!!a.valuationHistory?.length && <ul>{a.valuationHistory.map((v, i) => <li key={i}>{v.valuationDate} · {v.origin} · {v.sourceDescription} · {fmtMoney(v.conversion.reportingValue, profile.reportingCurrency, lang)}</li>)}</ul>}</details>)}
    {/* Saving an appraisal is a profile_creator write; the totals and saved appraisals stay readable. */}
    {feature('profile_creator') && <details open={restored ? true : undefined}><summary>{tr({ en: 'Add or update a documented appraisal', fr: 'Ajouter ou actualiser une évaluation documentée' })}</summary>
      {restored && <DraftRestoredNote />}
      {!profile.accounts?.length ? <p>{tr({ en: 'Create an account first to attach a private valuation.', fr: 'Créez un compte pour rattacher une évaluation privée.' })}</p> : <form onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy}><div className="form-grid">
        <div className="field"><label htmlFor="private-account">{tr({ en: 'Account', fr: 'Compte' })}</label><select id="private-account" required value={accountId} onChange={e => { setAccountId(e.target.value); setAssetId(''); }}><option value="">—</option>{profile.accounts.map(a => <option key={a.accountId} value={a.accountId}>{a.name}</option>)}</select></div>
        <div className="field"><label htmlFor="private-existing">{tr({ en: 'Create or update', fr: 'Créer ou actualiser' })}</label><select id="private-existing" value={assetId} onChange={e => load(e.target.value)}><option value="">{tr({ en: 'New asset (additional value)', fr: 'Nouvel actif (valeur supplémentaire)' })}</option>{account?.privateAssets?.map(a => <option key={a.assetId} value={a.assetId}>{a.name}</option>)}</select></div>
        {([['private-name', tr({ en: 'Asset name', fr: 'Nom de l’actif' }), name, setName], ['private-type', tr({ en: 'Asset type', fr: 'Type d’actif' }), type, setType], ['private-source', tr({ en: 'Valuation source and method', fr: 'Source et méthode d’évaluation' }), source, setSource], ['private-liquidity', tr({ en: 'Liquidity limits', fr: 'Limites de liquidité' }), liquidity, setLiquidity]] as const).map(([id, label, text, set]) => <div className="field" key={id}><label htmlFor={id}>{label}</label><input id={id} required={id !== 'private-liquidity'} maxLength={id === 'private-source' || id === 'private-liquidity' ? 1000 : 80} value={text} onChange={e => set(e.target.value)} /></div>)}
        <div className="field"><label htmlFor="private-origin">{tr({ en: 'Origin', fr: 'Origine' })}</label><select id="private-origin" value={origin} onChange={e => setOrigin(e.target.value as typeof origin)}><option value="user">user</option><option value="imported">imported</option></select></div>
        <div className="field"><label htmlFor="private-date">{tr({ en: 'Appraisal date', fr: 'Date d’évaluation' })}</label><input id="private-date" type="date" required value={date} onChange={e => setDate(e.target.value)} /></div>
        <div className="field"><label htmlFor="private-value">{tr({ en: 'Native appraised value', fr: 'Valeur évaluée native' })}</label><input id="private-value" type="number" min={0.01} step="any" required value={value} onChange={e => setValue(e.target.value)} /></div>
        <div className="field"><label htmlFor="private-currency">{tr({ en: 'Currency', fr: 'Devise' })}</label><select id="private-currency" value={currency} onChange={e => setCurrency(e.target.value)}>{(meta?.reportingCurrencies ?? [profile.reportingCurrency]).map(c => <option key={c} value={c}>{c}</option>)}</select></div>
      </div><button className="btn" type="submit">{tr({ en: 'Save dated appraisal', fr: 'Enregistrer l’évaluation datée' })}</button></fieldset></form>}
    </details>}{error && <ProfileWriteError error={error} onReload={keepDraft} />}
  </Card>;
}
