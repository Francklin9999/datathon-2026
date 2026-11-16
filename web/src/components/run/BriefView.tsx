'use client';
/**
 * BriefView (T14): renders typed segments only, never HTML from the model (WEB-08). Normal mode
 * hides struck sentences; audit mode shows them struck with failed codes and the auditor's note.
 * Code-owned content is shown as text, never as an identifier: a sentence that is a limitation code
 * reads as that limitation, a raw status value as the status word, a section id as its heading, a
 * rule token as the rule's short name with its profile code as a secondary label ("Growth-asset
 * limit (R3)"). Removed sentences are never shown here: a pluralised note links to the run's audit.
 */
import Link from 'next/link';
import type { Brief, Segment, Sentence } from '../../contracts/types';
import { limitationCodeOf, removedNote, sectionTitle, statusWord, struckSentences, visibleSentences, type BriefMode } from '../../lib/brief';
import { LIMITATION, SENTENCE_AUDIT, labelOf } from '../../lib/labels';
import { ruleName } from '../../lib/ruleNames';
import { fmtDateTime } from '../../lib/format';
import { useApp } from '../../state/app';
import { EvidenceChip, FactChip, useFactScope } from '../common/FactDrawer';

function RuleRef({ ruleId, display }: { ruleId: string; display: string }) {
  const { lang } = useApp();
  const name = ruleName(ruleId, lang);
  if (!name) return <span className="rule-ref mono" title={ruleId}>{display}</span>;
  return (
    <span className="rule-ref" title={ruleId}>
      {name}{display && display !== name && <> <span className="mono muted">({display})</span></>}
    </span>
  );
}

function SegmentView({ segment }: { segment: Segment }) {
  const { lang } = useApp();
  switch (segment.t) {
    case 'text': return <>{segment.text}</>;
    case 'fact': return <FactChip factId={segment.factId} display={segment.display} />;
    case 'rule': return <RuleRef ruleId={segment.ruleId} display={segment.display} />;
    case 'status': return <strong className="status-word">{statusWord(segment.display, lang)}</strong>;
    case 'evidence': return <EvidenceChip evidenceId={segment.evidenceId} display={segment.display} />;
    default: return null;
  }
}

export function SentenceText({ sentence }: { sentence: Sentence }) {
  const { lang } = useApp();
  const limitation = limitationCodeOf(sentence);
  if (limitation) return <>{labelOf(LIMITATION, limitation, lang)}</>;
  return <>{sentence.segments.map((s, i) => <SegmentView key={i} segment={s} />)}</>;
}

export function SentenceView({ sentence, mode }: { sentence: Sentence; mode: BriefMode }) {
  const { tr, lang } = useApp();
  const struck = sentence.audit.status === 'struck';
  const repaired = sentence.audit.status === 'repaired';
  const limitation = limitationCodeOf(sentence);
  return (
    <div className={`sent${struck ? ' struck' : ''}`} id={`sentence-${sentence.id}`}>
      <p className="txt">{struck ? <del><SentenceText sentence={sentence} /></del> : <SentenceText sentence={sentence} />}</p>
      {mode === 'audit' && (
        <div className="sent-audit small">
          <span className="mono muted">{sentence.id}{limitation ? ` · ${limitation}` : ''}</span>{' '}
          <span className={`audit-tag audit-${sentence.audit.status}`}>{labelOf(SENTENCE_AUDIT, sentence.audit.status, lang)}</span>
          {sentence.audit.failedChecks.length > 0 && (
            <span className="mono"> · {tr({ en: 'failed', fr: 'échecs' })}: {sentence.audit.failedChecks.join(', ')}</span>
          )}
          {sentence.audit.note && <span className="block srcnote">{tr(sentence.audit.note)}</span>}
        </div>
      )}
      {mode === 'normal' && repaired && (
        <span className="small muted">{tr({ en: 'Repaired by the auditor', fr: 'Corrigée par l’auditeur' })}</span>
      )}
    </div>
  );
}

/** The run's Evidence page at the first removed sentence; the Evidence list outside a run scope. */
function removedHref(runId: string | null, firstStruck: string | undefined): string {
  if (!runId) return '/evidence-audit/';
  return `/evidence-audit/?runId=${encodeURIComponent(runId)}${firstStruck ? `#sentence-${encodeURIComponent(firstStruck)}` : ''}`;
}

export function BriefView({ brief, mode = 'normal' }: { brief: Brief; mode?: BriefMode }) {
  const { tr, lang } = useApp();
  const scope = useFactScope();
  const runId = scope && scope.kind !== 'local' ? scope.runId : null;
  return (
    <div className="brief">
      {brief.sections.map(section => {
        const sentences = visibleSentences(section, mode);
        const struck = struckSentences(section);
        const hidden = mode === 'normal' ? struck.length : 0;
        const note = removedNote(hidden);
        return (
          <section key={section.id} className="brief-section">
            <h3 className="brief-heading">{sectionTitle(section, lang)}</h3>
            {sentences.length === 0 && (
              <p className="muted small">{tr({ en: 'No sentence in this section.', fr: 'Aucune phrase dans cette section.' })}</p>
            )}
            {sentences.map(sentence => <SentenceView key={sentence.id} sentence={sentence} mode={mode} />)}
            {hidden > 0 && (
              <p className="small muted">
                {tr(note.text)} <Link href={removedHref(runId, struck[0]?.id)}>{tr(note.link)}</Link>
              </p>
            )}
          </section>
        );
      })}
      <p className="brief-disclaimer small">{tr(brief.disclaimer)}</p>
      <p className="small muted">
        {tr({ en: 'Written', fr: 'Rédigé le' })} {fmtDateTime(brief.generatedAt, lang)}
        {mode !== 'normal' && <>, {tr({ en: 'model', fr: 'modèle' })} <span className="mono">{brief.model}</span></>}
      </p>
    </div>
  );
}
