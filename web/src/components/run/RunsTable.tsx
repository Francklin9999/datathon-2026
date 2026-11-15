'use client';
/**
 * The analyses of this session as one table, shared by Evidence and System: filter chips by state
 * (with counts), then title, kind, profile, status, verdict, date and duration. Run IDs stay out of
 * sight; each title links to the page that inspects the run.
 */
import Link from 'next/link';
import { useState } from 'react';
import type { I18NText, RunStatus, RunSummary } from '../../contracts/types';
import { useApp } from '../../state/app';
import { RUN_KIND, labelOf } from '../../lib/labels';
import { fmtDateTime, fmtDuration } from '../../lib/format';
import { RunStatusBadge, VerdictBadge } from '../common/Badges';

type Filter = 'all' | 'done' | 'active' | 'failed';
const GROUP: Record<RunStatus, Exclude<Filter, 'all'>> = {
  succeeded: 'done', queued: 'active', running: 'active', waiting_input: 'active', failed: 'failed', cancelled: 'failed',
};
const FILTERS: readonly { value: Filter; label: I18NText }[] = [
  { value: 'all', label: { en: 'All', fr: 'Toutes' } },
  { value: 'done', label: { en: 'Done', fr: 'Terminées' } },
  { value: 'active', label: { en: 'In progress', fr: 'En cours' } },
  { value: 'failed', label: { en: 'Failed or cancelled', fr: 'Échouées ou annulées' } },
];

export function RunsTable({ items, linkFor, selectedId = null, statusOf }: {
  items: readonly RunSummary[];
  linkFor: (runId: string) => string;
  selectedId?: string | null;
  /** Live status for a run being polled elsewhere on the page. */
  statusOf?: (item: RunSummary) => RunStatus;
}) {
  const { tr, lang, profiles } = useApp();
  const [filter, setFilter] = useState<Filter>('all');
  const status = (item: RunSummary) => statusOf?.(item) ?? item.status;
  const count = (f: Filter) => (f === 'all' ? items.length : items.filter(i => GROUP[status(i)] === f).length);
  const shown = filter === 'all' ? items : items.filter(i => GROUP[status(i)] === filter);
  return (
    <>
      <div className="filter-chips" role="group" aria-label={tr({ en: 'Filter by state', fr: 'Filtrer par état' })}>
        {FILTERS.filter(f => f.value === 'all' || count(f.value) > 0).map(f => (
          <button key={f.value} type="button" className="fchip" aria-pressed={filter === f.value} onClick={() => setFilter(f.value)}>
            {tr(f.label)}<span className="fchip-count">{count(f.value)}</span>
          </button>
        ))}
      </div>
      <div className="table-scroll runs-table" role="region" aria-label={tr({ en: 'Analyses of this session', fr: 'Analyses de cette session' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Analysis', fr: 'Analyse' })}</th>
              <th scope="col">{tr({ en: 'Profile', fr: 'Profil' })}</th>
              <th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th>
              <th scope="col">{tr({ en: 'Verdict', fr: 'Verdict' })}</th>
              <th scope="col">{tr({ en: 'Date', fr: 'Date' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Duration', fr: 'Durée' })}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(item => (
              <tr key={item.runId} className={item.runId === selectedId ? 'row-selected' : ''}>
                <th scope="row">
                  <Link href={linkFor(item.runId)} aria-current={item.runId === selectedId ? 'true' : undefined}>{tr(item.title)}</Link>
                  <span className="block small muted">{labelOf(RUN_KIND, item.kind, lang)}</span>
                </th>
                <td>{item.profileId ? (profiles.find(p => p.profileId === item.profileId)?.name ?? '—') : '—'}</td>
                <td><RunStatusBadge status={status(item)} /></td>
                <td>{item.verdict ? <VerdictBadge verdict={item.verdict} /> : '—'}</td>
                <td className="small">{fmtDateTime(item.createdAt, lang)}</td>
                <td className="num-col">{fmtDuration(item.durationMs, lang)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
