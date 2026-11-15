import { test } from 'node:test';
import assert from 'node:assert/strict';
import { easeOutCubic, formatLike, parseFigure } from '../src/lib/ui/countup';

const roundTrip = (text: string, lang: 'en' | 'fr') => {
  const parts = parseFigure(text, lang);
  assert.ok(parts, text);
  assert.equal(formatLike(parts, parts.value), text, `${lang} ${text}`);
  return parts;
};

test('count-up: English figures keep groups, decimals and signs', () => {
  assert.equal(roundTrip('CAD 600,000', 'en').value, 600000);
  assert.equal(roundTrip('+50.0%', 'en').value, 50);
  assert.equal(roundTrip('−4.7%', 'en').value, -4.7);
  assert.equal(roundTrip('0.123', 'en').decimals, 3);
  assert.equal(roundTrip('1,234.56', 'en').value, 1234.56);
  assert.equal(roundTrip('6.3', 'en').value, 6.3);
});

test('count-up: French figures keep narrow spaces and decimal commas', () => {
  assert.equal(roundTrip('600\u202f000 $CA', 'fr').value, 600000);
  assert.equal(roundTrip('+50,0 %', 'fr').value, 50);
  assert.equal(roundTrip('−4,7 %', 'fr').value, -4.7);
  assert.equal(roundTrip('0,123', 'fr').decimals, 3);
  assert.equal(roundTrip('1\u00a0234,5', 'fr').value, 1234.5);
});

test('count-up: intermediate values are written in the source style', () => {
  const en = parseFigure('CAD 600,000', 'en')!;
  assert.equal(formatLike(en, 0), 'CAD 0');
  assert.equal(formatLike(en, 12345.6), 'CAD 12,346');
  const pct = parseFigure('+50.0%', 'en')!;
  assert.equal(formatLike(pct, 0), '0.0%');
  assert.equal(formatLike(pct, 12.34), '+12.3%');
  const neg = parseFigure('−4,7 %', 'fr')!;
  assert.equal(formatLike(neg, -2.25), '−2,3 %');
});

test('count-up: no number means no animation, and the easing settles on 1', () => {
  assert.equal(parseFigure('Unavailable', 'en'), null);
  assert.equal(easeOutCubic(0), 0);
  assert.equal(easeOutCubic(1), 1);
  assert.equal(easeOutCubic(2), 1);
  assert.ok(easeOutCubic(0.5) > 0.5);
});

test('animations: the setting wins over the system, a hidden page never animates', async () => {
  const { animationsAllowed } = await import('../src/lib/ui/theme');
  assert.equal(animationsAllowed(undefined, false, false), true);
  assert.equal(animationsAllowed(undefined, true, false), false);
  assert.equal(animationsAllowed('on', true, false), true);
  assert.equal(animationsAllowed('off', false, false), false);
  assert.equal(animationsAllowed('on', false, true), false);
});
