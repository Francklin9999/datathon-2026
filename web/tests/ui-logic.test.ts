/** Glass UI pure logic: theme resolution, keyboard navigation, chart/donut geometry. */
import assert from 'node:assert/strict';
import test from 'node:test';
import { THEME_BOOT_SCRIPT, resolveTheme } from '../src/lib/ui/theme';
import { nextSegmentIndex, windowShortLabel } from '../src/lib/ui/segmented';

test('nextSegmentIndex wraps and supports Home/End', () => {
  assert.equal(nextSegmentIndex(0, 'ArrowRight', 5), 1);
  assert.equal(nextSegmentIndex(4, 'ArrowRight', 5), 0);
  assert.equal(nextSegmentIndex(0, 'ArrowLeft', 5), 4);
  assert.equal(nextSegmentIndex(1, 'ArrowDown', 5), 2);
  assert.equal(nextSegmentIndex(1, 'ArrowUp', 5), 0);
  assert.equal(nextSegmentIndex(2, 'Home', 5), 0);
  assert.equal(nextSegmentIndex(2, 'End', 5), 4);
  assert.equal(nextSegmentIndex(2, 'Enter', 5), null);
});

test('window short labels stay short in both languages', () => {
  for (const code of ['full', '1y', '3y', '5y', 'ytd'] as const) {
    for (const lang of ['en', 'fr'] as const) assert.ok(windowShortLabel(code, lang).length <= 4, `${code}/${lang}`);
  }
  assert.equal(windowShortLabel('ytd', 'en'), 'YTD');
  assert.equal(windowShortLabel('full', 'fr'), 'Tout');
});

test('resolveTheme honours an explicit preference', () => {
  assert.equal(resolveTheme('dark', false), 'dark');
  assert.equal(resolveTheme('light', true), 'light');
});

test('resolveTheme falls back to the system for system/missing/corrupt values', () => {
  assert.equal(resolveTheme('system', true), 'dark');
  assert.equal(resolveTheme(null, false), 'light');
  assert.equal(resolveTheme('purple', true), 'dark');
});

test('boot script reads the same key the provider writes and sets data-theme', () => {
  assert.match(THEME_BOOT_SCRIPT, /aplomb\.pref\.theme/);
  assert.match(THEME_BOOT_SCRIPT, /data-theme|dataset\.theme/);
  assert.match(THEME_BOOT_SCRIPT, /try/);
});

import { donutArcs } from '../src/lib/ui/donut';
import { areaPath, chartScale, linePath, nearestIndex } from '../src/lib/ui/chart';

const GEOM = { cx: 50, cy: 50, r: 40, thickness: 10, gapDeg: 2 };

test('donutArcs: proportional, ignores non-positive, never NaN', () => {
  const arcs = donutArcs([{ key: 'a', value: 50 }, { key: 'b', value: 47 }, { key: 'c', value: 3 }, { key: 'z', value: 0 }, { key: 'n', value: -4 }], GEOM);
  assert.deepEqual(arcs.map(a => a.key), ['a', 'b', 'c']);
  assert.ok(Math.abs(arcs.reduce((s, a) => s + a.pct, 0) - 100) < 1e-9);
  assert.ok(Math.abs((arcs[0]?.pct ?? 0) - 50) < 1e-9);
  assert.ok(arcs.every(a => a.d.length > 0 && !a.d.includes('NaN')));
});

test('donutArcs: weights not summing to 100 are normalised', () => {
  const arcs = donutArcs([{ key: 'a', value: 30 }, { key: 'b', value: 30 }], GEOM);
  assert.deepEqual(arcs.map(a => a.pct), [50, 50]);
});

test('donutArcs: single item is a full ring; empty input is empty', () => {
  const [only, ...rest] = donutArcs([{ key: 'x', value: 80 }], GEOM);
  assert.equal(rest.length, 0);
  assert.equal(only?.pct, 100);
  assert.ok(only && only.d.length > 0 && !only.d.includes('NaN'));
  assert.deepEqual(donutArcs([], GEOM), []);
  assert.deepEqual(donutArcs([{ key: 'z', value: 0 }], GEOM), []);
});

test('chartScale pads range and survives flat series', () => {
  assert.deepEqual(chartScale([100, 100]), { lo: 99, hi: 101 });
  const s = chartScale([0, 100]);
  assert.ok(s.lo < 0 && s.hi > 100);
  assert.deepEqual(chartScale([]), { lo: 0, hi: 1 });
});

test('nearestIndex clamps and picks the closest x', () => {
  assert.equal(nearestIndex([0, 10, 20], -5), 0);
  assert.equal(nearestIndex([0, 10, 20], 14), 1);
  assert.equal(nearestIndex([0, 10, 20], 16), 2);
  assert.equal(nearestIndex([0, 10, 20], 99), 2);
  assert.equal(nearestIndex([5], 0), 0);
  assert.equal(nearestIndex([], 3), -1);
});

