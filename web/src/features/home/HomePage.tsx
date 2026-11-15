'use client';
/**
 * Home — Portfolio Analyst Brief (T13, web/page-specs/home.md). Deterministic overview and
 * performance load in parallel; the cached brief is fetched separately and at most one
 * automatic portfolio_brief run is created per cache key (HOME-02). Refresh creates a real run.
 */
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type {
  CachedBriefResponse, I18NText, OverviewResponse, PerformanceResponse, Profile, Run,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery, type QueryState } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { CountsLine, RunStatusBadge, VerdictBadge } from '../../components/common/Badges';
import { LineChart, SeriesTable, type Series } from '../../components/common/LineChart';
import { BriefView, SentenceText } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import { NEE_REASON, OBJECTIVE, RISK_LEVEL, RUN_STATUS, WINDOW, labelOf } from '../../lib/labels';
import { factIdFor, fmtDate, fmtMoney, fmtPct, fmtSignedPct } from '../../lib/format';
import { isTerminal } from '../../lib/runs';

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
  const { tr, lang, windowCode, meta } = app;
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
      <PageHeader eyebrow={tr({ en: 'Portfolio analyst brief', fr: 'Note d’analyse du portefeuille' })} title={profile.name}>
        <p className="page-sub">{tr(profile.blurb)}</p>
        <p className="small muted">
          {tr({ en: 'Fictional capital', fr: 'Capital fictif' })}{' '}
          <strong className="num">{fmtMoney(profile.portfolio.totalValue, profile.portfolio.currency, lang)}</strong>
          {' · '}{tr({ en: 'Horizon', fr: 'Horizon' })} {horizonText(profile, tr)}
          {' · '}{tr({ en: 'Risk level', fr: 'Niveau de risque' })} {labelOf(RISK_LEVEL, profile.riskLevel, lang)}
          {' · '}{labelOf(OBJECTIVE, profile.objective, lang)}
          {meta && <> · {tr({ en: 'Data as of', fr: 'Données au' })} {fmtDate(meta.dataAsOf, lang)}</>}
          {' · '}{labelOf(WINDOW, windowCode, lang)}
        </p>
        <div className="row-actions">
          <Link className="btn" href="/decision-desk/">{tr({ en: 'Test a move', fr: 'Tester un mouvement' })}</Link>
          <Link className="btn ghost" href="/portfolio/">{tr({ en: 'Inspect plan', fr: 'Examiner le plan' })}</Link>
        </div>
      </PageHeader>

      {overview.error && (
        <ErrorState error={overview.error} onRetry={overview.reload}
          title={tr({ en: 'The portfolio overview is unavailable. No summary figures are shown.', fr: 'L’aperçu du portefeuille est indisponible. Aucun chiffre de synthèse n’est affiché.' })} />
      )}
      {overview.loading && <Loading label={tr({ en: 'Loading deterministic overview…', fr: 'Chargement de l’aperçu déterministe…' })} />}
      {overview.data && overviewScope && (
        <FactScopeProvider scope={overviewScope}>
          <MetricStrip overview={overview.data} />
          <div className="cols">
            <PerformanceCard state={performance} />
            <PlanHealth overview={overview.data} />
          </div>
        </FactScopeProvider>
      )}

      <AnalystBrief profile={profile} />
    </>
  );
}

function Tile({ label, children, note }: { label: string; children: ReactNode; note?: string }) {
  return (
    <div className="tile">
      <span className="eyebrow block">{label}</span>
      <span className="big">{children}</span>
      {note && <span className="small muted block">{note}</span>}
    </div>
  );
}

function MetricStrip({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const unavailable = <span className="small muted">{tr({ en: 'Unavailable for this period.', fr: 'Indisponible pour cette période.' })}</span>;
  const pct = (value: number | null, factId: string | undefined, signed: boolean) => {
    if (value === null) return unavailable;
    const text = signed ? fmtSignedPct(value, lang) : fmtPct(value, lang);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
  return (
    <Card title={tr({ en: 'Current fictional portfolio', fr: 'Portefeuille fictif actuel' })}>
      <div className="tiles">
        <Tile label={tr({ en: 'Fictional value', fr: 'Valeur fictive' })} note={overview.snapshot.currency}>
          <span className="num">{fmtMoney(overview.snapshot.totalValue, overview.snapshot.currency, lang)}</span>
        </Tile>
        <Tile label={tr({ en: 'Year to date (historical)', fr: 'Depuis le début de l’année (historique)' })}>
          {pct(overview.returns.ytdPct, factIdFor(overview.returns.factIds, "ytdPct"), true)}
        </Tile>
        <Tile label={tr({ en: 'Trailing 1 year (historical)', fr: 'Sur 1 an (historique)' })}>
          {pct(overview.returns.y1Pct, factIdFor(overview.returns.factIds, "y1Pct"), true)}
        </Tile>
        <Tile label={tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })}>
          {pct(overview.risk.volatilityPct, factIdFor(overview.risk.factIds, "volatilityPct"), false)}
        </Tile>
        <Tile label={tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })} note={tr({ en: 'positive loss', fr: 'perte positive' })}>
          {pct(overview.risk.maxDrawdownPct, factIdFor(overview.risk.factIds, "maxDrawdownPct"), false)}
        </Tile>
      </div>
      <p className="small muted" style={{ marginTop: 12 }}>
        {tr({ en: 'Constant-weight historical figures for today’s fictional holdings, not account gains.', fr: 'Chiffres historiques à pondérations constantes pour les positions fictives actuelles, pas des gains de compte.' })}
        {' '}{tr({ en: 'Measured risk category', fr: 'Catégorie de risque mesurée' })}: {labelOf(RISK_LEVEL, overview.risk.riskCategory, lang)}
      </p>
    </Card>
  );
}

