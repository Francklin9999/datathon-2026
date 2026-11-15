'use client';
/**
 * RuleTable (T14, reused by Portfolio/Home/World/Time Machine): one row per rule check with the rule's
 * assumption label, measured value, threshold, headroom, status, missing-evidence reason and
 * source chips. Horizontally scrollable on narrow screens with real table headers.
 *
 * The rows come from the checks of the result, not from the profile: `rules` only supplies the label
 * wording, the assumption tag and the derivation method. Every figure, including the threshold inside
 * the sentence, is the one the check was evaluated with (lib/format.ts::ruleSentence).
 */
import type { ReactNode } from 'react';
import type { PolicyRule, RuleCheck } from '../../contracts/types';
import { NEE_REASON, labelOf } from '../../lib/labels';
import { comparatorSymbol, fmtUnit, ruleSentence } from '../../lib/format';
import { useApp } from '../../state/app';
import { StatusBadge } from '../common/Badges';
import { FactChip } from '../common/FactDrawer';

export { ruleSentence };

export function RuleTable({ checks, rules, caption, renderEdit }: {
  checks: readonly RuleCheck[];
  rules?: readonly PolicyRule[] | undefined;
  caption: string;
  renderEdit?: ((rule: PolicyRule, check: RuleCheck) => ReactNode) | undefined;
}) {
  const { tr, lang } = useApp();
  const byId = new Map((rules ?? []).map(rule => [rule.ruleId, rule]));
  if (checks.length === 0) {
    return <p className="muted">{tr({ en: 'No rule checks were returned.', fr: 'Aucune vérification de règle n’a été retournée.' })}</p>;
  }
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table rule-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{tr({ en: 'Rule', fr: 'Règle' })}</th>
            <th scope="col">{tr({ en: 'Rule assumption', fr: 'Hypothèse de règle' })}</th>
            <th scope="col" className="num-col">{tr({ en: 'Value', fr: 'Valeur' })}</th>
            <th scope="col" className="num-col">{tr({ en: 'Threshold', fr: 'Seuil' })}</th>
            <th scope="col" className="num-col">{tr({ en: 'Headroom', fr: 'Marge' })}</th>
            <th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th>
            {renderEdit && <th scope="col">{tr({ en: 'Edit', fr: 'Modifier' })}</th>}
          </tr>
        </thead>
        <tbody>
          {checks.map(check => {
            const rule = byId.get(check.ruleId);
            return (
              <tr key={`${check.ruleId}-${check.code}`} className={`row-${check.status}`}>
                <th scope="row" className="mono">{check.code}</th>
                <td className="rule-cell">
                  <span className="block">{ruleSentence(rule, check, lang)}</span>
                  {rule?.isAssumption && <span className="tag">{tr({ en: 'rule assumption', fr: 'hypothèse de règle' })}</span>}
                  {rule && !rule.enabled && <span className="tag tag-muted">{tr({ en: 'disabled in the current plan', fr: 'désactivée dans le plan actuel' })}</span>}
                  {/* Without a profile rule the sentence above already is the check's detail. */}
                  {rule && <span className="block small muted">{tr(check.detail)}</span>}
                  {check.neeReason && (
                    <span className="block small nee-reason">{labelOf(NEE_REASON, check.neeReason, lang)}</span>
                  )}
                  {check.worst && (
                    <span className="block small muted">{tr({ en: 'Driven by', fr: 'Déterminé par' })} <span className="mono">{check.worst.id}</span></span>
                  )}
                  {check.evidenceIds.length > 0 && (
                    <span className="block small muted">{tr({ en: 'Evidence', fr: 'Preuves' })}: <span className="mono">{check.evidenceIds.join(', ')}</span></span>
                  )}
                  {rule?.derivation && (
                    <details className="small">
                      <summary>{tr({ en: 'How the threshold was derived', fr: 'Comment le seuil a été dérivé' })}</summary>
                      <p className="mono break">{rule.derivation.formula}</p>
                      <p className="muted">{tr(rule.rationale)}</p>
                    </details>
                  )}
                </td>
                <td className="num-col">
                  {check.valueFactId
                    ? <FactChip factId={check.valueFactId} display={fmtUnit(check.value, check.unit, lang)} />
                    : <span className="num">{fmtUnit(check.value, check.unit, lang)}</span>}
                </td>
                <td className="num-col">
                  <span className="muted">{comparatorSymbol(check.comparator)} </span>
                  {check.thresholdFactId
                    ? <FactChip factId={check.thresholdFactId} display={fmtUnit(check.threshold, check.unit, lang)} />
                    : <span className="num">{fmtUnit(check.threshold, check.unit, lang)}</span>}
                </td>
                <td className="num-col num">{check.headroom === null ? '—' : fmtUnit(check.headroom, check.unit, lang)}</td>
                <td><StatusBadge status={check.status} /></td>
                {renderEdit && <td>{rule ? renderEdit(rule, check) : null}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
