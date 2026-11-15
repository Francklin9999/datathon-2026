'use client';
/**
 * Agents & System (T15, web/page-specs/agents-system.md): what actually ran. A static role map and
 * the approved service diagram annotated with the real `/meta` state, then a session run picker whose
 * selected run shows only the steps, tool calls, datasets and usage recorded in its payload. Nothing
 * is inferred from timers, no "skipped" placeholder exists, and the session capability is never shown.
 */
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { Run, RunSummary, RunsResponse, Step, ToolCall } from '../../contracts/types';
import { API_BASE, FIXTURES_ENABLED, getApiClient } from '../../api/index';
import { asApiError, isAbort, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useRun } from '../../state/useRun';
import { Card, PageHeader } from '../../components/common/Page';
import { Empty, ErrorState, Loading } from '../../components/common/States';
import { RunStatusBadge, VerdictBadge } from '../../components/common/Badges';
import { RunTimeline } from '../../components/run/RunTimeline';
import {
  ACTOR, AGENT_ROLE, ERROR_CODE, FEATURE_FLAG, RUN_KIND, RUN_STATUS, SABOTAGE_MODE, STEP_TYPE, labelOf,
} from '../../lib/labels';
import { fmtDate, fmtDateTime, fmtDuration, fmtNumber } from '../../lib/format';
import { isTerminal } from '../../lib/runs';
import {
  ARCHITECTURE, ROLE_CARDS, RUN_LIMITS, formatArgs, guardrailReading, runBudget, runGuardrailAudit, stepDeviations,
  stepProduced, workNature, siteBuildIdentity, type ArchNodeId, type GuardrailReading, type WorkNature,
} from '../../lib/system';

const PAGE_SIZE = 20;
const MAX_ID_LINKS = 12;

const NATURE_LABEL: Record<WorkNature, { en: string; fr: string }> = {
  model: { en: 'Model work', fr: 'Travail du modèle' },
  code: { en: 'Deterministic code', fr: 'Code déterministe' },
  mixed: { en: 'Deterministic code + model review', fr: 'Code déterministe + revue par modèle' },
};
const NATURE_CLASS: Record<WorkNature, string> = { model: 's-tension', code: 's-pass', mixed: 's-nee' };

export function AgentsSystemPage() {
  const { tr } = useApp();
  const params = useSearchParams();
  const runId = params.get('runId');
  // The selected run's live state, so its picker row does not keep the status read at page open.
  const [live, setLive] = useState<Run | null>(null);
  return (
    <>
      <PageHeader eyebrow={tr({ en: 'Agents & System', fr: 'Agents et système' })} title={tr({ en: 'What actually ran', fr: 'Ce qui s’est réellement exécuté' })}>
        <p className="page-sub">{tr({ en: 'Code computes every figure and verdict; models plan, research and explain. This page separates what is configured from what a run recorded.', fr: 'Le code calcule chaque chiffre et chaque verdict ; les modèles planifient, recherchent et expliquent. Cette page distingue ce qui est configuré de ce qu’une exécution a enregistré.' })}</p>
      </PageHeader>
      <BuildIdentity />
      <RoleMap />
      <ArchitectureCard />
      <RunPicker selectedId={runId} live={live && live.runId === runId ? live : null} />
      {runId && <RunDetail key={runId} runId={runId} onRun={setLive} />}
    </>
  );
}

function BuildIdentity() {
  const { tr, lang, meta } = useApp();
  const [build, setBuild] = useState<{ revision: string; builtAt: string } | null>(null);
  const [apiRevision, setApiRevision] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/deployment.json', { signal: controller.signal, cache: 'no-store' })
      .then(response => response.ok ? response.json() : null)
      .then(value => setBuild(siteBuildIdentity(value)))
      .catch(() => { if (!controller.signal.aborted) setBuild(null); });
    if (!FIXTURES_ENABLED) {
      fetch(`${API_BASE}/health`, { signal: controller.signal, cache: 'no-store' })
        .then(response => response.ok ? response.headers.get('X-Aplomb-Build') : null)
        .then(revision => setApiRevision(revision && /^[0-9a-f]{40}$/.test(revision) ? revision : null))
        .catch(() => { if (!controller.signal.aborted) setApiRevision(null); });
    }
    return () => controller.abort();
  }, []);
  return <Card title={tr({ en: 'Release identity', fr: 'Identité de la version' })}>
    {build ? <p className="small">{tr({ en: 'Frontend commit', fr: 'Commit de l’interface' })}: <span className="mono break">{build.revision}</span><br />
      {tr({ en: 'Frontend built', fr: 'Interface construite le' })}: {fmtDateTime(build.builtAt, lang)}</p>
      : <p className="small muted">{tr({ en: 'Frontend build manifest unavailable.', fr: 'Manifeste de l’interface indisponible.' })}</p>}
    <p className="small">{tr({ en: 'API contract version', fr: 'Version du contrat API' })}: <span className="mono">{meta?.contractVersion ?? '—'}</span> · {tr({ en: 'Dataset snapshot', fr: 'Instantané des données' })}: <span className="mono">{meta?.dataVersion ?? '—'}</span></p>
    <p className="small">{tr({ en: 'Backend commit', fr: 'Commit du serveur' })}: {apiRevision ? <span className="mono break">{apiRevision}</span> : tr({ en: 'unavailable', fr: 'indisponible' })}</p>
    <p className="small muted">{tr({ en: 'Backend identity comes from the API response header; feature flags are listed below.', fr: 'L’identité du serveur provient de l’en-tête de réponse API ; les fonctionnalités sont listées ci-dessous.' })}</p>
  </Card>;
}

