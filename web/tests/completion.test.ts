/** Ask Aplomb completion while typing: phrases, numbers, tickers, names, ambiguity and both languages. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { buildCompletionVocab, completeRequest, spokenName } from '../src/lib/completion';

const TICKERS = ['AAPL', 'AMZN', 'NVDA', 'TSLA', 'TD.TO', 'RY.TO', 'XBB.TO'];
const NAMES = ['Apple Inc.', 'Amazon.com, Inc.', 'NVIDIA Corporation', 'Tesla, Inc.', 'Royal Bank of Canada'];
const en = buildCompletionVocab('en', TICKERS, NAMES);
const fr = buildCompletionVocab('fr', TICKERS, NAMES);
const ghost = (text: string, vocab = en) => completeRequest(text, vocab)?.ghost ?? null;

test('completion: openers start a request, in the interface language first', () => {
  assert.deepEqual(completeRequest('a', en), { ghost: 'dd', accepted: 'add' });
  assert.equal(ghost('a', fr), 'jouter');
  assert.equal(ghost('more ex'), 'posure to');
  assert.equal(ghost('aj'), 'outer');
  assert.equal(ghost('add'), null);
});

test('completion: an opener is never offered inside a request', () => {
  assert.equal(ghost('add 5% of A'), null);
  assert.equal(ghost('add 5% of a'), null);
});

test('completion: numbers get their unit and the next words', () => {
  assert.equal(ghost('add 5'), '% of');
  assert.equal(ghost('add 2.5%'), ' of');
  assert.equal(ghost('ajouter 5', fr), ' % de');
  assert.equal(ghost('ajouter 5 %', fr), ' de');
  assert.equal(ghost('more AI exposure, lose at most 15'), '%');
  assert.equal(ghost('more AI exposure, lose at most 15%'), ' in a bad year');
});

test('completion: a ticker completes in capitals when only one matches', () => {
  assert.deepEqual(completeRequest('add 5% of nv', en), { ghost: 'DA', accepted: 'add 5% of NVDA' });
  assert.deepEqual(completeRequest('add 5% of RY', en), { ghost: '.TO', accepted: 'add 5% of RY.TO' });
  assert.equal(ghost('add 5% of T'), null);
  assert.equal(ghost('add 5% of NVDA'), null);
});

test('completion: company names complete without legal suffixes', () => {
  assert.deepEqual(completeRequest('add 5% of tes', en), { ghost: 'la', accepted: 'add 5% of tesla' });
  assert.equal(ghost('add 5% of roy'), 'al Bank of Canada');
  assert.equal(ghost('add 5% of nvi'), 'DIA');
  assert.equal(spokenName('Tesla, Inc.'), 'Tesla');
  assert.equal(spokenName('Alphabet Inc. Class A'), 'Alphabet');
  assert.equal(spokenName('Royal Bank of Canada'), 'Royal Bank of Canada');
});

test('completion: connectors complete as far as the matches agree, back to a whole word', () => {
  assert.equal(ghost('add 5% of NVDA, fun'), 'ded');
  assert.equal(ghost('add 5% of NVDA, funded f'), 'rom');
  assert.equal(ghost('add 5% of NVDA, funded from b'), 'onds');
  assert.equal(ghost('add 5% of NVDA, funded from c'), 'ash');
  assert.equal(ghost('add 5% of NVDA, funded p'), 'ro rata');
  assert.equal(ghost('add 5% of NVDA, funded from'), null);
  assert.equal(ghost('add 5% of NVDA, w'), 'ith new money');
  assert.equal(ghost('w'), null);
});

test('completion: French ignores missing accents and keyboard apostrophes', () => {
  assert.equal(ghost('ajouter 5 % de NVDA, finance par les o', fr), 'bligations');
  assert.equal(ghost("ajouter 5 % de NVDA, financé par l'e", fr), 'ncaisse');
  assert.equal(ghost('ajouter 5 % de NVDA, financé au p', fr), 'rorata');
});

test('completion: nothing after a space or for empty text', () => {
  assert.equal(ghost(''), null);
  assert.equal(ghost('   '), null);
  assert.equal(ghost('add '), null);
  assert.equal(ghost('add 5% of nv '), null);
});
