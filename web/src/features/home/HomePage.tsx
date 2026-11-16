'use client';
/**
 * Home — Portfolio Analyst Brief (T13, web/page-specs/home.md) as a dashboard: a scope bar (period,
 * benchmark, asset classes, minimum weight, chart view; ScopeBar says which control reaches which widget) drives the widgets, and the widgets can be
 * moved by their header and resized from their corner at any time (stored layout). A widget never
 * scrolls: it shows the essentials and opens the rest in a details sheet (⤢). Deterministic overview and performance load in parallel; the
 * cached brief is fetched separately. At most one portfolio_brief run is written automatically per
 * session, profile and data version, and only when no brief of that data version exists (HOME-02,
 * lib/briefAuto.ts); otherwise the latest brief is shown with a note. Refresh creates a real run.
 */
import Link from 'next/link';
import { RotateCcw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  AssetsResponse, CachedBriefResponse, I18NText, OverviewResponse, PerformanceResponse, Profile, RuleCheck, RuleStatus, Run, WindowCode,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { prefetchQuery, useQuery, type QueryState } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, ProfileGate } from '../../components/common/Page';
import { Sheet, SheetSection, useSheet } from '../../components/common/Sheet';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { Skeleton } from '../../components/ui/Skeleton';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge, StatusBadge, VerdictBadge } from '../../components/common/Badges';
import { LineChart, SeriesTable, type Series } from '../../components/common/LineChart';
import { BriefView, SentenceText } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import { NEE_REASON, OBJECTIVE, RUN_STATUS, STEP_TYPE, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate, fmtMoney, fmtSignedPct, fmtUnit } from '../../lib/format';
import {
  briefDisplay, briefProgress, briefStaleReason, briefWindowNote, briefWindowOf, portfolioSummary, shouldAutoRunBrief, staleNote,
} from '../../lib/brief';
import { autoBriefKey, autoBriefUsed, markAutoBrief } from '../../lib/briefAuto';
import { isTerminal } from '../../lib/runs';
import type { LayoutItem, WidgetLimits } from '../../lib/ui/layout';
import { ASSET_GROUPS, scopeWindow, scopeWindowKey, type DashboardScope } from '../../lib/ui/scope';
import { drawdownSeries, indexSeries, periodChangePct, periodEnds } from '../../lib/ui/series';
import { Reveal } from '../../components/ui/Reveal';
import { CountUp } from '../../components/ui/CountUp';
import { AllocationCard } from './AllocationCard';
import { AutomationsCard } from './AutomationsCard';
import { ClosestToLimit } from './ClosestToLimit';
import { DashboardGrid, type WidgetDef } from './DashboardGrid';
import { KeyFigures, KeyFiguresSkeleton } from './KeyFigures';
import { DiversificationCard, HorizonsCard, StressCard } from './FigureCards';
import { ScopeBar, periodLabel } from './ScopeBar';
import { PositionsCard } from './PositionsCard';
import { useDashboardScope } from './useDashboardScope';

/** Run started for each cache key in this page load (survives navigation between pages). */
const startedRuns = new Map<string, string>();

/**
 * Default arrangement (12 columns × 32 px rows, 16 px gaps: a widget of h rows is 48h − 16 px tall)
 * and the size limits of each widget. Every minimum still holds the widget's essentials without
 * scrolling; lists and the chart grow with the widget.
 */
const DEFAULT_LAYOUT: readonly LayoutItem[] = [
  { id: 'figures', w: 12, h: 4 },
  { id: 'automations', w: 12, h: 4 },
  { id: 'performance', w: 8, h: 9 },
  { id: 'allocation', w: 4, h: 9 },
  { id: 'health', w: 5, h: 7 },
  { id: 'positions', w: 7, h: 7 },
  { id: 'brief', w: 12, h: 8 },
  { id: 'horizons', w: 4, h: 5 },
  { id: 'stress', w: 4, h: 5 },
  { id: 'diversification', w: 4, h: 5 },
];
const LIMITS: Record<string, WidgetLimits> = {
  figures: { minW: 6, maxW: 12, minH: 4, maxH: 7 },
  automations: { minW: 4, maxW: 12, minH: 4, maxH: 8 },
  performance: { minW: 5, maxW: 12, minH: 7, maxH: 18 },
  allocation: { minW: 3, maxW: 8, minH: 8, maxH: 14 },
  positions: { minW: 4, maxW: 12, minH: 4, maxH: 18 },
  health: { minW: 4, maxW: 12, minH: 5, maxH: 18 },
  horizons: { minW: 3, maxW: 6, minH: 5, maxH: 8 },
  stress: { minW: 3, maxW: 6, minH: 5, maxH: 8 },
  diversification: { minW: 3, maxW: 6, minH: 4, maxH: 8 },
  brief: { minW: 6, maxW: 12, minH: 6, maxH: 24 },
};

