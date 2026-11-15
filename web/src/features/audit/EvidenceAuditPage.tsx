'use client';
/**
 * Evidence & Audit (T14, web/page-specs/evidence-audit.md). Loads the owned run (or lists session runs),
 * shows the brief with audit markings, a searchable fact ledger, rule checks, A01–A14 results, the
 * actual timeline and the datasets read. ?factId= deep-links the fact drawer (AUDUI-06).
 */
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
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
import { BriefView } from '../../components/run/BriefView';
import { RuleTable } from '../../components/run/RuleTable';
import { RunTimeline } from '../../components/run/RunTimeline';
import { AuditPanel } from '../../components/run/AuditPanel';
import { FACT_KIND, RUN_KIND, RUN_STATUS, SABOTAGE_MODE, VERIFICATION, labelOf } from '../../lib/labels';
import { fmtDateTime, fmtDuration } from '../../lib/format';
import { briefsOf, danglingReferences } from '../../lib/brief';

const SABOTAGE_MODES: readonly SabotageMode[] = ['invented_number', 'false_comparison', 'unsupported_interpretation'];

export function EvidenceAuditPage() {
  const params = useSearchParams();
  const runId = params.get('runId');
  return runId ? <RunAudit key={runId} runId={runId} factId={params.get('factId')} /> : <RunList />;
}

