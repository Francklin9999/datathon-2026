'use client';
/**
 * Home — Portfolio Analyst Brief (T13, web/page-specs/home.md) as a dashboard: a scope bar (period,
 * benchmark, asset classes, minimum weight, chart view) drives every widget, and the widgets can be
 * moved and resized (stored layout). Deterministic overview and performance load in parallel; the
 * cached brief is fetched separately and at most one automatic portfolio_brief run is created per
 * cache key (HOME-02). Refresh creates a real run.
 */
import Link from 'next/link';
import { LayoutGrid, RotateCcw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type {
  AssetsResponse, CachedBriefResponse, I18NText, OverviewResponse, PerformanceResponse, Profile, RuleCheck, RuleStatus, Run,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery, type QueryState } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge, StatusBadge, VerdictBadge } from '../../components/common/Badges';
import { LineChart, SeriesTable, type Series } from '../../components/common/LineChart';
import { BriefView, SentenceText } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import { NEE_REASON, OBJECTIVE, RISK_LEVEL, RUN_STATUS, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate, fmtSignedPct, fmtUnit } from '../../lib/format';
import { portfolioSummary } from '../../lib/brief';
import { isTerminal } from '../../lib/runs';
import type { LayoutItem, WidgetLimits } from '../../lib/ui/layout';
import { ASSET_GROUPS, scopeWindow, scopeWindowKey, type DashboardScope } from '../../lib/ui/scope';
import { drawdownSeries, indexSeries, periodChangePct } from '../../lib/ui/series';
import { Reveal } from '../../components/ui/Reveal';
import { AllocationCard } from './AllocationCard';
import { DashboardGrid, type WidgetDef } from './DashboardGrid';
import { KeyFigures, KeyFiguresSkeleton } from './KeyFigures';
import { DiversificationCard, HorizonsCard, StressCard } from './FigureCards';
import { ScopeBar, periodLabel } from './ScopeBar';
import { PositionsCard } from './PositionsCard';
import { useDashboardScope } from './useDashboardScope';

/** Run started for each cache key in this page load (survives navigation between pages). */
const startedRuns = new Map<string, string>();
/** Cache keys for which an automatic brief run was already requested in this page load. */
const autoRequested = new Set<string>();

/** Default arrangement (12 columns × 32 px rows) and the size limits of each widget. */
const DEFAULT_LAYOUT: readonly LayoutItem[] = [
  { id: 'figures', w: 12, h: 5 },
  { id: 'performance', w: 8, h: 11 },
  { id: 'allocation', w: 4, h: 11 },
  { id: 'brief', w: 12, h: 14 },
  { id: 'positions', w: 7, h: 10 },
  { id: 'health', w: 5, h: 10 },
  { id: 'horizons', w: 4, h: 5 },
  { id: 'stress', w: 4, h: 5 },
  { id: 'diversification', w: 4, h: 5 },
];
const LIMITS: Record<string, WidgetLimits> = {
  figures: { minW: 6, maxW: 12, minH: 5, maxH: 7 },
  performance: { minW: 5, maxW: 12, minH: 8, maxH: 18 },
  allocation: { minW: 3, maxW: 8, minH: 8, maxH: 14 },
  positions: { minW: 4, maxW: 12, minH: 6, maxH: 18 },
  health: { minW: 4, maxW: 12, minH: 6, maxH: 18 },
  horizons: { minW: 3, maxW: 6, minH: 4, maxH: 8 },
  stress: { minW: 3, maxW: 6, minH: 4, maxH: 8 },
  diversification: { minW: 3, maxW: 6, minH: 4, maxH: 8 },
  brief: { minW: 6, maxW: 12, minH: 6, maxH: 24 },
};

