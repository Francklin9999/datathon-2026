/** Regressions for the web audit findings (2026-11-15): rule sentences, brief rendering, plan rules. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { PolicyRule, RuleCheck } from '../src/contracts/types';
import { limitationCodeOf, sectionTitle, statusWord } from '../src/lib/brief';
import { fmtPct, fmtSignedPct, ruleSentence } from '../src/lib/format';
import { disabledRules, planRuleRows } from '../src/lib/planRules';

const profiles = JSON.parse(readFileSync(new URL('../../contracts/fixtures/profiles.json', import.meta.url), 'utf8'));
const robert = profiles.items.find((p: { profileId: string }) => p.profileId === 'robert');
const capRule: PolicyRule = robert.rules.find((r: PolicyRule) => r.ruleId === 'cap.position');

function checkFor(rule: PolicyRule, threshold: number): RuleCheck {
  return {
    ruleId: rule.ruleId, code: rule.code, status: 'pass', value: 5, threshold, unit: rule.unit, comparator: rule.comparator,
    headroom: threshold - 5, worst: null, valueFactId: null, thresholdFactId: null,
    detail: { en: 'detail', fr: 'détail' }, neeReason: null, evidenceIds: [],
  };
}

test('a rule sentence states the threshold the check was evaluated with, not the current profile value', () => {
  const evaluatedAt = 7.5;
  assert.notEqual(capRule.threshold, evaluatedAt);
  const sentence = ruleSentence(capRule, checkFor(capRule, evaluatedAt), 'en');
  assert.match(sentence, /7\.5/);
  assert.doesNotMatch(sentence, new RegExp(`\\b${capRule.threshold}\\b`));
  assert.match(ruleSentence(capRule, null, 'en'), new RegExp(String(capRule.threshold)));
});

test('audit-appended limitation codes, section ids and raw statuses are shown as words', () => {
  assert.equal(limitationCodeOf({ segments: [{ t: 'text', text: 'LIM_SAMPLE_WINDOW' }] }), 'LIM_SAMPLE_WINDOW');
  assert.equal(limitationCodeOf({ segments: [{ t: 'text', text: 'The LIM_SAMPLE_WINDOW applies.' }] }), null);
  assert.equal(limitationCodeOf({ segments: [{ t: 'text', text: 'LIM_NOT_A_CODE' }] }), null);
  assert.equal(sectionTitle({ id: 'assumptions', title: { en: 'Assumptions', fr: 'assumptions' } }, 'fr'), 'Hypothèses');
  assert.equal(sectionTitle({ id: 'facts', title: { en: 'Key figures', fr: 'Chiffres clés' } }, 'fr'), 'Chiffres clés');
  assert.notEqual(statusWord('nee', 'fr'), 'nee');
  assert.equal(statusWord('en conflit', 'fr'), 'en conflit');
});

test('disabled rules stay listed in the plan so they can be enabled again', () => {
  const rules: PolicyRule[] = robert.rules.map((r: PolicyRule) => (r.ruleId === 'cap.position' ? { ...r, enabled: false } : r));
  const checks = robert.rules.filter((r: PolicyRule) => r.ruleId !== 'cap.position').map((r: PolicyRule) => checkFor(r, r.threshold ?? 0));
  const rows = planRuleRows(rules, checks);
  assert.equal(rows.length, rules.length);
  assert.ok(rows.some(row => row.ruleId === 'cap.position'));
  assert.deepEqual(disabledRules(rules).map(r => r.ruleId), ['cap.position']);
  assert.equal(planRuleRows(rules, null).length, rules.length);
});

test('percentages never show a negative zero', () => {
  assert.equal(fmtPct(-0.00001, 'en'), '0.0%');
  assert.equal(fmtSignedPct(-0.00001, 'fr'), '0,0 %');
});
