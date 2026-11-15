/**
 * WCAG AA guard for the tokens (web/DESIGN.md "Themes and tokens"). Surfaces are solid, so every text
 * role is measured on the page background, the card surface and the raised surface, in both themes.
 * Change a token in styles/tokens.css → this test re-measures it.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

type RGBA = [number, number, number, number];
const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8');

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  assert.ok(start >= 0, selector);
  const body = css.slice(start, css.indexOf('\n}', start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]!] = m[2]!.trim();
  return out;
}
const LIGHT = block(':root');
const DARK = { ...LIGHT, ...block("html[data-theme='dark']") };

function parse(value: string | undefined): RGBA {
  assert.ok(value, 'token missing from tokens.css');
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex) { const h = hex[1]!; return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)).concat(1) as RGBA; }
  const rgba = value.match(/^rgba?\(([^)]+)\)$/);
  assert.ok(rgba, `unsupported colour ${value}`);
  const [r, g, b, a = '1'] = rgba[1]!.split(',').map(s => s.trim());
  return [Number(r), Number(g), Number(b), Number(a)];
}
const over = (fg: RGBA, bg: RGBA): RGBA => [0, 1, 2].map(i => fg[3] * fg[i]! + (1 - fg[3]) * bg[i]!).concat(1) as RGBA;
const lum = (c: RGBA) => {
  const s = c.slice(0, 3).map(v => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * s[0]! + 0.7152 * s[1]! + 0.0722 * s[2]!;
};
const contrast = (a: RGBA, b: RGBA) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x! + 0.05) / (y! + 0.05); };
const WHITE: RGBA = [255, 255, 255, 1];

for (const [name, t] of [['light', LIGHT], ['dark', DARK]] as const) {
  const c = (k: string) => parse(t[k]);
  const surfaces: [string, RGBA][] = [['bg', c('bg')], ['surface', c('surface')], ['raised', c('raised')], ['deep', c('deep')]];
  const check = (fgKey: string, min: number) => {
    for (const [sName, s] of surfaces) {
      const ratio = contrast(over(c(fgKey), s), s);
      assert.ok(ratio >= min, `${fgKey} on ${sName}: ${ratio.toFixed(2)} < ${min}`);
    }
  };

  test(`${name}: the three text roles reach AA on every surface`, () => {
    for (const k of ['text', 'text-2', 'text-3']) check(k, 4.5);
  });

  test(`${name}: accent text and status colours reach AA on every surface`, () => {
    for (const k of ['accent-text', 'pass-fg', 'tension-fg', 'conflict-fg', 'nee-fg']) check(k, 4.5);
  });

  test(`${name}: white on the accent fill reaches AA (primary buttons)`, () => {
    for (const k of ['accent', 'accent-hover']) {
      const ratio = contrast(WHITE, c(k));
      assert.ok(ratio >= 4.5, `white on ${k}: ${ratio.toFixed(2)}`);
    }
  });

  test(`${name}: focus ring reaches 3:1 against every surface (WCAG 1.4.11)`, () => check('focus', 3));
}
