'use client';
/**
 * "Why the answers differ" in the Decision Desk compare view (rules SPEC §6, EF-10): the rules whose
 * answer differs between the two profiles, from `BatchCheckResponse.differences` (contract 1.6.0).
 * Renders nothing when the API omits the key (before 1.6.0) or a side failed.
 */
import type { ApiError, BatchCheckResponse, CheckResult } from '../../contracts/types';
import { StatusBadge } from '../../components/common/Badges';
import { differenceRows } from '../../lib/ruleDifferences';
import { useApp } from '../../state/app';

const isApiErrorBody = (value: CheckResult | ApiError): value is ApiError => 'error' in value;

export function CompareDifferences({ data, names }: { data: BatchCheckResponse; names: readonly [string, string] }) {
  const { tr } = useApp();
  const [first, second] = data.results;
  if (data.results.length !== 2 || !first || !second || isApiErrorBody(first) || isApiErrorBody(second)) return null;
  const [nameA, nameB] = names;
  const rows = differenceRows(data.differences, first.ruleChecks, second.ruleChecks, nameA, nameB);
  if (rows === null) return null;
  const caption = tr({ en: 'Why the answers differ', fr: 'Pourquoi les réponses diffèrent' });
  return (
    <section className="compare-differences" aria-label={caption} style={{ marginTop: 16 }}>
      <h3 className="h4">{caption}</h3>
      {rows.length === 0 ? (
        <p className="small muted">{tr({ en: 'Both plans give the same answer on every rule.', fr: 'Les deux plans donnent la même réponse pour chaque règle.' })}</p>
      ) : (
        <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
          <table className="data-table">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr>
                <th scope="col">{tr({ en: 'Rule', fr: 'Règle' })}</th>
                <th scope="col">{nameA}</th>
                <th scope="col">{nameB}</th>
                <th scope="col">{tr({ en: 'Why', fr: 'Pourquoi' })}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.ruleId}>
                  <th scope="row">
                    {row.name ? <>{tr(row.name)}<span className="block small muted mono">{row.ruleId}</span></> : <span className="mono">{row.ruleId}</span>}
                  </th>
                  <td>{row.statusA ? <StatusBadge status={row.statusA} /> : <span className="small muted">{tr({ en: 'No such rule', fr: 'Règle absente' })}</span>}</td>
                  <td>{row.statusB ? <StatusBadge status={row.statusB} /> : <span className="small muted">{tr({ en: 'No such rule', fr: 'Règle absente' })}</span>}</td>
                  <td className="small">{tr(row.sentence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="small muted">{tr({ en: 'Rules are matched by rule ID and compared by code.', fr: 'Les règles sont appariées par identifiant et comparées par le code.' })}</p>
    </section>
  );
}
