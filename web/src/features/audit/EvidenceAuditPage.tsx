'use client';
/**
 * Evidence & Audit (T14, web/page-specs/evidence-audit.md). Loads the owned run (or lists session runs,
 * the app's one list of analyses), shows the brief with audit markings and the audit report, the
 * sabotage test, rule checks, a searchable fact ledger, the actual timeline and the datasets read. ?factId= deep-links the fact drawer (AUDUI-06).
 */
import Link from 'next/link';
import { ListTree } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import type { Brief, Run, RuleCheck, RunsResponse, SabotageMode } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { invalidateQueries, useQuery } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, PageHeader } from '../../components/common/Page';
import { Empty, ErrorState, Loading } from '../../components/common/States';
import { FactScopeProvider, LimitationList, useFactDrawer, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge, VerdictBadge } from '../../components/common/Badges';
import { BriefView, SentenceView } from '../../components/run/BriefView';
import { RuleTable } from '../../components/run/RuleTable';
import { RunTimeline } from '../../components/run/RunTimeline';
import { AuditPanel } from '../../components/run/AuditPanel';
import { AUDIT_CHECK, FACT_KIND, RUN_KIND, RUN_STATUS, SABOTAGE_MODE, VERIFICATION, labelOf } from '../../lib/labels';
import { fmtDate, fmtDateTime } from '../../lib/format';
import { RunsTable, stepsHref } from '../../components/run/RunsTable';
import { ResearchOutcomeNote } from '../../components/run/ResearchOutcomeNote';
import { briefsOf, danglingReferences } from '../../lib/brief';
import {
  ATTEMPT_OUTCOME, SOURCES_TRIED_ID, allAttemptsFailed, researchAttempts, researchToolLabel, runListKey, runListProfileId,
  sentenceHashTarget, type RunListScope,
} from '../../lib/evidence';
import { fold } from '../../lib/suggest';
import './audit.css';

const SABOTAGE_MODES: readonly SabotageMode[] = ['invented_number', 'false_comparison', 'unsupported_interpretation'];

export function EvidenceAuditPage() {
  const params = useSearchParams();
  const runId = params.get('runId');
  return runId ? <RunAudit key={runId} runId={runId} factId={params.get('factId')} /> : <RunList />;
}

function RunList() {
  const { tr, sessionId, profile, profilesLoaded } = useApp();
  // The browser session's runs cover every profile and earlier visits (QA 6.5: per session, not shared);
  // the list starts on the active profile, with "All profiles" one click away.
  const [scope, setScope] = useState<RunListScope>('profile');
  const profileId = runListProfileId(scope, profile?.profileId);
  // The session's run list changes as runs are created: always refetch when the list is shown.
  useState(() => invalidateQueries(key => key.startsWith('runs|')));
  // Wait for the profiles (loaded or failed) so the first read already has the right scope.
  const runs = useQuery<RunsResponse>(sessionId && profilesLoaded ? runListKey(sessionId, profileId) : null,
    signal => getApiClient().runs({ limit: 50, ...(profileId ? { profileId } : {}) }, signal));
  return (
    <>
      <PageHeader title={tr({ en: 'Evidence and audit', fr: 'Preuves et audit' })}>
        <p className="page-sub">{tr({ en: 'Every analysis you started, with two ways in: its evidence and audit, or the steps it took.', fr: 'Chaque analyse lancée, avec deux entrées : ses preuves et son audit, ou les étapes suivies.' })}</p>
      </PageHeader>
      <Card id="runs" tour="run-list" title={tr({ en: 'Analyses started in this browser', fr: 'Analyses lancées dans ce navigateur' })}
        info={tr({
          en: 'Every analysis started in this browser, on this visit and earlier ones, newest first. Show the active profile or all profiles. Another browser or device does not see them.',
          fr: 'Toutes les analyses lancées dans ce navigateur, lors de cette visite et des précédentes, de la plus récente à la plus ancienne. Affichez le profil actif ou tous les profils. Un autre navigateur ou appareil ne les voit pas.',
        })}>
        {profile && (
          <div className="filter-chips" role="group" aria-label={tr({ en: 'Show analyses for', fr: 'Afficher les analyses pour' })}>
            <button type="button" className="fchip" aria-pressed={scope === 'profile'} onClick={() => setScope('profile')}>
              {tr({ en: `This profile (${profile.name})`, fr: `Ce profil (${profile.name})` })}
            </button>
            <button type="button" className="fchip" aria-pressed={scope === 'all'} onClick={() => setScope('all')}>
              {tr({ en: 'All profiles', fr: 'Tous les profils' })}
            </button>
          </div>
        )}
        {(runs.loading || (sessionId !== null && !profilesLoaded)) && <Loading />}
        {runs.error && <ErrorState error={runs.error} onRetry={runs.reload} />}
        {runs.data && runs.data.items.length === 0 && (
          <Empty>{profileId && profile
            ? tr({ en: `No analysis for ${profile.name} yet in this browser. Start one from Decide or Home, or choose All profiles.`, fr: `Aucune analyse pour ${profile.name} dans ce navigateur pour l’instant. Lancez-en une depuis Décider ou l’Accueil, ou choisissez Tous les profils.` })
            : tr({ en: 'No analysis yet. Start one from Decide or Home.', fr: 'Aucune analyse pour l’instant. Lancez-en une depuis Décider ou l’Accueil.' })}</Empty>
        )}
        {runs.data && runs.data.items.length > 0 && (
          <RunsTable items={runs.data.items} />
        )}
      </Card>
    </>
  );
}

