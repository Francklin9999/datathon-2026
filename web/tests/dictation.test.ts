/** Ask Aplomb dictation: recognizer lookup, language, words heard, the field they produce, error messages. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { dictationMessage, findSpeechRecognition, heardText, speechLang, withDictation, type HeardResults } from '../src/lib/dictation';

/** A results list shaped like the browser's: one [transcript, isFinal] pair per result. */
function results(...items: readonly (readonly [string, boolean])[]): HeardResults {
  return items.map(([transcript, isFinal]) => Object.assign([{ transcript }], { isFinal }));
}

class Standard {}
class Prefixed {}

test('dictation: the recognizer is found standard first, then prefixed', () => {
  assert.equal(findSpeechRecognition({ SpeechRecognition: Standard, webkitSpeechRecognition: Prefixed }), Standard);
  assert.equal(findSpeechRecognition({ webkitSpeechRecognition: Prefixed }), Prefixed);
  assert.equal(findSpeechRecognition({ webkitSpeechRecognition: Prefixed, isSecureContext: true }), Prefixed);
});

test('dictation: no recognizer, a non-constructor or an insecure page means no microphone', () => {
  assert.equal(findSpeechRecognition(undefined), null);
  assert.equal(findSpeechRecognition(null), null);
  assert.equal(findSpeechRecognition({}), null);
  assert.equal(findSpeechRecognition({ SpeechRecognition: 'yes', webkitSpeechRecognition: {} }), null);
  assert.equal(findSpeechRecognition({ SpeechRecognition: Standard, isSecureContext: false }), null);
});

test('dictation: Canadian English and French follow the interface language', () => {
  assert.equal(speechLang('en'), 'en-CA');
  assert.equal(speechLang('fr'), 'fr-CA');
});

test('dictation: words heard keep their order, final or interim, without blanks', () => {
  assert.equal(heardText(results()), '');
  assert.equal(heardText(results(['add 5% of', true], [' NVDA ', false])), 'add 5% of NVDA');
  assert.equal(heardText(results(['', true], ['   ', false], ['funded from bonds', true])), 'funded from bonds');
  const noAlternative: HeardResults = [Object.assign([], { isFinal: true })];
  assert.equal(heardText(noAlternative), '');
});

test('dictation: the words follow what was typed, with one space, within the field limit', () => {
  assert.equal(withDictation('', 'add 5% of NVDA', 600), 'add 5% of NVDA');
  assert.equal(withDictation('add 5% of  ', ' NVDA', 600), 'add 5% of NVDA');
  assert.equal(withDictation('add 5% of NVDA', '', 600), 'add 5% of NVDA');
  assert.equal(withDictation('', '   ', 600), '');
  assert.equal(withDictation('abc', 'defgh', 6), 'abc de');
  assert.equal(withDictation('', 'x'.repeat(700), 600).length, 600);
});

test('dictation: every stop on an error says why in both languages; a deliberate stop says nothing', () => {
  assert.equal(dictationMessage('aborted'), null);
  const codes = ['no-speech', 'not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported', 'bad-grammar', 'phrases-not-supported', ''];
  for (const code of codes) {
    const message = dictationMessage(code);
    assert.ok(message, code);
    assert.ok(message.en.trim() && message.fr.trim(), code);
    assert.ok(!message.en.includes('!') && !message.fr.includes('!'), `${code}: no exclamation marks`);
  }
  assert.notDeepEqual(dictationMessage('not-allowed'), dictationMessage('network'));
  assert.deepEqual(dictationMessage('bad-grammar'), dictationMessage('something-new'));
});
