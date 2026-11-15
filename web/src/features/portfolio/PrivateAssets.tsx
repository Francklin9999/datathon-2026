'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtMoney } from '../../lib/format';

export function PrivateAssets({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, meta } = useApp();
  const [accountId, setAccountId] = useState(profile.activeAccountId === 'aggregate' ? '' : profile.activeAccountId ?? '');
  const [assetId, setAssetId] = useState('');
  const [name, setName] = useState('');
  const [type, setType] = useState('');
  const [date, setDate] = useState('');
  const [value, setValue] = useState('');
  const [currency, setCurrency] = useState(profile.reportingCurrency);
  const [origin, setOrigin] = useState<'user' | 'imported'>('user');
  const [source, setSource] = useState('');
  const [liquidity, setLiquidity] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const account = profile.accounts?.find(a => a.accountId === accountId);
  const assets = (profile.accounts ?? []).flatMap(a => (a.privateAssets ?? []).map(asset => ({ ...asset, accountName: a.name })));
  const traded = profile.accounts?.length ? profile.accounts.reduce((n, a) => n + a.portfolio.totalValue, 0) : profile.portfolio.totalValue;
  const privateValue = assets.reduce((n, a) => n + a.valuation.conversion.reportingValue, 0);
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
    try { applyProfile(await getApiClient().savePrivateAsset(profile.profileId, accountId, { version: profile.version, ...(assetId ? { assetId } : {}), name, assetType: type, liquidityNotes: liquidity, valuationDate: date, nativeValue: Number(value), nativeCurrency: currency, origin, sourceDescription: source })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Private and illiquid asset valuations', fr: 'Valorisations des actifs privés et illiquides' })}>
    <p>{tr({ en: 'These are additional user or imported appraisals, separate from traded portfolio capital. Do not enter the same asset twice. Market risk, performance, allocation limits and rebalancing exclude these assets because no traded return or liquidation model is available. An appraisal is not an executable sale price.', fr: 'Ces évaluations supplémentaires, saisies ou importées, sont séparées du capital coté. Ne comptez pas deux fois un actif. Risque, performance, limites et rééquilibrage excluent ces actifs sans série de prix ni modèle de liquidation. Une évaluation n’est pas un prix de vente exécutable.' })}</p>
    <dl className="kv-list"><div className="kv"><dt>{tr({ en: 'All accounts: modeled traded capital', fr: 'Tous comptes : capital coté modélisé' })}</dt><dd>{fmtMoney(traded, profile.reportingCurrency, lang)}</dd></div><div className="kv"><dt>{tr({ en: 'Additional private appraisals', fr: 'Évaluations privées supplémentaires' })}</dt><dd>{fmtMoney(privateValue, profile.reportingCurrency, lang)}</dd></div><div className="kv"><dt>{tr({ en: 'Combined reported value', fr: 'Valeur totale déclarée' })}</dt><dd>{fmtMoney(traded + privateValue, profile.reportingCurrency, lang)}</dd></div></dl>
    {assets.map(a => <details key={a.assetId}><summary>{a.accountName} · {a.name} · {fmtMoney(a.valuation.conversion.reportingValue, profile.reportingCurrency, lang)}</summary><p>{a.assetType} · {a.liquidityNotes}</p><p>{a.valuation.valuationDate} · {a.valuation.origin} · {a.valuation.sourceDescription}</p><p className="small muted">{tr({ en: 'FX receipt date', fr: 'Date du reçu FX' })}: {a.valuation.conversion.valuationDate} · {a.valuation.conversion.dataVersion} · {fmtMoney(a.valuation.conversion.nativeValue, a.valuation.conversion.nativeCurrency, lang)}</p>{!!a.valuationHistory?.length && <ul>{a.valuationHistory.map((v, i) => <li key={i}>{v.valuationDate} · {v.origin} · {v.sourceDescription} · {fmtMoney(v.conversion.reportingValue, profile.reportingCurrency, lang)}</li>)}</ul>}</details>)}
    <details><summary>{tr({ en: 'Add or update a documented appraisal', fr: 'Ajouter ou actualiser une évaluation documentée' })}</summary>
      {!profile.accounts?.length ? <p>{tr({ en: 'Create an account first to attach a private valuation.', fr: 'Créez un compte pour rattacher une évaluation privée.' })}</p> : <form onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy}><div className="form-grid">
        <div className="field"><label htmlFor="private-account">{tr({ en: 'Account', fr: 'Compte' })}</label><select id="private-account" required value={accountId} onChange={e => { setAccountId(e.target.value); setAssetId(''); }}><option value="">—</option>{profile.accounts.map(a => <option key={a.accountId} value={a.accountId}>{a.name}</option>)}</select></div>
        <div className="field"><label htmlFor="private-existing">{tr({ en: 'Create or update', fr: 'Créer ou actualiser' })}</label><select id="private-existing" value={assetId} onChange={e => load(e.target.value)}><option value="">{tr({ en: 'New asset (additional value)', fr: 'Nouvel actif (valeur supplémentaire)' })}</option>{account?.privateAssets?.map(a => <option key={a.assetId} value={a.assetId}>{a.name}</option>)}</select></div>
        {([['private-name', tr({ en: 'Asset name', fr: 'Nom de l’actif' }), name, setName], ['private-type', tr({ en: 'Asset type', fr: 'Type d’actif' }), type, setType], ['private-source', tr({ en: 'Valuation source and method', fr: 'Source et méthode d’évaluation' }), source, setSource], ['private-liquidity', tr({ en: 'Liquidity limits', fr: 'Limites de liquidité' }), liquidity, setLiquidity]] as const).map(([id, label, text, set]) => <div className="field" key={id}><label htmlFor={id}>{label}</label><input id={id} required={id !== 'private-liquidity'} maxLength={id === 'private-source' || id === 'private-liquidity' ? 1000 : 80} value={text} onChange={e => set(e.target.value)} /></div>)}
        <div className="field"><label htmlFor="private-origin">{tr({ en: 'Origin', fr: 'Origine' })}</label><select id="private-origin" value={origin} onChange={e => setOrigin(e.target.value as typeof origin)}><option value="user">user</option><option value="imported">imported</option></select></div>
        <div className="field"><label htmlFor="private-date">{tr({ en: 'Appraisal date', fr: 'Date d’évaluation' })}</label><input id="private-date" type="date" required value={date} onChange={e => setDate(e.target.value)} /></div>
        <div className="field"><label htmlFor="private-value">{tr({ en: 'Native appraised value', fr: 'Valeur évaluée native' })}</label><input id="private-value" type="number" min={0.01} step="any" required value={value} onChange={e => setValue(e.target.value)} /></div>
        <div className="field"><label htmlFor="private-currency">{tr({ en: 'Currency', fr: 'Devise' })}</label><select id="private-currency" value={currency} onChange={e => setCurrency(e.target.value)}>{(meta?.reportingCurrencies ?? [profile.reportingCurrency]).map(c => <option key={c} value={c}>{c}</option>)}</select></div>
      </div><button className="btn" type="submit">{tr({ en: 'Save dated appraisal', fr: 'Enregistrer l’évaluation datée' })}</button></fieldset></form>}
    </details>{error && <ErrorState error={error} />}
  </Card>;
}
