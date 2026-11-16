'use client';
/**
 * Portfolio — holdings, rules and descriptive risk (T13, web/page-specs/portfolio.md). Rule edits PATCH
 * one threshold/flag and adopt the returned profileVersion, which re-keys overview and brief caches
 * (PORT-02). Previews go through /check with overrides and are never saved implicitly.
 */
import { useMemo, useState } from 'react';
import { PositionQuantities } from './PositionQuantities';
import { AccountEditor } from './AccountEditor';
import { PrivateAssets } from './PrivateAssets';
import { Accounts } from './Accounts';
import { AddRule } from './AddRule';
import { RiskDiagnostics } from './RiskDiagnostics';
import { ORIGIN } from './portfolioLabels';
import './portfolio.css';
import type {
  CheckResult, DeriveRulesResponse, FrontierResponse, Lang, OverviewResponse, PolicyRule, Profile,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { sameSubject } from '../../lib/ui/scope';
import { WindowControl } from '../../components/shell/TopBar';
import { Tabs, tabPanelProps, useTabParam } from '../../components/ui/Tabs';
import { ProxyNote } from '../../components/common/Note';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { CountsLine, VerdictBadge } from '../../components/common/Badges';
import { RuleTable } from '../../components/run/RuleTable';
import { GroupBars } from '../../components/run/Results';
import { ASSET_CLASS, WINDOW, labelOf } from '../../lib/labels';
import { CorrelationHeatmap } from './CorrelationHeatmap';
import { CountUp } from '../../components/ui/CountUp';
import { factIdFor, fmtMoney, fmtNumber, fmtPct, fmtSignedPct, fmtUnit } from '../../lib/format';
import { disabledRules, planRuleRows } from '../../lib/planRules';
import { InvestmentPlaybook } from '../investor-lab/InvestmentPlaybook';
import { LOWEST_12M_INFO, LOWEST_12M_SHORT } from '../../lib/ui/figures';
import { holdingReturnsOf } from '../../lib/overviewReturns';

export function PortfolioPage() {
  return <ProfileGate>{profile => <PortfolioContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

const TABS = ['holdings', 'risk', 'rules', 'accounts'] as const;
type PortfolioTab = typeof TABS[number];

function PortfolioContent({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, windowCode, lang } = app;
  const base = profileKey(app);
  const [tab, setTab] = useTabParam<PortfolioTab>('tab', TABS, 'holdings');
  // A new period keeps the figures on screen (dimmed) until the new ones land; another profile never does.
  const keepOverview = useMemo(() => ({ keepPreviousFrom: sameSubject('overview', base) }), [base]);
  const overview = useQuery<OverviewResponse>(base && `overview|${base}|${windowCode}`,
    signal => getApiClient().overview(profile.profileId, windowCode, signal), keepOverview);
  const scope = useMemo<FactScope | null>(() => (overview.data
    ? { kind: 'local', label: { en: 'Portfolio figures, computed by code.', fr: 'Chiffres du portefeuille, calculés par le code.' }, facts: overview.data.facts }
    : null), [overview.data]);
  const { key: panelKey, ...panel } = tabPanelProps('portfolio', tab);

  const overviewState = <>
    {overview.loading && !overview.data && <Loading />}
    {overview.error && <ErrorState error={overview.error} onRetry={overview.reload}
      title={tr({ en: 'The portfolio overview is unavailable. No figures are shown.', fr: 'L’aperçu du portefeuille est indisponible. Aucun chiffre n’est affiché.' })} />}
    {overview.stale && <p className="sr-only" role="status">{tr({ en: 'Updating the figures for the new period', fr: 'Mise à jour des chiffres pour la nouvelle période' })}</p>}
  </>;

  return (
    <>
      <PageHeader actions={<WindowControl />} tour="portfolio-header"
        title={tr({ en: 'Holdings, rules and risk', fr: 'Positions, règles et risque' })}>
        <p className="page-sub">
          {tr({ en: `${fmtMoney(profile.portfolio.totalValue, profile.portfolio.currency, lang)} of fictional capital for ${profile.name}.`, fr: `${fmtMoney(profile.portfolio.totalValue, profile.portfolio.currency, lang)} de capital fictif pour ${profile.name}.` })}
        </p>
      </PageHeader>
      <div data-tour="portfolio-tabs">
        <Tabs<PortfolioTab> idBase="portfolio" label={tr({ en: 'Portfolio sections', fr: 'Sections du portefeuille' })} value={tab} onChange={setTab} tabs={[
          { id: 'holdings', label: tr({ en: 'Holdings', fr: 'Positions' }), title: tr({ en: 'What the portfolio holds and how it is spread', fr: 'Ce que détient le portefeuille et sa répartition' }) },
          { id: 'risk', label: tr({ en: 'Risk', fr: 'Risque' }), title: tr({ en: 'How the portfolio behaved in the past', fr: 'Comment le portefeuille s’est comporté par le passé' }) },
          { id: 'rules', label: tr({ en: 'Rules', fr: 'Règles' }), title: tr({ en: 'The limits every decision is checked against', fr: 'Les limites vérifiées pour chaque décision' }) },
          { id: 'accounts', label: tr({ en: 'Accounts', fr: 'Comptes' }), title: tr({ en: 'Accounts, quantities and private assets', fr: 'Comptes, quantités et actifs privés' }) },
        ]} />
      </div>
      <div key={panelKey} {...panel} data-tour={`portfolio-panel-${tab}`} {...(overview.stale && tab !== 'accounts' ? { 'aria-busy': true } : {})}>
        {tab === 'holdings' && <>
          {overviewState}
          {overview.data && scope && (
            <FactScopeProvider scope={scope}>
              <Holdings overview={overview.data} profile={profile} />
              <Allocation overview={overview.data} />
              <LimitationList compactAfter={0} codes={overview.data.limitations} />
            </FactScopeProvider>
          )}
        </>}
        {tab === 'risk' && <>
          {overviewState}
          {overview.data && scope && <FactScopeProvider scope={scope}><Risk overview={overview.data} /></FactScopeProvider>}
          <RiskDiagnostics profile={profile} />
          {overview.data && <LimitationList compactAfter={0} codes={overview.data.limitations} />}
        </>}
        {tab === 'rules' && <>
          {overview.error && overviewState}
          {app.feature('profile_creator') && <InvestmentPlaybook key={`${profile.profileId}|${profile.version}`} profile={profile} />}
          <Rules profile={profile} overview={overview.data} scope={scope} />
          <AddRule profile={profile} />
          <Frontier profile={profile} />
        </>}
        {tab === 'accounts' && <div data-tour="accounts">
          <Accounts key={`accounts|${profile.profileId}|${profile.version}`} profile={profile} />
          <PositionQuantities key={`quantities|${profile.profileId}|${profile.version}`} profile={profile} />
          <AccountEditor key={`account-edit|${profile.profileId}|${profile.version}`} profile={profile} />
          <PrivateAssets key={`private|${profile.profileId}|${profile.version}`} profile={profile} />
        </div>}
      </div>
    </>
  );
}

function Holdings({ overview, profile }: { overview: OverviewResponse; profile: Profile }) {
  const { tr, lang } = useApp();
  const snapshot = overview.snapshot;
  const returns = holdingReturnsOf(overview);
  const total = snapshot.positions.reduce((s, p) => s + p.weightPct, 0);
  return (
    <Card id="holdings" section={tr({ en: 'Holdings', fr: 'Positions' })} tour="holdings" title={tr({ en: 'Holdings', fr: 'Positions' })}
      info={tr({ en: 'Modeled value is weight × capital. A documented quantity is what you entered in Accounts; it does not change the modeled value.', fr: 'La valeur modélisée est poids × capital. Une quantité documentée est celle saisie dans Comptes ; elle ne change pas la valeur modélisée.' })}>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Holdings table', fr: 'Tableau des positions' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
              <th scope="col">{tr({ en: 'Class', fr: 'Catégorie' })}</th>
              <th scope="col">{tr({ en: 'Sector', fr: 'Secteur' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
              <th scope="col">{tr({ en: 'Quantity', fr: 'Quantité' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Modeled value', fr: 'Valeur modélisée' })} ({snapshot.currency})</th>
              <th scope="col" className="num-col">{tr({ en: '1-year return (historical)', fr: 'Rendement 1 an (historique)' })}</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.positions.map(p => {
              const r = returns.get(p.ticker);
              return (
                <tr key={p.ticker}>
                  <th scope="row"><span className="ticker">{p.ticker}</span><span className="block small muted">{p.name}</span><span className="block small muted">{p.market ?? '—'} · {p.quoteCurrency ?? '—'} · {p.listingCountry ?? '—'}</span>
                    <details className="holding-source"><summary className="small">{tr({ en: 'Source and history', fr: 'Source et historique' })}</summary>
                      <p className="small">{tr({ en: 'Source asset ID', fr: 'Identifiant source de l’actif' })}: <span className="mono">{p.sourceAssetId ?? '—'}</span></p>
                      <p className="small">{p.history?.firstDate ?? '—'} — {p.history?.lastDate ?? '—'} · {p.history?.nObs ?? '—'} {tr({ en: 'price observations', fr: 'observations de prix' })}</p>
                      <p className="small muted">{tr({ en: 'Ticker and market come from the source and are not cross-checked against an ISIN or issuer register.', fr: 'Symbole et marché viennent de la source, sans contrôle croisé avec un ISIN ou un registre d’émetteurs.' })}</p>
                    </details>
                  </th>
                  <td>{labelOf(ASSET_CLASS, p.assetClass, lang)}</td>
                  <td>{p.sector}</td>
                  <td className="num-col num"><CountUp text={fmtPct(p.weightPct, lang)} /></td>
                  <td>{(() => {
                    const q = profile.portfolio.positions.find(h => h.ticker === p.ticker);
                    if (q?.quantity === undefined || q.quantity === null) return <span className="small muted">{tr({ en: 'Not entered', fr: 'Non saisie' })}</span>;
                    return <>
                      <span>{fmtNumber(q.quantity, lang, 4)}</span>
                      <span className="block small muted">{q.quantityAsOf}{q.quantityOrigin ? ` · ${labelOf(ORIGIN, q.quantityOrigin, lang)}` : ''}</span>
                      {q.quantitySource && <details><summary className="small">{tr({ en: 'Quantity source', fr: 'Source de la quantité' })}</summary><p className="small">{q.quantitySource}</p></details>}
                    </>;
                  })()}</td>
                  <td className="num-col num"><CountUp text={fmtMoney(p.marketValue, snapshot.currency, lang)} /></td>
                  <td className="num-col num">
                    {r === undefined
                      ? <span className="muted" title={tr({ en: 'Not supplied for this holding', fr: 'Non fourni pour cette position' })}>—</span>
                      : r.pct === null ? tr({ en: 'Unavailable', fr: 'Indisponible' })
                        : r.factId ? <FactChip factId={r.factId} display={fmtSignedPct(r.pct, lang)} /> : fmtSignedPct(r.pct, lang)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={3}>{tr({ en: 'Total', fr: 'Total' })} ({snapshot.positions.length})</th>
              <td className="num-col num">{fmtPct(total, lang, 2)}</td>
              <td />
              <td className="num-col num">{fmtMoney(snapshot.totalValue, snapshot.currency, lang)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <ProxyNote />
    </Card>
  );
}

function Allocation({ overview }: { overview: OverviewResponse }) {
  const { tr } = useApp();
  const s = overview.snapshot;
  return (
    <div className="grid-3" id="allocation" data-section={tr({ en: 'Allocation', fr: 'Répartition' })}>
      <Card title={tr({ en: 'By asset group', fr: 'Par groupe d’actifs' })}>
        <GroupBars items={s.byAssetGroup} label={tr({ en: 'Allocation by asset group', fr: 'Répartition par groupe d’actifs' })} />
      </Card>
      <Card title={tr({ en: 'By sector (direct equities)', fr: 'Par secteur (actions directes)' })}
        info={tr({ en: 'Direct single-name equities only; funds are not looked through.', fr: 'Actions individuelles directes seulement ; les fonds ne sont pas décomposés.' })}>
        {s.bySector.length === 0
          ? <p className="muted small">{tr({ en: 'No direct single-name equities', fr: 'Aucune action individuelle directe' })}</p>
          : <GroupBars items={s.bySector} label={tr({ en: 'Sector weights', fr: 'Poids sectoriels' })} render={k => k} />}
      </Card>
      <Card title={tr({ en: 'By listing country', fr: 'Par pays de cotation' })}
        info={tr({ en: 'Listing-country proxy, not economic exposure.', fr: 'Approximation par pays de cotation, pas l’exposition économique.' })}>
        <GroupBars items={s.byCountry} label={tr({ en: 'Country weights', fr: 'Poids par pays' })} render={k => k} />
      </Card>
    </div>
  );
}

function Risk({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const { risk, concentration, correlation } = overview;
  const cell = (value: number | null, key: string, signed = false) => {
    if (value === null) return <span className="small muted">{tr({ en: 'Unavailable for this period', fr: 'Indisponible pour cette période' })}</span>;
    const text = signed ? fmtSignedPct(value, lang) : fmtPct(value, lang);
    const factId = factIdFor(risk.factIds, key);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
  return (
    <Card id="risk" section={tr({ en: 'Risk', fr: 'Risque' })} tour="risk" title={tr({ en: 'Historical risk', fr: 'Risque historique' })}
      info={`${tr({ en: 'Measured on this sample of past prices. The 2022 replay is signed; the stress rule compares the loss as a positive number.', fr: 'Mesuré sur cet échantillon de prix passés. Le rejeu 2022 est signé ; la règle de stress compare la perte en nombre positif.' })} ${tr(LOWEST_12M_INFO)}`}>
      <div className="tiles">
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })}</span><span className="big">{cell(risk.volatilityPct, 'volatilityPct')}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })}</span><span className="big">{cell(risk.maxDrawdownPct, 'maxDrawdownPct')}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: '2022 replay return', fr: 'Rendement rejoué 2022' })}</span><span className="big">{cell(risk.stress2022Pct, 'stress2022Pct', true)}</span></div>
        <div className="tile"><span className="eyebrow block">{tr(LOWEST_12M_SHORT)}</span><span className="big">{cell(risk.worst12mPct, 'worst12mPct', true)}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Effective positions', fr: 'Positions effectives' })}</span><span className="big num" title={`HHI ${fmtNumber(concentration.hhi, lang, 3)}`}><CountUp text={fmtNumber(concentration.effectiveN, lang, 1)} /></span></div>
      </div>
      <h3 className="h4">{tr({ en: 'Correlation of daily returns', fr: 'Corrélation des rendements quotidiens' })}</h3>
      {correlation === null
        ? <p className="small muted">{tr({ en: 'Not shown: more than 20 holdings, or not supplied', fr: 'Non affichée : plus de 20 positions, ou non fournie' })}</p>
        : (
          <CorrelationHeatmap tickers={correlation.tickers} matrix={correlation.matrix} />
        )}
    </Card>
  );
}

function RuleEditor({ rule, profile, onPreview }: {
  rule: PolicyRule; profile: Profile; onPreview: (rule: PolicyRule, threshold: number | null, enabled: boolean) => void;
}) {
  const { tr, lang, applyProfile, reloadProfiles, announce } = useApp();
  const [threshold, setThreshold] = useState<string>(rule.threshold === null ? '' : String(rule.threshold));
  const [enabled, setEnabled] = useState(rule.enabled);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  if (!rule.editable) return <span className="small muted">{tr({ en: 'Fixed', fr: 'Fixe' })}</span>;
  const numeric = threshold === '' ? null : Number(threshold);
  const bounds = rule.bounds;
  const invalid = numeric !== null && (!Number.isFinite(numeric) || (bounds !== null && (numeric < bounds.min || numeric > bounds.max)));
  const changed = numeric !== rule.threshold || enabled !== rule.enabled;
  const inputId = `thr-${rule.ruleId}`;

  const save = async () => {
    setSaving(true); setError(null);
    try {
      const body: { threshold?: number; enabled?: boolean } = {};
      if (numeric !== null && numeric !== rule.threshold) body.threshold = numeric;
      if (enabled !== rule.enabled) body.enabled = enabled;
      const response = await getApiClient().patchRule(profile.profileId, rule.ruleId, body);
      applyProfile({ ...profile, version: response.profileVersion, rules: profile.rules.map(r => (r.ruleId === rule.ruleId ? response.rule : r)) });
      announce(tr({ en: `Rule “${tr(rule.label)}” saved; earlier briefs are now out of date.`, fr: `Règle « ${tr(rule.label)} » enregistrée ; les notes antérieures sont périmées.` }));
    } catch (caught) {
      const apiError = asApiError(caught);
      setError(apiError);
      if (apiError.code === 'conflict') reloadProfiles();
    } finally { setSaving(false); }
  };

  return (
    <div className="field">
      {rule.threshold !== null && (
        <>
          <label htmlFor={inputId} className="small">{tr({ en: 'Threshold', fr: 'Seuil' })} ({rule.unit})</label>
          <input id={inputId} type="number" value={threshold} onChange={e => setThreshold(e.target.value)}
            {...(bounds ? { min: bounds.min, max: bounds.max, step: bounds.step } : {})} aria-invalid={invalid}
            aria-describedby={`${inputId}-hint`} />
          <span id={`${inputId}-hint`} className="hint">
            {bounds ? `${fmtUnit(bounds.min, rule.unit, lang)} – ${fmtUnit(bounds.max, rule.unit, lang)}` : ''}
          </span>
        </>
      )}
      <label className="small rule-enabled">
        <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
        {tr({ en: 'Enabled', fr: 'Activée' })}
      </label>
      {invalid && <span className="field-error">{tr({ en: 'Outside the allowed range', fr: 'Hors de la plage permise' })}</span>}
      <div className="row-actions rule-edit-actions">
        <button type="button" className="btn ghost btn-sm" disabled={!changed || invalid} onClick={() => onPreview(rule, numeric, enabled)}>
          {tr({ en: 'Preview', fr: 'Aperçu' })}
        </button>
        <button type="button" className="btn btn-sm" disabled={!changed || invalid || saving} onClick={() => void save()}>
          {tr({ en: 'Save', fr: 'Enregistrer' })}
        </button>
      </div>
      {error && (
        <span className="field-error" role="alert">
          {error.code === 'conflict'
            ? tr({ en: 'This rule changed elsewhere or cannot be edited; profiles were reloaded.', fr: 'Cette règle a changé ailleurs ou n’est pas modifiable ; les profils ont été rechargés.' })
            : error.message}
        </span>
      )}
    </div>
  );
}

function Rules({ profile, overview, scope }: { profile: Profile; overview: OverviewResponse | null; scope: FactScope | null }) {
  const { tr, windowSpec, applyProfile, announce } = useApp();
  const [preview, setPreview] = useState<{ result: CheckResult | null; error: ApiRequestError | null; ruleLabel: string } | null>(null);
  const [deriveOpen, setDeriveOpen] = useState(false);
  const [derived, setDerived] = useState<DeriveRulesResponse | null>(null);
  const [deriveError, setDeriveError] = useState<ApiRequestError | null>(null);

  const runPreview = async (rule: PolicyRule, threshold: number | null, enabled: boolean) => {
    setPreview({ result: null, error: null, ruleLabel: tr(rule.label) });
    try {
      const result = await getApiClient().check({
        profileId: profile.profileId, move: null, window: windowSpec,
        ruleOverrides: [{ ruleId: rule.ruleId, enabled, ...(threshold !== null ? { threshold } : {}) }],
      });
      setPreview({ result, error: null, ruleLabel: tr(rule.label) });
    } catch (error) {
      setPreview({ result: null, error: asApiError(error), ruleLabel: tr(rule.label) });
    }
  };

  const derive = async (reset: boolean) => {
    setDeriveOpen(false); setDeriveError(null);
    try {
      const response = await getApiClient().deriveRules(profile.profileId, { reset, window: windowSpec });
      applyProfile({ ...profile, rules: response.rules, version: response.profileVersion });
      setDerived(response);
      announce(tr({ en: 'Derived rules restored; earlier briefs are now stale.', fr: 'Règles dérivées restaurées ; les notes antérieures sont périmées.' }));
    } catch (error) { setDeriveError(asApiError(error)); }
  };

  const previewScope = useMemo<FactScope | null>(() => (preview?.result
    ? { kind: 'local', label: { en: 'Unsaved rule preview.', fr: 'Aperçu de règle non enregistré.' }, facts: preview.result.facts }
    : null), [preview]);
  const derivedScope = useMemo<FactScope | null>(() => (derived
    ? { kind: 'local', label: { en: 'Rule derivation inputs.', fr: 'Intrants de dérivation des règles.' }, facts: derived.facts }
    : null), [derived]);

  // One row per profile rule: the overview has no check for a disabled rule, which must stay
  // listed (marked disabled, with its toggle) so it can be enabled again.
  const checks = planRuleRows(profile.rules, overview ? overview.ruleChecks : null);
  const disabled = disabledRules(profile.rules);

  const table = (
    <RuleTable checks={checks} rules={profile.rules} caption={tr({ en: 'Rules of this plan', fr: 'Règles de ce plan' })}
      renderEdit={rule => <RuleEditor key={`${rule.ruleId}-${profile.version}`} rule={rule} profile={profile} onPreview={(r, t, e) => void runPreview(r, t, e)} />} />
  );

  return (
    <Card id="rules" section={tr({ en: 'Rules', fr: 'Règles' })} tour="rules" title={tr({ en: 'Plan rules', fr: 'Règles du plan' })}
      info={tr({ en: 'Each rule is an editable assumption: change a threshold, preview the effect, then save. Saving makes earlier briefs out of date.', fr: 'Chaque règle est une hypothèse modifiable : changez un seuil, prévisualisez l’effet, puis enregistrez. Enregistrer rend les notes antérieures périmées.' })}
      actions={<button type="button" className="btn ghost btn-sm" onClick={() => setDeriveOpen(o => !o)} aria-expanded={deriveOpen}>{tr({ en: 'Restore derived rules', fr: 'Restaurer les règles dérivées' })}</button>}>
      {deriveOpen && (
        <div className="state" role="group" aria-label={tr({ en: 'Restore derived rules', fr: 'Restaurer les règles dérivées' })}>
          <p className="state-title">{tr({ en: 'Recompute derived thresholds from the risk level, horizon and preferences?', fr: 'Recalculer les seuils dérivés à partir du risque, de l’horizon et des préférences ?' })}</p>
          <div className="row-actions">
            <button type="button" className="btn ghost btn-sm" onClick={() => void derive(false)}>{tr({ en: 'Keep my edits', fr: 'Garder mes modifications' })}</button>
            <button type="button" className="btn danger btn-sm" onClick={() => void derive(true)}>{tr({ en: 'Reset my edits too', fr: 'Réinitialiser aussi mes modifications' })}</button>
            <button type="button" className="btn ghost btn-sm" onClick={() => setDeriveOpen(false)}>{tr({ en: 'Cancel', fr: 'Annuler' })}</button>
          </div>
        </div>
      )}
      {deriveError && <ErrorState error={deriveError} />}
      {derived && derivedScope && (
        <FactScopeProvider scope={derivedScope}>
          <p className="small">{tr({ en: 'Derived rules applied. Based on:', fr: 'Règles dérivées appliquées. Fondées sur :' })} {Object.entries(derived.facts).map(([id, fact]) => <FactChip key={id} factId={id} display={`${tr(fact.label)}: ${tr(fact.display)}`} />)}</p>
        </FactScopeProvider>
      )}
      {overview === null && <p className="small muted">{tr({ en: 'Statuses appear once the portfolio figures load; the rules below come from the profile', fr: 'Les statuts apparaissent une fois les chiffres chargés ; les règles ci-dessous viennent du profil' })}</p>}
      {disabled.length > 0 && (
        <p className="small muted">
          {tr({ en: 'Disabled, not counted in the plan verdict:', fr: 'Désactivées, non comptées dans le verdict du plan :' })}{' '}
          {disabled.map(rule => tr(rule.label)).join(', ')}.{' '}
          {tr({ en: 'Each stays listed below and can be enabled again.', fr: 'Chacune reste listée ci-dessous et peut être réactivée.' })}
        </p>
      )}
      {scope ? <FactScopeProvider scope={scope}>{table}</FactScopeProvider> : table}
      {preview && (
        <div className="card rule-preview" aria-live="polite">
          <p className="eyebrow">{tr({ en: 'Unsaved preview', fr: 'Aperçu non enregistré' })} · {preview.ruleLabel}</p>
          {!preview.result && !preview.error && <Loading />}
          {preview.error && <ErrorState error={preview.error} />}
          {preview.result && previewScope && (
            <FactScopeProvider scope={previewScope}>
              <VerdictBadge verdict={preview.result.verdict} />
              <CountsLine counts={preview.result.counts} />
              <RuleTable checks={preview.result.ruleChecks} rules={profile.rules} caption={tr({ en: 'Preview rule checks', fr: 'Vérifications en aperçu' })} />
            </FactScopeProvider>
          )}
        </div>
      )}
    </Card>
  );
}

function Frontier({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, feature, windowCode, lang } = app;
  const [active, setActive] = useState(false);
  const base = profileKey(app);
  // Loaded on demand: the request starts the first time the fold opens.
  const frontier = useQuery<FrontierResponse>(active && base ? `frontier|${base}|${windowCode}` : null,
    signal => getApiClient().frontier(profile.profileId, windowCode, signal));
  if (!feature('frontier_chart')) return null;
  return (
    <details className="fold section-fold" id="frontier" data-tour="frontier" onToggle={event => { if (event.currentTarget.open) setActive(true); }}>
      <summary>{tr({ en: 'Risk/return frontier (historical)', fr: 'Frontière risque/rendement (historique)' })}</summary>
      <div className="fold-body">
        <p className="small muted">{tr({ en: 'Points illustrate the past sample, not optimal future portfolios.', fr: 'Les points illustrent l’échantillon passé, pas des portefeuilles futurs optimaux.' })}</p>
        {frontier.loading && <Loading />}
        {frontier.error && <ErrorState error={frontier.error} onRetry={frontier.reload} />}
        {frontier.data && <FrontierChart data={frontier.data} lang={lang} />}
      </div>
    </details>
  );
}

function FrontierChart({ data, lang }: { data: FrontierResponse; lang: Lang }) {
  const { tr } = useApp();
  const [picked, setPicked] = useState<{ label: string; weights: { ticker: string; weightPct: number }[] } | null>(null);
  const points = [...data.assets, ...data.minVarFrontier, ...data.histMvFrontier, data.portfolio, ...(data.portfolioAfter ? [data.portfolioAfter] : [])];
  if (points.length === 0) return <Unavailable title={tr({ en: 'No frontier points returned.', fr: 'Aucun point de frontière retourné.' })} />;
  const W = 640; const H = 300; const P = 48;
  const xs = points.map(p => p.volPct); const ys = points.map(p => p.histReturnPct);
  const xMin = Math.min(0, ...xs); const xMax = Math.max(...xs, data.volBudgetPct) * 1.05;
  const yMin = Math.min(...ys); const yMax = Math.max(...ys);
  const x = (v: number) => P + ((v - xMin) / Math.max(1e-9, xMax - xMin)) * (W - 2 * P);
  const y = (v: number) => H - P - ((v - yMin) / Math.max(1e-9, yMax - yMin)) * (H - 2 * P);
  const line = (pts: { volPct: number; histReturnPct: number }[]) => pts.map(p => `${x(p.volPct)},${y(p.histReturnPct)}`).join(' ');
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label={tr({ en: 'Frontier chart; a list of points follows', fr: 'Graphique de frontière ; une liste des points suit' })}>
        <line x1={x(data.volBudgetPct)} x2={x(data.volBudgetPct)} y1={P / 2} y2={H - P} stroke="var(--tension-fg)" strokeDasharray="4 4" />
        <polyline points={line(data.minVarFrontier)} fill="none" stroke="var(--chart-1)" strokeWidth={2} />
        <polyline points={line(data.histMvFrontier)} fill="none" stroke="var(--chart-4)" strokeWidth={2} strokeDasharray="6 4" />
        {data.assets.map(a => <circle key={a.ticker} cx={x(a.volPct)} cy={y(a.histReturnPct)} r={3} fill="var(--text-3)" />)}
        <circle cx={x(data.portfolio.volPct)} cy={y(data.portfolio.histReturnPct)} r={6} fill="var(--text)" />
        {data.portfolioAfter && <circle cx={x(data.portfolioAfter.volPct)} cy={y(data.portfolioAfter.histReturnPct)} r={6} fill="var(--conflict-fg)" />}
        <text x={W / 2} y={H - 10} textAnchor="middle" className="chart-axis">{tr({ en: 'Historical annualized volatility (%)', fr: 'Volatilité annualisée historique (%)' })}</text>
        <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle" className="chart-axis">{tr({ en: 'Historical annualized return (%)', fr: 'Rendement annualisé historique (%)' })}</text>
      </svg>
      <div className="legend">
        <span><span className="swatch" aria-hidden="true" />{tr({ en: 'Risk-only minimum-variance curve', fr: 'Courbe de variance minimale (risque seul)' })}</span>
        <span><span className="swatch" style={{ background: 'var(--chart-4)' }} aria-hidden="true" />{tr({ en: 'Historical mean-variance illustration', fr: 'Illustration moyenne-variance historique' })}</span>
        <span><span className="swatch" style={{ background: 'var(--tension-fg)' }} aria-hidden="true" />{tr({ en: 'Volatility budget', fr: 'Budget de volatilité' })} {fmtPct(data.volBudgetPct, lang)}</span>
        <span>● {tr({ en: 'Current portfolio', fr: 'Portefeuille actuel' })}, {data.currency}, {labelOf(WINDOW, data.window.code, lang).toLowerCase()}</span>
      </div>
      <details className="fold small">
        <summary>{tr({ en: 'List of frontier points', fr: 'Liste des points de la frontière' })}</summary>
        <ul className="list-plain">
          {data.minVarFrontier.map((p, i) => (
            <li key={`mv-${i}`}>
              <button type="button" className="linklike" onClick={() => setPicked({ label: `${tr({ en: 'Minimum-variance point', fr: 'Point de variance minimale' })} ${i + 1}`, weights: p.weights })}>
                {tr({ en: 'Minimum-variance point', fr: 'Point de variance minimale' })} {i + 1}: {tr({ en: 'volatility', fr: 'volatilité' })} {fmtPct(p.volPct, lang)}, {tr({ en: 'return', fr: 'rendement' })} {fmtPct(p.histReturnPct, lang)}
              </button>
            </li>
          ))}
          {data.histMvFrontier.map((p, i) => (
            <li key={`hm-${i}`}>
              <button type="button" className="linklike" onClick={() => setPicked({ label: `${tr({ en: 'Mean-variance point', fr: 'Point moyenne-variance' })} ${i + 1}`, weights: p.weights })}>
                {tr({ en: 'Mean-variance point', fr: 'Point moyenne-variance' })} {i + 1}: {tr({ en: 'volatility', fr: 'volatilité' })} {fmtPct(p.volPct, lang)}, {tr({ en: 'return', fr: 'rendement' })} {fmtPct(p.histReturnPct, lang)}
              </button>
            </li>
          ))}
        </ul>
      </details>
      {picked && (
        <div className="state" aria-live="polite">
          <p className="state-title">{picked.label}: {tr({ en: 'hypothetical weights (inspection only; not saved, not a recommendation)', fr: 'pondérations hypothétiques (consultation seulement ; non enregistrées, pas une recommandation)' })}</p>
          <p className="small mono">{picked.weights.map(w => `${w.ticker} ${fmtPct(w.weightPct, lang)}`).join(' · ')}</p>
        </div>
      )}
      <LimitationList codes={data.limitations} />
    </figure>
  );
}
