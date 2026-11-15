'use client';
/**
 * Home — Portfolio Analyst Brief (T13, web/page-specs/home.md), laid out as the glass dashboard
 * (docs/superpowers/specs/2026-11-14-glass-ui-design.md §5.4). Deterministic overview and
 * performance load in parallel; the cached brief is fetched separately and at most one
 * automatic portfolio_brief run is created per cache key (HOME-02). Refresh creates a real run.
 */
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type {
  CachedBriefResponse, I18NText, OverviewResponse, PerformanceResponse, Profile, RuleCheck, RuleStatus, Run,
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
import { NEE_REASON, OBJECTIVE, RUN_STATUS, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate, fmtUnit } from '../../lib/format';
import { isTerminal } from '../../lib/runs';
import { AllocationCard } from './AllocationCard';
import { KpiSkeleton, KpiTiles } from './KpiTiles';
import { ProfileRail } from './ProfileRail';
import { TopPositionsCard } from './TopPositionsCard';
import { Reveal } from '../../components/ui/Reveal';

/** Run started for each cache key in this page load (survives navigation between pages). */
const startedRuns = new Map<string, string>();
/** Cache keys for which an automatic brief run was already requested in this page load. */
const autoRequested = new Set<string>();

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
  const { tr, lang, windowCode } = app;
  const client = getApiClient();
  const base = profileKey(app);
  const overview = useQuery<OverviewResponse>(base && `overview|${base}|${windowCode}`,
    signal => client.overview(profile.profileId, windowCode, signal));
  const performance = useQuery<PerformanceResponse>(base && `performance|${base}|${windowCode}`,
    signal => client.performance(profile.profileId, windowCode, signal));
  const overviewScope = useMemo<FactScope | null>(() => (overview.data
    ? { kind: 'local', label: { en: 'Deterministic overview response (no model).', fr: 'Réponse d’aperçu déterministe (aucun modèle).' }, facts: overview.data.facts }
    : null), [overview.data]);

  return (
    <>
      <Reveal as="header" index={0} className="dash-header">
        <div className="dash-heading">
          <p className="eyebrow">{tr({ en: 'Portfolio analyst brief', fr: 'Note d’analyse du portefeuille' })}</p>
          <h1 className="page-title">{profile.name}</h1>
          <p className="page-sub">{tr(profile.blurb)}</p>
          <ul className="dash-meta" aria-label={tr({ en: 'Profile summary', fr: 'Résumé du profil' })}>
            {/* Capital is the first KPI, currency/risk/data date sit in the topbar and the window in its
                control: only what appears nowhere else is repeated here. */}
            <li className="meta-chip">{tr({ en: 'Horizon', fr: 'Horizon' })} <strong>{horizonText(profile, tr)}</strong></li>
            <li className="meta-chip">{tr({ en: 'Objective', fr: 'Objectif' })} <strong>{labelOf(OBJECTIVE, profile.objective, lang)}</strong></li>
          </ul>
        </div>
        <div className="dash-actions">
          <Link className="btn" href="/decision-desk/">{tr({ en: 'Test a move', fr: 'Tester un mouvement' })}</Link>
          <Link className="btn ghost" href="/portfolio/">{tr({ en: 'Inspect plan', fr: 'Examiner le plan' })}</Link>
        </div>
      </Reveal>

      {overview.error && (
        <ErrorState error={overview.error} onRetry={overview.reload}
          title={tr({ en: 'The portfolio overview is unavailable. No summary figures are shown.', fr: 'L’aperçu du portefeuille est indisponible. Aucun chiffre de synthèse n’est affiché.' })} />
      )}
      {overview.loading && <KpiSkeleton label={tr({ en: 'Loading deterministic overview…', fr: 'Chargement de l’aperçu déterministe…' })} />}
      {overview.data && overviewScope && (
        <FactScopeProvider scope={overviewScope}>
          <div className="dash">
            <div className="dash-main">
              <KpiTiles overview={overview.data} />
              <Reveal index={2} className="dash-row dash-row-chart">
                <PerformanceCard state={performance} />
                <AllocationCard overview={overview.data} />
              </Reveal>
              <Reveal index={3} className="dash-row dash-row-split">
                <TopPositionsCard overview={overview.data} />
                <PlanHealth overview={overview.data} />
              </Reveal>
            </div>
            <ProfileRail overview={overview.data} />
          </div>
        </FactScopeProvider>
      )}

      <Reveal index={4}><AnalystBrief profile={profile} /></Reveal>
    </>
  );
}

