/**
 * "Why the answers differ" for the Decision Desk compare view (rules SPEC §6, EF-10).
 *
 * The rows come from `BatchCheckResponse.differences` (contract 1.6.0), computed by the backend's
 * `explain_difference`; nothing is aligned here. An API before 1.6.0 omits the key and
 * `differenceRows` returns null, so the view shows only the two rule tables, as before.
 */
import type { I18NText, Lang, RuleCheck, RuleDifference, RuleStatus } from '../contracts/types';
import { ruleValueText, fmtUnit } from './format';
import { ruleNameText } from './ruleNames';

export interface DifferenceRow {
  ruleId: string;
  /** Short rule name, or null for an unknown ID (the caller shows the ID). */
  name: I18NText | null;
  reason: RuleDifference['reason'];
  statusA: RuleStatus | null;
  statusB: RuleStatus | null;
  /** One sentence naming both profiles, with the figures the checks were evaluated with. */
  sentence: I18NText;
}

type Side = Pick<RuleCheck, 'comparator' | 'threshold' | 'unit' | 'value'>;

function both(build: (lang: Lang) => string): I18NText {
  return { en: build('en'), fr: build('fr') };
}

function sentenceOf(d: RuleDifference, a: Side | undefined, b: Side | undefined, nameA: string, nameB: string): I18NText {
  // Each side's figure is formatted with that side's check (its unit; signed when it is a return).
  const format = (side: Side | undefined, v: number | null, lang: Lang, threshold: boolean) => {
    if (!side) return '—';
    return threshold ? fmtUnit(v, side.unit, lang) : ruleValueText({ ...side, value: v }, lang);
  };
  const valueA = (lang: Lang) => format(a ?? b, d.valueA, lang, false);
  const valueB = (lang: Lang) => format(b ?? a, d.valueB, lang, false);
  const limitA = (lang: Lang) => format(a ?? b, d.thresholdA, lang, true);
  const limitB = (lang: Lang) => format(b ?? a, d.thresholdB, lang, true);
  switch (d.reason) {
    case 'rule_only_in_a':
      return { en: `Only ${nameA}’s plan has this rule.`, fr: `Seul le plan du profil ${nameA} comporte cette règle.` };
    case 'rule_only_in_b':
      return { en: `Only ${nameB}’s plan has this rule.`, fr: `Seul le plan du profil ${nameB} comporte cette règle.` };
    case 'threshold_differs':
      return both(lang => {
        const limits = lang === 'fr'
          ? `Seuils différents : ${nameA} ${limitA(lang)}, ${nameB} ${limitB(lang)}.`
          : `Different thresholds: ${nameA} ${limitA(lang)}, ${nameB} ${limitB(lang)}.`;
        if (d.valueA === null && d.valueB === null) return limits;
        const measured = lang === 'fr'
          ? ` Valeur mesurée : ${nameA} ${valueA(lang)}, ${nameB} ${valueB(lang)}.`
          : ` Measured value: ${nameA} ${valueA(lang)}, ${nameB} ${valueB(lang)}.`;
        return limits + measured;
      });
    case 'portfolio_differs':
      return both(lang => {
        if (d.valueA === d.valueB) {
          return lang === 'fr' ? 'Même seuil et même valeur mesurée, statut différent.' : 'Same threshold and measured value, different status.';
        }
        const values = `${nameA} ${valueA(lang)}, ${nameB} ${valueB(lang)}`;
        if (d.thresholdA === null) {
          return lang === 'fr' ? `Portefeuilles différents : ${values}.` : `Different portfolios: ${values}.`;
        }
        return lang === 'fr'
          ? `Même seuil (${limitA(lang)}), portefeuilles différents : ${values}.`
          : `Same threshold (${limitA(lang)}), different portfolios: ${values}.`;
      });
    case 'same':
      return { en: 'Same threshold, value and status.', fr: 'Même seuil, même valeur et même statut.' };
  }
}

/**
 * The rules whose answer differs between the two profiles, rules whose status differs first (in
 * the backend's order within each group). Null when the response carries no `differences`
 * (an API before 1.6.0); an empty list when every rule gives the same answer.
 */
export function differenceRows(
  differences: readonly RuleDifference[] | undefined,
  checksA: readonly RuleCheck[],
  checksB: readonly RuleCheck[],
  nameA: string,
  nameB: string,
): DifferenceRow[] | null {
  if (!differences) return null;
  const a = new Map(checksA.map(c => [c.ruleId, c]));
  const b = new Map(checksB.map(c => [c.ruleId, c]));
  const rows = differences
    .filter(d => d.reason !== 'same')
    .map(d => ({
      ruleId: d.ruleId,
      name: ruleNameText(d.ruleId),
      reason: d.reason,
      statusA: d.statusA,
      statusB: d.statusB,
      sentence: sentenceOf(d, a.get(d.ruleId), b.get(d.ruleId), nameA, nameB),
    }));
  const statusChanged = (r: DifferenceRow) => r.statusA !== r.statusB;
  return [...rows.filter(statusChanged), ...rows.filter(r => !statusChanged(r))];
}