test('areaPath closes the line down to the baseline', () => {
  const d = areaPath([{ x: 0, y: 10 }, { x: 5, y: 4 }, { x: 10, y: 6 }], 20);
  assert.match(d, /^M0(\.0+)?,20/);
  assert.match(d, /Z$/);
  assert.equal(areaPath([], 20), '');
});

test('linePath joins points in order', () => {
  assert.equal(linePath([{ x: 0, y: 1 }, { x: 2, y: 3 }]), 'M0.00,1.00 L2.00,3.00');
  assert.equal(linePath([]), '');
});

import { themeToApply } from '../src/lib/ui/theme';
import { chartLineProps } from '../src/lib/ui/chart';
import { segmentAccessibleName } from '../src/lib/ui/segmented';

test('themeToApply waits until the stored preference has been read (no flash over the boot script)', () => {
  assert.equal(themeToApply(null, true), null);
  assert.equal(themeToApply(null, false), null);
  assert.equal(themeToApply('dark', false), 'dark');
  assert.equal(themeToApply('system', true), 'dark');
});

test('only the solid series gets pathLength; the dashed benchmark keeps real dashes', () => {
  assert.deepEqual(chartLineProps(false), { pathLength: 1 });
  const dashed = chartLineProps(true);
  assert.equal('pathLength' in dashed, false);
  assert.equal(dashed.strokeDasharray, '5 5');
});

test('segment accessible name starts with the visible label (WCAG 2.5.3)', () => {
  assert.equal(segmentAccessibleName('YTD', 'Year to date'), 'YTD, Year to date');
  assert.equal(segmentAccessibleName('Country', undefined), undefined);
  assert.equal(segmentAccessibleName('All', 'All'), undefined);
});

import { splitLimitations } from '../src/lib/ui/limitations';
import { MOTION_BOOT_SCRIPT, themeColorFor } from '../src/lib/ui/theme';

test('splitLimitations dedupes, keeps order and folds after n', () => {
  assert.deepEqual(splitLimitations(['A', 'B', 'A', 'C'], undefined), { shown: ['A', 'B', 'C'], folded: [] });
  assert.deepEqual(splitLimitations(['A', 'B', 'A', 'C'], 1), { shown: ['A'], folded: ['B', 'C'] });
  assert.deepEqual(splitLimitations(['A', 'B'], 0), { shown: [], folded: ['A', 'B'] });
  assert.deepEqual(splitLimitations([], 1), { shown: [], folded: [] });
});

test('browser theme-color follows the resolved theme, not only the OS', () => {
  assert.equal(themeColorFor('light'), '#ECEFF5');
  assert.equal(themeColorFor('dark'), '#0B0D12');
});

test('motion boot script pauses entrance motion while the page is hidden', () => {
  assert.match(MOTION_BOOT_SCRIPT, /visibilityState/);
  assert.match(MOTION_BOOT_SCRIPT, /data-motion/);
  assert.match(MOTION_BOOT_SCRIPT, /visibilitychange/);
});

import { listboxNext, typeaheadIndex } from '../src/lib/ui/listbox';

test('listboxNext moves within bounds (no wrap) and supports Home/End', () => {
  assert.equal(listboxNext(0, 'ArrowDown', 3), 1);
  assert.equal(listboxNext(2, 'ArrowDown', 3), 2);
  assert.equal(listboxNext(0, 'ArrowUp', 3), 0);
  assert.equal(listboxNext(-1, 'ArrowDown', 3), 0);
  assert.equal(listboxNext(1, 'Home', 3), 0);
  assert.equal(listboxNext(1, 'End', 3), 2);
  assert.equal(listboxNext(1, 'a', 3), null);
  assert.equal(listboxNext(0, 'ArrowDown', 0), null);
});

test('typeaheadIndex finds the next label by prefix, case-insensitive, wrapping', () => {
  const labels = ['Robert', 'Amira', 'Mateo', 'Rachel'];
  assert.equal(typeaheadIndex(labels, 'r', 0), 3);
  assert.equal(typeaheadIndex(labels, 'r', 3), 0);
  assert.equal(typeaheadIndex(labels, 'AM', 0), 1);
  assert.equal(typeaheadIndex(labels, 'z', 0), -1);
  assert.equal(typeaheadIndex(labels, '', 0), -1);
});

import { SIDEBAR_BOOT_SCRIPT, SIDEBAR_PREF_KEY, isSidebarState } from '../src/lib/ui/theme';

test('sidebar state is a stored preference applied before first paint', () => {
  assert.equal(SIDEBAR_PREF_KEY, 'sidebar');
  assert.match(SIDEBAR_BOOT_SCRIPT, /aplomb\.pref\.sidebar/);
  assert.match(SIDEBAR_BOOT_SCRIPT, /data-sidebar/);
  assert.match(SIDEBAR_BOOT_SCRIPT, /try/);
  assert.equal(isSidebarState('collapsed'), true);
  assert.equal(isSidebarState('expanded'), true);
  assert.equal(isSidebarState('wide'), false);
});

import { readFileSync } from 'node:fs';
import { longestTransitionMs, placePopover } from '../src/components/ui/popoverPlacement';
import { DUR, EASE, readAnimationsAllowed } from '../src/lib/ui/theme';

