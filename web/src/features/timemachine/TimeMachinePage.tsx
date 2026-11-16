'use client';
/**
 * Time Machine (T15, web/page-specs/time-machine.md). Cutoff first, outcome later: the user picks a
 * supported as-of date and a move, a `replay` run is computed only from rows available at that date,
 * and later outcomes appear only after an explicit reveal, in a separate ledger (reveal fact scope).
 * A historical simulation, not forecast validation: the fixed warning stays on screen.
 */
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { Profile, ReplayPresetsResponse, ReplayResult, RevealResult, Run } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge, VerdictBadge } from '../../components/common/Badges';
import { LineChart, SeriesTable } from '../../components/common/LineChart';
import { RuleTable } from '../../components/run/RuleTable';
import { BriefView } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import {
  BoundaryNote, FundingOptions, ScenarioCards, SnapshotCompare, VerdictHeader, fundingLabel,
} from '../../components/run/Results';
import { CancelButton, MoveFormCard, QuestionForm } from '../decision/DecisionDeskPage';
import { Note } from '../../components/common/Note';
import { RUN_STATUS, labelOf } from '../../lib/labels';
import { fmtDate, fmtDateTime, fmtNumber, fmtPct, fmtSignedPct } from '../../lib/format';
import { describeRequest, moveOf, roundSize, validateMoveForm, type MoveForm } from '../../lib/move';
import { isTerminal } from '../../lib/runs';
import { REPLAY_FIX_MOVE, replayTickerIssue } from '../../lib/tickerCoverage';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { readPref, writePref } from '../../lib/session';
import {
  AS_OF_ISSUE, UNTIL_ISSUE, asOfIssue, factForValue, gatePassportHref, replayRefusal, revealBounds, revealRequest, revealSeries,
  revealableReplay, signedLedgerHash, untilIssue,
} from '../../lib/replay';

const EMPTY_FORM: MoveForm = { ticker: '', sizePct: 0, fundingMode: 'auto', fromTickers: [] };
const TITLE = { en: 'Replay a move at a past date', fr: 'Rejouer un mouvement à une date passée' };
const WARNING_SEEN = 'timemachine.warning.seen';

export function TimeMachinePage() {
  const { tr, feature, meta } = useApp();
  if (meta && !feature('time_machine')) {
    return (
      <>
        <PageHeader title={tr(TITLE)} />
        <Unavailable title={tr({ en: 'The Time Machine is turned off in this deployment.', fr: 'La Machine à remonter le temps est désactivée dans ce déploiement.' })}>
          {tr({ en: 'No historical replay can be started or reopened here, and no result is shown. The Decision Desk and Evidence & Audit remain available.', fr: 'Aucun rejeu historique ne peut être lancé ni rouvert ici, et aucun résultat n’est affiché. Le Pupitre de décision et Preuves et audit restent disponibles.' })}
        </Unavailable>
      </>
    );
  }
  return <ProfileGate>{profile => <TimeMachineContent profile={profile} />}</ProfileGate>;
}

/** Fixed wording (page spec): shown before analysis. Open on the first visit, folded afterwards. */
function FixedWarning() {
  const { tr } = useApp();
  const [open] = useState(() => readPref(WARNING_SEEN) !== 'true');
  useEffect(() => { writePref(WARNING_SEEN, 'true'); }, []);
  return (
    <details className="fold tm-warning" role="note" open={open} data-tour="tm-warning">
      <summary>{tr({ en: 'What this replay can and cannot show', fr: 'Ce que ce rejeu peut et ne peut pas montrer' })}</summary>
      <div className="fold-body">
      <ul className="bullets small">
        <li>{tr({ en: 'The language model’s knowledge is not erased. Figures come from date-filtered data, but wording may reflect what happened later.', fr: 'Les connaissances du modèle de langage ne sont pas effacées. Les chiffres viennent de données filtrées par date, mais la formulation peut refléter ce qui s’est passé ensuite.' })}</li>
        <li>{tr({ en: 'Prices are adjusted and macro series are revised: this is not the data as originally published on that date.', fr: 'Les prix sont ajustés et les séries macro révisées : ce ne sont pas les données telles que publiées à cette date.' })}</li>
        <li>{tr({ en: 'The asset universe was selected later, among names that are large today.', fr: 'L’univers d’actifs a été choisi plus tard, parmi des titres importants aujourd’hui.' })}</li>
        <li>{tr({ en: 'This is a historical simulation, not a validation of any forecast and not an offline replay of a real decision.', fr: 'C’est une simulation historique, pas la validation d’une prévision ni le rejeu hors ligne d’une décision réelle.' })}</li>
      </ul>
      </div>
    </details>
  );
}

