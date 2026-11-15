/** T13/T14 pure logic: polling, race gate, briefs, labels, validation (web/SPEC.md §3, §6). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Run, Step } from '../src/contracts/types';
import { AuditCheckCode, ErrorCode, LimitationCode, NeeReason } from '../src/contracts/catalog';
import { validateContract } from '../src/contracts/validate';
import { contiguousCompletedSeq, isTerminal, mergeRunDelta, nextPollDelay } from '../src/lib/runs';
import {
  buildCheckRequest, createLatestGate, moveOf, sameDecisionRequest, validateMoveForm, type MoveForm,
} from '../src/lib/move';
import { danglingReferences, factUsage, visibleSentences } from '../src/lib/brief';
import { AUDIT_CHECK, ERROR_CODE, LIMITATION, NEE_REASON, labelOf } from '../src/lib/labels';
import { validateHoldings, weightSum } from '../src/lib/holdings';
import { EMPTY_PROFILE_FORM, applyDraft, toCreateRequest, validateProfileForm } from '../src/lib/profileForm';
import { factIdFor, fillThreshold } from '../src/lib/format';

test('factIds accept both fixture ("volatilityPct") and live API ("volatility") keys', () => {
  assert.equal(factIdFor({ volatilityPct: 'F-004' }, 'volatilityPct'), 'F-004');
  assert.equal(factIdFor({ volatility: 'F-104' }, 'volatilityPct'), 'F-104');
  assert.equal(factIdFor({ ytdPct: 'F-001' }, 'ytdPct'), 'F-001');
  assert.equal(factIdFor({}, 'stress2022Pct'), undefined);
  assert.equal(factIdFor(undefined, 'stress2022Pct'), undefined);
});

test('rule labels never double the unit symbol', () => {
  assert.equal(fillThreshold('above {threshold}% of the portfolio', 12, 'pct', 'en'), 'above 12.0% of the portfolio');
  assert.equal(fillThreshold('au-dessus de {threshold} % du portefeuille', 12, 'pct', 'fr'), 'au-dessus de 12,0 % du portefeuille');
  assert.equal(fillThreshold('inside the {threshold} cap', 10, 'pct', 'en'), 'inside the 10.0% cap');
  assert.equal(fillThreshold('No crypto assets', 0, 'pct', 'en'), 'No crypto assets');
  assert.equal(fillThreshold('limit {threshold}', null, 'pct', 'en'), 'limit —');
});

const fixtureRun = (): Run => validateContract('Run',
  JSON.parse(readFileSync(new URL('../../contracts/fixtures/run.decision.robert-tsla-25.json', import.meta.url), 'utf8')));

function step(seq: number, status: Step['status']): Step {
  const base = fixtureRun().steps[0];
  assert.ok(base);
  return { ...base, seq, status };
}

test('watermark is the highest contiguous completed seq, never a running one', () => {
  assert.equal(contiguousCompletedSeq([]), 0);
  assert.equal(contiguousCompletedSeq([step(1, 'done'), step(2, 'done'), step(3, 'running')]), 2);
  assert.equal(contiguousCompletedSeq([step(1, 'done'), step(3, 'done')]), 1, 'gap stops the watermark');
  assert.equal(contiguousCompletedSeq([step(2, 'done'), step(1, 'failed')]), 2, 'failed counts as completed');
});

test('delta merge upserts steps by seq and merges fact maps by id', () => {
  const full = fixtureRun();
  const prev: Run = { ...full, status: 'running', steps: [step(1, 'done'), step(2, 'running')], facts: { 'F-001': full.facts['F-001']! } };
  const delta: Run = { ...full, status: 'running', steps: [step(2, 'done'), step(3, 'running')], facts: { 'F-002': full.facts['F-002']! } };
  const merged = mergeRunDelta(prev, delta);
  assert.deepEqual(merged.steps.map(s => [s.seq, s.status]), [[1, 'done'], [2, 'done'], [3, 'running']]);
  assert.deepEqual(Object.keys(merged.facts).sort(), ['F-001', 'F-002']);
  assert.equal(mergeRunDelta(prev, { ...delta, runId: 'run_other' }).runId, 'run_other');
});

test('poll cadence: 1 s active, 5 s waiting, stop at terminal, backoff on failure', () => {
  assert.equal(nextPollDelay('queued', 0), 1000);
  assert.equal(nextPollDelay('running', 0), 1000);
  assert.equal(nextPollDelay('waiting_input', 0), 5000);
  for (const status of ['succeeded', 'failed', 'cancelled'] as const) {
    assert.equal(nextPollDelay(status, 0), null);
    assert.ok(isTerminal(status));
  }
  assert.equal(nextPollDelay('running', 2), 4000);
  assert.equal(nextPollDelay('running', 20), 30_000);
  assert.equal(nextPollDelay('running', 1, 10_000), 10_000, 'Retry-After wins when longer');
});

const form = (patch: Partial<MoveForm> = {}): MoveForm => ({ ticker: 'TSLA', sizePct: 25, fundingMode: 'pro_rata', fromTickers: [], ...patch });

test('size 0 previews the baseline with move=null (DESK-03)', () => {
  assert.equal(moveOf(form({ sizePct: 0 })), null);
  assert.equal(buildCheckRequest('robert', form({ sizePct: 0 }), { code: 'full' }).move, null);
  assert.deepEqual(buildCheckRequest('robert', form(), { code: 'full' }).move, { ticker: 'TSLA', sizePct: 25, funding: { mode: 'pro_rata' } });
  assert.equal(buildCheckRequest('robert', form({ fundingMode: 'auto' }), { code: 'full' }).compareFunding, true);
  assert.deepEqual(moveOf(form({ fundingMode: 'from_holdings', fromTickers: ['XIU.TO'] }))?.funding, { mode: 'from_holdings', fromTickers: ['XIU.TO'] });
  validateContract('CheckRequest', buildCheckRequest('robert', form(), { code: 'full' }));
  validateContract('CheckRequest', buildCheckRequest('robert', form({ sizePct: 0 }), { code: '1y' }));
});

test('only the latest slider request may apply its response (AT-20)', () => {
  const gate = createLatestGate();
  const first = gate.issue();
  const second = gate.issue();
  assert.equal(gate.isLatest(first), false);
  assert.equal(gate.isLatest(second), true);
  gate.invalidate();
  assert.equal(gate.isLatest(second), false);
});

test('move form validation mirrors api.md 4.2', () => {
  assert.deepEqual(validateMoveForm(form(), 0), []);
  assert.deepEqual(validateMoveForm(form({ ticker: '' }), 0).map(i => i.field), ['ticker']);
  assert.deepEqual(validateMoveForm(form({ sizePct: 95 }), 10).map(i => i.field), ['sizePct']);
  assert.deepEqual(validateMoveForm(form({ sizePct: 95, fundingMode: 'new_money' }), 10), []);
  assert.deepEqual(validateMoveForm(form({ fundingMode: 'from_holdings' }), 0).map(i => i.field), ['fromTickers']);
});

test('a brief is stale when the request on screen differs from the run request', () => {
  const run = { type: 'move', move: { ticker: 'TSLA', sizePct: 25, funding: { mode: 'pro_rata' } } } as const;
  assert.ok(sameDecisionRequest(run, { type: 'move', move: { ticker: 'TSLA', sizePct: 25, funding: { mode: 'auto' } } }));
  assert.ok(!sameDecisionRequest(run, { type: 'move', move: { ticker: 'TSLA', sizePct: 10, funding: { mode: 'pro_rata' } } }));
  assert.ok(!sameDecisionRequest(run, { type: 'move', move: { ticker: 'TSLA', sizePct: 25, funding: { mode: 'from_cash' } } }));
});

test('fixture run: references resolve, usage is projected, struck text hidden in normal mode', () => {
  const run = fixtureRun();
  assert.deepEqual(danglingReferences(run), []);
  const usage = factUsage(run, 'F-004');
  assert.ok(usage.sentenceIds.includes('S-01'));
  const section = run.result?.kind === 'decision' ? run.result.decision.brief.sections[0] : undefined;
  assert.ok(section);
  const struck = { ...section, sentences: section.sentences.map(s => ({ ...s, audit: { ...s.audit, status: 'struck' as const } })) };
  assert.equal(visibleSentences(struck, 'normal').length, 0);
  assert.equal(visibleSentences(struck, 'audit').length, section.sentences.length);
});

test('every displayed catalog code has a non-empty English and French label', () => {
  const tables = [
    [LIMITATION, Object.values(LimitationCode)], [NEE_REASON, Object.values(NeeReason)],
    [AUDIT_CHECK, Object.values(AuditCheckCode)], [ERROR_CODE, Object.values(ErrorCode)],
  ] as const;
  for (const [table, codes] of tables) {
    for (const code of codes) {
      const entry = (table as Record<string, { en: string; fr: string } | undefined>)[code];
      assert.ok(entry?.en.trim() && entry.fr.trim(), `missing label for ${code}`);
    }
  }
  assert.equal(labelOf(ERROR_CODE, 'some_new_code', 'en'), 'Some new code', 'unknown codes are humanised, never raw');
});

test('holdings validation exposes the actual sum (CRE-03)', () => {
  assert.equal(weightSum([{ ticker: 'A', weightPct: 60 }, { ticker: 'B', weightPct: 39.5 }]), 99.5);
  const issues = validateHoldings([{ ticker: 'A', weightPct: 60 }, { ticker: 'a', weightPct: 39.5 }], 1000);
  assert.deepEqual(issues.map(i => i.code).sort(), ['duplicate', 'sum']);
  assert.equal(issues.find(i => i.code === 'sum')?.detail, '99.50');
  assert.deepEqual(validateHoldings([{ ticker: 'A', weightPct: 100.005 }], 1), []);
  assert.deepEqual(validateHoldings([{ ticker: 'A', weightPct: -1 }, { ticker: 'B', weightPct: 101 }], 0).map(i => i.code).sort(), ['capital', 'negative']);
});

test('profile form: required fields block save; drafts are provisional; request matches contract', () => {
  const empty = validateProfileForm(EMPTY_PROFILE_FORM).map(i => i.field as string);
  for (const field of ['name', 'riskLevel', 'horizonMin', 'objective', 'experience', 'reportingCurrency']) assert.ok(empty.includes(field), field);
  const { form: drafted, filled } = applyDraft(EMPTY_PROFILE_FORM, { name: 'Test persona', riskLevel: 'moderate', horizonYears: { min: 5, max: null } });
  assert.deepEqual(filled, ['name', 'riskLevel', 'horizonYears']);
  const complete = { ...drafted, objective: 'balanced' as const, experience: 'beginner' as const, reportingCurrency: 'CAD' as const };
  assert.deepEqual(validateProfileForm(complete), []);
  const request = toCreateRequest(complete, 'run_01JCQ000000000000000000001');
  validateContract('CreateProfileRequest', request);
  assert.equal(request.portfolio, null, 'no holdings → server proposes a starting mix');
  assert.equal(request.rules, null);
  assert.deepEqual(request.horizonYears, { min: 5, max: null });
  assert.ok(validateProfileForm({ ...complete, horizonMin: '10', horizonMax: '5' }).some(i => i.field === 'horizonMax'));
});
