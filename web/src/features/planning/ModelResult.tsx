'use client';
import type { Fact } from '../../contracts/types';
import { record, rows, scalar, texts, type Json, type ModelResult } from '../../api/expandedInvestor';
import { useApp } from '../../state/app';
import { FactChip, FactScopeProvider } from '../../components/common/FactDrawer';

export function ResultRows({ value, columns, label }: { value: Json | undefined; columns: { key: string; label: string }[]; label: string }) {
  const items = rows(value);
  if (!items.length) return null;
  return <div className="table-scroll" role="region" tabIndex={0} aria-label={label}><table><thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{items.map((row, i) => <tr key={i}>{columns.map(c => <td key={c.key} style={{ overflowWrap: 'anywhere' }}>{scalar(row[c.key])}</td>)}</tr>)}</tbody></table></div>;
}

export function ModelResultView({ value }: { value: ModelResult }) {
  const { tr } = useApp();
  const sourceIds = texts(value.sourceFactIds);
  const facts = record(value.facts) as unknown as Record<string, Fact>;
  const missing = [...texts(value.missingInputs), ...texts(value.missingHoldings)];
  return <div role="status">
    {value.state && <p><strong>{scalar(value.state).replaceAll('_', ' ')}</strong>{value.currency ? ` · ${scalar(value.currency)}` : ''}</p>}
    {!!missing.length && <p>{tr({ en: 'Missing inputs', fr: 'Entrées manquantes' })}: {missing.join('; ')}</p>}
    {value.unavailable && <p>{tr({ en: 'Unavailable', fr: 'Indisponible' })}: {scalar(value.unavailable)}</p>}
    {!!sourceIds.length && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Calculation source inputs', fr: 'Sources du calcul' }, facts }}><div className="row-actions">{sourceIds.filter(id => id in facts).map(id => <FactChip key={id} factId={id} display={id} />)}</div></FactScopeProvider>}
    {texts(value.assumptions).map((s, i) => <p className="small muted" key={`a${i}`}>{s}</p>)}
    {texts(value.limitations).map((s, i) => <p className="small muted" key={`l${i}`}>{s}</p>)}
    {value.method && <p className="small muted">{scalar(value.method)}</p>}
    <details><summary>{tr({ en: 'Inspect all calculation inputs and outputs', fr: 'Examiner toutes les entrées et sorties du calcul' })}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(value, null, 2)}</pre></details>
  </div>;
}
