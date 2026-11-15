'use client';
/**
 * RunTimeline (T14): only steps that actually executed, with their actual actor, tool calls,
 * durations, models and token usage (contracts/run-events.md). No pulsing fake progress.
 */
import type { Run, Step } from '../../contracts/types';
import { ACTOR, AGENT_ROLE, STEP_TYPE, labelOf } from '../../lib/labels';
import { fmtDateTime, fmtDuration, fmtNumber } from '../../lib/format';
import { useApp } from '../../state/app';
import { RunStatusBadge } from '../common/Badges';

function StepItem({ step }: { step: Step }) {
  const { tr, lang } = useApp();
  return (
    <li className={`step step-${step.status}`}>
      <span className="dot" aria-hidden="true">{step.status === 'done' ? '✓' : step.status === 'failed' ? '✕' : step.seq}</span>
      <div className="step-body">
        <p className="step-title">
          <strong>{labelOf(STEP_TYPE, step.type, lang)}</strong>
          {step.iteration > 1 && <span className="tag">{tr({ en: 'iteration', fr: 'itération' })} {step.iteration}</span>}
          <span className="muted small"> · {labelOf(AGENT_ROLE, step.agent, lang)} · {labelOf(ACTOR, step.actor, lang)}</span>
        </p>
        <p className="small">
          {step.status === 'running'
            ? <span className="pill s-tension">{tr({ en: 'Running', fr: 'En cours' })}</span>
            : step.status === 'failed'
              ? <span className="pill s-conflict">{tr({ en: 'Failed', fr: 'Échec' })}</span>
              : <span className="pill s-pass">{tr({ en: 'Done', fr: 'Terminé' })}</span>}
          {' '}<span className="muted">{fmtDateTime(step.startedAt, lang)} · {fmtDuration(step.durationMs, lang)}</span>
        </p>
        <p className="small">{tr(step.summary)}</p>
        {step.model && (
          <p className="small muted">
            {tr({ en: 'Model', fr: 'Modèle' })} <span className="mono">{step.model}</span>
            {step.usage && <> · {fmtNumber(step.usage.inputTokens, lang, 0)} / {fmtNumber(step.usage.outputTokens, lang, 0)} {tr({ en: 'tokens in/out', fr: 'jetons entrée/sortie' })}</>}
          </p>
        )}
        {step.toolCalls.length > 0 && (
          <details className="small tool-calls">
            <summary>{step.toolCalls.length} {tr({ en: 'tool call(s)', fr: 'appel(s) d’outil' })}</summary>
            <ul>
              {step.toolCalls.map(call => (
                <li key={call.id} className={call.ok ? '' : 'tool-failed'}>
                  <span className="mono">{call.id} {call.tool}</span> · {call.ok ? 'ok' : tr({ en: 'failed', fr: 'échec' })} · {fmtDuration(call.durationMs, lang)}
                  <span className="block">{call.resultSummary}</span>
                  {call.error && <span className="block error-text">{call.error}</span>}
                  {call.datasetsRead.length > 0 && (
                    <span className="block muted">
                      {call.datasetsRead.map(d => `${d.datasetId}: ${fmtNumber(d.rows, lang, 0)} ${tr({ en: 'rows', fr: 'lignes' })}, ${fmtNumber(d.rowsWithheld, lang, 0)} ${tr({ en: 'withheld', fr: 'retenues' })}`).join(' · ')}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </li>
  );
}

export function RunTimeline({ run }: { run: Run }) {
  const { tr, lang } = useApp();
  return (
    <div className="timeline">
      <div className="timeline-head">
        <RunStatusBadge status={run.status} />
        <span className="small muted mono">{run.runId}</span>
        <span className="small muted">
          {fmtNumber(run.usage.llmCalls, lang, 0)} {tr({ en: 'model call(s)', fr: 'appel(s) de modèle' })} · {fmtNumber(run.usage.toolCalls, lang, 0)} {tr({ en: 'tool call(s)', fr: 'appel(s) d’outil' })} · {fmtDuration(run.usage.durationMs, lang)}
        </span>
      </div>
      {run.flags.fixture && (
        <p className="banner banner-fixture small">{tr({ en: 'Development fixture: these steps are illustrative and were not executed.', fr: 'Jeu d’essai de développement : ces étapes sont illustratives et n’ont pas été exécutées.' })}</p>
      )}
      {run.steps.length === 0
        ? <p className="muted small">{run.status === 'queued'
          ? tr({ en: 'Queued: no step has started yet.', fr: 'En file : aucune étape n’a commencé.' })
          : tr({ en: 'No step recorded.', fr: 'Aucune étape enregistrée.' })}</p>
        : <ol className="steps">{run.steps.map(step => <StepItem key={step.seq} step={step} />)}</ol>}
      {run.error && (
        <div className="state state-error" role="alert">
          <p className="state-title">{tr({ en: 'The run failed. Steps executed so far remain visible; no signed result exists.', fr: 'L’exécution a échoué. Les étapes réalisées restent visibles ; aucun résultat signé n’existe.' })}</p>
          <p className="small mono">{run.error.code}: {run.error.message}</p>
        </div>
      )}
    </div>
  );
}