export function HomePage() {
  return <ProfileGate>{profile => <HomeContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

function briefKey(base: string, windowCode: WindowCode, lang: string): string {
  return `brief|${base}|${windowCode}|${lang}`;
}

/** Where the brief's figures come from: the whole portfolio and the global window, not the dashboard scope. */
function briefScope(windowCode: WindowCode, tr: (t: I18NText) => string): string {
  return tr({
    en: `Whole portfolio, ${labelOf(WINDOW, windowCode, 'en').toLowerCase()} window. The custom range and the asset-class and minimum-weight filters don’t apply.`,
    fr: `Portefeuille complet, fenêtre ${labelOf(WINDOW, windowCode, 'fr').toLowerCase()}. La plage personnalisée et les filtres de classes d’actifs et de poids minimum ne s’appliquent pas.`,
  });
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
  // The first and last day the API resolved for the window on screen: a new custom Range starts there.
  const shownId = overview.data?.returns.factIds.selectedPct;
  const shownFact = shownId ? overview.data?.facts[shownId] : undefined;
  const shownPeriod = shownFact?.period ? { start: shownFact.period.start, end: shownFact.period.end } : null;
  // The brief lookup starts with the overview instead of waiting for its widget to mount.
  useEffect(() => {
    prefetchQuery(base && briefKey(base, windowCode, lang), signal => client.brief(profile.profileId, lang, signal));
  }, [base, windowCode, lang, client, profile.profileId]);
  const assets = useQuery<AssetsResponse>(base && `assets|${meta?.dataVersion ?? ''}`, signal => client.assets({ limit: 200 }, signal));
  const overviewScope = useMemo<FactScope | null>(() => (overview.data
    ? { kind: 'local', label: { en: 'Deterministic overview response (no model).', fr: 'Réponse d’aperçu déterministe (aucun modèle).' }, facts: overview.data.facts }
    : null), [overview.data]);
  const [resetToken, setResetToken] = useState(0);
  const [customized, setCustomized] = useState(false);
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
      { id: 'figures', title: t('Key figures', 'Chiffres clés'), section: t('Figures', 'Chiffres'), bare: true, limits: LIMITS.figures!, render: () => <KeyFigures overview={data} period={period} /> },
      { id: 'automations', title: t('Automations', 'Automatisations'), section: t('Automations', 'Automatisations'), limits: LIMITS.automations!, render: () => <AutomationsCard profile={profile} /> },
      { id: 'performance', title: t('Past performance', 'Performance passée'), section: t('Performance', 'Performance'), limits: LIMITS.performance!, render: () => <PerformanceCard state={performance} scope={scope} period={period} /> },
      { id: 'allocation', title: t('Allocation', 'Répartition'), section: t('Allocation', 'Répartition'), limits: LIMITS.allocation!, render: () => <AllocationCard overview={data} scope={scope} /> },
      { id: 'positions', title: t('Positions', 'Positions'), section: t('Positions', 'Positions'), limits: LIMITS.positions!, render: () => <PositionsCard overview={data} scope={scope} /> },
      { id: 'health', title: t('Plan health', 'Santé du plan'), section: t('Plan', 'Plan'), limits: LIMITS.health!, render: () => <PlanHealth overview={data} period={period} /> },
      { id: 'horizons', title: t('Longer horizons', 'Horizons plus longs'), limits: LIMITS.horizons!, render: () => <HorizonsCard overview={data} /> },
      { id: 'stress', title: t('Stress test', 'Test de résistance'), limits: LIMITS.stress!, render: () => <StressCard overview={data} /> },
      { id: 'diversification', title: t('Diversification', 'Diversification'), limits: LIMITS.diversification!, render: () => <DiversificationCard overview={data} /> },
      { id: 'brief', title: t('Portfolio brief', 'Note de portefeuille'), section: t('Brief', 'Note'), limits: LIMITS.brief!, render: () => <AnalystBrief profile={profile} scopeNote={briefScope(windowCode, tr)} customRange={scope.period.mode === 'custom' ? period : null} /> },
    ];
  }, [data, performance, scope, period, profile, tr, windowCode]);

  return (
    <>
      <Reveal as="header" index={0} className="dash-header">
        <div className="dash-heading">
          <h1 className="page-title">{tr({ en: `${profile.name}’s portfolio`, fr: `Portefeuille de ${profile.name}` })}</h1>
          <p className="page-sub">{tr(profile.blurb)}</p>
          <p className="dash-meta">
            <span>{tr({ en: 'Objective', fr: 'Objectif' })} <strong>{labelOf(OBJECTIVE, profile.objective, lang)}</strong></span>
            <span>{tr({ en: 'Horizon', fr: 'Horizon' })} <strong>{horizonText(profile, tr)}</strong></span>
            {meta && <span>{tr({ en: 'Data as of', fr: 'Données au' })} <strong>{fmtDate(meta.dataAsOf, lang)}</strong></span>}
          </p>
        </div>
        <div className="dash-actions">
          {/* Always shown so it can be found; inactive while the layout is already the default one. */}
          <button type="button" className="btn ghost btn-sm layout-reset" disabled={!customized}
            onClick={() => { setResetToken(n => n + 1); announce(tr({ en: 'Default layout restored', fr: 'Disposition par défaut rétablie' })); }}
            title={customized
              ? tr({ en: 'Put the widgets back in their original places and sizes', fr: 'Remettre les widgets à leur place et à leur taille d’origine' })
              : tr({ en: 'The widgets are in their original layout', fr: 'Les widgets sont dans leur disposition d’origine' })}>
            <RotateCcw aria-hidden="true" size={14} strokeWidth={1.75} />{tr({ en: 'Reset layout', fr: 'Disposition par défaut' })}
          </button>
          <Link className="btn ghost" href="/portfolio/">{tr({ en: 'Inspect plan', fr: 'Examiner le plan' })}</Link>
          <Link className="btn ink" href="/decision-desk/" data-tour="test-move">{tr({ en: 'Test a move', fr: 'Tester un mouvement' })}</Link>
        </div>
      </Reveal>

      <ScopeBar scope={scope} setScope={setScope} windowCode={windowCode} setWindow={setWindow}
        dataAsOf={meta?.dataAsOf ?? new Date().toISOString().slice(0, 10)} shownPeriod={shownPeriod}
        groups={groups} benchmarks={benchmarks} tr={tr} lang={lang} announce={announce} />

      {overview.error && <AnalystBrief profile={profile} scopeNote={briefScope(windowCode, tr)} customRange={scope.period.mode === 'custom' ? period : null} />}
      {overview.error && (
        <ErrorState error={overview.error} onRetry={overview.reload}
          title={tr({ en: 'The portfolio overview is unavailable for this scope. No summary figures are shown.', fr: 'L’aperçu du portefeuille est indisponible pour ce périmètre. Aucun chiffre de synthèse n’est affiché.' })} />
      )}
      {overview.loading && <KeyFiguresSkeleton label={tr({ en: 'Loading figures…', fr: 'Chargement des chiffres…' })} />}
      {data && overviewScope && (
        <FactScopeProvider scope={overviewScope}>
          {/* No animated wrapper: each widget enters on its own (DashboardGrid, Web Animations), which
              survives the DOM moves of a reorder. */}
          <DashboardGrid widgets={widgets} defaults={DEFAULT_LAYOUT} resetToken={resetToken} announce={announce} labels={labels}
            onCustomizedChange={setCustomized} />
        </FactScopeProvider>
      )}
    </>
  );
}