export function HomePage() {
  return <ProfileGate>{profile => <HomeContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

export function horizonText(profile: Pick<Profile, 'horizonYears'>, tr: (t: I18NText) => string): string {
  const { min, max } = profile.horizonYears;
  if (max === null) return tr({ en: `${min}+ years`, fr: `${min} ans et plus` });
  return tr({ en: `${min}–${max} years`, fr: `${min} à ${max} ans` });
}

function HomeContent({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang, windowCode, setWindow, meta, announce } = app;
  const client = getApiClient();
  const base = profileKey(app);
  const [scope, setScope] = useDashboardScope();
  const windowSpec = scopeWindow(scope, windowCode);
  const windowKey = scopeWindowKey(scope, windowCode);
  const overview = useQuery<OverviewResponse>(base && `overview|${base}|${windowKey}`,
    signal => client.overview(profile.profileId, windowSpec, signal));
  const performance = useQuery<PerformanceResponse>(base && `performance|${base}|${windowKey}|${scope.benchmark ?? '-'}`,
    signal => client.performance(profile.profileId, windowSpec, signal, scope.benchmark));
  const assets = useQuery<AssetsResponse>(base && `assets|${meta?.dataVersion ?? ''}`, signal => client.assets({ limit: 200 }, signal));
  const overviewScope = useMemo<FactScope | null>(() => (overview.data
    ? { kind: 'local', label: { en: 'Deterministic overview response (no model).', fr: 'Réponse d’aperçu déterministe (aucun modèle).' }, facts: overview.data.facts }
    : null), [overview.data]);
  const [editing, setEditing] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [stacked, setStacked] = useState(false);
  const period = periodLabel(scope, windowCode, lang);

  const benchmarks = useMemo(() => (assets.data?.items ?? [])
    .filter(a => a.assetClass.startsWith('etf'))
    .map(a => ({ value: a.ticker, label: a.ticker, meta: a.name })), [assets.data]);
  const groups = useMemo(() => {
    const present = overview.data?.snapshot.byAssetGroup.map(g => g.key) ?? [];
    return ASSET_GROUPS.filter(g => present.includes(g) || scope.assetGroups.includes(g));
  }, [overview.data, scope.assetGroups]);

  const labels = useMemo(() => ({
    moved: (title: string, position: number, total: number) => tr({ en: `${title} moved to position ${position} of ${total}`, fr: `${title} déplacé en position ${position} sur ${total}` }),
    resized: (title: string, w: number, h: number) => tr({ en: `${title} resized to ${w} columns by ${h} rows`, fr: `${title} redimensionné à ${w} colonnes sur ${h} lignes` }),
  }), [tr]);

  const data = overview.data;
  const widgets = useMemo<WidgetDef[]>(() => {
    if (!data) return [];
    const t = (en: string, fr: string) => tr({ en, fr });
    return [
      { id: 'figures', title: t('Key figures', 'Chiffres clés'), limits: LIMITS.figures!, render: () => <KeyFigures overview={data} period={period} /> },
      { id: 'performance', title: t('Hypothetical constant-weight history', 'Historique hypothétique à pondérations constantes'), limits: LIMITS.performance!, render: () => <PerformanceCard state={performance} scope={scope} period={period} /> },
      { id: 'allocation', title: t('Allocation', 'Répartition'), limits: LIMITS.allocation!, render: () => <AllocationCard overview={data} scope={scope} /> },
      { id: 'positions', title: t('Positions', 'Positions'), limits: LIMITS.positions!, render: () => <PositionsCard overview={data} scope={scope} /> },
      { id: 'health', title: t('Plan health', 'Santé du plan'), limits: LIMITS.health!, render: () => <PlanHealth overview={data} period={period} /> },
      { id: 'horizons', title: t('Longer horizons', 'Horizons plus longs'), limits: LIMITS.horizons!, render: () => <HorizonsCard overview={data} /> },
      { id: 'stress', title: t('Stress test', 'Test de résistance'), limits: LIMITS.stress!, render: () => <StressCard overview={data} /> },
      { id: 'diversification', title: t('Diversification', 'Diversification'), limits: LIMITS.diversification!, render: () => <DiversificationCard overview={data} /> },
      { id: 'brief', title: t('Your Portfolio Intelligence Brief', 'Votre note stratégique de portefeuille'), limits: LIMITS.brief!, render: () => <AnalystBrief profile={profile} scopeNote={tr({ en: `Brief requests use the full portfolio and the global ${labelOf(WINDOW, windowCode, 'en').toLowerCase()} risk window; dashboard filters and custom dates do not apply. A cached brief may use an earlier window, as noted below.`, fr: `Les demandes de note utilisent le portefeuille complet et la fenêtre de risque globale ${labelOf(WINDOW, windowCode, 'fr').toLowerCase()} ; les filtres et dates personnalisées du tableau ne s’y appliquent pas. Une note en cache peut utiliser une fenêtre antérieure, indiquée ci-dessous.` })} /> },
    ];
  }, [data, performance, scope, period, profile, tr, windowCode]);

  return (
    <>
      <Reveal as="header" index={0} className="dash-header">
        <div className="dash-heading">
          <p className="eyebrow">{tr({ en: 'Portfolio analyst brief', fr: 'Note d’analyse du portefeuille' })}</p>
          <h1 className="page-title">{profile.name}</h1>
          <p className="page-sub">{tr(profile.blurb)}</p>
          <p className="dash-meta">
            {/* Capital is the first figure, currency/risk/data date sit in the header bar and the period in
                the scope bar: only what appears nowhere else is repeated here. */}
            <span>{tr({ en: 'Age', fr: 'Âge' })} <strong>{profile.age ?? '—'}</strong></span>
            <span>{tr({ en: 'Risk tolerance', fr: 'Tolérance au risque' })} <strong>{labelOf(RISK_LEVEL, profile.riskLevel, lang)}</strong></span>
            <span>{tr({ en: 'Horizon', fr: 'Horizon' })} <strong>{horizonText(profile, tr)}</strong></span>
            <span>{tr({ en: 'Objective', fr: 'Objectif' })} <strong>{labelOf(OBJECTIVE, profile.objective, lang)}</strong></span>
          </p>
        </div>
        <div className="dash-actions">
          <Link className="btn" href="/decision-desk/">{tr({ en: 'Test a move', fr: 'Tester un mouvement' })}</Link>
          <Link className="btn ghost" href="/portfolio/">{tr({ en: 'Inspect plan', fr: 'Examiner le plan' })}</Link>
        </div>
      </Reveal>

      <ScopeBar scope={scope} setScope={setScope} windowCode={windowCode} setWindow={setWindow}
        dataAsOf={meta?.dataAsOf ?? new Date().toISOString().slice(0, 10)} groups={groups} benchmarks={benchmarks} tr={tr} lang={lang} />

      <div className="grid-tools">
        <span className="small muted">{editing && !stacked
          ? tr({ en: 'Drag a widget by its handle, resize it from its corner, or use the arrow keys on either', fr: 'Glissez un widget par sa poignée, redimensionnez-le par son coin, ou utilisez les flèches sur l’une ou l’autre' })
          : ''}</span>
        <div className="grid-tools-actions">
          {editing && !stacked && (
            <button type="button" className="btn ghost btn-sm" onClick={() => { setResetToken(n => n + 1); announce(tr({ en: 'Default layout restored', fr: 'Disposition par défaut rétablie' })); }}>
              <RotateCcw aria-hidden="true" size={14} strokeWidth={1.5} />{tr({ en: 'Reset layout', fr: 'Disposition par défaut' })}
            </button>
          )}
          {!stacked && <button type="button" className="btn ghost btn-sm" aria-pressed={editing} onClick={() => setEditing(v => !v)}>
            <LayoutGrid aria-hidden="true" size={14} strokeWidth={1.5} />{tr({ en: 'Edit layout', fr: 'Modifier la disposition' })}
          </button>}
        </div>
      </div>

      {overview.error && <AnalystBrief profile={profile} scopeNote={tr({ en: `Brief requests use the full portfolio and the global ${labelOf(WINDOW, windowCode, 'en').toLowerCase()} risk window; dashboard filters and custom dates do not apply.`, fr: `Les demandes de note utilisent le portefeuille complet et la fenêtre de risque globale ${labelOf(WINDOW, windowCode, 'fr').toLowerCase()} ; les filtres et dates personnalisées du tableau ne s’y appliquent pas.` })} />}
      {overview.error && (
        <ErrorState error={overview.error} onRetry={overview.reload}
          title={tr({ en: 'The portfolio overview is unavailable for this scope. No summary figures are shown.', fr: 'L’aperçu du portefeuille est indisponible pour ce périmètre. Aucun chiffre de synthèse n’est affiché.' })} />
      )}
      {overview.loading && <KeyFiguresSkeleton label={tr({ en: 'Loading deterministic overview…', fr: 'Chargement de l’aperçu déterministe…' })} />}
      {data && overviewScope && (
        <FactScopeProvider scope={overviewScope}>
          <Reveal index={1}>
            <DashboardGrid widgets={widgets} defaults={DEFAULT_LAYOUT} editing={editing} resetToken={resetToken} announce={announce} labels={labels} onStackedChange={setStacked} />
          </Reveal>
        </FactScopeProvider>
      )}
    </>
  );
}

function PerformanceCard({ state, scope, period }: { state: QueryState<PerformanceResponse>; scope: DashboardScope; period: string }) {
  const { tr, lang } = useApp();
  const [asTable, setAsTable] = useState(false);
  const data = state.data;
  let body: ReactNode = null;
  let change: ReactNode = null;
  if (data && data.series.length > 1) {
    const view = (points: PerformanceResponse['series']) => (scope.chartMode === 'indexed' ? indexSeries(points)
      : scope.chartMode === 'drawdown' ? drawdownSeries(points) : points);
    const series: Series[] = [{ label: tr({ en: 'Fictional portfolio, today’s weights', fr: 'Portefeuille fictif, pondérations actuelles' }), points: view(data.series), color: 'var(--chart-1)' }];
    if (data.benchmark) series.push({ label: data.benchmark.ticker, points: view(data.benchmark.series), color: 'var(--chart-4)', dashed: true });
    const unit = scope.chartMode === 'indexed' ? tr({ en: 'index, start = 100', fr: 'indice, début = 100' })
      : scope.chartMode === 'drawdown' ? tr({ en: '% below the running peak', fr: '% sous le plus haut atteint' }) : data.currency;
    const digits = scope.chartMode === 'drawdown' ? 1 : 0;
    // Visible caption in plain words; the method code stays in the table caption for audit.
    const caption = `${period}, ${fmtDate(data.series[0]?.date ?? '', lang)} → ${fmtDate(data.series[data.series.length - 1]?.date ?? '', lang)}`;
    body = asTable
      ? <SeriesTable series={series} lang={lang} unitLabel={unit} caption={`${caption}, ${data.method}`} digits={digits} />
      : <LineChart series={series} lang={lang} unitLabel={unit} caption={caption} digits={digits} area={scope.chartMode !== 'drawdown'} />;
    const own = periodChangePct(data.series);
    const bench = data.benchmark ? periodChangePct(data.benchmark.series) : null;
    change = (
      <p className="period-change">
        {own !== null && <span>{tr({ en: 'Over the period', fr: 'Sur la période' })} <strong>{fmtSignedPct(own, lang)}</strong></span>}
        {data.benchmark && bench !== null && <span>{data.benchmark.ticker} <strong>{fmtSignedPct(bench, lang)}</strong></span>}
        <span>{tr({ en: 'read from the plotted series', fr: 'lu sur la série tracée' })}</span>
      </p>
    );
  }
  return (
    <Card title={tr({ en: 'Hypothetical constant-weight history', fr: 'Historique hypothétique à pondérations constantes' })}
      actions={data && data.series.length > 1 ? (
        <button type="button" className="btn ghost btn-sm" onClick={() => setAsTable(v => !v)}>
          {asTable ? tr({ en: 'Show chart', fr: 'Afficher le graphique' }) : tr({ en: 'Show table', fr: 'Afficher le tableau' })}
        </button>
      ) : undefined}>
      {state.loading && <Loading variant="skeleton" />}
      {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
      {data && data.series.length < 2 && <Unavailable title={tr({ en: 'Unavailable for this period', fr: 'Indisponible pour cette période' })} />}
      {change}
      {body}
      {/* Constant weights first and always visible (HOME spec); the rest fold away (deduplicated). */}
      {data && <LimitationList compactAfter={1} codes={['LIM_CONSTANT_WEIGHTS', ...data.limitations]} />}
    </Card>
  );
}

const STATUS_ORDER: readonly RuleStatus[] = ['conflict', 'tension', 'pass', 'nee', 'info'];

/** Rules with the least relative room before their threshold (same units as the rule itself). */
function closestToLimit(checks: readonly RuleCheck[], n: number): RuleCheck[] {
  const room = (c: RuleCheck) => (c.headroom ?? 0) / Math.max(1e-9, Math.abs(c.threshold ?? 0) || 1);
  return checks
    .filter(c => c.headroom !== null && c.headroom >= 0 && c.threshold !== null && c.status !== 'nee' && c.status !== 'info')
    .sort((a, b) => room(a) - room(b))
    .slice(0, n);
}

function PlanHealth({ overview, period }: { overview: OverviewResponse; period: string }) {
  const { tr, lang } = useApp();
  const nee = overview.ruleChecks.filter(c => c.status === 'nee');
  const counts = overview.counts;
  const total = STATUS_ORDER.reduce((sum, status) => sum + counts[status], 0);
  const closest = closestToLimit(overview.ruleChecks, 3);
  const figure = (value: number | null, factId: string | null, unit: RuleCheck['unit']) => {
    const text = fmtUnit(value, unit, lang);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
  return (
    <Card title={tr({ en: 'Plan health', fr: 'Santé du plan' })}
      actions={<Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'Open rules', fr: 'Ouvrir les règles' })}</Link>}>
      <div className="health-head">
        <VerdictBadge verdict={overview.verdict} large />
        <span className="small muted">{tr({ en: `${total} rule checks, ${period}`, fr: `${total} vérifications de règles, ${period}` })}</span>
      </div>
      <dl className="status-counts" aria-label={tr({ en: 'Rule checks by status', fr: 'Vérifications par statut' })}>
        {STATUS_ORDER.map(status => (
          <div key={status} className="status-count" {...(counts[status] === 0 ? { 'data-zero': 'true' } : {})}>
            <dt><StatusBadge status={status} /></dt>
            <dd><strong>{counts[status]}</strong></dd>
          </div>
        ))}
      </dl>
      {closest.length > 0 && (
        <>
          <h3 className="h4">{tr({ en: 'Closest to their limit', fr: 'Les plus proches de leur limite' })}</h3>
          <ul className="limit-list">
            {closest.map(check => (
              <li key={check.ruleId}>
                <p className="limit-detail"><span className="rule-code">{check.code}</span>{tr(check.detail)}</p>
                <p className="limit-figs small">
                  {figure(check.value, check.valueFactId, check.unit)}
                  <span> {tr({ en: 'against a limit of', fr: 'pour une limite de' })} </span>
                  {figure(check.threshold, check.thresholdFactId, check.unit)}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
      {nee.length > 0 && (
        <div className="small nee-reason">
          <p><strong>{tr({ en: 'Not enough evidence (separate from financial checks)', fr: 'Preuves insuffisantes (distinct des vérifications financières)' })}</strong></p>
          <ul className="bullets">
            {nee.map(check => (
              <li key={check.ruleId}><span className="mono">{check.code}</span> {tr(check.detail)}{check.neeReason ? ` — ${labelOf(NEE_REASON, check.neeReason, lang)}` : ''}</li>
            ))}
          </ul>
        </div>
      )}
      <LimitationList compactAfter={0} codes={overview.limitations} />
    </Card>
  );
}

function AnalystBrief({ profile, scopeNote }: { profile: Profile; scopeNote?: string }) {
  const app = useApp();
  const { tr, lang, windowCode, announce, sessionId, meta } = app;
  const base = profileKey(app);
  const cacheKey = base && `brief|${base}|${windowCode}|${lang}`;
  const cached = useQuery<CachedBriefResponse>(cacheKey, signal => getApiClient().brief(profile.profileId, lang, signal));
  // The run started for a key outlives this component: coming back to a persona, window, language
  // or to Home shows that run (or its progress) again instead of an empty card (HOME-02).
  const [runId, setRunId] = useState<string | null>(() => (cacheKey ? startedRuns.get(cacheKey) ?? null : null));
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const [creating, setCreating] = useState(false);

  // A new key (profile version, data, window, language) shows that key's own run, never stale prose.
  useEffect(() => { setRunId(cacheKey ? startedRuns.get(cacheKey) ?? null : null); setCreateError(null); }, [cacheKey]);

  const start = useCallback(async (force: boolean) => {
    if (!sessionId || !meta) return;
    setCreating(true);
    setCreateError(null);
    try {
      const idem = force ? undefined : `brief-${profile.profileId}-v${profile.version}-${meta.dataVersion}-${windowCode}-${lang}`;
      const created = await getApiClient().createRun(
        { kind: 'portfolio_brief', profileId: profile.profileId, lang, window: { code: windowCode }, ...(force ? { force: true } : {}) },
        idem,
      );
      if (cacheKey) startedRuns.set(cacheKey, created.runId);
      setRunId(created.runId);
    } catch (error) {
      setCreateError(asApiError(error));
    } finally {
      setCreating(false);
    }
  }, [sessionId, meta, profile.profileId, profile.version, windowCode, lang, cacheKey]);

  // The lookup returns the latest brief of this profile and language whatever its window.
  const cachedRun = cached.data?.run ?? null;
  const cachedWindow = cachedRun?.input.kind === 'portfolio_brief' ? cachedRun.input.window.code : null;
  const sameWindow = cachedRun !== null && cachedWindow === windowCode;

  useEffect(() => {
    if (!cacheKey || !cached.data || (cached.data.run && sameWindow) || runId) return;
    if (autoRequested.has(cacheKey)) return;
    autoRequested.add(cacheKey);
    void start(false);
  }, [cacheKey, cached.data, sameWindow, runId, start]);

  const polled = useRun(runId, finished => announce(`${tr({ en: 'Portfolio brief', fr: 'Note de portefeuille' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run: Run | null = runId ? polled.run : cachedRun;
  const stale = !runId && Boolean(cached.data?.stale);
  const otherWindow = !runId && cachedRun !== null && !sameWindow ? cachedWindow : null;
  const busy = creating || (run !== null && !isTerminal(run.status));

  return (
    <Card id="analyst-brief" title={tr({ en: 'Your Portfolio Intelligence Brief', fr: 'Votre note stratégique de portefeuille' })}
      actions={(
        <button type="button" className="btn ghost btn-sm" onClick={() => void start(true)} disabled={busy}>
          {tr({ en: 'Refresh brief', fr: 'Actualiser la note' })}
        </button>
      )}>
      {scopeNote && <p className="scope-note">{scopeNote}</p>}
      {cached.loading && <Loading label={tr({ en: 'Looking for a cached brief…', fr: 'Recherche d’une note en cache…' })} />}
      {cached.error && <ErrorState error={cached.error} onRetry={cached.reload}
        title={tr({ en: 'The analyst brief is unavailable. Deterministic cards remain valid.', fr: 'La note d’analyse est indisponible. Les cartes déterministes restent valables.' })} />}
      {createError && (
        <ErrorState error={createError} onRetry={() => void start(true)}
          title={tr({ en: 'The brief could not be started. Deterministic cards remain valid.', fr: 'La note n’a pas pu être lancée. Les cartes déterministes restent valables.' })} />
      )}
      {polled.error && <ErrorState error={polled.error} onRetry={polled.reload} />}
      {stale && run && (
        <p className="stale-note">{tr({ en: 'This brief was written for an earlier profile or data version. Refresh to update it.', fr: 'Cette note a été rédigée pour une version antérieure du profil ou des données. Actualisez pour la mettre à jour.' })}</p>
      )}
      {otherWindow && run && (
        <p className="stale-note">{tr({ en: `This brief was written for the ${labelOf(WINDOW, otherWindow, 'en')} window, not the one selected.`, fr: `Cette note a été rédigée pour la fenêtre ${labelOf(WINDOW, otherWindow, 'fr')}, pas pour celle qui est choisie.` })}</p>
      )}
      {run && <BriefRun run={run} />}
      {runId && !run && !polled.error && <Loading label={tr({ en: 'Starting brief run…', fr: 'Démarrage de la note…' })} />}
    </Card>
  );
}

function BriefRun({ run }: { run: Run }) {
  const { tr, feature } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }), [run]);
  const result = run.result?.kind === 'portfolio_brief' ? run.result.portfolioBrief : null;
  if (run.status !== 'succeeded' || !result) {
    return (
      <div>
        <p><RunStatusBadge status={run.status} /></p>
        {run.status === 'failed' && (
          <p className="small">{tr({ en: 'The brief run failed; no signed brief exists. Deterministic cards remain usable.', fr: 'L’exécution de la note a échoué ; aucune note signée n’existe. Les cartes déterministes restent utilisables.' })}</p>
        )}
        <details open={run.status !== 'failed'}>
          <summary className="small">{tr({ en: 'Execution trace', fr: 'Trace d’exécution' })}</summary>
          <RunTimeline run={run} />
        </details>
      </div>
    );
  }
  return (
    <FactScopeProvider scope={scope}>
      {run.flags.fixture && <p className="banner banner-fixture">{tr({ en: 'Development fixture — no agents executed.', fr: 'Jeu d’essai — aucun agent exécuté.' })}</p>}
      {(() => {
        const summary = portfolioSummary(result.brief);
        return summary.length > 0 && <div className="brief-section"><h3 className="h4">{tr({ en: 'Executive summary', fr: 'Résumé exécutif' })}</h3>
          {summary.map(s => <p key={s.id}><SentenceText sentence={s} /></p>)}
        </div>;
      })()}
      <div className="grid-3">
        {result.focusCards.map((card, i) => (
          <article key={i} className="scenario">
            <p className="eyebrow">{tr({ en: `Focus ${i + 1}`, fr: `Priorité ${i + 1}` })}</p>
            <h3 className="h4">{tr(card.title)}</h3>
            {card.body.filter(s => s.audit.status !== 'struck').map(sentence => (
              <p key={sentence.id} className="small"><SentenceText sentence={sentence} /></p>
            ))}
            <Link className="btn ghost btn-sm" href={card.body.some(s => s.segments.some(x => x.t === 'rule'))
              ? `/evidence-audit/?runId=${encodeURIComponent(run.runId)}`
              : card.factIds.some(id => run.facts[id]?.metric === 'weight.asset_group') ? '/sources/'
              : card.factIds.some(id => run.facts[id]?.metric === 'drawdown.max') && feature('time_machine') ? '/time-machine/' : '/portfolio/'}>
              {tr({ en: 'Open investigation', fr: 'Ouvrir la recherche' })}</Link>
          </article>
        ))}
      </div>
      <details><summary>{tr({ en: 'Methodology, assumptions and evidence gaps', fr: 'Méthode, hypothèses et preuves manquantes' })}</summary>
        <BriefView brief={{ ...result.brief, sections: result.brief.sections.map(s => ({ ...s,
          sentences: s.sentences.filter(sentence => !portfolioSummary(result.brief).some(x => x.id === sentence.id))
        })).filter(s => s.sentences.length > 0) }} />
      </details>
      <p className="row-actions small">
        <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Inspect evidence and audit', fr: 'Examiner les preuves et l’audit' })}</Link>
      </p>
    </FactScopeProvider>
  );
}