function mainBrief(run: Run): Brief | null {
  if (!run.result || run.result.kind === 'sabotage') return null;
  return briefsOf(run.result)[0] ?? null;
}

function RunAudit({ runId, factId }: { runId: string; factId: string | null }) {
  const { tr, lang, announce } = useApp();
  const router = useRouter();
  const polled = useRun(runId, finished => announce(`${labelOf(RUN_KIND, finished.kind, lang)}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;
  const scope = useMemo<FactScope | null>(() => (run ? { kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence } : null), [run]);
  const drawer = useFactDrawer();
  const { openFact, current } = drawer;

  // Deep link: open ?factId= once, when the run first loads.
  const initialised = useRef(false);
  const pendingOpen = useRef<string | null>(null);
  useEffect(() => {
    if (!scope || initialised.current) return;
    initialised.current = true;
    if (factId) { pendingOpen.current = factId; openFact(scope, factId); }
  }, [scope, factId, openFact]);

  // Keep ?factId= in sync with the drawer so a refresh restores the same fact.
  useEffect(() => {
    if (!initialised.current) return;
    if (pendingOpen.current && !current) return;
    pendingOpen.current = null;
    const wanted = current?.type === 'fact' && current.scope.kind === 'run' && current.scope.runId === runId ? current.id : null;
    if (wanted === factId) return;
    router.replace(`/evidence-audit/?runId=${encodeURIComponent(runId)}${wanted ? `&factId=${encodeURIComponent(wanted)}` : ''}`, { scroll: false });
  }, [current, runId, factId, router]);

  const brief = run ? mainBrief(run) : null;
  const dangling = run ? danglingReferences(run) : [];

  // "See it in Evidence" links here at #sentence-…; the sentence exists only once the brief renders.
  const hasBrief = Boolean(brief);
  useEffect(() => {
    if (!hasBrief) return undefined;
    const reveal = () => {
      const target = sentenceHashTarget(window.location.hash);
      if (target) document.getElementById(target)?.scrollIntoView({ block: 'center' });
    };
    reveal();
    window.addEventListener('hashchange', reveal);
    return () => window.removeEventListener('hashchange', reveal);
  }, [hasBrief]);

  return (
    <>
      <PageHeader title={run ? labelOf(RUN_KIND, run.kind, lang) : tr({ en: 'Analysis', fr: 'Analyse' })}
        actions={<>
          <Link className="btn ghost btn-sm" href={stepsHref(runId)}><ListTree size={16} aria-hidden="true" />{tr({ en: 'See steps', fr: 'Voir les étapes' })}</Link>
          <Link className="btn ghost btn-sm" href="/evidence-audit/">{tr({ en: 'All analyses', fr: 'Toutes les analyses' })}</Link>
        </>}>
      </PageHeader>
      {polled.loading && !run && <Loading />}
      {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
        {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This analysis does not exist or belongs to another session.', fr: 'Cette analyse n’existe pas ou appartient à une autre session.' }) } : {})} />}
      {run && scope && (
        <FactScopeProvider scope={scope}>
          <RunHeader run={run} />
          {dangling.length > 0 && (
            <div className="state state-error" role="alert">
              <p className="state-title">{tr({ en: 'Some references do not resolve inside this analysis:', fr: 'Certaines références ne se résolvent pas dans cette analyse :' })}</p>
              <p className="mono small">{dangling.join(', ')}</p>
            </div>
          )}
          {run.status === 'failed' && (
            <p className="stale-note">{tr({ en: 'This analysis failed, so there is no result. The steps and facts computed before the failure stay visible.', fr: 'Cette analyse a échoué : il n’y a pas de résultat. Les étapes et faits calculés avant l’échec restent visibles.' })}</p>
          )}
          {run.result?.kind === 'sabotage' && <SabotageResultView run={run} />}
          {brief && (
            <div className="cols">
              <Card id="brief" section={tr({ en: 'Brief', fr: 'Note' })} tour="audit-brief" title={tr({ en: 'Brief with audit marks', fr: 'Note avec marques d’audit' })}
                info={tr({ en: 'Struck sentences appear only here, with the checks they failed.', fr: 'Les phrases rayées n’apparaissent qu’ici, avec les vérifications échouées.' })}>
                <ResearchOutcomeNote run={run} onEvidencePage />
                <BriefView brief={brief} mode="audit" />
              </Card>
              <Card id="audit" section={tr({ en: 'Audit', fr: 'Audit' })} tour="audit-report" title={tr({ en: 'Audit report', fr: 'Rapport d’audit' })}>
                <AuditPanel brief={brief} run={run} />
                <p className="small muted">{tr({
                  en: 'Checks attest the recorded references, source quotations, arithmetic relations and review performed. A matching quotation confirms what a source said; it does not prove the source is correct. Interpretation review can miss unsupported claims.',
                  fr: 'Les contrôles attestent les références, les citations, les relations numériques et la revue enregistrées. Une citation conforme confirme les propos de la source, sans prouver leur exactitude. La revue peut manquer des affirmations non étayées.',
                })}</p>
              </Card>
            </div>
          )}
          <SabotageControls run={run} />
          <RuleChecksPanel run={run} />
          <FactLedger run={run} scope={scope} />
          <EvidenceList run={run} scope={scope} />
          <SourcesTried run={run} />
          <details className="fold section-fold" id="timeline" data-section={tr({ en: 'Steps', fr: 'Étapes' })}>
            <summary>{tr({ en: 'Steps', fr: 'Étapes' })}</summary>
            <div className="fold-body"><RunTimeline run={run} /></div>
          </details>
          <DatasetsUsed run={run} />
        </FactScopeProvider>
      )}
    </>
  );
}

function RunHeader({ run }: { run: Run }) {
  const { tr, lang, profiles } = useApp();
  const profileName = profiles.find(p => p.profileId === run.profileId)?.name ?? null;
  return (
    <Card>
      <div className="verdict-header">
        <RunStatusBadge status={run.status} />
        {run.result?.kind === 'decision' && <VerdictBadge verdict={run.result.decision.verdict} />}
        {run.flags.sabotage && <span className="tag tag-strong">{tr({ en: 'Sabotage demonstration', fr: 'Démonstration de sabotage' })}: {labelOf(SABOTAGE_MODE, run.flags.sabotage, lang)}</span>}
        {run.flags.timeMachine && <span className="tag">{tr({ en: 'Historical replay', fr: 'Rejeu historique' })}</span>}
      </div>
      <p className="small muted">
        {profileName ? `${profileName}, ` : ''}{tr({ en: 'data as of', fr: 'données au' })} {fmtDate(run.asOf, lang)}, {tr({ en: 'started', fr: 'lancée le' })} {fmtDateTime(run.createdAt, lang)}
      </p>
      {run.parentRunId && (
        <p className="small">{tr({ en: 'Derived from an earlier analysis, left unchanged.', fr: 'Dérivée d’une analyse antérieure, laissée inchangée.' })} <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.parentRunId)}`}>{tr({ en: 'Open it', fr: 'L’ouvrir' })}</Link></p>
      )}
      <details className="tech-details">
        <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
        <p className="mono break">{run.runId}, {run.dataVersion}, {run.lang.toUpperCase()}</p>
      </details>
    </Card>
  );
}

