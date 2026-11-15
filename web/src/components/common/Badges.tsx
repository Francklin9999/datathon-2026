'use client';
/** Status badges always pair text with an icon; colour is never the only signal (DESIGN.md). */
import type { RuleStatus, RunStatus, Verdict, VerdictCounts } from '../../contracts/types';
import { RULE_STATUS, RUN_STATUS, VERDICT, labelOf } from '../../lib/labels';
import { useApp } from '../../state/app';

const STATUS_ICON: Record<RuleStatus, string> = { pass: '✓', tension: '!', conflict: '✕', nee: '?', info: 'i' };
const VERDICT_CLASS: Record<Verdict, string> = { compatible: 'pass', tension: 'tension', conflict: 'conflict', insufficient: 'nee' };
const VERDICT_ICON: Record<Verdict, string> = { compatible: '✓', tension: '!', conflict: '✕', insufficient: '?' };

export function StatusBadge({ status }: { status: RuleStatus }) {
  const { lang } = useApp();
  return (
    <span className={`pill s-${status}`}>
      <span aria-hidden="true" className="pill-icon">{STATUS_ICON[status]}</span>
      {labelOf(RULE_STATUS, status, lang)}
    </span>
  );
}

export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  const { lang } = useApp();
  return (
    <span className={`vbadge vbadge-${VERDICT_CLASS[verdict]}${large ? ' vbadge-lg' : ''}`}>
      <span aria-hidden="true" className="pill-icon">{VERDICT_ICON[verdict]}</span>
      {labelOf(VERDICT, verdict, lang)}
    </span>
  );
}

const RUN_CLASS: Record<RunStatus, string> = {
  queued: 'nee', running: 'tension', waiting_input: 'tension', succeeded: 'pass', failed: 'conflict', cancelled: 'nee',
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const { lang } = useApp();
  return <span className={`pill s-${RUN_CLASS[status]}`}>{labelOf(RUN_STATUS, status, lang)}</span>;
}

/** Full count line: every status including information checks (api.md 4.2). */
export function CountsLine({ counts }: { counts: VerdictCounts }) {
  const { tr } = useApp();
  return (
    <p className="counts small">
      <span><strong className="num">{counts.conflict}</strong> {tr({ en: 'conflict', fr: 'conflit(s)' })}</span>
      <span><strong className="num">{counts.tension}</strong> {tr({ en: 'tension', fr: 'tension(s)' })}</span>
      <span><strong className="num">{counts.pass}</strong> {tr({ en: 'fit', fr: 'conforme(s)' })}</span>
      <span><strong className="num">{counts.nee}</strong> {tr({ en: 'not enough evidence', fr: 'preuves insuffisantes' })}</span>
      <span><strong className="num">{counts.info}</strong> {tr({ en: 'information', fr: 'information' })}</span>
    </p>
  );
}
