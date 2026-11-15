/** Dashboard pure logic: widget layout (move / resize / restore), series views and data scope. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fitCount, isDefaultLayout, keyboardMove, keyboardResize, moveItem, normalizeLayout, reorderTarget, resizeItem, sizeFromPointer,
  type LayoutItem, type WidgetLimits,
} from '../src/lib/ui/layout';
import { drawdownSeries, indexSeries, periodChangePct } from '../src/lib/ui/series';
import * as SECTIONS from '../src/lib/ui/sections';
import { DEFAULT_SCOPE, filterPositions, normalizeScope, scopeWindow, scopeWindowKey, validateRange } from '../src/lib/ui/scope';

const LIMITS: Record<string, WidgetLimits> = {
  a: { minW: 4, maxW: 12, minH: 2, maxH: 8 },
  b: { minW: 3, maxW: 6, minH: 3, maxH: 6 },
  c: { minW: 3, maxW: 12, minH: 2, maxH: 4 },
};
const DEFAULTS: LayoutItem[] = [{ id: 'a', w: 12, h: 3 }, { id: 'b', w: 4, h: 4 }, { id: 'c', w: 8, h: 2 }];

test('moveItem reorders and keeps every widget once', () => {
  assert.deepEqual(moveItem(DEFAULTS, 'c', 0).map(i => i.id), ['c', 'a', 'b']);
  assert.deepEqual(moveItem(DEFAULTS, 'a', 2).map(i => i.id), ['b', 'c', 'a']);
  assert.deepEqual(moveItem(DEFAULTS, 'a', 99).map(i => i.id), ['b', 'c', 'a']);
  assert.equal(moveItem(DEFAULTS, 'zzz', 0), DEFAULTS);
});

test('resizeItem clamps to each widget limits', () => {
  const r = resizeItem(DEFAULTS, 'b', 20, 1, LIMITS);
  assert.deepEqual(r.find(i => i.id === 'b'), { id: 'b', w: 6, h: 3 });
  assert.deepEqual(resizeItem(DEFAULTS, 'a', 2, 9, LIMITS).find(i => i.id === 'a'), { id: 'a', w: 4, h: 8 });
});

test('normalizeLayout keeps known order, drops unknown, appends missing, clamps, survives garbage', () => {
  const stored = [{ id: 'c', w: 30, h: 1 }, { id: 'zzz', w: 4, h: 4 }, { id: 'a', w: 6, h: 3 }];
  assert.deepEqual(normalizeLayout(stored, DEFAULTS, LIMITS), [{ id: 'c', w: 12, h: 2 }, { id: 'a', w: 6, h: 3 }, { id: 'b', w: 4, h: 4 }]);
  assert.deepEqual(normalizeLayout('nonsense', DEFAULTS, LIMITS), DEFAULTS);
  assert.deepEqual(normalizeLayout([{ id: 'a', w: 'x', h: null }], DEFAULTS, LIMITS)[0], { id: 'a', w: 12, h: 3 });
  assert.deepEqual(normalizeLayout([{ id: 'a' }, { id: 'a', w: 4, h: 4 }], DEFAULTS, LIMITS).map(i => i.id), ['a', 'b', 'c']);
});

test('keyboard move and resize', () => {
  assert.deepEqual(keyboardMove(DEFAULTS, 'b', 'ArrowLeft')?.map(i => i.id), ['b', 'a', 'c']);
  assert.deepEqual(keyboardMove(DEFAULTS, 'b', 'ArrowDown')?.map(i => i.id), ['a', 'c', 'b']);
  assert.equal(keyboardMove(DEFAULTS, 'a', 'ArrowUp'), null);
  assert.equal(keyboardMove(DEFAULTS, 'b', 'Enter'), null);
  assert.deepEqual(keyboardResize(DEFAULTS, 'b', 'ArrowRight', LIMITS)?.find(i => i.id === 'b'), { id: 'b', w: 5, h: 4 });
  assert.deepEqual(keyboardResize(DEFAULTS, 'b', 'ArrowUp', LIMITS)?.find(i => i.id === 'b'), { id: 'b', w: 4, h: 3 });
  assert.equal(keyboardResize(DEFAULTS, 'c', 'ArrowUp', LIMITS), null); // already at minH: nothing to do
});

test('sizeFromPointer snaps a drag to whole columns and rows', () => {
  assert.deepEqual(sizeFromPointer({ w: 4, h: 4 }, 130, -40, 100, 48), { w: 5, h: 3 });
  assert.deepEqual(sizeFromPointer({ w: 4, h: 4 }, 10, 10, 100, 48), { w: 4, h: 4 });
});

const P = [{ date: '2024-01-01', value: 200 }, { date: '2024-01-02', value: 220 }, { date: '2024-01-03', value: 176 }, { date: '2024-01-04', value: 230 }];

test('indexSeries rebases to 100 on the first point', () => {
  assert.deepEqual(indexSeries(P).map(p => Math.round(p.value * 1e9) / 1e9), [100, 110, 88, 115]);
  assert.deepEqual(indexSeries([]), []);
  assert.deepEqual(indexSeries([{ date: 'd', value: 0 }]), []);
});

test('drawdownSeries is the fall from the running peak, in percent', () => {
  const dd = drawdownSeries(P).map(p => Math.round(p.value * 100) / 100);
  assert.deepEqual(dd, [0, 0, -20, 0]);
});

test('periodChangePct compares last to first', () => {
  assert.ok(Math.abs((periodChangePct(P) ?? 0) - 15) < 1e-9);
  assert.equal(periodChangePct([P[0]!]), null);
  assert.equal(periodChangePct([]), null);
});

test('scope: window follows the app window unless a custom range is set', () => {
  assert.deepEqual(scopeWindow(DEFAULT_SCOPE, '5y'), { code: '5y' });
  const custom = { ...DEFAULT_SCOPE, period: { mode: 'custom' as const, start: '2023-01-01', end: '2026-01-01' } };
  assert.deepEqual(scopeWindow(custom, '5y'), { code: 'custom', start: '2023-01-01', end: '2026-01-01' });
  assert.equal(scopeWindowKey(custom, '5y'), 'custom:2023-01-01..2026-01-01');
  assert.equal(scopeWindowKey(DEFAULT_SCOPE, 'ytd'), 'ytd');
});

test('validateRange catches format, order and out-of-data dates', () => {
  assert.equal(validateRange('2023-01-01', '2026-01-01', '2026-11-12'), null);
  assert.equal(validateRange('2023-13-01', '2026-01-01', '2026-11-12'), 'format');
  assert.equal(validateRange('2026-01-01', '2023-01-01', '2026-11-12'), 'order');
  assert.equal(validateRange('2023-01-01', '2026-01-01', '2025-06-01'), 'after_data');
  assert.equal(validateRange('', '2026-01-01', '2026-11-12'), 'format');
});

test('normalizeScope tolerates corrupt storage and unknown values', () => {
  assert.deepEqual(normalizeScope(null), DEFAULT_SCOPE);
  const s = normalizeScope({ benchmark: 'SPY', assetGroups: ['equity', 'nope'], minWeight: 2, chartMode: 'indexed', period: { mode: 'custom', start: '2023-01-01', end: '2024-01-01' } });
  assert.equal(s.benchmark, 'SPY');
  assert.deepEqual(s.assetGroups, ['equity']);
  assert.equal(s.minWeight, 2);
  assert.equal(s.chartMode, 'indexed');
  assert.deepEqual(s.period, { mode: 'custom', start: '2023-01-01', end: '2024-01-01' });
  assert.equal(normalizeScope({ chartMode: 'rainbow', minWeight: -3 }).chartMode, 'value');
  assert.equal(normalizeScope({ minWeight: -3 }).minWeight, 0);
});

test('filterPositions applies asset groups and minimum weight, largest first', () => {
  const positions = [
    { ticker: 'A', weightPct: 30, name: 'A', assetClass: 'etf_bond', assetGroup: 'fixed_income', sector: 'Bonds', marketValue: 1 },
    { ticker: 'B', weightPct: 1.5, name: 'B', assetClass: 'stock', assetGroup: 'equity', sector: 'Tech', marketValue: 1 },
    { ticker: 'C', weightPct: 15, name: 'C', assetClass: 'etf_equity', assetGroup: 'equity', sector: 'Broad', marketValue: 1 },
  ] as const;
  assert.deepEqual(filterPositions(positions, DEFAULT_SCOPE).map(p => p.ticker), ['A', 'C', 'B']);
  assert.deepEqual(filterPositions(positions, { ...DEFAULT_SCOPE, assetGroups: ['equity'] }).map(p => p.ticker), ['C', 'B']);
  assert.deepEqual(filterPositions(positions, { ...DEFAULT_SCOPE, assetGroups: ['equity'], minWeight: 2 }).map(p => p.ticker), ['C']);
});

import { windowQuery } from '../src/api/client';

test('windowQuery sends presets as codes and custom ranges with their dates', () => {
  assert.deepEqual(windowQuery('5y'), { window: '5y' });
  assert.deepEqual(windowQuery({ code: 'ytd' }), { window: 'ytd' });
  assert.deepEqual(windowQuery({ code: 'custom', start: '2023-01-01', end: '2026-01-01' }), { window: 'custom', start: '2023-01-01', end: '2026-01-01' });
  assert.deepEqual(windowQuery({ code: 'custom' }), { window: 'full' }); // incomplete custom never reaches the API
});

test('normalizeScope snaps the minimum weight to an offered step, so the control always shows the filter in force', () => {
  assert.equal(normalizeScope({ minWeight: 3 }).minWeight, 2);
  assert.equal(normalizeScope({ minWeight: 0.5 }).minWeight, 0);
  assert.equal(normalizeScope({ minWeight: 50 }).minWeight, 10);
  assert.equal(normalizeScope({ minWeight: 5 }).minWeight, 5);
});

test('custom scope rejects calendar dates that JavaScript rolls into the next month', () => {
  assert.equal(validateRange('2026-02-30', '2026-03-10', '2026-11-12'), 'format');
  assert.equal(validateRange('2025-02-29', '2025-03-10', '2026-11-12'), 'format');
  assert.equal(validateRange('2024-02-29', '2024-03-10', '2026-11-12'), null);
});
test('reorderTarget drops before or after the hovered widget, null when nothing moves', () => {
  // Dragging c over a: before a → index 0; after a → index 1.
  assert.equal(reorderTarget(DEFAULTS, 'c', 'a', true), 0);
  assert.equal(reorderTarget(DEFAULTS, 'c', 'a', false), 1);
  // Dragging a over b: after b → index 1 in [b, c] → a lands between b and c.
  assert.deepEqual(moveItem(DEFAULTS, 'a', reorderTarget(DEFAULTS, 'a', 'b', false)!).map(i => i.id), ['b', 'a', 'c']);
  // Already there: a sits before b, so "before b" changes nothing.
  assert.equal(reorderTarget(DEFAULTS, 'a', 'b', true), null);
  assert.equal(reorderTarget(DEFAULTS, 'a', 'a', true), null);
  assert.equal(reorderTarget(DEFAULTS, 'a', 'zzz', true), null);
});

test('isDefaultLayout compares order and sizes', () => {
  assert.equal(isDefaultLayout(DEFAULTS.map(i => ({ ...i })), DEFAULTS), true);
  assert.equal(isDefaultLayout(moveItem(DEFAULTS, 'c', 0), DEFAULTS), false);
  assert.equal(isDefaultLayout(resizeItem(DEFAULTS, 'b', 5, 4, LIMITS), DEFAULTS), false);
  assert.equal(isDefaultLayout(DEFAULTS.slice(0, 2), DEFAULTS), false);
});

test('fitCount: rows that fit, bounded by the minimum and the total', () => {
  assert.equal(fitCount(220, 44, 11), 5);
  assert.equal(fitCount(219, 44, 11), 4);
  assert.equal(fitCount(10, 44, 11), 1);
  assert.equal(fitCount(10, 44, 11, 0), 0);
  assert.equal(fitCount(10_000, 44, 11), 11);
  assert.equal(fitCount(-5, 44, 3, 0), 0);
  assert.equal(fitCount(100, 44, 0), 0);
});

test('activeSection: a chosen section stays active while on screen; otherwise the lowest row past the line, first wins', () => {
  const { activeSection } = SECTIONS;
  // Row 1: figures; row 2: plan and positions side by side; row 3: brief.
  const boxes = [
    { id: 'figures', top: -600, bottom: -400 },
    { id: 'plan', top: 100, bottom: 420 },
    { id: 'positions', top: 100, bottom: 420 },
    { id: 'brief', top: 440, bottom: 800 },
  ];
  const base = { line: 300, viewportHeight: 900, atBottom: false };
  assert.equal(activeSection(boxes, { ...base, preferred: null }), 'plan');
  assert.equal(activeSection(boxes, { ...base, preferred: 'positions' }), 'positions');
  // A choice outside the active row does not override it.
  assert.equal(activeSection(boxes, { ...base, preferred: 'figures' }), 'plan');
  // Tops a few pixels apart are one row.
  assert.equal(activeSection([{ id: 'a', top: 100, bottom: 300 }, { id: 'b', top: 104, bottom: 300 }], { ...base, preferred: 'b' }), 'b');
  // At the bottom: the chosen section while on screen, otherwise the last.
  assert.equal(activeSection(boxes, { ...base, atBottom: true, preferred: 'positions' }), 'positions');
  assert.equal(activeSection(boxes, { ...base, atBottom: true, preferred: null }), 'brief');
  assert.equal(activeSection(boxes, { ...base, atBottom: true, preferred: 'figures' }), 'brief');
  // A short chosen section that the next one overtakes at the line keeps the highlight while visible.
  const short = [{ id: 'figures', top: 0, bottom: 176 }, { id: 'performance', top: 192, bottom: 600 }, { id: 'allocation', top: 192, bottom: 600 }];
  assert.equal(activeSection(short, { ...base, preferred: 'figures' }), 'figures');
  assert.equal(activeSection(short, { ...base, preferred: null }), 'performance');
  // Nothing past the line yet: the first section.
  const low = boxes.map(b => ({ ...b, top: b.top + 1000, bottom: b.bottom + 1000 }));
  assert.equal(activeSection(low, { ...base, preferred: null }), 'figures');
  assert.equal(activeSection([], { ...base, preferred: null }), null);
});
