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