function NatureBadge({ nature }: { nature: WorkNature }) {
  const { tr } = useApp();
  return <span className={`pill ${NATURE_CLASS[nature]}`}>{tr(NATURE_LABEL[nature])}</span>;
}

function RoleMap() {
  const { tr, lang } = useApp();
  return (
    <Card id="roles" title={tr({ en: 'Roles: who may do what', fr: 'Rôles : qui peut faire quoi' })}>
      <p className="small muted">{tr({ en: 'A static description of the design. It is not a claim that any of these ran; the selected run below shows that.', fr: 'Une description statique de la conception. Elle n’affirme pas que ces rôles se sont exécutés ; l’exécution sélectionnée ci-dessous le montre.' })}</p>
      <ul className="role-grid">
        {ROLE_CARDS.map(card => (
          <li key={card.role} className="role-card">
            <h3 className="h4">{labelOf(AGENT_ROLE, card.role, lang)}</h3>
            <p><NatureBadge nature={card.nature} /></p>
            <p className="small">{tr(card.purpose)}</p>
            <p className="small"><span className="eyebrow">{tr({ en: 'Steps', fr: 'Étapes' })}</span> {card.steps.map(step => labelOf(STEP_TYPE, step, lang)).join(', ')}</p>
            <p className="eyebrow">{tr({ en: 'Allowed tools', fr: 'Outils autorisés' })}</p>
            {card.tools.length === 0
              ? <p className="small"><strong>{tr({ en: 'None', fr: 'Aucun' })}</strong></p>
              : <ul className="tool-list">{card.tools.map(tool => <li key={tool} className="mono">{tool}</li>)}</ul>}
            <p className="small muted">{tr(card.toolsNote)}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ArchitectureCard() {
  const { tr, lang, meta } = useApp();
  if (!meta) return null;
  const flags = Object.entries(meta.features as Record<string, boolean>).sort(([a], [b]) => a.localeCompare(b));
  const titleOf = (id: ArchNodeId) => tr(ARCHITECTURE.find(node => node.id === id)?.title ?? { en: id, fr: id });
  const modelLine = (label: string, id: string | null) => (
    <span className="block">{label}: {id ? <span className="mono break">{id}</span> : <strong>{tr({ en: 'not configured', fr: 'non configuré' })}</strong>}</span>
  );
  const on = (flag: string) => Boolean((meta.features as Record<string, boolean>)[flag]);
  const state: Partial<Record<ArchNodeId, ReactNode>> = {
    api: <span className="block">{tr({ en: 'Reported by /meta: contract', fr: 'Indiqué par /meta : contrat' })} <span className="mono">{meta.contractVersion}</span></span>,
    s3: (
      <span className="block">
        {tr({ en: 'Data version', fr: 'Version des données' })} <span className="mono break">{meta.dataVersion}</span> · {tr({ en: 'data as of', fr: 'données au' })} {fmtDate(meta.dataAsOf, lang)}
      </span>
    ),
    bedrock: (
      <>
        {modelLine(tr({ en: 'Strong model ID', fr: 'Identifiant du modèle principal' }), meta.models.strong)}
        {modelLine(tr({ en: 'Fast model ID', fr: 'Identifiant du modèle rapide' }), meta.models.fast)}
        <span className="block">{tr({ en: 'Guardrails flag', fr: 'Indicateur de garde-fous' })}: <strong>{on('guardrails') ? tr({ en: 'on', fr: 'activé' }) : tr({ en: 'off', fr: 'désactivé' })}</strong></span>
      </>
    ),
    research: (
      <span className="block">{tr({ en: 'Open-web research flag', fr: 'Indicateur de recherche sur le Web ouvert' })}: <strong>{on('research_open_web') ? tr({ en: 'on', fr: 'activé' }) : tr({ en: 'off', fr: 'désactivé' })}</strong></span>
    ),
  };
  return (
    <Card id="architecture" title={tr({ en: 'Architecture and reported configuration', fr: 'Architecture et configuration déclarée' })}>
      <div className="state state-unavailable" role="note">
        <p className="state-title">{tr({ en: 'Configuration is not proof of execution', fr: 'Une configuration n’est pas une preuve d’exécution' })}</p>
        <p className="small">{tr({ en: 'The values below come from GET /meta. A model ID or a flag shown here says what this deployment is set up to use; it does not show that a Bedrock call occurred. A model call is evidenced only by the model ID and token usage recorded on a step of a run (below).', fr: 'Les valeurs ci-dessous viennent de GET /meta. Un identifiant de modèle ou un indicateur affiché ici dit ce que ce déploiement est configuré pour utiliser ; il ne montre pas qu’un appel Bedrock a eu lieu. Un appel de modèle n’est attesté que par l’identifiant de modèle et les jetons enregistrés sur une étape d’exécution (ci-dessous).' })}</p>
      </div>
      <p className="small">
        {tr({ en: 'Environment reported', fr: 'Environnement déclaré' })}: <strong>{meta.environment === 'aws' ? 'AWS' : tr({ en: 'local', fr: 'local' })}</strong>.{' '}
        {meta.environment === 'local' && tr({ en: 'This API reports a local environment: the AWS services named below are the approved target design, not what answered this page.', fr: 'Cette API déclare un environnement local : les services AWS nommés ci-dessous sont la conception cible approuvée, pas ce qui a répondu à cette page.' })}
      </p>
      <ol className="arch-list" aria-label={tr({ en: 'Approved service diagram, as a list of components and what each calls', fr: 'Schéma de services approuvé, en liste de composants et de leurs appels' })}>
        {ARCHITECTURE.map(node => (
          <li key={node.id} className="arch-node">
            <h3 className="h4">{tr(node.title)}</h3>
            <p className="small">{tr(node.role)}</p>
            {node.sendsTo.length > 0 && (
              <ul className="small arch-edges">
                {node.sendsTo.map(edge => (
                  <li key={edge.to}><span aria-hidden="true">→ </span><strong>{titleOf(edge.to)}</strong>: {tr(edge.label)}</li>
                ))}
              </ul>
            )}
            {state[node.id] && <p className="small arch-state">{state[node.id]}</p>}
          </li>
        ))}
      </ol>
      <h3 className="h4">{tr({ en: 'Feature flags reported by /meta', fr: 'Indicateurs de fonctionnalités déclarés par /meta' })}</h3>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Feature flags', fr: 'Indicateurs de fonctionnalités' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Feature', fr: 'Fonctionnalité' })}</th>
              <th scope="col">{tr({ en: 'Flag', fr: 'Indicateur' })}</th>
              <th scope="col">{tr({ en: 'State', fr: 'État' })}</th>
            </tr>
          </thead>
          <tbody>
            {flags.map(([flag, enabled]) => (
              <tr key={flag}>
                <th scope="row">{labelOf(FEATURE_FLAG, flag, lang)}</th>
                <td className="mono small">{flag}</td>
                <td><span className={`pill ${enabled ? 's-pass' : 's-nee'}`}>{enabled ? tr({ en: 'On', fr: 'Activé' }) : tr({ en: 'Off', fr: 'Désactivé' })}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

interface PickerState { items: RunSummary[]; nextCursor: string | null; loading: boolean; error: ApiRequestError | null; loaded: boolean }

function RunPicker({ selectedId, live }: { selectedId: string | null; live: Run | null }) {
  const { tr, lang, sessionId, profiles } = useApp();
  const [state, setState] = useState<PickerState>({ items: [], nextCursor: null, loading: false, error: null, loaded: false });
  const [nonce, setNonce] = useState(0);

  // The session's run list changes as runs are created: always fetch it fresh when the page opens.
  useEffect(() => {
    if (!sessionId) return undefined;
    const controller = new AbortController();
    setState({ items: [], nextCursor: null, loading: true, error: null, loaded: false });
    getApiClient().runs({ limit: PAGE_SIZE }, controller.signal).then(
      (page: RunsResponse) => setState({ items: page.items, nextCursor: page.nextCursor, loading: false, error: null, loaded: true }),
      error => { if (!isAbort(error) && !controller.signal.aborted) setState(s => ({ ...s, loading: false, error: asApiError(error) })); },
    );
    return () => controller.abort();
  }, [sessionId, nonce]);

  const more = async () => {
    if (!state.nextCursor) return;
    const cursor = state.nextCursor;
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const page = await getApiClient().runs({ limit: PAGE_SIZE, cursor });
      setState(s => ({
        items: [...s.items, ...page.items.filter(item => !s.items.some(existing => existing.runId === item.runId))],
        nextCursor: page.nextCursor, loading: false, error: null, loaded: true,
      }));
    } catch (error) {
      setState(s => ({ ...s, loading: false, error: asApiError(error) }));
    }
  };

  return (
    <Card id="runs" title={tr({ en: 'Runs of this session', fr: 'Exécutions de cette session' })}
      actions={<button type="button" className="btn ghost btn-sm" onClick={() => setNonce(n => n + 1)} disabled={state.loading}>{tr({ en: 'Refresh', fr: 'Actualiser' })}</button>}>
      <p className="small muted">{tr({ en: 'Only runs created from this browser session are listed. Pick one to see what it recorded.', fr: 'Seules les exécutions créées depuis cette session de navigateur sont listées. Choisissez-en une pour voir ce qu’elle a enregistré.' })}</p>
      {state.loaded && state.items.length === 0 && !state.error && (
        <Empty>{tr({ en: 'No run yet in this session. Start one from Home, the Decision Desk, the World Explorer or the Time Machine.', fr: 'Aucune exécution dans cette session. Lancez-en une depuis l’Accueil, le Pupitre de décision, l’Explorateur mondial ou la Machine à remonter le temps.' })}</Empty>
      )}
      {state.items.length > 0 && (
        <div className="table-scroll" role="region" aria-label={tr({ en: 'Session runs', fr: 'Exécutions de la session' })} tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{tr({ en: 'Run', fr: 'Exécution' })}</th>
                <th scope="col">{tr({ en: 'Kind', fr: 'Type' })}</th>
                <th scope="col">{tr({ en: 'Profile', fr: 'Profil' })}</th>
                <th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th>
                <th scope="col">{tr({ en: 'Verdict', fr: 'Verdict' })}</th>
                <th scope="col">{tr({ en: 'Created', fr: 'Créée' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Duration', fr: 'Durée' })}</th>
              </tr>
            </thead>
            <tbody>
              {state.items.map(item => (
                <tr key={item.runId} className={item.runId === selectedId ? 'row-selected' : ''}>
                  <th scope="row">
                    <Link href={`/agents-system/?runId=${encodeURIComponent(item.runId)}#run-detail`} aria-current={item.runId === selectedId ? 'true' : undefined}>{tr(item.title)}</Link>
                    <span className="block small mono muted">{item.runId}</span>
                  </th>
                  <td>{labelOf(RUN_KIND, item.kind, lang)}</td>
                  <td>{item.profileId ? (profiles.find(p => p.profileId === item.profileId)?.name ?? item.profileId) : '—'}</td>
                  <td><RunStatusBadge status={live && live.runId === item.runId ? live.status : item.status} /></td>
                  <td>{item.verdict ? <VerdictBadge verdict={item.verdict} /> : '—'}</td>
                  <td className="small">{fmtDateTime(item.createdAt, lang)}</td>
                  <td className="num-col">{fmtDuration(item.durationMs, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {state.loading && <Loading />}
      {state.error && <ErrorState error={state.error} onRetry={() => (state.loaded && state.nextCursor ? void more() : setNonce(n => n + 1))} />}
      {state.loaded && (
        <p className="row-actions small">
          <span>{tr({ en: `${state.items.length} run(s) loaded`, fr: `${state.items.length} exécution(s) chargée(s)` })}{state.nextCursor ? tr({ en: '; more exist.', fr: ' ; il en existe d’autres.' }) : tr({ en: '; that is all of them.', fr: ' ; ce sont toutes les exécutions.' })}</span>
          {state.nextCursor && !state.loading && (
            <button type="button" className="btn ghost btn-sm" onClick={() => void more()}>{tr({ en: 'Load more runs', fr: 'Charger plus d’exécutions' })}</button>
          )}
        </p>
      )}
    </Card>
  );
}

const GUARDRAIL_TEXT: Record<GuardrailReading, { en: string; fr: string }> = {
  no_brief: { en: 'This run has no signed brief, so no guardrail record exists for it.', fr: 'Cette exécution n’a pas de note signée ; aucun enregistrement de garde-fou n’existe pour elle.' },
  applied: { en: 'Configured (flag on) and applied to this run’s brief.', fr: 'Configuré (indicateur activé) et appliqué à la note de cette exécution.' },
  applied_flag_off: { en: 'Applied to this run’s brief, although /meta now reports the flag off.', fr: 'Appliqué à la note de cette exécution, bien que /meta déclare maintenant l’indicateur désactivé.' },
  configured_not_applied: { en: 'Configured (flag on) but not applied to this run’s brief.', fr: 'Configuré (indicateur activé) mais non appliqué à la note de cette exécution.' },
  not_configured: { en: 'Not configured (flag off) and not applied.', fr: 'Non configuré (indicateur désactivé) et non appliqué.' },
};

function RunDetail({ runId, onRun }: { runId: string; onRun: (run: Run | null) => void }) {
  const { tr, lang, announce, profiles, feature } = useApp();
  const router = useRouter();
  const polled = useRun(runId, finished => announce(`${labelOf(RUN_KIND, finished.kind, lang)}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;
  useEffect(() => { onRun(run); }, [run, onRun]);
  const headingRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { headingRef.current?.focus(); }, [runId]);

  return (
    <div ref={headingRef} tabIndex={-1} id="run-detail" className="focus-target">
      <Card title={`${tr({ en: 'Selected run', fr: 'Exécution sélectionnée' })}${run ? ` · ${labelOf(RUN_KIND, run.kind, lang)}` : ''}`}
        actions={<button type="button" className="btn ghost btn-sm" onClick={() => router.push('/agents-system/#runs')}>{tr({ en: 'Close run', fr: 'Fermer l’exécution' })}</button>}>
        <p className="small mono muted break">{runId}</p>
        {polled.loading && !run && <Loading />}
        {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
          {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This run does not exist or belongs to another session.', fr: 'Cette exécution n’existe pas ou appartient à une autre session.' }) } : {})} />}
        {polled.pollError && (
          <p className="small muted" role="status">{tr({ en: 'Polling paused after an error; retrying with backoff.', fr: 'Interrogation suspendue après une erreur ; nouvel essai progressif.' })} ({polled.pollError.code})</p>
        )}
        {run && <RunBody run={run} profileName={run.profileId ? (profiles.find(p => p.profileId === run.profileId)?.name ?? run.profileId) : null} guardrailsConfigured={feature('guardrails')} />}
      </Card>
    </div>
  );
}

function StateLine({ run }: { run: Run }) {
  const { tr } = useApp();
  const text = (() => {
    switch (run.status) {
      case 'queued': return tr({ en: 'Queued: no step has started. Nothing is shown until a step is recorded.', fr: 'En file : aucune étape n’a commencé. Rien n’est affiché tant qu’aucune étape n’est enregistrée.' });
      case 'running': return tr({ en: 'Running: steps appear as the worker records them.', fr: 'En cours : les étapes apparaissent à mesure que le traitement les enregistre.' });
      case 'waiting_input': return tr({ en: 'Waiting for an answer to a clarifying question; the run resumes from the same state once answered.', fr: 'En attente d’une réponse à une question de clarification ; l’exécution reprend du même état une fois la réponse donnée.' });
      case 'succeeded': return tr({ en: 'Terminal: a signed result exists.', fr: 'Terminal : un résultat signé existe.' });
      case 'failed': return tr({ en: 'Terminal: failed. The steps executed before the failure remain below; no signed result exists.', fr: 'Terminal : échec. Les étapes réalisées avant l’échec restent ci-dessous ; aucun résultat signé n’existe.' });
      default: return tr({ en: 'Terminal: cancelled. No signed result exists.', fr: 'Terminal : annulée. Aucun résultat signé n’existe.' });
    }
  })();
  return <p className="small"><RunStatusBadge status={run.status} /> {text}</p>;
}

function RunBody({ run, profileName, guardrailsConfigured }: { run: Run; profileName: string | null; guardrailsConfigured: boolean }) {
  const { tr, lang } = useApp();
  const budget = useMemo(() => runBudget(run), [run]);
  const guardrailAudit = runGuardrailAudit(run);
  const reading = guardrailReading(guardrailsConfigured, guardrailAudit);
  const auditHref = `/evidence-audit/?runId=${encodeURIComponent(run.runId)}`;
  const question = run.status === 'waiting_input' ? run.question : null;
  const continueHref = run.kind === 'replay' ? `/time-machine/?runId=${encodeURIComponent(run.runId)}`
    : run.kind === 'decision' ? `/decision-desk/?runId=${encodeURIComponent(run.runId)}` : null;

  return (
    <>
      {run.flags.fixture && <p className="banner banner-fixture">{tr({ en: 'Development fixture: these steps are illustrative and were not executed.', fr: 'Jeu d’essai de développement : ces étapes sont illustratives et n’ont pas été exécutées.' })}</p>}
      <StateLine run={run} />
      {question && (
        <div className="state" role="note">
          <p className="state-title">{tr({ en: 'Question the run is waiting on', fr: 'Question attendue par l’exécution' })}</p>
          <p>{tr(question.text)}</p>
          {continueHref && <Link href={continueHref}>{tr({ en: 'Answer it where the run was started', fr: 'Y répondre là où l’exécution a été lancée' })}</Link>}
        </div>
      )}
      {run.error && (
        <div className="state state-error" role="alert">
          <p className="state-title">{labelOf(ERROR_CODE, run.error.code, lang)}</p>
          <p className="small">{run.error.message}</p>
          <p className="small mono">{tr({ en: 'Request', fr: 'Requête' })} {run.error.requestId}</p>
        </div>
      )}

      <dl className="meta-grid">
        <div className="kv"><dt className="k">{tr({ en: 'Profile', fr: 'Profil' })}</dt><dd className="v">{profileName ?? '—'}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Created', fr: 'Créée' })}</dt><dd className="v">{fmtDateTime(run.createdAt, lang)}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Last update', fr: 'Dernière mise à jour' })}</dt><dd className="v">{fmtDateTime(run.updatedAt, lang)}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Information cutoff', fr: 'Date limite d’information' })}</dt><dd className="v">{fmtDate(run.asOf, lang)}{run.flags.timeMachine && <span className="tag">{tr({ en: 'Time Machine', fr: 'Machine à remonter le temps' })}</span>}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Data snapshot', fr: 'Instantané de données' })}</dt><dd className="v mono break">{run.dataVersion}</dd></div>
        {run.parentRunId && (
          <div className="kv"><dt className="k">{tr({ en: 'Derived from run', fr: 'Dérivée de l’exécution' })}</dt>
            <dd className="v"><Link href={`/agents-system/?runId=${encodeURIComponent(run.parentRunId)}#run-detail`} className="mono break">{run.parentRunId}</Link></dd></div>
        )}
        {run.flags.sabotage && (
          <div className="kv"><dt className="k">{tr({ en: 'Sabotage demonstration', fr: 'Démonstration de sabotage' })}</dt><dd className="v">{labelOf(SABOTAGE_MODE, run.flags.sabotage, lang)}</dd></div>
        )}
      </dl>

      <h3 className="h4">{tr({ en: 'Run budget (totals recorded on the run)', fr: 'Budget de l’exécution (totaux enregistrés sur l’exécution)' })}</h3>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Run budget', fr: 'Budget de l’exécution' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Measure', fr: 'Mesure' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Recorded', fr: 'Enregistré' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Contract default limit', fr: 'Limite par défaut du contrat' })}</th>
            </tr>
          </thead>
          <tbody>
            <tr><th scope="row">{tr({ en: 'Model calls', fr: 'Appels de modèle' })}</th><td className="num-col num">{fmtNumber(budget.llmCalls, lang, 0)}</td><td className="num-col num">{RUN_LIMITS.llmCalls}</td></tr>
            <tr><th scope="row">{tr({ en: 'Input tokens', fr: 'Jetons en entrée' })}</th><td className="num-col num">{fmtNumber(budget.inputTokens, lang, 0)}</td><td className="num-col">—</td></tr>
            <tr><th scope="row">{tr({ en: 'Output tokens', fr: 'Jetons en sortie' })}</th><td className="num-col num">{fmtNumber(budget.outputTokens, lang, 0)}</td><td className="num-col">—</td></tr>
            <tr><th scope="row">{tr({ en: 'Tool calls (all)', fr: 'Appels d’outil (tous)' })}</th><td className="num-col num">{fmtNumber(budget.toolCalls, lang, 0)}</td><td className="num-col">—</td></tr>
            <tr><th scope="row">{tr({ en: 'Research tool calls (in recorded research steps)', fr: 'Appels d’outils de recherche (dans les étapes de recherche enregistrées)' })}</th><td className="num-col num">{fmtNumber(budget.researchToolCalls, lang, 0)}</td><td className="num-col num">{RUN_LIMITS.researchToolCalls}</td></tr>
            <tr><th scope="row">{tr({ en: 'Revision loops (recorded revision steps)', fr: 'Boucles de révision (étapes de révision enregistrées)' })}</th><td className="num-col num">{fmtNumber(budget.reviseLoops, lang, 0)}</td><td className="num-col num">{RUN_LIMITS.reviseLoops}</td></tr>
            <tr><th scope="row">{tr({ en: 'Failed tool calls (recorded)', fr: 'Appels d’outil en échec (enregistrés)' })}</th><td className="num-col num">{fmtNumber(budget.failedToolCalls, lang, 0)}</td><td className="num-col">—</td></tr>
            <tr><th scope="row">{tr({ en: 'Wall-clock duration', fr: 'Durée réelle' })}</th><td className="num-col num">{fmtDuration(budget.durationMs, lang)}</td><td className="num-col num">{fmtDuration(RUN_LIMITS.wallClockTargetMs, lang)} / {fmtDuration(RUN_LIMITS.wallClockHardMs, lang)}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="small muted">{tr({ en: 'Limits are the documented contract defaults (target / hard for duration); a deployment may override them. Recorded values come from the run payload, not from timers in this page.', fr: 'Les limites sont les valeurs par défaut documentées du contrat (cible / stricte pour la durée) ; un déploiement peut les modifier. Les valeurs enregistrées viennent de la charge utile de l’exécution, pas de minuteries de cette page.' })}</p>

      <h3 className="h4">{tr({ en: 'Guardrail: configured versus applied', fr: 'Garde-fou : configuré ou appliqué' })}</h3>
      <p className="small">
        <span className={`pill ${reading === 'applied' || reading === 'applied_flag_off' ? 's-pass' : 's-nee'}`}>
          {guardrailAudit?.applied ? tr({ en: 'Applied', fr: 'Appliqué' }) : tr({ en: 'Not applied', fr: 'Non appliqué' })}
        </span>{' '}
        {tr(GUARDRAIL_TEXT[reading])}
        {guardrailAudit?.applied && (
          <> {tr({ en: 'Recorded action', fr: 'Action enregistrée' })}: <span className="mono">{guardrailAudit.action}</span>{guardrailAudit.id && <> · <span className="mono break">{guardrailAudit.id}</span></>}</>
        )}
      </p>

      <h3 className="h4">{tr({ en: 'Steps recorded', fr: 'Étapes enregistrées' })} ({budget.stepsRecorded})</h3>
      <p className="small muted">{tr({ en: 'Same timeline as the Decision Desk and Evidence & Audit. A step that was not needed is absent; there are no “skipped” entries.', fr: 'Même chronologie que le Pupitre de décision et Preuves et audit. Une étape inutile est absente ; il n’y a pas d’entrées « ignorées ».' })}</p>
      <RunTimeline run={run} />

      {run.steps.length > 0 && (
        <>
          <h3 className="h4">{tr({ en: 'Step detail', fr: 'Détail des étapes' })}</h3>
          <div className="step-details">
            {run.steps.map(step => <StepDetail key={step.seq} step={step} runId={run.runId} />)}
          </div>
        </>
      )}

      <p className="row-actions small">
        <Link href={auditHref}>{tr({ en: 'Open Evidence & Audit for this run', fr: 'Ouvrir Preuves et audit pour cette exécution' })}</Link>
        {!isTerminal(run.status) && <span className="muted">{tr({ en: 'The run is still active; this view updates as steps are recorded.', fr: 'L’exécution est encore active ; cette vue se met à jour à mesure que les étapes sont enregistrées.' })}</span>}
      </p>
    </>
  );
}

function IdLinks({ ids, runId, linkFacts }: { ids: readonly string[]; runId: string; linkFacts: boolean }) {
  const { tr } = useApp();
  const shown = ids.slice(0, MAX_ID_LINKS);
  return (
    <>
      {shown.map(id => (linkFacts
        ? <Link key={id} className="mono id-link" href={`/evidence-audit/?runId=${encodeURIComponent(runId)}&factId=${encodeURIComponent(id)}`}>{id}</Link>
        : <span key={id} className="mono id-link">{id}</span>))}
      {ids.length > shown.length && <span className="muted"> {tr({ en: `and ${ids.length - shown.length} more`, fr: `et ${ids.length - shown.length} de plus` })}</span>}
    </>
  );
}

function ToolCallDetail({ call }: { call: ToolCall }) {
  const { tr, lang } = useApp();
  return (
    <li className={`tool-call${call.ok ? '' : ' tool-failed'}`}>
      <p>
        <span className="mono">{call.id} {call.tool}</span>{' '}
        <span className={`pill ${call.ok ? 's-pass' : 's-conflict'}`}>{call.ok ? tr({ en: 'OK', fr: 'OK' }) : tr({ en: 'Failed', fr: 'Échec' })}</span>{' '}
        <span className="muted">{fmtDateTime(call.startedAt, lang)} · {fmtDuration(call.durationMs, lang)}</span>
      </p>
      <p>{call.resultSummary}</p>
      {call.error && <p className="error-text">{tr({ en: 'Error', fr: 'Erreur' })}: {call.error}</p>}
      <details>
        <summary>{tr({ en: 'Arguments as sent (sensitive values redacted)', fr: 'Arguments tels qu’envoyés (valeurs sensibles masquées)' })}</summary>
        <pre className="args mono">{formatArgs(call.args)}</pre>
      </details>
      {call.datasetsRead.length > 0 && (
        <div className="table-scroll" role="region" aria-label={`${tr({ en: 'Datasets read by', fr: 'Jeux de données lus par' })} ${call.id}`} tabIndex={0}>
          <table className="data-table compact">
            <thead>
              <tr>
                <th scope="col">{tr({ en: 'Dataset read', fr: 'Jeu de données lu' })}</th>
                <th scope="col">{tr({ en: 'Version', fr: 'Version' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Rows read', fr: 'Lignes lues' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Rows withheld', fr: 'Lignes retenues' })}</th>
              </tr>
            </thead>
            <tbody>
              {call.datasetsRead.map((dataset, i) => (
                <tr key={`${dataset.datasetId}-${i}`}>
                  <th scope="row"><Link className="mono" href={`/sources/?datasetId=${encodeURIComponent(dataset.datasetId)}&dataVersion=${encodeURIComponent(dataset.dataVersion)}`}>{dataset.datasetId}</Link></th>
                  <td className="mono small break">{dataset.dataVersion}</td>
                  <td className="num-col num">{fmtNumber(dataset.rows, lang, 0)}</td>
                  <td className="num-col num">{fmtNumber(dataset.rowsWithheld, lang, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(call.factIds.length > 0 || call.evidenceIds.length > 0) && (
        <p className="muted">{tr({ en: 'Produced', fr: 'Produit' })}: {call.factIds.length} {tr({ en: 'fact(s)', fr: 'fait(s)' })}, {call.evidenceIds.length} {tr({ en: 'evidence item(s)', fr: 'preuve(s)' })}</p>
      )}
    </li>
  );
}

function StepDetail({ step, runId }: { step: Step; runId: string }) {
  const { tr, lang } = useApp();
  const produced = stepProduced(step);
  const deviations = stepDeviations(step);
  const failedCalls = step.toolCalls.filter(call => !call.ok).length;
  const statusText = step.status === 'running' ? tr({ en: 'Running', fr: 'En cours' }) : step.status === 'failed' ? tr({ en: 'Failed', fr: 'Échec' }) : tr({ en: 'Done', fr: 'Terminé' });
  return (
    <details className="step-detail" open={step.status === 'failed' || failedCalls > 0}>
      <summary>
        <span className="mono">#{step.seq}</span> <strong>{labelOf(STEP_TYPE, step.type, lang)}</strong>
        {step.iteration > 1 && <span className="tag">{tr({ en: 'iteration', fr: 'itération' })} {step.iteration}</span>}
        {' · '}{labelOf(AGENT_ROLE, step.agent, lang)} · {statusText}
        {failedCalls > 0 && <span className="error-text"> · {failedCalls} {tr({ en: 'failed tool call(s)', fr: 'appel(s) d’outil en échec' })}</span>}
      </summary>
      <div className="small step-detail-body">
        <dl>
          <div className="kv"><dt className="k">{tr({ en: 'Actor recorded', fr: 'Acteur enregistré' })}</dt>
            <dd className="v">{labelOf(ACTOR, step.actor, lang)} <NatureBadge nature={workNature(step.actor)} /></dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'Iteration', fr: 'Itération' })}</dt><dd className="v num">{step.iteration}</dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'Model ID recorded', fr: 'Identifiant de modèle enregistré' })}</dt>
            <dd className="v">{step.model ? <span className="mono break">{step.model}</span> : tr({ en: 'None recorded: no model call is evidenced for this step.', fr: 'Aucun : aucun appel de modèle n’est attesté pour cette étape.' })}</dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'Token usage recorded', fr: 'Jetons enregistrés' })}</dt>
            <dd className="v">{step.usage
              ? <span className="num">{fmtNumber(step.usage.inputTokens, lang, 0)} {tr({ en: 'in', fr: 'en entrée' })} / {fmtNumber(step.usage.outputTokens, lang, 0)} {tr({ en: 'out', fr: 'en sortie' })}</span>
              : tr({ en: 'None recorded', fr: 'Aucun' })}</dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'Measured duration', fr: 'Durée mesurée' })}</dt>
            <dd className="v">{step.durationMs === null ? tr({ en: 'Not finished', fr: 'Non terminée' }) : fmtDuration(step.durationMs, lang)} · {tr({ en: 'started', fr: 'début' })} {fmtDateTime(step.startedAt, lang)}{step.endedAt && <> · {tr({ en: 'ended', fr: 'fin' })} {fmtDateTime(step.endedAt, lang)}</>}</dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'What was done (code-authored)', fr: 'Ce qui a été fait (rédigé par le code)' })}</dt><dd className="v">{tr(step.summary)}</dd></div>
          <div className="kv"><dt className="k">{tr({ en: 'Produced', fr: 'Produit' })}</dt>
            <dd className="v">
              <span className="block">{produced.factIds.length} {tr({ en: 'fact(s)', fr: 'fait(s)' })}{produced.factIds.length > 0 && <>: <IdLinks ids={produced.factIds} runId={runId} linkFacts /></>}</span>
              <span className="block">{produced.evidenceIds.length} {tr({ en: 'evidence item(s)', fr: 'preuve(s)' })}{produced.evidenceIds.length > 0 && <>: <IdLinks ids={produced.evidenceIds} runId={runId} linkFacts={false} /></>}</span>
              <span className="block"><Link href={`/evidence-audit/?runId=${encodeURIComponent(runId)}`}>{tr({ en: 'See them in Evidence & Audit', fr: 'Les voir dans Preuves et audit' })}</Link></span>
            </dd></div>
        </dl>
        {deviations.length > 0 && (
          <p className="stale-note" role="note">
            {tr({ en: 'Recorded values differ from the contract’s step table; the recorded values are what is shown.', fr: 'Les valeurs enregistrées diffèrent du tableau des étapes du contrat ; ce sont les valeurs enregistrées qui sont affichées.' })}{' '}
            {deviations.map(d => (d.field === 'agent'
              ? `${tr({ en: 'Role', fr: 'Rôle' })}: ${labelOf(AGENT_ROLE, d.recorded, lang)} (${tr({ en: 'contract', fr: 'contrat' })}: ${labelOf(AGENT_ROLE, d.contract, lang)})`
              : `${tr({ en: 'Actor', fr: 'Acteur' })}: ${labelOf(ACTOR, d.recorded, lang)} (${tr({ en: 'contract', fr: 'contrat' })}: ${labelOf(ACTOR, d.contract, lang)})`)).join(' · ')}
          </p>
        )}
        <p className="eyebrow">{tr({ en: 'Tool calls', fr: 'Appels d’outil' })} ({step.toolCalls.length})</p>
        {step.toolCalls.length === 0
          ? <p className="muted">{tr({ en: 'No tool call was recorded for this step.', fr: 'Aucun appel d’outil n’a été enregistré pour cette étape.' })}</p>
          : <ul className="tool-call-list">{step.toolCalls.map(call => <ToolCallDetail key={call.id} call={call} />)}</ul>}
      </div>
    </details>
  );
}
