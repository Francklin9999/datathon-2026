/** Profile text drafts are additive and reviewable (QA t2, audit web-pages-core#10, t5 T5.2 holdings). */
import assert from 'node:assert/strict';
import test from 'node:test';
import type { ProfileDraftResult } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import {
  EMPTY_PROFILE_FORM, applyDraft, draftQuestion, draftReviewRows, partialFromForm, profileFieldLabel, toCreateRequest,
  validateProfileForm, type ProfileForm,
} from '../src/lib/profileForm';

const filledForm: ProfileForm = {
  ...EMPTY_PROFILE_FORM, name: 'Kenji Sato', experience: 'beginner',
  investorContext: { investorType: 'individual', liquidityNotes: 'x' },
};

test('applyDraft fills the current form and merges investorContext key by key', () => {
  const { form, filled } = applyDraft(filledForm, {
    riskLevel: 'moderate', horizonYears: { min: 10, max: 15 }, objective: 'growth', reportingCurrency: 'JPY',
    investorContext: { country: 'JP', riskCapacity: 'low' },
  });
  assert.equal(form.name, 'Kenji Sato', 'a field the draft does not propose keeps its value');
  assert.equal(form.experience, 'beginner');
  assert.equal(form.investorContext?.liquidityNotes, 'x', 'context the user entered stays');
  assert.equal(form.investorContext?.investorType, 'individual');
  assert.equal(form.investorContext?.country, 'JP');
  assert.equal(form.investorContext?.riskCapacity, 'low');
  assert.deepEqual([form.horizonMin, form.horizonMax, form.reportingCurrency], ['10', '15', 'JPY']);
  for (const field of ['riskLevel', 'horizonYears', 'objective', 'reportingCurrency', 'investorContext.country', 'investorContext.riskCapacity']) {
    assert.ok(filled.includes(field), field);
  }
  assert.ok(!filled.includes('name'));
  validateContract('CreateProfileRequest', toCreateRequest(form, 'run_01JCQ000000000000000000001'));
});

test('partialFromForm sends only complete, valid values as confirmed fields', () => {
  assert.deepEqual(partialFromForm(EMPTY_PROFILE_FORM), {});
  const fields = partialFromForm({
    ...EMPTY_PROFILE_FORM, name: '  Amira  ', age: '41.5', riskLevel: 'low', horizonMin: '10', horizonMax: '5',
    reportingCurrency: 'JP', objective: 'balanced', investorContext: { country: 'CA', riskCapacity: 'moderate', liquidityNotes: 'not sent' },
  });
  assert.deepEqual(fields, { name: 'Amira', riskLevel: 'low', objective: 'balanced', investorContext: { country: 'CA', riskCapacity: 'moderate' } },
    'a non-integer age, a reversed horizon and a 2-letter currency are not sent');
  validateContract('CreateProfileDraftRunRequest', { kind: 'profile_draft', lang: 'en', text: 'x', fields });
  assert.deepEqual(partialFromForm({ ...EMPTY_PROFILE_FORM, horizonMin: '15', reportingCurrency: 'USD' }),
    { horizonYears: { min: 15, max: null }, reportingCurrency: 'USD' });
});

test('draftReviewRows lists every proposed and withheld field, capacity, currency and horizon first', () => {
  const draft: ProfileDraftResult = {
    profile: { name: 'Kenji Sato', objective: 'growth', horizonYears: { min: 10, max: 15 }, reportingCurrency: 'JPY',
      occupation: 'teacher', investorContext: { riskCapacity: 'low' } },
    explanations: [{ field: 'objective', text: { en: 'Stated as growth.', fr: 'Indiqué comme croissance.' } }],
    unresolved: [
      { field: 'investorContext.country', question: { en: 'The draft proposed JP…', fr: 'Le brouillon propose « JP »…' } },
      { field: 'riskLevel', question: { en: 'Confirm riskLevel', fr: 'Confirm riskLevel' } },
    ],
  };
  const { proposed, withheld } = draftReviewRows(draft, { name: 'Kenji Sato' });
  assert.deepEqual(proposed.map(r => r.field), ['investorContext.riskCapacity', 'reportingCurrency', 'horizonYears', 'objective', 'name', 'occupation']);
  assert.deepEqual(withheld.map(r => r.field), ['riskLevel', 'investorContext.country']);
  for (const row of [...proposed, ...withheld]) {
    assert.ok(row.label.en && row.label.fr && row.label.en !== row.field, `label for ${row.field}`);
  }
  const byField = new Map(proposed.map(r => [r.field, r]));
  assert.deepEqual(byField.get('investorContext.riskCapacity')?.value, { en: 'Low', fr: 'Faible' });
  assert.deepEqual(byField.get('horizonYears')?.value, { en: '10–15 years', fr: '10 à 15 ans' });
  assert.deepEqual(byField.get('objective')?.explanation, { en: 'Stated as growth.', fr: 'Indiqué comme croissance.' });
  assert.equal(byField.get('name')?.alreadyInForm, true);
  assert.equal(byField.get('objective')?.alreadyInForm, false);
  assert.equal(byField.get('occupation')?.applied, false, 'the form has no occupation field');
  const old = withheld.find(r => r.field === 'riskLevel')!;
  assert.notEqual(old.question.en, old.question.fr, 'an old API’s English-only "Confirm <field>" gets a French text');
  assert.deepEqual(draftQuestion({ field: 'x', question: { en: 'Pick one.', fr: 'Choisissez.' } }), { en: 'Pick one.', fr: 'Choisissez.' });
});

test('every label a draft can show exists in both languages', () => {
  for (const field of ['horizonYears', 'occupation', 'preferences', 'portfolio', 'investorContext.country', 'investorContext.riskCapacity', 'reportingCurrency', 'riskLevel']) {
    const { en, fr } = profileFieldLabel(field);
    assert.ok(en.trim() && fr.trim() && en !== field, field);
  }
});

test('holdings outside the loaded universe block save; no universe means no ticker check', () => {
  const form: ProfileForm = {
    ...EMPTY_PROFILE_FORM, name: 'A', riskLevel: 'low', horizonMin: '5', objective: 'balanced', experience: 'beginner',
    reportingCurrency: 'CAD', ownHoldings: true, capital: '1000',
    positions: [{ ticker: '7203.T', weightPct: '50' }, { ticker: 'aapl', weightPct: '40' }, { ticker: 'CASH.CAD', weightPct: '10' }],
  };
  const universe = [{ ticker: 'AAPL' }, { ticker: 'XBB.TO' }];
  const issues = validateProfileForm(form, universe);
  assert.deepEqual(issues, [{ field: 'positions', code: 'unsupported', tickers: ['7203.T'] }]);
  assert.deepEqual(validateProfileForm(form), [], 'without a loaded universe the tickers are not checked');
  assert.deepEqual(validateProfileForm({ ...form, ownHoldings: false }, universe), [], 'no holdings entered, nothing to check');
});
