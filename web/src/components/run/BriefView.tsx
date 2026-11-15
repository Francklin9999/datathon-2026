'use client';
/**
 * BriefView (T14): renders typed segments only, never HTML from the model (WEB-08). Normal mode
 * hides struck sentences; audit mode shows them struck with failed codes and the auditor's note.
 */
import type { Brief, Segment, Sentence } from '../../contracts/types';
import { visibleSentences, type BriefMode } from '../../lib/brief';
import { SENTENCE_AUDIT, labelOf } from '../../lib/labels';
import { fmtDateTime } from '../../lib/format';
import { useApp } from '../../state/app';
import { EvidenceChip, FactChip } from '../common/FactDrawer';

function SegmentView({ segment }: { segment: Segment }) {
  switch (segment.t) {
    case 'text': return <>{segment.text}</>;
    case 'fact': return <FactChip factId={segment.factId} display={segment.display} />;
    case 'rule': return <span className="rule-ref mono" title={segment.ruleId}>{segment.display}</span>;
    case 'status': return <strong className="status-word">{segment.display}</strong>;
    case 'evidence': return <EvidenceChip evidenceId={segment.evidenceId} display={segment.display} />;
    default: return null;
  }
}

export function SentenceText({ sentence }: { sentence: Sentence }) {
  return <>{sentence.segments.map((s, i) => <SegmentView key={i} segment={s} />)}</>;
}

export function SentenceView({ sentence, mode }: { sentence: Sentence; mode: BriefMode }) {
  const { tr, lang } = useApp();
  const struck = sentence.audit.status === 'struck';
  const repaired = sentence.audit.status === 'repaired';
  return (
    <div className={`sent${struck ? ' struck' : ''}`} id={`sentence-${sentence.id}`}>
      <p className="txt">{struck ? <del><SentenceText sentence={sentence} /></del> : <SentenceText sentence={sentence} />}</p>
      {mode === 'audit' && (
        <div className="sent-audit small">
          <span className="mono muted">{sentence.id}</span>{' '}
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

export function BriefView({ brief, mode = 'normal', headingLevel = 3 }: { brief: Brief; mode?: BriefMode; headingLevel?: 2 | 3 }) {
  const { tr, lang } = useApp();
  const Heading = headingLevel === 2 ? 'h2' : 'h3';
  return (
    <div className="brief">
      {brief.sections.map(section => {
        const sentences = visibleSentences(section, mode);
        const hidden = section.sentences.length - sentences.length;
        return (
          <section key={section.id} className="brief-section">
            <Heading className="brief-heading">{tr(section.title)}</Heading>
            {sentences.length === 0 && (
              <p className="muted small">{tr({ en: 'No sentence in this section.', fr: 'Aucune phrase dans cette section.' })}</p>
            )}
            {sentences.map(sentence => <SentenceView key={sentence.id} sentence={sentence} mode={mode} />)}
            {mode === 'normal' && hidden > 0 && (
              <p className="small muted">
                {tr({ en: `${hidden} sentence(s) removed by the auditor; see Evidence & Audit.`, fr: `${hidden} phrase(s) retirée(s) par l’auditeur ; voir Preuves et audit.` })}
              </p>
            )}
          </section>
        );
      })}
      <p className="brief-disclaimer small">{tr(brief.disclaimer)}</p>
      <p className="small muted">
        {tr({ en: 'Written', fr: 'Rédigé' })} {fmtDateTime(brief.generatedAt, lang)} · {tr({ en: 'model', fr: 'modèle' })} <span className="mono">{brief.model}</span>
      </p>
    </div>
  );
}
