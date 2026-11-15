/**
 * WCAG AA guard for the glass tokens (web/DESIGN.md "Themes and tokens"). Text is checked over its
 * worst background: the glass composited over the brightest point of the ambient gold shaft.
 * Change a token in styles/tokens.css → this test re-measures it in both themes.
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

for (const [name, t] of [['light', LIGHT], ['dark', DARK]] as const) {
  const c = (k: string) => parse(t[k]!);
  const bg = c('bg');
  const shaft = over(c('glow-shaft-core'), bg);          // brightest ambient point
  const teal = over(c('glow-teal'), bg);                  // where the footer sits
  const glass = over(c('glass'), shaft);
  const tile = over(c('tile'), glass);

  test(`${name}: body text tokens reach AA on glass over the gold shaft`, () => {
    for (const k of ['text', 'text-2', 'text-3', 'accent-text', 'gold-text']) assert.ok(contrast(c(k), glass) >= 4.5, `${k} ${contrast(c(k), glass).toFixed(2)}`);
    assert.ok(contrast(c('text-3'), tile) >= 4.5, `text-3 on tile ${contrast(c('text-3'), tile).toFixed(2)}`);
  });

  test(`${name}: focus ring and active-nav edge reach 3:1 (WCAG 1.4.11)`, () => {
    for (const k of ['focus', 'nav-edge']) assert.ok(contrast(c(k), glass) >= 3, `${k} ${contrast(c(k), glass).toFixed(2)}`);
  });

  test(`${name}: footer text on the bare ambient reaches AA`, () => {
    assert.ok(contrast(c('footer-text'), teal) >= 4.5, `footer ${contrast(c('footer-text'), teal).toFixed(2)}`);
  });

  test(`${name}: white text on the accent card reaches AA at both gradient stops`, () => {
    for (const stop of [c('accent-card-1'), c('accent-card-2')]) {
      const solid = over(stop, glass);
      assert.ok(contrast([255, 255, 255, 1], solid) >= 4.5, `title ${contrast([255, 255, 255, 1], solid).toFixed(2)}`);
      const note = over(c('accent-card-note'), solid);
      assert.ok(contrast(note, solid) >= 4.5, `note ${contrast(note, solid).toFixed(2)}`);
    }
  });
}