function selectedChecks(run: Run): RuleCheck[] | null {
  const result = run.result;
  if (result?.kind === 'decision') {
    return result.decision.scenarios.find(s => s.scenarioId === result.decision.selectedScenarioId)?.ruleChecks ?? null;
  }
  if (result?.kind === 'replay') {
    return result.replay.decision.scenarios.find(s => s.scenarioId === result.replay.decision.selectedScenarioId)?.ruleChecks ?? null;
  }
  if (result?.kind === 'portfolio_brief') return result.portfolioBrief.ruleChecks;
  return null;
}

function RuleChecksPanel({ run }: { run: Run }) {
  const { tr, profiles } = useApp();
  const checks = selectedChecks(run);
  if (!checks) return null;
  const rules = profiles.find(p => p.profileId === run.profileId)?.rules;
  return (
    <Card id="rules" section={tr({ en: 'Rules', fr: 'Règles' })} title={tr({ en: 'Rule checks', fr: 'Vérifications des règles' })}>
      <RuleTable checks={checks} rules={rules} caption={tr({ en: 'Rule checks of the selected scenario', fr: 'Vérifications du scénario sélectionné' })} />
      {run.result?.kind === 'decision' && <LimitationList codes={run.result.decision.limitations} />}
    </Card>
  );
}