function TimeMachineContent({ profile }: { profile: Profile }) {
  const { tr, lang, sessionId, meta, announce, profiles, selectProfile, feature } = useApp();
  // The same cached read as the move form's suggestions: no extra request.
  const universe = useAssetUniverse();
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get('runId');

  const presets = useQuery<ReplayPresetsResponse>(
    sessionId && meta ? `replay-presets|${sessionId}|${meta.dataVersion}` : null,
    signal => getApiClient().replayPresets(signal),
  );

  const [asOf, setAsOf] = useState('');
  const [form, setForm] = useState<MoveForm>(EMPTY_FORM);
  const touched = useRef(false);
  const update = useCallback((patch: Partial<MoveForm>) => {
    touched.current = true;
    setForm(f => ({ ...f, ...patch }));
  }, []);
  const chooseAsOf = (value: string) => { touched.current = true; setAsOf(value); };

  const polled = useRun(runId, finished => announce(`${tr({ en: 'Historical replay', fr: 'Rejeu historique' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;

  // Restore the form once from a run opened by deep link, unless the user already edited it.
  const restoredFor = useRef<string | null>(null);
  useEffect(() => {
    if (!run || run.input.kind !== 'replay' || restoredFor.current === run.runId || touched.current) return;
    restoredFor.current = run.runId;
    setAsOf(run.input.asOf);
    if (run.input.request.type === 'move') {
      const m = run.input.request.move;
      setForm({ ticker: m.ticker, sizePct: m.sizePct, fundingMode: m.funding.mode, fromTickers: m.funding.fromTickers ?? [] });
    }
  }, [run]);

  const currentWeight = profile.portfolio.positions.find(p => p.ticker === form.ticker.trim().toUpperCase())?.weightPct ?? 0;
  const maxSize = form.fundingMode === 'new_money' ? 100 : Math.max(0, roundSize(100 - currentWeight));
  // There is no preview here: a ticker outside the snapshot is caught before Run, not by POST /runs.
  const tickerIssue = replayTickerIssue(form.ticker, universe, profile.portfolio.positions.map(p => p.ticker), feature('on_demand_tickers'));
  const formIssues = validateMoveForm(form, currentWeight);
  const issues = tickerIssue ? [...formIssues, tickerIssue] : formIssues;
  const shownIssues = form.sizePct > 0 || form.ticker.trim() ? issues : [];
  const move = moveOf(form);
  const dateIssue = presets.data ? asOfIssue(asOf, presets.data) : null;

  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const canStart = Boolean(presets.data) && dateIssue === null && move !== null && issues.length === 0 && !creating;
  const start = async () => {
    if (!move || !presets.data || dateIssue) return;
    setCreating(true); setCreateError(null);
    try {
      const created = await getApiClient().createRun({
        kind: 'replay', profileId: profile.profileId, lang, request: { type: 'move', move }, asOf, window: { code: 'full' },
      }, `replay-${crypto.randomUUID()}`);
      touched.current = false;
      router.replace(`/time-machine/?runId=${encodeURIComponent(created.runId)}`);
    } catch (error) {
      setCreateError(asApiError(error));
    } finally { setCreating(false); }
  };

  const otherProfileId = run?.profileId && run.profileId !== profile.profileId ? run.profileId : null;

  return (
    <>
      <PageHeader tour="tm-header"
        title={tr(TITLE)}>
        <p className="page-sub">{tr({ en: `Pick a past date and a move for ${profile.name}. The analysis sees only the data of that date; you reveal what happened next when you choose.`, fr: `Choisissez une date passée et un mouvement pour ${profile.name}. L’analyse ne voit que les données de cette date ; vous révélez la suite quand vous le décidez.` })}</p>
      </PageHeader>

      <FixedWarning />

      <div className="cols">
        <div>
          <Card id="cutoff" section={tr({ en: 'Date', fr: 'Date' })} tour="tm-cutoff" title={tr({ en: 'Pick a past date', fr: 'Choisir une date passée' })}
            info={tr({ en: 'The information cutoff: the replay uses only data that was available at the end of this day.', fr: 'La date limite d’information : le rejeu n’utilise que les données disponibles à la fin de ce jour.' })}>
            {presets.loading && <Loading label={tr({ en: 'Loading the dates the data supports…', fr: 'Chargement des dates prises en charge par les données…' })} />}
            {presets.error && (
              <ErrorState error={presets.error} onRetry={presets.reload}
                title={tr({ en: 'The supported dates could not be loaded. No date is offered until they are.', fr: 'Les dates prises en charge n’ont pas pu être chargées. Aucune date n’est proposée d’ici là.' })} />
            )}
            {presets.data && (
              <>
                <p className="small">
                  {tr({ en: 'Supported cutoff dates', fr: 'Dates limites prises en charge' })}:{' '}
                  <strong>{fmtDate(presets.data.earliestAsOf, lang)}</strong> → <strong>{fmtDate(presets.data.latestAsOf, lang)}</strong>.{' '}
                  {tr({ en: 'Earlier dates lack history; later ones leave nothing to reveal.', fr: 'Avant : historique insuffisant ; après : rien à révéler.' })}
                </p>
                {presets.data.presets.length === 0 ? (
                  <p className="small muted">{tr({ en: 'No preset date was computed from the loaded data. Enter a date in the supported range.', fr: 'Aucune date prédéfinie n’a été calculée à partir des données chargées. Saisissez une date dans la plage prise en charge.' })}</p>
                ) : (
                  <ul className="preset-list" aria-label={tr({ en: 'Preset dates computed from the data', fr: 'Dates prédéfinies calculées à partir des données' })}>
                    {presets.data.presets.map(preset => (
                      <li key={`${preset.asOf}-${preset.label.en}`}>
                        <button type="button" className="preset" aria-pressed={asOf === preset.asOf} onClick={() => chooseAsOf(preset.asOf)}>
                          <span className="preset-label">{tr(preset.label)}</span>
                          <span className="small preset-why">{tr(preset.why)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="field" style={{ marginTop: 12 }}>
                  <label htmlFor="tm-asof">{tr({ en: 'Or enter a cutoff date', fr: 'Ou saisir une date limite' })}</label>
                  <input id="tm-asof" type="date" value={asOf} min={presets.data.earliestAsOf} max={presets.data.latestAsOf}
                    onChange={e => chooseAsOf(e.target.value)} aria-invalid={Boolean(asOf && dateIssue)} aria-describedby="tm-asof-hint" />
                  <span id="tm-asof-hint" className="hint">
                    {tr({ en: 'End of day (UTC).', fr: 'Fin de journée (UTC).' })}
                  </span>
                  {asOf && dateIssue && <span className="field-error" role="alert">{tr(AS_OF_ISSUE[dateIssue])}</span>}
                </div>
                <LimitationList codes={presets.data.notices} compactAfter={0} title={tr({ en: 'Notes', fr: 'Remarques' })} />
              </>
            )}
            <Note>{tr({ en: 'No macro data vintage is fetched: macro series revised after the date stay withheld in replays.', fr: 'Aucun millésime de données macroéconomiques n’est récupéré : les séries macro révisées après la date restent retenues dans les rejeux.' })}</Note>
          </Card>
        </div>
        <div>
          <MoveFormCard profile={profile} form={form} update={update} maxSize={maxSize} currentWeight={currentWeight} issues={shownIssues} goal={null} />
          <Card id="tm-start" section={tr({ en: 'Start', fr: 'Lancer' })} tour="tm-start" title={tr({ en: 'Start the replay', fr: 'Lancer le rejeu' })}>
            <p className="small">
              {move
                ? `${describeRequest({ type: 'move', move }, lang)}, ${fundingLabel(move.funding, lang)}`
                : tr({ en: 'No move set yet: choose an asset and a size above 0', fr: 'Aucun mouvement défini : choisissez un actif et une taille supérieure à 0' })}
              {', '}
              {asOf && !dateIssue
                ? <>{tr({ en: 'cutoff', fr: 'date limite' })} <strong>{fmtDate(asOf, lang)}</strong></>
                : tr({ en: 'no cutoff chosen', fr: 'aucune date limite choisie' })}
            </p>
            <div className="row-actions">
              <button type="button" className="btn" disabled={!canStart} onClick={() => void start()}
                aria-describedby={shownIssues.length > 0 ? 'tm-start-reason' : undefined}>
                {tr({ en: 'Start replay', fr: 'Lancer le rejeu' })}
              </button>
              {shownIssues.length > 0 && <span id="tm-start-reason" className="small muted">{tr(REPLAY_FIX_MOVE)}</span>}
            </div>
            {creating && <Loading label={tr({ en: 'Starting…', fr: 'Lancement…' })} />}
            {createError && (
              <ErrorState error={createError}
                {...(createError.code === 'upstream_unavailable' ? { title: tr({ en: 'The replay could not be started: the analysis service is unavailable. Nothing was computed.', fr: 'Le rejeu n’a pas pu être lancé : le service d’analyse est indisponible. Rien n’a été calculé.' }) } : {})}>
                <CreateRefusal error={createError} />
              </ErrorState>
            )}
          </Card>
        </div>
      </div>

      {runId && (
        <Card id="replay-run" section={tr({ en: 'Result', fr: 'Résultat' })} tour="tm-result" title={tr({ en: 'Replay result', fr: 'Résultat du rejeu' })}>
          {polled.loading && !run && <Loading />}
          {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
            {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This replay does not exist or belongs to another session.', fr: 'Ce rejeu n’existe pas ou appartient à une autre session.' }) } : {})} />}
          {polled.pollError && (
            <p className="small muted" role="status">{tr({ en: 'Connection lost, retrying…', fr: 'Connexion perdue, nouvel essai…' })}</p>
          )}
          {otherProfileId && (
            <p className="stale-note">
              {tr({ en: 'This replay belongs to another fictional profile.', fr: 'Ce rejeu concerne un autre profil fictif.' })}{' '}
              <button type="button" className="linklike" onClick={() => selectProfile(otherProfileId)}>
                {tr({ en: 'Switch to', fr: 'Basculer vers' })} {profiles.find(p => p.profileId === otherProfileId)?.name ?? otherProfileId}
              </button>
            </p>
          )}
          {run && run.kind !== 'replay' && (
            <Unavailable title={tr({ en: 'This analysis is not a historical replay.', fr: 'Cette analyse n’est pas un rejeu historique.' })}>
              <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Open it in Evidence & Audit', fr: 'L’ouvrir dans Preuves et audit' })}</Link>
            </Unavailable>
          )}
          {run && run.kind === 'replay' && <ReplayRun key={run.runId} run={run} profile={otherProfileId ? null : profile} />}
        </Card>
      )}
    </>
  );
}

/** What the API said in `error.details` when it refused the replay (api.md 5.1: 422). */
function CreateRefusal({ error }: { error: ApiRequestError }) {
  const { tr, lang } = useApp();
  const refusal = replayRefusal(error.details);
  if (!refusal) return null;
  return (
    <>
      {refusal.earliestAsOf && refusal.latestAsOf && (
        <p className="small">{tr({ en: 'Dates the API accepts', fr: 'Dates acceptées par l’API' })}: <strong>{fmtDate(refusal.earliestAsOf, lang)}</strong> → <strong>{fmtDate(refusal.latestAsOf, lang)}</strong>.</p>
      )}
      {refusal.unknownAtAsOf.length > 0 && (
        <p className="small">
          {tr({ en: 'These portfolio assets have no price at the chosen date, so the portfolio cannot be replayed there', fr: 'Ces actifs du portefeuille n’ont pas de prix à la date choisie ; le portefeuille ne peut donc pas y être rejoué' })}:{' '}
          {refusal.unknownAtAsOf.map(ticker => <span key={ticker} className="tag mono">{ticker}</span>)}
          <span className="block muted">{tr({ en: 'Choose a later date or another fictional profile. No price is back-filled.', fr: 'Choisissez une date ultérieure ou un autre profil fictif. Aucun prix n’est reconstitué.' })}</span>
        </p>
      )}
    </>
  );
}

function CutoffBanner({ asOf }: { asOf: string }) {
  const { tr, lang } = useApp();
  return (
    <div className="cutoff-banner" role="note">
      <p className="cutoff-title">{tr({ en: 'Information cutoff', fr: 'Date limite d’information' })}: <strong>{fmtDate(asOf, lang)}</strong></p>
      <p className="small">{tr({ en: 'Only data available on this date is used. Later outcomes stay hidden until you reveal them.', fr: 'Seules les données disponibles à cette date sont utilisées. La suite reste masquée jusqu’à la révélation.' })}</p>
    </div>
  );
}

/** `dataVersion` is the snapshot the replay is pinned to, so Sources can warn on drift (SRC-04). */
function GatePanel({ replay, dataVersion }: { replay: ReplayResult; dataVersion: string }) {
  const { tr, lang } = useApp();
  const datasets = replay.gate.datasets;
  return (
    <details className="fold">
      <summary id="gate-title">{tr({ en: 'Date gate: what the analysis could and could not read', fr: 'Filtre de date : ce que l’analyse a pu lire ou non' })}</summary>
      <div className="fold-body">
      {datasets.length === 0 ? (
        <p className="small muted">{tr({ en: 'The analysis reported no gated dataset.', fr: 'L’analyse n’a signalé aucun jeu de données filtré.' })}</p>
      ) : (
        <div className="table-scroll" role="region" aria-label={tr({ en: 'Rows visible and withheld per dataset', fr: 'Lignes visibles et retenues par jeu de données' })} tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{tr({ en: 'Dataset', fr: 'Jeu de données' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Rows visible', fr: 'Lignes visibles' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Rows withheld', fr: 'Lignes retenues' })}</th>
                <th scope="col">{tr({ en: 'Last visible date', fr: 'Dernière date visible' })}</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map(dataset => (
                <tr key={dataset.datasetId}>
                  <th scope="row">
                    <Link href={gatePassportHref(dataset.datasetId, dataVersion)} className="mono">{dataset.datasetId}</Link>
                  </th>
                  <td className="num-col num">{fmtNumber(dataset.rowsVisible, lang, 0)}</td>
                  <td className="num-col num">{fmtNumber(dataset.rowsWithheld, lang, 0)}</td>
                  <td>{fmtDate(dataset.lastVisibleDate, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="small muted">{tr({ en: 'Rows are withheld when their availability is later than the cutoff or unknown, even if their observation date is earlier. A check that needs them reports insufficient evidence.', fr: 'Les lignes sont retenues lorsque leur disponibilité est ultérieure à la date limite ou inconnue, même si leur date d’observation est antérieure. Une vérification qui en a besoin signale des preuves insuffisantes.' })}</p>
      </div>
    </details>
  );
}

function SignedLedger({ run, replay }: { run: Run; replay: ReplayResult }) {
  const { tr, lang } = useApp();
  const audit = replay.decision.brief.audit;
  return (
    <details className="fold">
      <summary>{tr({ en: 'Signed decision ledger', fr: 'Registre signé de la décision' })}</summary>
      <div className="fold-body">
      <p className="mono small break">{audit.ledgerHash}</p>
      <p className="small muted">
        {tr({ en: 'Signed', fr: 'Signé le' })} {fmtDateTime(audit.signedAt, lang)}, {tr({ en: 'data', fr: 'données' })} <span className="mono">{run.dataVersion}</span>.{' '}
        {tr({ en: 'The hash identifies this ledger; it is not proof that its contents are true.', fr: 'L’empreinte identifie ce registre ; elle ne prouve pas que son contenu est vrai.' })}
      </p>
      </div>
    </details>
  );
}

function ReplayRun({ run, profile }: { run: Run; profile: Profile | null }) {
  const { tr, lang } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }), [run]);
  const replay = run.result?.kind === 'replay' ? run.result.replay : null;
  const asOf = run.input.kind === 'replay' ? run.input.asOf : run.asOf;
  const decision = replay?.decision ?? null;
  const selected = decision?.scenarios.find(s => s.scenarioId === decision.selectedScenarioId) ?? null;
  const original = run.input.kind === 'replay' ? run.input.request : null;

  return (
    <>
      <CutoffBanner asOf={asOf} />
      <FactScopeProvider scope={scope}>
        {original && (
          <p className="small">
            {tr({ en: 'Request', fr: 'Requête' })}: <strong>{describeRequest(original, lang)}</strong>
            {original.type === 'move' && <> · {fundingLabel(original.move.funding, lang)}</>} · {tr({ en: 'created', fr: 'créée' })} {fmtDateTime(run.createdAt, lang)}
          </p>
        )}
        {!isTerminal(run.status) && run.status !== 'waiting_input' && (
          <p className="small"><RunStatusBadge status={run.status} /></p>
        )}
        {run.status === 'waiting_input' && run.question && <QuestionForm run={run} />}
        {run.status === 'cancelled' && (
          <Unavailable title={tr({ en: 'This replay was cancelled. No signed result exists and nothing can be revealed.', fr: 'Ce rejeu a été annulé. Aucun résultat signé n’existe et rien ne peut être révélé.' })} />
        )}

        {replay && decision && (
          <>
            <VerdictHeader verdict={decision.verdict} counts={decision.counts} />
            {decision.request.type === 'move' && <BoundaryNote sizePct={decision.maxCompatibleSizePct} counts={decision.counts} />}
            <LimitationList codes={replay.notices} title={tr({ en: 'Notices for this replay', fr: 'Avis pour ce rejeu' })} />
            <GatePanel replay={replay} dataVersion={run.dataVersion} />

            {selected && (
              <>
                <h3 className="h4">{tr({ en: 'Rule checks at the cutoff (selected scenario)', fr: 'Vérifications des règles à la date limite (scénario sélectionné)' })}</h3>
                <p className="small muted">{tr({ en: 'Checks without enough data at the cutoff stay listed as not enough evidence.', fr: 'Les vérifications sans données suffisantes à la date limite restent listées comme preuves insuffisantes.' })}</p>
                <RuleTable checks={selected.ruleChecks} rules={profile?.rules} caption={tr({ en: 'Rule checks at the information cutoff', fr: 'Vérifications des règles à la date limite d’information' })} />
                <h3 className="h4">{tr({ en: 'Before and after (selected scenario, at the cutoff)', fr: 'Avant et après (scénario sélectionné, à la date limite)' })}</h3>
                <SnapshotCompare before={decision.portfolioBefore} after={selected.portfolioAfter} />
              </>
            )}
            <h3 className="h4">{tr({ en: 'Hypothetical scenarios', fr: 'Scénarios hypothétiques' })}</h3>
            <ScenarioCards scenarios={decision.scenarios} selectedId={decision.selectedScenarioId} />
            <FundingOptions options={decision.fundingOptions} />
            <h3 className="h4">{tr({ en: 'Audited brief (written with the cutoff data)', fr: 'Note auditée (rédigée avec les données de la date limite)' })}</h3>
            <BriefView brief={decision.brief} />
            <LimitationList codes={decision.limitations} />
            <SignedLedger run={run} replay={replay} />
            <p className="row-actions small">
              <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'See the evidence and audit', fr: 'Voir les preuves et l’audit' })}</Link>
            </p>
          </>
        )}

        <details className="fold" open={!decision}>
          <summary>{tr({ en: 'Steps', fr: 'Étapes' })}, {labelOf(RUN_STATUS, run.status, lang).toLowerCase()}</summary>
          <RunTimeline run={run} />
        </details>
        {!isTerminal(run.status) && <CancelButton runId={run.runId} />}
      </FactScopeProvider>

      <RevealPanel run={run} />
    </>
  );
}

interface RevealState { loading: boolean; error: ApiRequestError | null; result: RevealResult | null }
type HashCheck = 'idle' | 'checking' | 'same' | 'changed' | 'unverified';

function RevealPanel({ run }: { run: Run }) {
  const { tr, lang, announce } = useApp();
  const replay = revealableReplay(run);
  const [until, setUntil] = useState(replay?.revealAvailableUntil ?? '');
  const [state, setState] = useState<RevealState>({ loading: false, error: null, result: null });
  const [hashCheck, setHashCheck] = useState<HashCheck>('idle');
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  // A replay that succeeds while the page is open: prefill the last available date once.
  const prefilled = useRef(Boolean(replay));
  useEffect(() => {
    if (replay && !prefilled.current) { prefilled.current = true; setUntil(replay.revealAvailableUntil); }
  }, [replay]);

  if (!replay) {
    return (
      <section className="reveal" aria-labelledby="reveal-title">
        <h3 className="h4" id="reveal-title">{tr({ en: 'Later outcomes', fr: 'Résultats ultérieurs' })}</h3>
        <p className="small muted">
          {isTerminal(run.status)
            ? tr({ en: 'Not available: only a replay with a signed result can be revealed.', fr: 'Non disponible : seul un rejeu avec un résultat signé peut être révélé.' })
            : tr({ en: 'Hidden. The reveal becomes available once the replay has a signed result.', fr: 'Masqués. La révélation devient disponible une fois le rejeu signé.' })}
        </p>
      </section>
    );
  }

  const bounds = revealBounds(replay);
  const issue = untilIssue(until, replay);
  const hashBefore = signedLedgerHash(run);

  const reveal = async () => {
    if (issue) return;
    setState(s => ({ ...s, loading: true, error: null }));
    setHashCheck('idle');
    try {
      const result = await getApiClient().reveal(run.runId, revealRequest(until));
      setState({ loading: false, error: null, result });
      announce(tr({ en: 'Later outcomes revealed.', fr: 'Résultats ultérieurs révélés.' }));
      setTimeout(() => headingRef.current?.focus(), 0);
      // Re-read the run: the signed decision must be exactly what it was before the reveal (TMUI-05).
      setHashCheck('checking');
      try {
        const fresh = await getApiClient().run(run.runId, null);
        setHashCheck(signedLedgerHash(fresh) === hashBefore ? 'same' : 'changed');
      } catch { setHashCheck('unverified'); }
    } catch (error) {
      setState(s => ({ ...s, loading: false, error: asApiError(error) }));
    }
  };

  return (
    <section className="reveal" aria-labelledby="reveal-title">
      <h3 className="h4" id="reveal-title" data-tour="tm-reveal">{tr({ en: 'Later outcomes', fr: 'Résultats ultérieurs' })}</h3>
      {!state.result && (
        <p className="small">{tr({ en: 'Still hidden. Revealing does not change the verdict, the brief or the signed ledger above; it adds a separate, deterministic ledger of what the fixed scenarios did afterwards.', fr: 'Toujours masqués. La révélation ne change ni le verdict, ni la note, ni le registre signé ci-dessus ; elle ajoute un registre distinct et déterministe de ce que les scénarios figés ont fait ensuite.' })}</p>
      )}
      {bounds ? (
        <form className="reveal-form" onSubmit={e => { e.preventDefault(); void reveal(); }}>
          <div className="field">
            <label htmlFor="tm-until">{tr({ en: 'Reveal up to', fr: 'Révéler jusqu’au' })}</label>
            <input id="tm-until" type="date" value={until} min={bounds.min} max={bounds.max} onChange={e => setUntil(e.target.value)}
              aria-invalid={Boolean(issue)} aria-describedby="tm-until-hint" />
            <span id="tm-until-hint" className="hint">
              {tr({ en: 'After', fr: 'Après le' })} {fmtDate(replay.asOf, lang)}, {tr({ en: 'no later than', fr: 'au plus tard le' })} {fmtDate(bounds.max, lang)} ({tr({ en: 'last date in the data snapshot', fr: 'dernière date de l’instantané' })}).{' '}
              {tr({ en: 'Leave empty for the last date.', fr: 'Laissez vide pour la dernière date.' })}
            </span>
            {issue && <span className="field-error" role="alert">{tr(UNTIL_ISSUE[issue])}</span>}
          </div>
          <button type="submit" className="btn" disabled={Boolean(issue) || state.loading}>
            {state.result ? tr({ en: 'Reveal again with this date', fr: 'Révéler de nouveau avec cette date' }) : tr({ en: 'Reveal later outcomes', fr: 'Révéler les résultats ultérieurs' })}
          </button>
        </form>
      ) : (
        <Unavailable title={tr(UNTIL_ISSUE.no_later_data)} />
      )}
      {state.loading && <Loading label={tr({ en: 'Computing later outcomes (no model)…', fr: 'Calcul des résultats ultérieurs (sans modèle)…' })} />}
      {state.error && (
        <ErrorState error={state.error} onRetry={() => void reveal()}
          title={tr({ en: 'The reveal failed. The signed decision above is unchanged; you can retry.', fr: 'La révélation a échoué. La décision signée ci-dessus est inchangée ; vous pouvez réessayer.' })} />
      )}
      {state.result && (
        <RevealView run={run} replay={replay} reveal={state.result} hashCheck={hashCheck} hashBefore={hashBefore} headingRef={headingRef} />
      )}
    </section>
  );
}

function RevealView({ run, replay, reveal, hashCheck, hashBefore, headingRef }: {
  run: Run; replay: ReplayResult; reveal: RevealResult; hashCheck: HashCheck; hashBefore: string | null;
  headingRef: RefObject<HTMLHeadingElement | null>;
}) {
  const { tr, lang } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'reveal', runId: run.runId, until: reveal.until, facts: reveal.facts }), [run.runId, reveal]);
  const series = useMemo(() => revealSeries(reveal, tr), [reveal, tr]);
  const unit = tr({ en: 'index, 100 at the cutoff', fr: 'indice, 100 à la date limite' });
  const caption = tr({
    en: `Hypothetical value of each fixed scenario from ${reveal.asOf} to ${reveal.until}`,
    fr: `Valeur hypothétique de chaque scénario figé du ${reveal.asOf} au ${reveal.until}`,
  });
  return (
    <div className="reveal-result">
      <h4 className="h4" tabIndex={-1} ref={headingRef}>
        {tr({ en: 'Revealed', fr: 'Révélé' })}: {fmtDate(reveal.asOf, lang)} → {fmtDate(reveal.until, lang)}
      </h4>
      <p className="stale-note" role="note">{tr(reveal.statement)}</p>
      <p className="small">{tr({ en: 'Observed hypothetical outcomes in this dataset. They are not evidence of a prediction, and not evidence that one scenario is better in general.', fr: 'Résultats hypothétiques observés dans ce jeu de données. Ils ne prouvent ni une prédiction, ni la supériorité générale d’un scénario.' })}</p>

      {reveal.outcomes.length === 0 ? (
        <p className="muted">{tr({ en: 'The reveal returned no scenario outcome.', fr: 'La révélation n’a renvoyé aucun résultat de scénario.' })}</p>
      ) : (
        <FactScopeProvider scope={scope}>
          <div className="scenarios">
            {reveal.outcomes.map(outcome => {
              const returnFact = factForValue(reveal.facts, outcome.factIds, outcome.returnPct);
              const drawdownFact = factForValue(reveal.facts, outcome.factIds, outcome.maxDrawdownPct, returnFact);
              const others = outcome.factIds.filter(id => id !== returnFact && id !== drawdownFact);
              const first = outcome.series[0];
              const last = outcome.series[outcome.series.length - 1];
              return (
                <article key={outcome.scenarioId} className="scenario" aria-label={tr(outcome.label)}>
                  <p className="eyebrow">{tr({ en: 'Fixed scenario', fr: 'Scénario figé' })}</p>
                  <h4 className="h4">{tr(outcome.label)}</h4>
                  <dl>
                    <div className="kv">
                      <dt className="k">{tr({ en: 'Realized return over the period', fr: 'Rendement réalisé sur la période' })}</dt>
                      <dd className="v">{returnFact
                        ? <FactChip factId={returnFact} display={reveal.facts[returnFact]?.display[lang] ?? fmtSignedPct(outcome.returnPct, lang)} />
                        : <span className="num">{fmtSignedPct(outcome.returnPct, lang)}</span>}</dd>
                    </div>
                    <div className="kv">
                      <dt className="k">{tr({ en: 'Maximum drawdown (positive loss)', fr: 'Baisse maximale (perte positive)' })}</dt>
                      <dd className="v">{drawdownFact
                        ? <FactChip factId={drawdownFact} display={reveal.facts[drawdownFact]?.display[lang] ?? fmtPct(outcome.maxDrawdownPct, lang)} />
                        : <span className="num">{fmtPct(outcome.maxDrawdownPct, lang)}</span>}</dd>
                    </div>
                    <div className="kv">
                      <dt className="k">{tr({ en: 'Actual dates', fr: 'Dates réelles' })}</dt>
                      <dd className="v">{first && last ? `${fmtDate(first.date, lang)} → ${fmtDate(last.date, lang)}` : '—'}</dd>
                    </div>
                  </dl>
                  {others.length > 0 && (
                    <p className="small">{tr({ en: 'Reveal facts', fr: 'Faits de révélation' })}: {others.map(id => <FactChip key={id} factId={id} />)}</p>
                  )}
                  {outcome.factIds.length === 0 && (
                    <p className="small muted">{tr({ en: 'No reveal fact was returned for this scenario.', fr: 'Aucun fait de révélation n’a été renvoyé pour ce scénario.' })}</p>
                  )}
                </article>
              );
            })}
          </div>
          <LineChart series={series} lang={lang} unitLabel={unit} caption={caption} digits={1} />
          <details className="fold">
            <summary className="small">{tr({ en: 'Same series as a table (month-ends and both endpoints)', fr: 'Mêmes séries en tableau (fins de mois et les deux extrémités)' })}</summary>
            <SeriesTable series={series} lang={lang} unitLabel={unit} caption={caption} digits={1} />
          </details>
        </FactScopeProvider>
      )}

      <div className="ledger">
        <p className="eyebrow">{tr({ en: 'Original signed decision (unchanged by the reveal)', fr: 'Décision signée d’origine (inchangée par la révélation)' })}</p>
        <p><VerdictBadge verdict={replay.decision.verdict} /> <span className="small">{tr({ en: 'verdict at the cutoff', fr: 'verdict à la date limite' })} {fmtDate(replay.asOf, lang)}</span></p>
        <p className="mono small break">{hashBefore ?? '—'}</p>
        <p className="small" role="status">
          {hashCheck === 'checking' && tr({ en: 'Re-reading the analysis to compare the signed hash…', fr: 'Relecture de l’analyse pour comparer l’empreinte signée…' })}
          {hashCheck === 'same' && <><span aria-hidden="true">✓ </span>{tr({ en: 'Checked: the analysis was re-read after the reveal and its signed ledger hash is identical.', fr: 'Vérifié : l’analyse a été relue après la révélation et l’empreinte de son registre signé est identique.' })}</>}
          {hashCheck === 'changed' && <strong className="error-text"><span aria-hidden="true">✕ </span>{tr({ en: 'Warning: the analysis re-read after the reveal reports a different signed hash. Treat this result as unreliable.', fr: 'Attention : l’analyse relue après la révélation indique une empreinte différente. Considérez ce résultat comme non fiable.' })}</strong>}
          {hashCheck === 'unverified' && tr({ en: 'Not checked: the analysis could not be re-read after the reveal. The hash shown is the one loaded before it.', fr: 'Non vérifié : l’analyse n’a pas pu être relue après la révélation. L’empreinte affichée est celle chargée avant.' })}
        </p>
        <p className="small muted">{tr({ en: 'The brief above was written without these outcomes and is not rewritten.', fr: 'La note ci-dessus a été rédigée sans ces résultats et n’est pas réécrite.' })}</p>
      </div>
    </div>
  );
}
