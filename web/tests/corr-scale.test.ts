import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CORR_SCALE, contrast, corrColor, corrStrength, corrText, luminance } from '../src/lib/ui/corr';
import type { ThemeMode } from '../src/lib/ui/theme';

const THEMES: ThemeMode[] = ['light', 'dark'];
const STEPS = Array.from({ length: 41 }, (_, i) => -1 + i * 0.05);

test('heatmap: the ends are the poles and zero is the neutral middle', () => {
  for (const theme of THEMES) {
    assert.equal(corrColor(-1, theme), CORR_SCALE[theme].neg.toUpperCase());
    assert.equal(corrColor(1, theme), CORR_SCALE[theme].pos.toUpperCase());
    assert.equal(corrColor(0, theme), CORR_SCALE[theme].mid.toUpperCase());
    assert.equal(corrColor(Number.NaN, theme), CORR_SCALE[theme].mid.toUpperCase());
    assert.equal(corrColor(3, theme), corrColor(1, theme));
  }
});

test('heatmap: lightness moves monotonically away from the middle on each arm', () => {
  for (const theme of THEMES) {
    const lightToward = (sign: 1 | -1) => STEPS.filter(v => v >= 0).map(v => luminance(corrColor(sign * v, theme)));
    for (const sign of [1, -1] as const) {
      const arm = lightToward(sign);
      const direction = Math.sign((arm[arm.length - 1] ?? 0) - (arm[0] ?? 0));
      for (let i = 1; i < arm.length; i++) {
        assert.ok(Math.sign((arm[i] ?? 0) - (arm[i - 1] ?? 0)) !== -direction, `${theme} arm ${sign} not monotonic at ${i}`);
      }
    }
  }
});

test('heatmap: every cell text reaches WCAG AA on its own background', () => {
  for (const theme of THEMES) {
    for (const r of STEPS) {
      const bg = corrColor(r, theme);
      const ratio = contrast(bg, corrText(bg, theme));
      assert.ok(ratio >= 4.5, `${theme} r=${r.toFixed(2)} ${bg}: ${ratio.toFixed(2)}`);
    }
  }
});

test('heatmap: strength bands read in plain words', () => {
  assert.equal(corrStrength(0.1), 'independent');
  assert.equal(corrStrength(-0.15), 'independent');
  assert.equal(corrStrength(0.35), 'together_weak');
  assert.equal(corrStrength(0.62), 'together');
  assert.equal(corrStrength(0.9), 'together_strong');
  assert.equal(corrStrength(-0.6), 'opposite');
  assert.equal(corrStrength(-0.85), 'opposite_strong');
});