function PerformanceCard({ state }: { state: QueryState<PerformanceResponse> }) {
  const { tr, lang } = useApp();
  const [asTable, setAsTable] = useState(false);
  const data = state.data;
  let body: ReactNode = null;
  if (data && data.series.length > 1) {
    const series: Series[] = [{ label: tr({ en: 'Fictional portfolio, today’s weights', fr: 'Portefeuille fictif, pondérations actuelles' }), points: data.series, color: 'var(--chart-1)' }];
    if (data.benchmark) series.push({ label: data.benchmark.ticker, points: data.benchmark.series, color: 'var(--chart-4)', dashed: true });
    // Visible caption in plain words; the method code stays in the table caption for audit.
    const caption = `${labelOf(WINDOW, data.window.code, lang)}, ${fmtDate(data.series[0]?.date ?? '', lang)} → ${fmtDate(data.series[data.series.length - 1]?.date ?? '', lang)}`;
    body = asTable
      ? <SeriesTable series={series} lang={lang} unitLabel={data.currency} caption={`${caption}, ${data.method}`} />
      : <LineChart series={series} lang={lang} unitLabel={data.currency} caption={caption} />;
  }
  return (
    <Card title={tr({ en: 'Hypothetical constant-weight history', fr: 'Historique hypothétique à pondérations constantes' })} className="dash-card"
      actions={data && data.series.length > 1 ? (
        <button type="button" className="btn ghost btn-sm" onClick={() => setAsTable(v => !v)}>
          {asTable ? tr({ en: 'Show chart', fr: 'Afficher le graphique' }) : tr({ en: 'Show table', fr: 'Afficher le tableau' })}
        </button>
      ) : undefined}>
      {state.loading && <Loading variant="skeleton" />}
      {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
      {data && data.series.length < 2 && <Unavailable title={tr({ en: 'Unavailable for this period.', fr: 'Indisponible pour cette période.' })} />}
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

function PlanHealth({ overview }: { overview: OverviewResponse }) {
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
    <Card title={tr({ en: 'Plan health', fr: 'Santé du plan' })} className="dash-card"
      actions={<Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'Open rules', fr: 'Ouvrir les règles' })}</Link>}>
      <div className="health-head">
        <VerdictBadge verdict={overview.verdict} large />
        <span className="small muted">{tr({ en: `${total} rule checks`, fr: `${total} vérifications de règles` })}</span>
      </div>
      <ul className="status-bars" aria-label={tr({ en: 'Rule checks by status', fr: 'Vérifications par statut' })}>
        {STATUS_ORDER.map(status => (
          <li key={status} className="status-bar">
            <StatusBadge status={status} />
            <span className="meter-track" aria-hidden="true">
              <span className={`meter-fill fill-${status}`} style={{ width: `${total ? (counts[status] / total) * 100 : 0}%` }} />
            </span>
            <strong className="num">{counts[status]}</strong>
          </li>
        ))}
      </ul>
      {closest.length > 0 && (
        <>
          <h3 className="h4">{tr({ en: 'Closest to their limit', fr: 'Les plus proches de leur limite' })}</h3>
          <ul className="limit-list">
            {closest.map(check => (
              <li key={check.ruleId}>
                <p className="limit-detail"><span className="rule-code mono">{check.code}</span> {tr(check.detail)}</p>
                <p className="limit-figs small">
                  {figure(check.value, check.valueFactId, check.unit)}
                  <span className="muted"> {tr({ en: 'against a limit of', fr: 'pour une limite de' })} </span>
                  {figure(check.threshold, check.thresholdFactId, check.unit)}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
      {nee.length > 0 && (
        <div className="small nee-reason">
          <p><strong>{tr({ en: 'Not enough evidence (separate from financial checks):', fr: 'Preuves insuffisantes (distinct des vérifications financières) :' })}</strong></p>
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

function AnalystBrief({ profile }: { profile: Profile }) {
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
    <Card id="analyst-brief" title={tr({ en: 'Analyst brief', fr: 'Note d’analyse' })}
      actions={(
        <button type="button" className="btn ghost btn-sm" onClick={() => void start(true)} disabled={busy}>
          {tr({ en: 'Refresh brief', fr: 'Actualiser la note' })}
        </button>
      )}>
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
  const { tr } = useApp();
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
      <div className="grid-3">
        {result.focusCards.map((card, i) => (
          <article key={i} className="scenario">
            <h3 className="h4">{tr(card.title)}</h3>
            {card.body.filter(s => s.audit.status !== 'struck').map(sentence => (
              <p key={sentence.id} className="small"><SentenceText sentence={sentence} /></p>
            ))}
          </article>
        ))}
      </div>
      <BriefView brief={result.brief} />
      <p className="row-actions small">
        <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Inspect evidence and audit', fr: 'Examiner les preuves et l’audit' })}</Link>
      </p>
    </FactScopeProvider>
  );
}