function FactLedger({ run, scope }: { run: Run; scope: FactScope }) {
  const { tr, lang } = useApp();
  const { openFact } = useFactDrawer();
  const [query, setQuery] = useState('');
  // Typing stays instant: the searched text is prepared once per run and the table follows a deferred
  // query. Case and accents are ignored ("verifie" finds "vérifié").
  const facts = useMemo(() => Object.values(run.facts), [run.facts]);
  const searchable = useMemo(() => facts.map(f => fold([f.id, f.metric, f.kind, f.key, f.label.en, f.label.fr].join('\n'))), [facts]);
  const deferredQuery = useDeferredValue(query);
  const q = fold(deferredQuery.trim());
  const filtered = useMemo(() => (q ? facts.filter((_, i) => searchable[i]?.includes(q)) : facts), [facts, searchable, q]);
  return (
    <details className="fold section-fold" id="ledger" data-section={tr({ en: 'Facts', fr: 'Faits' })} data-tour="ledger">
      <summary>{tr({ en: `Fact ledger (${facts.length})`, fr: `Registre des faits (${facts.length})` })}</summary>
      <div className="fold-body">
      <div className="search-row">
        <label htmlFor="ledger-search" className="sr-only">{tr({ en: 'Search facts', fr: 'Rechercher des faits' })}</label>
        <input id="ledger-search" type="search" value={query} onChange={e => setQuery(e.target.value)}
          placeholder={tr({ en: 'Search facts', fr: 'Rechercher un fait' })} />
        <span className="small muted" role="status">{filtered.length} / {facts.length}</span>
      </div>
      {facts.length === 0 ? <Empty>{tr({ en: 'No facts recorded yet.', fr: 'Aucun fait enregistré.' })}</Empty> : (
        <div className="table-scroll" role="region" aria-label={tr({ en: 'Fact ledger', fr: 'Registre des faits' })} tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">{tr({ en: 'Fact', fr: 'Fait' })}</th>
                <th scope="col">{tr({ en: 'Kind', fr: 'Nature' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Value', fr: 'Valeur' })}</th>
                <th scope="col">{tr({ en: 'Verification', fr: 'Vérification' })}</th>
                <th scope="col">{tr({ en: 'Availability', fr: 'Disponibilité' })}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(fact => (
                <tr key={fact.id}>
                  <th scope="row"><button type="button" className="linklike mono" onClick={() => openFact(scope, fact.id)}>{fact.id}</button></th>
                  <td>{tr(fact.label)}<span className="block small mono muted break">{fact.metric}</span></td>
                  <td>{labelOf(FACT_KIND, fact.kind, lang)}</td>
                  <td className="num-col num">{tr(fact.display)}</td>
                  <td>{labelOf(VERIFICATION, fact.verification.status, lang)}
                    <span className="block small mono muted break">{fact.verification.checks.map(c => `${c.code}: ${c.ok ? '✓' : '✕'}`).join(', ')}</span>
                  </td>
                  <td className="small">{fact.availableAt ? fmtDateTime(fact.availableAt, lang) : tr({ en: 'Timeless input or availability unknown — inspect provenance', fr: 'Entrée intemporelle ou disponibilité inconnue — examiner la provenance' })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      </div>
    </details>
  );
}

function EvidenceList({ run, scope }: { run: Run; scope: FactScope }) {
  const { tr } = useApp();
  const { openEvidence } = useFactDrawer();
  const items = Object.values(run.evidence);
  return (
    <details className="fold section-fold" id="evidence" data-section={tr({ en: 'Evidence', fr: 'Preuves' })}>
      <summary>{tr({ en: `Evidence (${items.length})`, fr: `Preuves (${items.length})` })}</summary>
      <div className="fold-body">
      {items.length === 0 ? <Empty>{tr({ en: 'No document evidence was collected in this analysis.', fr: 'Aucune preuve documentaire n’a été recueillie dans cette analyse.' })}</Empty> : (
        <ul className="list-plain">
          {items.map(e => (
            <li key={e.id}>
              <button type="button" className="linklike" onClick={() => openEvidence(scope, e.id)}><span className="mono">{e.id}</span> {e.title}</button>
              <span className="block small muted">{e.publisher}, {tr({ en: 'tier', fr: 'niveau' })} {e.tier}. {tr(e.claim)}</span>
            </li>
          ))}
        </ul>
      )}
      </div>
    </details>
  );
}

const ATTEMPT_PILL = { saved: 's-pass', nothing: 's-info', failed: 's-tension' } as const;

/**
 * Every external-source call of the research step with a plain reason (QA 7.5), from the run payload's
 * research toolCalls. Addresses are reduced to their host; fetched page text is never shown. Opens by
 * default when every attempt failed, and when the page is reached at #sources-tried.
 */
function SourcesTried({ run }: { run: Run }) {
  const { tr } = useApp();
  const attempts = researchAttempts(run);
  const ref = useRef<HTMLDetailsElement>(null);
  const failedAll = allAttemptsFailed(attempts);
  const [open, setOpen] = useState(failedAll);
  // A run still in progress gets its research calls later: open when they all failed, unless the user
  // already opened or closed the fold.
  const userToggled = useRef(false);
  useEffect(() => { if (failedAll && !userToggled.current) setOpen(true); }, [failedAll]);
  useEffect(() => {
    const reveal = () => {
      if (window.location.hash !== `#${SOURCES_TRIED_ID}`) return;
      setOpen(true);
      ref.current?.scrollIntoView({ block: 'start' });
    };
    reveal();
    window.addEventListener('hashchange', reveal);
    return () => window.removeEventListener('hashchange', reveal);
  }, []);
  return (
    <details ref={ref} className="fold section-fold" id={SOURCES_TRIED_ID} data-section={tr({ en: 'Sources tried', fr: 'Sources essayées' })}
      open={open} onToggle={e => {
        // A toggle that differs from the state came from the user, not from setOpen.
        if (e.currentTarget.open !== open) userToggled.current = true;
        setOpen(e.currentTarget.open);
      }}>
      <summary>{tr({ en: `Sources tried (${attempts.length})`, fr: `Sources essayées (${attempts.length})` })}</summary>
      <div className="fold-body">
        {attempts.length === 0 ? <Empty>{tr({ en: 'No external source was tried in this analysis.', fr: 'Aucune source externe n’a été essayée dans cette analyse.' })}</Empty> : (
          <>
            <p className="small muted">{tr({
              en: 'Each call the research step made to an external source, and what came of it. Addresses are shown by site only.',
              fr: 'Chaque appel de l’étape de recherche à une source externe, et ce qu’il a donné. Les adresses ne sont indiquées que par site.',
            })}</p>
            <ul className="list-plain">
              {attempts.map(a => (
                <li key={a.id}>
                  <span className={`pill ${ATTEMPT_PILL[a.outcome]}`}>{tr(ATTEMPT_OUTCOME[a.outcome])}</span>{' '}
                  <strong>{tr(researchToolLabel(a.tool))}</strong>
                  {a.target && <> · <span className="mono break">{a.target}</span></>}
                  {a.reason && <span className="block small muted">{tr(a.reason)}</span>}
                  {a.technical && (
                    <details className="tech-details">
                      <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
                      <p className="mono small break">{a.tool} · {a.technical}</p>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </details>
  );
}

function DatasetsUsed({ run }: { run: Run }) {
  const { tr } = useApp();
  const used = new Map<string, Set<string>>();
  const add = (datasetId: string, version: string) => {
    const set = used.get(datasetId) ?? new Set<string>();
    set.add(version);
    used.set(datasetId, set);
  };
  for (const step of run.steps) for (const call of step.toolCalls) for (const d of call.datasetsRead) add(d.datasetId, d.dataVersion);
  for (const fact of Object.values(run.facts)) for (const s of fact.sources) add(s.datasetId, s.dataVersion);
  return (
    <details className="fold section-fold" id="datasets" data-section={tr({ en: 'Data', fr: 'Données' })}>
      <summary>{tr({ en: 'Data sources used', fr: 'Sources de données utilisées' })}</summary>
      <div className="fold-body">
      {used.size === 0 ? <Empty>{tr({ en: 'No dataset read was recorded.', fr: 'Aucune lecture de données n’a été enregistrée.' })}</Empty> : (
        <ul className="list-plain">
          {[...used.entries()].flatMap(([datasetId, versions]) => [...versions].map(version => (
            <li key={`${datasetId}-${version}`}>
              <Link href={`/sources/?datasetId=${encodeURIComponent(datasetId)}&dataVersion=${encodeURIComponent(version)}`} className="mono">{datasetId}</Link>
              <span className="small muted">, {version}</span>
            </li>
          )))}
        </ul>
      )}
      </div>
    </details>
  );
}

function SabotageControls({ run }: { run: Run }) {
  const { tr, lang, feature } = useApp();
  const router = useRouter();
  const [mode, setMode] = useState<SabotageMode>('invented_number');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  if (!feature('sabotage_demo') || run.kind !== 'decision' || run.status !== 'succeeded') return null;
  const title = tr({ en: 'Sabotage test: try to slip a lie past the auditor', fr: 'Test de sabotage : glisser un mensonge à l’auditeur' });
  if (run.lang !== lang) {
    return (
      <Card id="sabotage" section={tr({ en: 'Sabotage test', fr: 'Test de sabotage' })} tour="sabotage" title={title}>
        <p className="small muted">{tr({ en: 'This analysis was written in French. Switch the language to French to run the test on it.', fr: 'Cette analyse a été rédigée en anglais. Passez en anglais pour lancer le test sur elle.' })}</p>
      </Card>
    );
  }
  const start = async () => {
    setBusy(true); setError(null);
    try {
      const created = await getApiClient().sabotage(run.runId, { mode, lang });
      router.push(`/evidence-audit/?runId=${encodeURIComponent(created.runId)}`);
    } catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return (
    <Card id="sabotage" section={tr({ en: 'Sabotage test', fr: 'Test de sabotage' })} tour="sabotage" title={title}>
      <p className="small">{tr({ en: 'Aplomb copies this signed brief, inserts one false sentence built from its own figures, then runs the full audit again (code checks, model review, guardrail). This analysis stays unchanged; the outcome is shown as it is.', fr: 'Aplomb copie cette note signée, y insère une phrase fausse construite à partir de ses propres chiffres, puis relance l’audit complet (contrôles par le code, relecture par le modèle, garde-fou). Cette analyse reste inchangée ; le résultat est montré tel quel.' })}</p>
      <fieldset>
        <legend>{tr({ en: 'Kind of lie', fr: 'Type de mensonge' })}</legend>
        <div className="checks">
          {SABOTAGE_MODES.map(m => (
            <label key={m}><input type="radio" name="sabotage-mode" value={m} checked={mode === m} onChange={() => setMode(m)} /> {labelOf(SABOTAGE_MODE, m, lang)}</label>
          ))}
        </div>
      </fieldset>
      <div className="row-actions"><button type="button" className="btn danger" disabled={busy} onClick={() => void start()}>{busy ? tr({ en: 'Starting…', fr: 'Lancement…' }) : tr({ en: 'Run the sabotage test', fr: 'Lancer le test de sabotage' })}</button></div>
      {error && <ErrorState error={error} />}
    </Card>
  );
}

function SabotageResultView({ run }: { run: Run }) {
  const { tr, lang } = useApp();
  if (run.result?.kind !== 'sabotage') return null;
  const s = run.result.sabotage;
  const failed = s.failedChecks.filter(c => !c.ok);
  const caught = s.caught && failed.length > 0;
  const injected = s.briefAfterAudit.sections.flatMap(section => section.sentences).find(sentence => sentence.id === 'S-INJECTED');
  const attempted = s.briefBeforeAudit.sections.some(section => section.sentences.some(sentence => sentence.id === 'S-INJECTED'));
  const codes = [...new Set(failed.map(c => c.code))];
  return (
    <Card id="sabotage-result" title={tr({ en: 'Sabotage test result', fr: 'Résultat du test de sabotage' })}>
      <div className={`sabotage-verdict ${caught ? 'is-caught' : 'is-missed'}`} role="status">
        <span className="sabotage-verdict-mark" aria-hidden="true">{caught ? '✓' : '!'}</span>
        <div>
          <p className="sabotage-verdict-title">
            {caught
              ? tr({ en: 'Caught: the auditor struck the false sentence', fr: 'Détecté : l’auditeur a rayé la phrase fausse' })
              : attempted
                ? tr({ en: 'Not caught: the false sentence passed the checks', fr: 'Non détecté : la phrase fausse a passé les contrôles' })
                : tr({ en: 'No false sentence was inserted; there was nothing to catch', fr: 'Aucune phrase fausse insérée ; il n’y avait rien à détecter' })}
          </p>
          <p className="small"><span className="tag tag-strong">{labelOf(SABOTAGE_MODE, s.mode, lang)}</span>{' '}
            {tr({ en: 'The original analysis and its signature are unchanged.', fr: 'L’analyse d’origine et sa signature sont inchangées.' })}</p>
        </div>
      </div>
      <h3 className="h4">{tr({ en: 'What was inserted', fr: 'Ce qui a été inséré' })}</h3>
      <p className="small">{s.injectedInstruction}</p>
      {injected && (
        <>
          <h3 className="h4">{tr({ en: 'The false sentence, as the auditor marked it', fr: 'La phrase fausse, telle que l’auditeur l’a marquée' })}</h3>
          <div className="sabotage-sentence"><SentenceView sentence={injected} mode="audit" /></div>
        </>
      )}
      {codes.length > 0 && (
        <>
          <h3 className="h4">{tr({ en: 'Checks that caught it', fr: 'Contrôles qui l’ont détectée' })}</h3>
          <ul className="list-plain small">
            {codes.map(code => {
              const details = [...new Set(failed.filter(c => c.code === code).map(c => c.detail))];
              return <li key={code}><span className="mono">{code}</span> {labelOf(AUDIT_CHECK, code, lang)}{details.length > 0 && <span className="muted"> · {details.join(' · ')}</span>}</li>;
            })}
          </ul>
        </>
      )}
      <details className="fold">
        <summary>{tr({ en: 'Full brief after audit', fr: 'Note complète après audit' })}</summary>
        <div className="fold-body"><BriefView brief={s.briefAfterAudit} mode="audit" /></div>
      </details>
      <details className="fold">
        <summary>{tr({ en: 'Raw draft before audit (unaudited, may contain falsehoods)', fr: 'Brouillon brut avant audit (non audité, peut contenir des faussetés)' })}</summary>
        <div className="fold-body">
          {s.briefBeforeAudit.sections.map(section => <section key={section.id}>
            <h4>{section.id}</h4>{section.sentences.map(sentence => <p key={sentence.id} className={`mono small${sentence.id === 'S-INJECTED' ? ' sabotage-raw-injected' : ''}`}>{sentence.template}</p>)}
          </section>)}
        </div>
      </details>
    </Card>
  );
}