function RunList() {
  const { tr, lang, sessionId } = useApp();
  // The session's run list changes as runs are created: always refetch when the list is shown.
  useState(() => invalidateQueries(key => key.startsWith('runs|')));
  const runs = useQuery<RunsResponse>(sessionId ? `runs|${sessionId}` : null, signal => getApiClient().runs({ limit: 50 }, signal));
  return (
    <>
      <PageHeader eyebrow={tr({ en: 'Evidence & Audit', fr: 'Preuves et audit' })} title={tr({ en: 'Runs in this session', fr: 'Exécutions de cette session' })}>
        <p className="page-sub">{tr({ en: 'Pick a run to inspect its ledger, audit and execution trace. Runs of other sessions are not accessible.', fr: 'Choisissez une exécution pour examiner son registre, son audit et sa trace. Les exécutions d’autres sessions ne sont pas accessibles.' })}</p>
      </PageHeader>
      <Card>
        {runs.loading && <Loading />}
        {runs.error && <ErrorState error={runs.error} onRetry={runs.reload} />}
        {runs.data && runs.data.items.length === 0 && (
          <Empty>{tr({ en: 'No runs yet. Start one from the Decision Desk or Home.', fr: 'Aucune exécution. Lancez-en une depuis le Pupitre de décision ou l’Accueil.' })}</Empty>
        )}
        {runs.data && runs.data.items.length > 0 && (
          <div className="table-scroll" role="region" aria-label={tr({ en: 'Session runs', fr: 'Exécutions de la session' })} tabIndex={0}>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">{tr({ en: 'Run', fr: 'Exécution' })}</th>
                  <th scope="col">{tr({ en: 'Kind', fr: 'Type' })}</th>
                  <th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th>
                  <th scope="col">{tr({ en: 'Verdict', fr: 'Verdict' })}</th>
                  <th scope="col">{tr({ en: 'Created', fr: 'Créée' })}</th>
                  <th scope="col" className="num-col">{tr({ en: 'Duration', fr: 'Durée' })}</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map(item => (
                  <tr key={item.runId}>
                    <th scope="row">
                      <Link href={`/evidence-audit/?runId=${encodeURIComponent(item.runId)}`}>{tr(item.title)}</Link>
                      <span className="block small mono muted">{item.runId}</span>
                    </th>
                    <td>{labelOf(RUN_KIND, item.kind, lang)}</td>
                    <td><RunStatusBadge status={item.status} /></td>
                    <td>{item.verdict ? <VerdictBadge verdict={item.verdict} /> : '—'}</td>
                    <td className="small">{fmtDateTime(item.createdAt, lang)}</td>
                    <td className="num-col">{fmtDuration(item.durationMs, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

  return (
    <>
      <PageHeader eyebrow={tr({ en: 'Evidence & Audit', fr: 'Preuves et audit' })} title={run ? labelOf(RUN_KIND, run.kind, lang) : tr({ en: 'Run', fr: 'Exécution' })}>
        <p className="small mono muted">{runId}</p>
        <p><Link href="/evidence-audit/">{tr({ en: 'All runs in this session', fr: 'Toutes les exécutions de la session' })}</Link></p>
      </PageHeader>
      {polled.loading && !run && <Loading />}
      {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
        {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This run does not exist or belongs to another session.', fr: 'Cette exécution n’existe pas ou appartient à une autre session.' }) } : {})} />}
      {run && scope && (
        <FactScopeProvider scope={scope}>
          <RunHeader run={run} />
          {dangling.length > 0 && (
            <div className="state state-error" role="alert">
              <p className="state-title">{tr({ en: 'Some references do not resolve inside this run:', fr: 'Certaines références ne se résolvent pas dans cette exécution :' })}</p>
              <p className="mono small">{dangling.join(', ')}</p>
            </div>
          )}
          {run.status === 'failed' && (
            <p className="stale-note">{tr({ en: 'This run failed: there is no signed result. The trace and any facts computed before the failure remain visible.', fr: 'Cette exécution a échoué : il n’y a aucun résultat signé. La trace et les faits calculés avant l’échec restent visibles.' })}</p>
          )}
          {run.result?.kind === 'sabotage' && <SabotageResultView run={run} />}
          {brief && (
            <div className="cols">
              <Card id="brief" title={tr({ en: 'Brief with audit markings', fr: 'Note avec marques d’audit' })}>
                <p className="small muted">{tr({ en: 'Struck sentences are shown here only, with the checks they failed.', fr: 'Les phrases rayées ne sont montrées qu’ici, avec les vérifications échouées.' })}</p>
                <BriefView brief={brief} mode="audit" />
              </Card>
              <Card id="audit" title={tr({ en: 'Audit report', fr: 'Rapport d’audit' })}>
                <AuditPanel audit={brief.audit} run={run} />
              </Card>
            </div>
          )}
          <RuleChecksPanel run={run} />
          <FactLedger run={run} scope={scope} />
          <EvidenceList run={run} scope={scope} />
          <Card id="timeline" title={tr({ en: 'Execution timeline', fr: 'Chronologie d’exécution' })}>
            <RunTimeline run={run} />
          </Card>
          <DatasetsUsed run={run} />
          <SabotageControls run={run} />
        </FactScopeProvider>
      )}
    </>
  );
}

function RunHeader({ run }: { run: Run }) {
  const { tr, lang } = useApp();
  return (
    <Card>
      <div className="verdict-header">
        <RunStatusBadge status={run.status} />
        {run.result?.kind === 'decision' && <VerdictBadge verdict={run.result.decision.verdict} />}
        {run.flags.sabotage && <span className="tag tag-strong">{tr({ en: 'Sabotage demonstration', fr: 'Démonstration de sabotage' })}: {labelOf(SABOTAGE_MODE, run.flags.sabotage, lang)}</span>}
        {run.flags.timeMachine && <span className="tag">{tr({ en: 'Historical replay', fr: 'Rejeu historique' })}</span>}
        {run.flags.fixture && <span className="tag">{tr({ en: 'Development fixture — no agents executed', fr: 'Jeu d’essai — aucun agent exécuté' })}</span>}
      </div>
      <p className="small muted">
        {tr({ en: 'Profile', fr: 'Profil' })} <span className="mono">{run.profileId ?? '—'}</span> · {tr({ en: 'information date', fr: 'date d’information' })} {run.asOf} · <span className="mono">{run.dataVersion}</span> · {tr({ en: 'created', fr: 'créée' })} {fmtDateTime(run.createdAt, lang)} · {run.lang.toUpperCase()}
      </p>
      {run.parentRunId && (
        <p className="small">{tr({ en: 'Derived from parent run (left unchanged)', fr: 'Dérivée de l’exécution parente (laissée inchangée)' })}: <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.parentRunId)}`} className="mono">{run.parentRunId}</Link></p>
      )}
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
    <Card id="rules" title={tr({ en: 'Rule checks and assumptions', fr: 'Vérifications et hypothèses de règles' })}>
      <RuleTable checks={checks} rules={rules} caption={tr({ en: 'Rule checks of the selected scenario', fr: 'Vérifications du scénario sélectionné' })} />
      {run.result?.kind === 'decision' && <LimitationList codes={run.result.decision.limitations} />}
    </Card>
  );
}

function FactLedger({ run, scope }: { run: Run; scope: FactScope }) {
  const { tr, lang } = useApp();
  const { openFact } = useFactDrawer();
  const [query, setQuery] = useState('');
  const facts = Object.values(run.facts);
  const q = query.trim().toLowerCase();
  const filtered = q
    ? facts.filter(f => [f.id, f.metric, f.kind, f.key, f.label.en, f.label.fr].some(v => v.toLowerCase().includes(q)))
    : facts;
  return (
    <Card id="ledger" title={tr({ en: `Fact ledger (${facts.length})`, fr: `Registre des faits (${facts.length})` })}>
      <div className="search-row">
        <label htmlFor="ledger-search" className="sr-only">{tr({ en: 'Search facts', fr: 'Rechercher des faits' })}</label>
        <input id="ledger-search" type="search" value={query} onChange={e => setQuery(e.target.value)}
          placeholder={tr({ en: 'Search by ID, metric or kind', fr: 'Rechercher par ID, mesure ou nature' })} />
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
              </tr>
            </thead>
            <tbody>
              {filtered.map(fact => (
                <tr key={fact.id}>
                  <th scope="row"><button type="button" className="linklike mono" onClick={() => openFact(scope, fact.id)}>{fact.id}</button></th>
                  <td>{tr(fact.label)}<span className="block small mono muted break">{fact.metric}</span></td>
                  <td>{labelOf(FACT_KIND, fact.kind, lang)}</td>
                  <td className="num-col num">{tr(fact.display)}</td>
                  <td>{labelOf(VERIFICATION, fact.verification.status, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function EvidenceList({ run, scope }: { run: Run; scope: FactScope }) {
  const { tr } = useApp();
  const { openEvidence } = useFactDrawer();
  const items = Object.values(run.evidence);
  return (
    <Card id="evidence" title={tr({ en: `Evidence (${items.length})`, fr: `Preuves (${items.length})` })}>
      {items.length === 0 ? <Empty>{tr({ en: 'No research evidence was collected in this run.', fr: 'Aucune preuve documentaire n’a été recueillie dans cette exécution.' })}</Empty> : (
        <ul className="list-plain">
          {items.map(e => (
            <li key={e.id}>
              <button type="button" className="linklike" onClick={() => openEvidence(scope, e.id)}><span className="mono">{e.id}</span> {e.title}</button>
              <span className="block small muted">{e.publisher} · {tr({ en: 'tier', fr: 'niveau' })} {e.tier} · {tr(e.claim)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
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
    <Card id="datasets" title={tr({ en: 'Data sources used', fr: 'Sources de données utilisées' })}>
      {used.size === 0 ? <Empty>{tr({ en: 'No dataset read was recorded.', fr: 'Aucune lecture de données n’a été enregistrée.' })}</Empty> : (
        <ul className="list-plain">
          {[...used.entries()].flatMap(([datasetId, versions]) => [...versions].map(version => (
            <li key={`${datasetId}-${version}`}>
              <Link href={`/sources/?datasetId=${encodeURIComponent(datasetId)}&dataVersion=${encodeURIComponent(version)}`} className="mono">{datasetId}</Link>
              <span className="small muted"> · {version}</span>
            </li>
          )))}
        </ul>
      )}
    </Card>
  );
}

function SabotageControls({ run }: { run: Run }) {
  const { tr, lang, feature } = useApp();
  const router = useRouter();
  const [mode, setMode] = useState<SabotageMode>('invented_number');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  if (!feature('sabotage_demo') || run.kind !== 'decision' || run.status !== 'succeeded') return null;
  const start = async () => {
    setBusy(true); setError(null);
    try {
      const created = await getApiClient().sabotage(run.runId, { mode, lang });
      router.push(`/evidence-audit/?runId=${encodeURIComponent(created.runId)}`);
    } catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return (
    <Card id="sabotage" title={tr({ en: 'Sabotage demonstration (labelled test)', fr: 'Démonstration de sabotage (test identifié)' })}>
      <p className="small">{tr({ en: 'Creates a separate child run in which the writer receives an instruction to lie. This run stays unchanged. The auditor may or may not catch it; the outcome is reported as it happens.', fr: 'Crée une exécution enfant distincte où le rédacteur reçoit l’instruction de mentir. Cette exécution reste inchangée. L’auditeur peut ou non le détecter ; le résultat est rapporté tel quel.' })}</p>
      <fieldset>
        <legend>{tr({ en: 'Injected instruction type', fr: 'Type d’instruction injectée' })}</legend>
        <div className="checks">
          {SABOTAGE_MODES.map(m => (
            <label key={m}><input type="radio" name="sabotage-mode" value={m} checked={mode === m} onChange={() => setMode(m)} /> {labelOf(SABOTAGE_MODE, m, lang)}</label>
          ))}
        </div>
      </fieldset>
      <div className="row-actions"><button type="button" className="btn danger" disabled={busy} onClick={() => void start()}>{tr({ en: 'Start demonstration', fr: 'Lancer la démonstration' })}</button></div>
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
  const attempted = s.briefBeforeAudit.sections.some(section => section.sentences.some(sentence => sentence.id === 'S-INJECTED'));
  return (
    <Card id="sabotage-result" title={tr({ en: 'Sabotage demonstration result', fr: 'Résultat de la démonstration de sabotage' })}>
      <p className="small"><span className="tag tag-strong">{labelOf(SABOTAGE_MODE, s.mode, lang)}</span></p>
      <h3 className="h4">{tr({ en: 'Exact injected instruction', fr: 'Instruction injectée exacte' })}</h3>
      <blockquote className="quote mono small">{s.injectedInstruction}</blockquote>
      <p className="stale-note" role="status">
        {caught
          ? tr({ en: `The audit flagged the injected content: ${failed.map(c => c.code).join(', ')} failed.`, fr: `L’audit a signalé le contenu injecté : ${failed.map(c => c.code).join(', ')} en échec.` })
          : attempted ? tr({ en: 'An attempted assertion was not caught by the implemented checks.', fr: 'Une affirmation tentée n’a pas été détectée par les contrôles en place.' }) : tr({ en: 'The writer returned no designated attempted assertion; there was nothing to catch.', fr: 'Le rédacteur n’a fourni aucune affirmation désignée ; il n’y avait rien à détecter.' })}
      </p>
      <div className="grid-2">
        <div>
          <h3 className="h4">{tr({ en: 'Draft before audit (audit view)', fr: 'Brouillon avant audit (vue d’audit)' })}</h3>
          <p className="small">{tr({ en: 'Unaudited test draft: preserved parent content plus any designated assertion produced by the writer. Test content may be false.', fr: 'Brouillon de test non audité : contenu initial conservé et éventuelle affirmation désignée du rédacteur. Le test peut contenir des faussetés.' })}</p>
          {s.briefBeforeAudit.sections.map(section => <section key={section.id}>
            <h4>{section.id}</h4>{section.sentences.map(sentence => <p key={sentence.id}>{sentence.template}</p>)}
          </section>)}
        </div>
        <div>
          <h3 className="h4">{tr({ en: 'After audit', fr: 'Après audit' })}</h3>
          <BriefView brief={s.briefAfterAudit} mode="audit" />
        </div>
      </div>
      {s.failedChecks.length > 0 && (
        <ul className="list-plain small">
          {s.failedChecks.map((c, i) => <li key={i}><span className="mono">{c.code}</span> {c.ok ? '✓' : '✕'} {c.detail} <span className="mono muted">{c.sentenceIds.join(', ')}</span></li>)}
        </ul>
      )}
    </Card>
  );
}