function PerformanceCard({ state, scope, period }: { state: QueryState<PerformanceResponse>; scope: DashboardScope; period: string }) {
  const { tr, lang } = useApp();
  const data = state.data;
  const title = tr({ en: 'Past performance', fr: 'Performance passée' });
  const info = tr({
    en: 'Today’s weights applied to past prices: a hypothetical history, not account gains. The line starts from the profile’s fictional capital on the first day of the period.',
    fr: 'Pondérations actuelles appliquées aux prix passés : un historique hypothétique, pas des gains réels. La courbe part du capital fictif du profil au premier jour de la période.',
  });
  if (!data || data.series.length < 2) {
    return (
      <Card title={title} tour="performance" info={info}>
        {state.loading && <Loading variant="skeleton" />}
        {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
        {data && <Unavailable title={tr({ en: 'Unavailable for this period', fr: 'Indisponible pour cette période' })} />}
      </Card>
    );
  }
  const view = (points: PerformanceResponse['series']) => (scope.chartMode === 'indexed' ? indexSeries(points)
    : scope.chartMode === 'drawdown' ? drawdownSeries(points) : points);
  const series: Series[] = [{ label: tr({ en: 'Fictional portfolio, today’s weights', fr: 'Portefeuille fictif, pondérations actuelles' }), points: view(data.series), color: 'var(--chart-1)' }];
  if (data.benchmark) series.push({ label: data.benchmark.ticker, points: view(data.benchmark.series), color: 'var(--chart-4)', dashed: true });
  const unit = scope.chartMode === 'indexed' ? tr({ en: 'index, start = 100', fr: 'indice, début = 100' })
    : scope.chartMode === 'drawdown' ? tr({ en: '% below the running peak', fr: '% sous le plus haut atteint' }) : data.currency;
  const digits = scope.chartMode === 'drawdown' ? 1 : 0;
  // Plain words in the sheet; the method code stays in the table caption for audit.
  const caption = `${period}, ${fmtDate(data.series[0]?.date ?? '', lang)} → ${fmtDate(data.series[data.series.length - 1]?.date ?? '', lang)}`;
  const own = periodChangePct(data.series);
  const bench = data.benchmark ? periodChangePct(data.benchmark.series) : null;
  // Value view: say where the line starts (the fictional capital) and ends, so its end is not read as "today's value".
  const ends = scope.chartMode === 'value' ? periodEnds(data.series) : null;
  const currency = data.currency;
  const money = (value: number) => fmtMoney(value, currency, lang);
  const endsText = ends
    ? tr({
      en: `${money(ends.first.value)} on ${fmtDate(ends.first.date, lang)} → ${money(ends.last.value)} on ${fmtDate(ends.last.date, lang)}`,
      fr: `${money(ends.first.value)} le ${fmtDate(ends.first.date, lang)} → ${money(ends.last.value)} le ${fmtDate(ends.last.date, lang)}`,
    })
    : null;
  return (
    <Card title={title} tour="performance" info={info} details={{
      render: () => (
        <>
          <SheetSection title={tr({ en: 'Series', fr: 'Séries' })}>
            <p className="figure-note">{caption} ({unit})</p>
          </SheetSection>
          <SeriesTable series={series} lang={lang} unitLabel={unit} caption={`${caption}, ${data.method}`} digits={digits} />
          <LimitationList compactAfter={1} codes={['LIM_CONSTANT_WEIGHTS', ...data.limitations]} />
        </>
      ),
    }}>
      <p className="period-change">
        {own !== null && <span>{tr({ en: 'Over the period', fr: 'Sur la période' })} <strong><CountUp text={fmtSignedPct(own, lang)} /></strong></span>}
        {data.benchmark && bench !== null && <span>{data.benchmark.ticker} <strong><CountUp text={fmtSignedPct(bench, lang)} /></strong></span>}
        {endsText && <span>{endsText}</span>}
      </p>
      <LineChart series={series} lang={lang} unitLabel={unit} caption={caption} digits={digits} area={scope.chartMode !== 'drawdown'} fill compact />
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
    <Card title={tr({ en: 'Plan health', fr: 'Santé du plan' })} tour="health" details={{
      render: () => (
        <>
          <p className="figure-note">{tr({ en: `${total} rule checks, ${period}`, fr: `${total} vérifications de règles, ${period}` })}</p>
          {closest.length > 0 && (
            <SheetSection title={tr({ en: 'Closest to their limit', fr: 'Les plus proches de leur limite' })}>
              <ul className="limit-list">
                {closest.map(check => (
                  <li key={check.ruleId}>
                    <p className="limit-detail">{tr(check.detail)}</p>
                    <p className="limit-figs small">
                      {figure(check.value, check.valueFactId, check.unit)}
                      <span> {tr({ en: 'against a limit of', fr: 'pour une limite de' })} </span>
                      {figure(check.threshold, check.thresholdFactId, check.unit)}
                    </p>
                  </li>
                ))}
              </ul>
            </SheetSection>
          )}
          {nee.length > 0 && (
            <SheetSection title={tr({ en: 'Not enough evidence (separate from financial checks)', fr: 'Preuves insuffisantes (distinct des vérifications financières)' })}>
              <ul className="bullets small nee-reason">
                {nee.map(check => (
                  <li key={check.ruleId}>{tr(check.detail)}{check.neeReason ? ` — ${labelOf(NEE_REASON, check.neeReason, lang)}` : ''}</li>
                ))}
              </ul>
            </SheetSection>
          )}
          <LimitationList compactAfter={0} codes={overview.limitations} />
          <p><Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'Open rules', fr: 'Ouvrir les règles' })}</Link></p>
        </>
      ),
    }}>
      <div className="health-head">
        <VerdictBadge verdict={overview.verdict} large />
        <span className="small muted">{tr({ en: `${total} checks`, fr: `${total} vérifications` })}</span>
      </div>
      <dl className="status-counts" aria-label={tr({ en: `Rule checks by status, ${period}`, fr: `Vérifications par statut, ${period}` })}>
        {STATUS_ORDER.filter(status => counts[status] > 0).map(status => (
          <div key={status} className="status-count">
            <dt><StatusBadge status={status} /></dt>
            <dd><strong><CountUp text={String(counts[status])} /></strong></dd>
          </div>
        ))}
      </dl>
      <ClosestToLimit checks={closest} />
    </Card>
  );
}