function PerformanceCard({ state }: { state: QueryState<PerformanceResponse> }) {
  const { tr, lang } = useApp();
  const [asTable, setAsTable] = useState(false);
  const data = state.data;
  let body: ReactNode = null;
  if (data && data.series.length > 1) {
    const series: Series[] = [{ label: tr({ en: 'Fictional portfolio, today’s weights', fr: 'Portefeuille fictif, pondérations actuelles' }), points: data.series, color: '#0B5E66' }];
    if (data.benchmark) series.push({ label: data.benchmark.ticker, points: data.benchmark.series, color: '#B07A1E', dashed: true });
    const caption = `${labelOf(WINDOW, data.window.code, lang)} · ${fmtDate(data.series[0]?.date ?? '', lang)} → ${fmtDate(data.series[data.series.length - 1]?.date ?? '', lang)} · ${data.method}`;
    body = asTable
      ? <SeriesTable series={series} lang={lang} unitLabel={data.currency} caption={caption} />
      : <LineChart series={series} lang={lang} unitLabel={data.currency} caption={caption} />;
  }
  return (
    <Card title={tr({ en: 'Hypothetical constant-weight history', fr: 'Historique hypothétique à pondérations constantes' })}
      actions={data && data.series.length > 1 ? (
        <button type="button" className="btn ghost btn-sm" onClick={() => setAsTable(v => !v)} aria-pressed={asTable}>
          {asTable ? tr({ en: 'Show chart', fr: 'Afficher le graphique' }) : tr({ en: 'Show table', fr: 'Afficher le tableau' })}
        </button>
      ) : undefined}>
      {state.loading && <Loading />}
      {state.error && <ErrorState error={state.error} onRetry={state.reload} />}
      {data && data.series.length < 2 && <Unavailable title={tr({ en: 'Unavailable for this period.', fr: 'Indisponible pour cette période.' })} />}
      {body}
      {data && <LimitationList codes={data.limitations.includes('LIM_CONSTANT_WEIGHTS') ? data.limitations : ['LIM_CONSTANT_WEIGHTS', ...data.limitations]} />}
    </Card>
  );
}

function PlanHealth({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const nee = overview.ruleChecks.filter(c => c.status === 'nee');
  return (
    <Card title={tr({ en: 'Plan health', fr: 'Santé du plan' })}>
      <VerdictBadge verdict={overview.verdict} large />
      <CountsLine counts={overview.counts} />
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
      <div className="row-actions"><Link href="/portfolio/">{tr({ en: 'Open rules on Portfolio', fr: 'Ouvrir les règles dans Portefeuille' })}</Link></div>
      <LimitationList codes={overview.limitations} />
    </Card>
  );
}

function AnalystBrief({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang, windowCode, announce, sessionId, meta } = app;
  const base = profileKey(app);
  const cacheKey = base && `brief|${base}|${windowCode}|${lang}`;
  const cached = useQuery<CachedBriefResponse>(cacheKey, signal => getApiClient().brief(profile.profileId, lang, signal));
  const [runId, setRunId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const [creating, setCreating] = useState(false);

  // Reset when the key (profile version, data, window, language) changes: no stale prose.
  useEffect(() => { setRunId(null); setCreateError(null); }, [cacheKey]);

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
      setRunId(created.runId);
    } catch (error) {
      setCreateError(asApiError(error));
    } finally {
      setCreating(false);
    }
  }, [sessionId, meta, profile.profileId, profile.version, windowCode, lang]);

  useEffect(() => {
    if (!cacheKey || !cached.data || cached.data.run || runId) return;
    if (autoRequested.has(cacheKey)) return;
    autoRequested.add(cacheKey);
    void start(false);
  }, [cacheKey, cached.data, runId, start]);

  const polled = useRun(runId, finished => announce(`${tr({ en: 'Portfolio brief', fr: 'Note de portefeuille' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run: Run | null = runId ? polled.run : cached.data?.run ?? null;
  const stale = !runId && Boolean(cached.data?.stale);
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
