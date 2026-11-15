'use client';
/**
 * Portfolio — holdings, rules and descriptive risk (T13, web/page-specs/portfolio.md). Rule edits PATCH
 * one threshold/flag and adopt the returned profileVersion, which re-keys overview and brief caches
 * (PORT-02). Previews go through /check with overrides and are never saved implicitly.
 */
import { useMemo, useState } from 'react';
import type {
  CheckResult, DeriveRulesResponse, FrontierResponse, Lang, OverviewResponse, PolicyRule, Profile,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { CountsLine, VerdictBadge } from '../../components/common/Badges';
import { RuleTable } from '../../components/run/RuleTable';
import { GroupBars } from '../../components/run/Results';
import { ASSET_CLASS, labelOf } from '../../lib/labels';
import { factIdFor, fmtMoney, fmtNumber, fmtPct, fmtSignedPct, fmtUnit } from '../../lib/format';
import { disabledRules, planRuleRows } from '../../lib/planRules';

export function PortfolioPage() {
  return <ProfileGate>{profile => <PortfolioContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

function PortfolioContent({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, windowCode, lang } = app;
  const base = profileKey(app);
  const overview = useQuery<OverviewResponse>(base && `overview|${base}|${windowCode}`,
    signal => getApiClient().overview(profile.profileId, windowCode, signal));
  const scope = useMemo<FactScope | null>(() => (overview.data
    ? { kind: 'local', label: { en: 'Deterministic overview response (no model).', fr: 'Réponse d’aperçu déterministe (aucun modèle).' }, facts: overview.data.facts }
    : null), [overview.data]);

  return (
    <>
      <PageHeader eyebrow={tr({ en: 'Fictional portfolio', fr: 'Portefeuille fictif' })}
        title={tr({ en: `${profile.name}: holdings, rules and risk`, fr: `${profile.name} : positions, règles et risque` })}>
        <p className="page-sub">
          {tr({ en: 'All values are in', fr: 'Toutes les valeurs sont en' })} {profile.portfolio.currency} · {fmtMoney(profile.portfolio.totalValue, profile.portfolio.currency, lang)} {tr({ en: 'fictional capital', fr: 'de capital fictif' })} · {tr({ en: 'profile version', fr: 'version du profil' })} {profile.version}
        </p>
      </PageHeader>
      {overview.loading && <Loading />}
      {overview.error && <ErrorState error={overview.error} onRetry={overview.reload}
        title={tr({ en: 'The portfolio overview is unavailable. No figures are shown.', fr: 'L’aperçu du portefeuille est indisponible. Aucun chiffre n’est affiché.' })} />}
      {overview.data && scope && (
        <FactScopeProvider scope={scope}>
          <Holdings overview={overview.data} />
          <Allocation overview={overview.data} />
          <Risk overview={overview.data} />
        </FactScopeProvider>
      )}
      <Rules profile={profile} overview={overview.data} scope={scope} />
      <Frontier profile={profile} />
      {overview.data && <LimitationList codes={overview.data.limitations} />}
    </>
  );
}

function Holdings({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const snapshot = overview.snapshot;
  const returns = new Map(overview.concentration.topPositions.map(p => [p.ticker, p.return1yPct]));
  const total = snapshot.positions.reduce((s, p) => s + p.weightPct, 0);
  return (
    <Card id="holdings" title={tr({ en: 'Holdings', fr: 'Positions' })}>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Holdings table', fr: 'Tableau des positions' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
              <th scope="col">{tr({ en: 'Class', fr: 'Catégorie' })}</th>
              <th scope="col">{tr({ en: 'Sector label', fr: 'Secteur' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Market value', fr: 'Valeur' })} ({snapshot.currency})</th>
              <th scope="col" className="num-col">{tr({ en: '1-year return (historical)', fr: 'Rendement 1 an (historique)' })}</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.positions.map(p => {
              const r = returns.get(p.ticker);
              return (
                <tr key={p.ticker}>
                  <th scope="row"><span className="mono">{p.ticker}</span><span className="block small muted">{p.name}</span></th>
                  <td>{labelOf(ASSET_CLASS, p.assetClass, lang)}</td>
                  <td>{p.sector}</td>
                  <td className="num-col num">{fmtPct(p.weightPct, lang)}</td>
                  <td className="num-col num">{fmtMoney(p.marketValue, snapshot.currency, lang)}</td>
                  <td className="num-col num">
                    {r === undefined
                      ? <span className="muted" title={tr({ en: 'Not supplied for this holding', fr: 'Non fourni pour cette position' })}>—</span>
                      : r === null ? tr({ en: 'Unavailable', fr: 'Indisponible' }) : fmtSignedPct(r, lang)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={3}>{tr({ en: 'Total', fr: 'Total' })} ({snapshot.positions.length})</th>
              <td className="num-col num">{fmtPct(total, lang, 2)}</td>
              <td className="num-col num">{fmtMoney(snapshot.totalValue, snapshot.currency, lang)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="small muted">{tr({ en: 'This is a fictional simulation portfolio. No transfer or order can be made from here.', fr: 'Ceci est un portefeuille de simulation fictif. Aucun transfert ni ordre ne peut être fait ici.' })}</p>
    </Card>
  );
}

function Allocation({ overview }: { overview: OverviewResponse }) {
  const { tr } = useApp();
  const s = overview.snapshot;
  return (
    <div className="grid-3">
      <Card title={tr({ en: 'By asset group', fr: 'Par groupe d’actifs' })}>
        <GroupBars items={s.byAssetGroup} label={tr({ en: 'Allocation by asset group', fr: 'Répartition par groupe d’actifs' })} />
      </Card>
      <Card title={tr({ en: 'By sector (direct equities)', fr: 'Par secteur (actions directes)' })}>
        {s.bySector.length === 0
          ? <p className="muted small">{tr({ en: 'No direct single-name equities.', fr: 'Aucune action individuelle directe.' })}</p>
          : <GroupBars items={s.bySector} label={tr({ en: 'Sector weights', fr: 'Poids sectoriels' })} render={k => k} />}
        <p className="small muted">{tr({ en: 'Direct single-name equities only; funds are not looked through.', fr: 'Actions individuelles directes seulement ; les fonds ne sont pas décomposés.' })}</p>
      </Card>
      <Card title={tr({ en: 'By listing country', fr: 'Par pays de cotation' })}>
        <GroupBars items={s.byCountry} label={tr({ en: 'Country weights', fr: 'Poids par pays' })} render={k => k} />
        <p className="small muted">{tr({ en: 'Listing-country proxy, not economic exposure.', fr: 'Approximation par pays de cotation, pas l’exposition économique.' })}</p>
      </Card>
    </div>
  );
}

function Risk({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const { risk, concentration, correlation } = overview;
  const cell = (value: number | null, key: string, signed = false) => {
    if (value === null) return <span className="small muted">{tr({ en: 'Unavailable for this period.', fr: 'Indisponible pour cette période.' })}</span>;
    const text = signed ? fmtSignedPct(value, lang) : fmtPct(value, lang);
    const factId = factIdFor(risk.factIds, key);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
  return (
    <Card id="risk" title={tr({ en: 'Descriptive risk (historical, in this sample)', fr: 'Risque descriptif (historique, dans cet échantillon)' })}>
      <div className="tiles">
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })}</span><span className="big">{cell(risk.volatilityPct, 'volatilityPct')}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })}</span><span className="big">{cell(risk.maxDrawdownPct, 'maxDrawdownPct')}</span><span className="small muted">{tr({ en: 'positive loss', fr: 'perte positive' })}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: '2022 replay return', fr: 'Rendement rejoué 2022' })}</span><span className="big">{cell(risk.stress2022Pct, 'stress2022Pct', true)}</span><span className="small muted">{tr({ en: 'signed; the stress rule compares the loss as a positive number', fr: 'signé ; la règle de stress compare la perte en nombre positif' })}</span></div>
        <div className="tile"><span className="eyebrow block">{tr({ en: 'Worst 12 months', fr: 'Pires 12 mois' })}</span><span className="big">{cell(risk.worst12mPct, 'worst12mPct', true)}</span></div>
        <div className="tile"><span className="eyebrow block">HHI · {tr({ en: 'effective N', fr: 'N effectif' })}</span><span className="big num">{fmtNumber(concentration.hhi, lang, 3)} · {fmtNumber(concentration.effectiveN, lang, 1)}</span></div>
      </div>
      <h3 className="h4">{tr({ en: 'Correlation of daily returns', fr: 'Corrélation des rendements quotidiens' })}</h3>
      {correlation === null
        ? <p className="small muted">{tr({ en: 'Not shown: more than 20 positions or not supplied.', fr: 'Non affichée : plus de 20 positions ou non fournie.' })}</p>
        : (
          <div className="table-scroll" role="region" aria-label={tr({ en: 'Correlation matrix', fr: 'Matrice de corrélation' })} tabIndex={0}>
            <table className="data-table">
              <thead><tr><th scope="col"><span className="sr-only">{tr({ en: 'Asset', fr: 'Actif' })}</span></th>{correlation.tickers.map(t => <th key={t} scope="col" className="corr-cell mono">{t}</th>)}</tr></thead>
              <tbody>
                {correlation.tickers.map((t, i) => (
                  <tr key={t}>
                    <th scope="row" className="mono">{t}</th>
                    {correlation.matrix[i]?.map((v, j) => <td key={j} className="corr-cell">{Number.isFinite(v) ? fmtNumber(v, lang, 2) : '—'}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
      announce(tr({ en: `Rule ${rule.code} saved; earlier briefs are now stale.`, fr: `Règle ${rule.code} enregistrée ; les notes antérieures sont périmées.` }));
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
      <label className="small" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
        <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />
        {tr({ en: 'Enabled', fr: 'Activée' })}
      </label>
      {invalid && <span className="field-error">{tr({ en: 'Outside the allowed range.', fr: 'Hors de la plage permise.' })}</span>}
      <div className="row-actions" style={{ marginTop: 4 }}>
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
  const [preview, setPreview] = useState<{ result: CheckResult | null; error: ApiRequestError | null; ruleCode: string } | null>(null);
  const [deriveOpen, setDeriveOpen] = useState(false);
  const [derived, setDerived] = useState<DeriveRulesResponse | null>(null);
  const [deriveError, setDeriveError] = useState<ApiRequestError | null>(null);

  const runPreview = async (rule: PolicyRule, threshold: number | null, enabled: boolean) => {
    setPreview({ result: null, error: null, ruleCode: rule.code });
    try {
      const result = await getApiClient().check({
        profileId: profile.profileId, move: null, window: windowSpec,
        ruleOverrides: [{ ruleId: rule.ruleId, enabled, ...(threshold !== null ? { threshold } : {}) }],
      });
      setPreview({ result, error: null, ruleCode: rule.code });
    } catch (error) {
      setPreview({ result: null, error: asApiError(error), ruleCode: rule.code });
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
    ? { kind: 'local', label: { en: 'Unsaved rule preview (/check, no model).', fr: 'Aperçu de règle non enregistré (/check, sans modèle).' }, facts: preview.result.facts }
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
    <Card id="rules" title={tr({ en: 'Plan rules (editable assumptions)', fr: 'Règles du plan (hypothèses modifiables)' })}
      actions={<button type="button" className="btn ghost btn-sm" onClick={() => setDeriveOpen(o => !o)} aria-expanded={deriveOpen}>{tr({ en: 'Restore derived rules…', fr: 'Restaurer les règles dérivées…' })}</button>}>
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
          <p className="small">{tr({ en: 'Derived rules applied. Derivation inputs:', fr: 'Règles dérivées appliquées. Intrants :' })} {Object.keys(derived.facts).map(id => <FactChip key={id} factId={id} />)}</p>
        </FactScopeProvider>
      )}
      {overview === null && <p className="small muted">{tr({ en: 'Statuses need the overview; rule definitions are shown from the profile.', fr: 'Les statuts nécessitent l’aperçu ; les définitions viennent du profil.' })}</p>}
      {disabled.length > 0 && (
        <p className="small muted">
          {tr({ en: 'Disabled, not counted in the plan verdict:', fr: 'Désactivées, non comptées dans le verdict du plan :' })}{' '}
          <span className="mono">{disabled.map(rule => rule.code).join(', ')}</span>.{' '}
          {tr({ en: 'Each stays listed below and can be enabled again.', fr: 'Chacune reste listée ci-dessous et peut être réactivée.' })}
        </p>
      )}
      {scope ? <FactScopeProvider scope={scope}>{table}</FactScopeProvider> : table}
      {preview && (
        <div className="card" style={{ marginTop: 16 }} aria-live="polite">
          <p className="eyebrow">{tr({ en: `Unsaved preview with ${preview.ruleCode} changed`, fr: `Aperçu non enregistré avec ${preview.ruleCode} modifiée` })}</p>
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
  const frontier = useQuery<FrontierResponse>(active && base ? `frontier|${base}|${windowCode}` : null,
    signal => getApiClient().frontier(profile.profileId, windowCode, signal));
  if (!feature('frontier_chart')) return null;
  return (
    <Card id="frontier" title={tr({ en: 'Risk/return frontier (historical, in this sample)', fr: 'Frontière risque/rendement (historique, dans cet échantillon)' })}
      actions={!active ? <button type="button" className="btn ghost btn-sm" onClick={() => setActive(true)}>{tr({ en: 'Load frontier', fr: 'Charger la frontière' })}</button> : undefined}>
      {!active && <p className="small muted">{tr({ en: 'Loaded on demand. Points illustrate the past sample, not optimal future portfolios.', fr: 'Chargée à la demande. Les points illustrent l’échantillon passé, pas des portefeuilles futurs optimaux.' })}</p>}
      {frontier.loading && <Loading />}
      {frontier.error && <ErrorState error={frontier.error} onRetry={frontier.reload} />}
      {frontier.data && <FrontierChart data={frontier.data} lang={lang} />}
    </Card>
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
        <line x1={x(data.volBudgetPct)} x2={x(data.volBudgetPct)} y1={P / 2} y2={H - P} stroke="#E3A53B" strokeDasharray="4 4" />
        <polyline points={line(data.minVarFrontier)} fill="none" stroke="#0B5E66" strokeWidth={2} />
        <polyline points={line(data.histMvFrontier)} fill="none" stroke="#8FA3B6" strokeWidth={2} strokeDasharray="6 4" />
        {data.assets.map(a => <circle key={a.ticker} cx={x(a.volPct)} cy={y(a.histReturnPct)} r={3} fill="#4A5B6C" />)}
        <circle cx={x(data.portfolio.volPct)} cy={y(data.portfolio.histReturnPct)} r={6} fill="#12202F" />
        {data.portfolioAfter && <circle cx={x(data.portfolioAfter.volPct)} cy={y(data.portfolioAfter.histReturnPct)} r={6} fill="#8A1B12" />}
        <text x={W / 2} y={H - 10} textAnchor="middle" className="chart-axis">{tr({ en: 'Historical annualized volatility (%)', fr: 'Volatilité annualisée historique (%)' })}</text>
        <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle" className="chart-axis">{tr({ en: 'Historical annualized return (%)', fr: 'Rendement annualisé historique (%)' })}</text>
      </svg>
      <div className="legend">
        <span><span className="swatch" aria-hidden="true" />{tr({ en: 'Risk-only minimum-variance curve', fr: 'Courbe de variance minimale (risque seul)' })}</span>
        <span><span className="swatch" style={{ background: '#8FA3B6' }} aria-hidden="true" />{tr({ en: 'Historical mean-variance illustration', fr: 'Illustration moyenne-variance historique' })}</span>
        <span><span className="swatch" style={{ background: '#E3A53B' }} aria-hidden="true" />{tr({ en: 'Volatility budget', fr: 'Budget de volatilité' })} {fmtPct(data.volBudgetPct, lang)}</span>
        <span>● {tr({ en: 'Current portfolio', fr: 'Portefeuille actuel' })} · {data.currency} · {data.window.code}</span>
      </div>
      <details className="small">
        <summary>{tr({ en: 'List of frontier points', fr: 'Liste des points de la frontière' })}</summary>
        <ul className="list-plain">
          {data.minVarFrontier.map((p, i) => (
            <li key={`mv-${i}`}>
              <button type="button" className="linklike" onClick={() => setPicked({ label: `MinVar ${i + 1}`, weights: p.weights })}>
                MinVar {i + 1}: {fmtPct(p.volPct, lang)} / {fmtPct(p.histReturnPct, lang)}
              </button>
            </li>
          ))}
          {data.histMvFrontier.map((p, i) => (
            <li key={`hm-${i}`}>
              <button type="button" className="linklike" onClick={() => setPicked({ label: `MV ${i + 1}`, weights: p.weights })}>
                MV {i + 1}: {fmtPct(p.volPct, lang)} / {fmtPct(p.histReturnPct, lang)}
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
