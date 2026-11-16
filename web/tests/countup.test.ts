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

test('animations: the setting also drives motion (drawers, sheets): Off reduces, On never, Auto follows the system', async () => {
  const { motionReducedFor } = await import('../src/lib/ui/theme');
  assert.equal(motionReducedFor('off'), 'always');
  assert.equal(motionReducedFor('on'), 'never');
  assert.equal(motionReducedFor(undefined), 'user');
});

test('count-up: dates, labels and identifiers are left alone', () => {
  assert.equal(parseFigure('2021-11-12', 'en'), null);
  assert.equal(parseFigure('Nov 12, 2026', 'en'), null);
  assert.equal(parseFigure('R5', 'en'), null);
  assert.equal(parseFigure('Fixed income 50%', 'en'), null);
  assert.equal(parseFigure('6.09% (2021-11-12 – 2026-11-12)', 'en')?.value, 6.09);
  assert.equal(parseFigure('$1.2', 'en')?.value, 1.2);
});

test('animations: on by default, before paint, unless Auto or Off was chosen', async () => {
  const { ANIM_BOOT_SCRIPT, DEFAULT_ANIM } = await import('../src/lib/ui/theme');
  assert.equal(DEFAULT_ANIM, 'on');
  const run = (stored: string | null) => {
    const attrs: Record<string, string> = {};
    const fakeWindow = { localStorage: { getItem: () => stored } };
    const fakeDocument = { documentElement: { setAttribute: (k: string, v: string) => { attrs[k] = v; } } };
    new Function('window', 'document', ANIM_BOOT_SCRIPT)(fakeWindow, fakeDocument);
    return attrs['data-anim'];
  };
  assert.equal(run(null), 'on');
  assert.equal(run('on'), 'on');
  assert.equal(run('off'), 'off');
  assert.equal(run('auto'), undefined);
  assert.equal(run('garbage'), 'on');
});
