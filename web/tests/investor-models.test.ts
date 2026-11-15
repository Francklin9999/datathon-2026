import assert from 'node:assert/strict';
import test from 'node:test';
import { factorFitResult, fundLookThroughResult, parseModelInput } from '../src/api/investorModels';

test('factor fit accepts finite descriptive outputs and retains unknown R²', () => {
  const response = { alphaPerPeriod: .001, betas: { market: 1.2, value: -.3 }, residualStdev: .01,
    rSquared: null, observations: 30, firstStart: '2024-01-01', lastEnd: '2024-02-15',
    sourceIds: ['user-supplied factor sample'], excludedReturns: 1, excludedFactors: 0,
    limitations: ['Sample only'] };
  assert.deepEqual(factorFitResult(response), response);
  assert.throws(() => factorFitResult({ ...response, betas: { market: Infinity } }));
  assert.throws(() => factorFitResult({ ...response, rSquared: undefined }));
  assert.throws(() => factorFitResult({ ...response, observations: -1 }));
  assert.throws(() => factorFitResult({ ...response, sourceIds: 'unverified' }));
});

test('fund result preserves unresolved value and provenance and rejects impossible totals', () => {
  const source = { source_id: 'supplied', url: 'https://example.org/holdings',
    content_sha256: 'a'.repeat(64), observed_at: null, published_at: null,
    available_at: '2024-01-01T00:00:00Z', retrieved_at: '2024-01-02T00:00:00Z',
    licence: 'caller-provided', limitations: [] };
  const response = { direct: { US0378331005: .5 }, indirect: { US5949181045: .2 },
    unresolvedWeight: .3, snapshotDates: { US4642872000: '2024-01-01' },
    sourceIds: { US4642872000: 'supplied' }, sources: { US4642872000: source },
    overlap: [{ firstIsin: 'US4642872000', secondIsin: 'US9229083632', weight: .2 }],
    limitations: ['Unverified input'] };
  assert.deepEqual(fundLookThroughResult(response), response);
  assert.throws(() => fundLookThroughResult({ ...response, unresolvedWeight: .5 }));
  assert.throws(() => fundLookThroughResult({ ...response, indirect: { US5949181045: NaN } }));
  assert.throws(() => fundLookThroughResult({ ...response, sources: { x: { ...source, content_sha256: 'missing' } } }));
  assert.throws(() => fundLookThroughResult({ ...response, overlap: [{ ...response.overlap[0], weight: 1.1 }] }));
});

test('model imports are bounded JSON objects and cannot execute user text', () => {
  assert.deepEqual(parseModelInput('{"names":["market"],"returns":[]}'), { names: ['market'], returns: [] });
  assert.throws(() => parseModelInput('[]'));
  assert.throws(() => parseModelInput('({ code: process.exit() })'));
  assert.throws(() => parseModelInput(JSON.stringify({ text: 'é'.repeat(120_001) })));
});