function AnalystBrief({ profile, scopeNote, customRange }: { profile: Profile; scopeNote?: string; customRange: string | null }) {
  const app = useApp();
  const { tr, lang, windowCode, announce, sessionId, meta } = app;
  const base = profileKey(app);
  const cacheKey = base && briefKey(base, windowCode, lang);
  const autoKey = sessionId && meta ? autoBriefKey(sessionId, profile.profileId, meta.dataVersion) : null;
  const cached = useQuery<CachedBriefResponse>(cacheKey, signal => getApiClient().brief(profile.profileId, lang, signal));
  // The run started for a key outlives this component: coming back to a persona, window, language
  // or to Home shows that run (or its progress) again instead of an empty card (HOME-02).
  const [runId, setRunId] = useState<string | null>(() => (cacheKey ? startedRuns.get(cacheKey) ?? null : null));
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const [creating, setCreating] = useState(false);
  // The last brief that succeeded in this card: it stays on screen while a newer one is written.
  const [lastGood, setLastGood] = useState<Run | null>(null);
  const sheet = useSheet();

  // A new key (profile version, data, window, language) shows that key's own run, never stale prose.
  useEffect(() => {
    setRunId(cacheKey ? startedRuns.get(cacheKey) ?? null : null);
    setCreateError(null);
    setLastGood(null);
  }, [cacheKey]);

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

  // At most one automatic run per session, profile and data version, remembered across reloads and
  // consumed by the first loaded lookup (so a language or window switch never writes one), and only
  // when no brief of the current data version exists. Otherwise the brief is shown with a note.
  useEffect(() => {
    if (!autoKey || !meta || !cached.data || runId) return;
    if (autoBriefUsed(autoKey)) return;
    markAutoBrief(autoKey);
    if (shouldAutoRunBrief(cached.data.run, meta.dataVersion)) void start(false);
  }, [autoKey, meta, cached.data, runId, start]);

  const polled = useRun(runId, finished => announce(`${tr({ en: 'Portfolio brief', fr: 'Note de portefeuille' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const current = runId ? polled.run : null;
  useEffect(() => {
    if (current && current.status === 'succeeded') setLastGood(current);
  }, [current]);
  const view = briefDisplay(runId, current, lastGood ?? cachedRun);
  const shown = view.shown;
  const refreshing = creating || (view.refreshing && !polled.error);
  const step = briefProgress(current);
  const stepText = step ? labelOf(STEP_TYPE, step, lang).toLocaleLowerCase(lang) : null;
  const staleReason = shown && shown.runId === cachedRun?.runId ? briefStaleReason(cached.data, meta?.dataVersion ?? null) : null;
  const windowNote = shown ? briefWindowNote(briefWindowOf(shown), windowCode, customRange) : null;
  const detailsRun = shown ?? current;
  const busy = creating || (current !== null && !isTerminal(current.status));
  const empty = Boolean(cached.data && !cachedRun) && !runId && !creating && !createError;

  return (
    <Card id="analyst-brief" title={tr({ en: 'Portfolio brief', fr: 'Note de portefeuille' })} tour="brief"
      {...(scopeNote ? { info: scopeNote } : {})}
      {...(detailsRun ? { details: { render: () => <BriefRun run={detailsRun} full /> } } : {})}
      actions={(
        <button type="button" className="btn ghost btn-sm" onClick={() => void start(true)} disabled={busy}>
          {tr({ en: 'Refresh brief', fr: 'Actualiser la note' })}
        </button>
      )}>
      {cached.loading && <Loading label={tr({ en: 'Looking for a cached brief…', fr: 'Recherche d’une note en cache…' })} />}
      {cached.error && <ErrorState error={cached.error} onRetry={cached.reload}
        title={tr({ en: 'The brief is unavailable. The figures above are unaffected.', fr: 'La note est indisponible. Les chiffres ci-dessus restent valables.' })} />}
      {createError && (
        <ErrorState error={createError} onRetry={() => void start(true)}
          title={createError.code === 'upstream_unavailable'
            ? tr({ en: 'The brief is written by AI, which this server does not offer right now. The figures above are unaffected.', fr: 'La note est rédigée par l’IA, que ce serveur ne propose pas pour l’instant. Les chiffres ci-dessus restent valables.' })
            : tr({ en: 'The brief could not be started. The figures above are unaffected.', fr: 'La note n’a pas pu être lancée. Les chiffres ci-dessus restent valables.' })} />
      )}
      {polled.error && <ErrorState error={polled.error} onRetry={polled.reload} />}
      {empty && (
        <p className="small muted">{tr({ en: 'No brief has been written for this selection yet. Use Refresh brief to write one.', fr: 'Aucune note n’a encore été rédigée pour cette sélection. Utilisez « Actualiser la note » pour en rédiger une.' })}</p>
      )}
      {refreshing && (
        <p className="small muted" role="status">
          {shown
            ? tr(stepText ? { en: `Refreshing… Current step: ${stepText}.`, fr: `Actualisation… Étape en cours : ${stepText}.` } : { en: 'Refreshing…', fr: 'Actualisation…' })
            : tr(stepText ? { en: `Writing the brief… Current step: ${stepText}.`, fr: `Rédaction de la note… Étape en cours : ${stepText}.` } : { en: 'Writing the brief…', fr: 'Rédaction de la note…' })}
        </p>
      )}
      {view.refreshFailed && (
        <p className="stale-note">{tr({ en: 'The new brief could not be written. The previous brief is still shown.', fr: 'La nouvelle note n’a pas pu être rédigée. La note précédente reste affichée.' })}</p>
      )}
      {staleReason && <p className="stale-note">{tr(staleNote(staleReason))}</p>}
      {windowNote && <p className="stale-note">{tr(windowNote)}</p>}
      {shown?.status === 'succeeded' && (
        <p className="brief-tools small">
          <button type="button" className="btn ghost btn-sm" aria-haspopup="dialog" onClick={event => sheet.show(event.currentTarget)}>
            {tr({ en: 'Read the full brief', fr: 'Lire la note complète' })}
          </button>
        </p>
      )}
      {shown && <BriefRun run={shown} full={false} dim={refreshing} />}
      {!shown && refreshing && <BriefSkeleton />}
      {shown?.status === 'succeeded' && (
        <Sheet open={sheet.open} origin={sheet.origin} onClose={sheet.hide} title={tr({ en: 'Portfolio brief', fr: 'Note de portefeuille' })}>
          {sheet.open && <BriefRun run={shown} full />}
        </Sheet>
      )}
    </Card>
  );
}

/** Placeholder of the widget while the first brief is written: two summary lines and three focus cards. */
function BriefSkeleton() {
  return (
    <>
      <div className="brief-summary" aria-hidden="true">
        <Skeleton width="92%" />
        <Skeleton width="68%" />
      </div>
      <div className="focus-grid" aria-hidden="true">
        {[0, 1, 2].map(i => (
          <div key={i} className="focus-card">
            <Skeleton width="55%" height={16} />
            <Skeleton />
            <Skeleton width="80%" />
          </div>
        ))}
      </div>
    </>
  );
}

/**
 * A brief run. In the widget: its status, or the executive summary and the focus cards, clamped. In
 * the sheet (`full`): everything, with the steps, the method and the audit link.
 */
function BriefRun({ run, full, dim = false }: { run: Run; full: boolean; dim?: boolean }) {
  const { tr, feature } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }), [run]);
  const result = run.result?.kind === 'portfolio_brief' ? run.result.portfolioBrief : null;
  if (run.status !== 'succeeded' || !result) {
    return (
      <div className="brief-status-block">
        <p><RunStatusBadge status={run.status} /></p>
        {run.status === 'failed' && (
          <p className="small">{tr({ en: 'The brief could not be written. The figures above are unaffected.', fr: 'La note n’a pas pu être rédigée. Les chiffres ci-dessus restent valables.' })}</p>
        )}
        {full && <RunTimeline run={run} />}
      </div>
    );
  }
  const summary = portfolioSummary(result.brief);
  // While a newer brief is written this one stays in place, greyed (no wrapper: the grid keeps filling the widget).
  const dimmed = dim ? ' is-refreshing' : '';
  return (
    <FactScopeProvider scope={scope}>
      {summary.length > 0 && (
        <div className={full ? 'brief-section' : `brief-summary${dimmed}`} {...(dim ? { 'aria-busy': true } : {})}>
          {full && <h3 className="h4">{tr({ en: 'Executive summary', fr: 'Résumé exécutif' })}</h3>}
          {summary.map(s => <p key={s.id}><SentenceText sentence={s} /></p>)}
        </div>
      )}
      <div className={full ? 'grid-3' : `focus-grid${dimmed}`} {...(dim ? { 'aria-busy': true } : {})}>
        {result.focusCards.map((card, i) => (
          <article key={i} className={full ? 'scenario' : 'focus-card'}>
            <h3 className="h4">{tr(card.title)}</h3>
            {card.body.filter(s => s.audit.status !== 'struck').map(sentence => (
              <p key={sentence.id} className="small"><SentenceText sentence={sentence} /></p>
            ))}
            {full && (
              <Link className="btn ghost btn-sm" href={card.body.some(s => s.segments.some(x => x.t === 'rule'))
                ? `/evidence-audit/?runId=${encodeURIComponent(run.runId)}`
                : card.factIds.some(id => run.facts[id]?.metric === 'weight.asset_group') ? '/sources/'
                : card.factIds.some(id => run.facts[id]?.metric === 'drawdown.max') && feature('time_machine') ? '/time-machine/' : '/portfolio/'}>
                {tr({ en: 'Open investigation', fr: 'Ouvrir la recherche' })}</Link>
            )}
          </article>
        ))}
      </div>
      {full && (
        <>
          <details className="fold"><summary>{tr({ en: 'Method, assumptions and evidence gaps', fr: 'Méthode, hypothèses et preuves manquantes' })}</summary>
            <BriefView brief={{ ...result.brief, sections: result.brief.sections.map(s => ({ ...s,
              sentences: s.sentences.filter(sentence => !summary.some(x => x.id === sentence.id)),
            })).filter(s => s.sentences.length > 0) }} />
          </details>
          <p className="row-actions small">
            <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Inspect evidence and audit', fr: 'Examiner les preuves et l’audit' })}</Link>
          </p>
        </>
      )}
    </FactScopeProvider>
  );
}
