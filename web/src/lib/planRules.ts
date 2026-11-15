/**
 * Rows of the Portfolio plan-rules table (web/page-specs/portfolio.md: "every rule row").
 *
 * The profile is the list of rules; the overview only carries a check for each enabled rule
 * (backend/aplomb/rules/SPEC.md: "Disabled rules produce no check"). A rule without a check keeps
 * its row, with no value and no status claim, so a disabled rule stays visible and can be enabled
 * again. Nothing is evaluated in the browser.
 */
import type { I18NText, PolicyRule, RuleCheck } from '../contracts/types';

export const RULE_NOT_EVALUATED = {
  overviewUnavailable: { en: 'Not evaluated: overview unavailable.', fr: 'Non évaluée : aperçu indisponible.' },
  disabled: {
    en: 'Not evaluated: this rule is disabled and does not count in the plan verdict. Tick “Enabled” and save to count it again.',
    fr: 'Non évaluée : cette règle est désactivée et ne compte pas dans le verdict du plan. Cochez « Activée » et enregistrez pour la compter de nouveau.',
  },
  noCheck: { en: 'Not evaluated: the overview returned no check for this rule.', fr: 'Non évaluée : l’aperçu n’a retourné aucune vérification pour cette règle.' },
} as const satisfies Record<string, I18NText>;

function unevaluated(rule: PolicyRule, detail: I18NText): RuleCheck {
  return {
    ruleId: rule.ruleId, code: rule.code, status: 'info', value: null, threshold: rule.threshold, unit: rule.unit,
    comparator: rule.comparator, headroom: null, worst: null, valueFactId: null, thresholdFactId: null,
    detail, neeReason: null, evidenceIds: [],
  };
}

/**
 * One row per profile rule, in profile order, using the overview check when there is one.
 * `overviewChecks` is null while the overview is loading or unavailable. Checks the overview
 * returned for a rule the profile does not list are appended, so nothing the API sent is dropped.
 */
export function planRuleRows(rules: readonly PolicyRule[], overviewChecks: readonly RuleCheck[] | null): RuleCheck[] {
  const byRule = new Map((overviewChecks ?? []).map(check => [check.ruleId, check]));
  const listed = new Set(rules.map(rule => rule.ruleId));
  const rows = rules.map(rule => {
    const check = byRule.get(rule.ruleId);
    if (check) return check;
    if (overviewChecks === null) return unevaluated(rule, RULE_NOT_EVALUATED.overviewUnavailable);
    return unevaluated(rule, rule.enabled ? RULE_NOT_EVALUATED.noCheck : RULE_NOT_EVALUATED.disabled);
  });
  return [...rows, ...(overviewChecks ?? []).filter(check => !listed.has(check.ruleId))];
}

/** Rules of the profile that are switched off, in profile order. */
export function disabledRules(rules: readonly PolicyRule[]): PolicyRule[] {
  return rules.filter(rule => !rule.enabled);
}
