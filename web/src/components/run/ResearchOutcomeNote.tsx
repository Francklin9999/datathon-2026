'use client';
/**
 * Plain note at the top of an answer whose research step ran and saved no source (QA 7.4). It adds
 * text and removes nothing: the brief, its disclaimer and the safety copy stay as they are.
 */
import Link from 'next/link';
import type { Run } from '../../contracts/types';
import { SOURCES_TRIED_ID, researchNothingNote } from '../../lib/evidence';
import { useApp } from '../../state/app';

/** `onEvidencePage`: the link is an in-page anchor; otherwise it opens the run's Evidence page. */
export function ResearchOutcomeNote({ run, onEvidencePage = false }: { run: Run; onEvidencePage?: boolean }) {
  const { tr } = useApp();
  const note = researchNothingNote(run);
  if (!note) return null;
  const label = tr({ en: 'See the sources tried', fr: 'Voir les sources essayées' });
  return (
    <div className="scope-note" role="note">
      <p><strong>{tr(note.title)}</strong> {tr(note.body)}</p>
      <p className="small">
        {onEvidencePage
          ? <a href={`#${SOURCES_TRIED_ID}`}>{label}</a>
          : <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}#${SOURCES_TRIED_ID}`}>{label}</Link>}
      </p>
    </div>
  );
}