const viewport = { width: 390, height: 800 };

test('placePopover: below the trigger, at least as wide as it, inside the viewport', () => {
  const p = placePopover({ top: 100, left: 20, bottom: 140, width: 160 }, { width: 120, height: 200 }, viewport, { minWidth: 220 });
  assert.equal(p.side, 'bottom');
  assert.equal(p.top, 146);
  assert.equal(p.left, 20);
  assert.equal(p.minWidth, 220);
  assert.equal(p.width, undefined);
  // Near the right edge it slides left instead of overflowing.
  const right = placePopover({ top: 100, left: 300, bottom: 140, width: 80 }, { width: 240, height: 100 }, viewport);
  assert.equal(right.left, 390 - 8 - 240);
});

test('placePopover: flips above when there is no room below, and caps its height', () => {
  const p = placePopover({ top: 700, left: 20, bottom: 740, width: 200 }, { width: 200, height: 300 }, viewport);
  assert.equal(p.side, 'top');
  assert.equal(p.top, 700 - 6 - 300);
  const tall = placePopover({ top: 100, left: 20, bottom: 140, width: 200 }, { width: 200, height: 2000 }, viewport);
  assert.equal(tall.side, 'bottom');
  assert.equal(tall.maxHeight, 360);
});

test('placePopover: exact width follows the trigger and never passes the viewport', () => {
  const p = placePopover({ top: 10, left: 0, bottom: 50, width: 600 }, { width: 100, height: 100 }, viewport, { exactWidth: true, minWidth: 240 });
  assert.equal(p.width, 390 - 16);
  assert.equal(p.left, 8);
});

test('longestTransitionMs reads computed transition lists', () => {
  assert.equal(longestTransitionMs('0.2s, 0.15s', '0s, 0.1s'), 250);
  assert.equal(longestTransitionMs('200ms', '0s'), 200);
  assert.equal(longestTransitionMs('0s', '0s'), 0);
  assert.equal(longestTransitionMs('', ''), 0);
});

test('motion: one curve and the duration tokens, shared by CSS and JavaScript', () => {
  const tokens = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8');
  assert.match(tokens, /--ease: cubic-bezier\(0\.22, 1, 0\.36, 1\);/);
  assert.deepEqual([...EASE], [0.22, 1, 0.36, 1]);
  assert.match(tokens, new RegExp(`--dur-menu: ${DUR.menu * 1000}ms;`));
  assert.match(tokens, new RegExp(`--dur-enter: ${DUR.enter * 1000}ms;`));
  assert.match(tokens, new RegExp(`--dur-draw: ${DUR.draw * 1000}ms;`));
  for (const token of ['--h-ctl: 40px', '--h-ctl-sm: 32px', '--r-inset: 14px', '--fs-12', '--fs-13', '--fs-15', '--fs-17', '--fs-20']) assert.ok(tokens.includes(token), token);
  // Outside a browser nothing animates.
  assert.equal(readAnimationsAllowed(), false);
});

test('motion gate: every duration token goes to 0s on Off, on a hidden page and under reduced motion unless On', () => {
  const motion = readFileSync(new URL('../src/styles/motion.css', import.meta.url), 'utf8');
  assert.match(motion, /html\[data-anim='off'\], html\[data-motion='off'\] \{\s*--dur-fast: 0s; --dur-menu: 0s; --dur-enter: 0s; --dur-draw: 0s;/);
  assert.match(motion, /@media \(prefers-reduced-motion: reduce\) \{\s*html:not\(\[data-anim='on'\]\) \{\s*--dur-fast: 0s;/);
  assert.match(motion, /animation-duration: 0s !important; animation-delay: 0s !important;/);
  // No other file of the shared layers carries its own reduced-motion switch.
  for (const file of ['components.css', 'dashboard.css', 'pages.css', 'tour.css', 'primitives.css', 'base.css']) {
    const css = readFileSync(new URL(`../src/styles/${file}`, import.meta.url), 'utf8');
    assert.doesNotMatch(css, /prefers-reduced-motion/, file);
  }
});

test('buttons wrap inside their pill and keep the control heights', () => {
  const css = readFileSync(new URL('../src/styles/components.css', import.meta.url), 'utf8');
  const btn = css.slice(css.indexOf('.btn {'), css.indexOf('}', css.indexOf('.btn {')));
  assert.match(btn, /white-space: normal/);
  assert.match(btn, /text-wrap: balance/);
  assert.match(btn, /min-height: var\(--h-ctl\)/);
  assert.match(btn, /opacity var\(--dur-fast\)/);
  assert.match(css, /\.btn-sm \{ min-height: var\(--h-ctl-sm\);/);
  // One definition each.
  assert.equal(css.match(/^\.scope-note \{/gm)?.length, 1);
  assert.equal(css.match(/^\.figure-note \{/gm)?.length, 1);
  const dashboard = readFileSync(new URL('../src/styles/dashboard.css', import.meta.url), 'utf8');
  assert.doesNotMatch(dashboard, /^\.(scope|figure)-note \{/m);
});
