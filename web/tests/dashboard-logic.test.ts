/** Dashboard pure logic: widget layout (move / resize / restore), series views and data scope. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
  fitCount, isDefaultLayout, keyboardMove, keyboardResize, moveItem, normalizeLayout, reorderTarget, resizeItem, sizeFromPointer,
  type LayoutItem, type WidgetLimits,
} from '../src/lib/ui/layout';
import { drawdownSeries, indexSeries, periodChangePct, periodEnds } from '../src/lib/ui/series';
import * as SECTIONS from '../src/lib/ui/sections';
import {
  DEFAULT_SCOPE, defaultRange, filterPositions, hiddenFilterCount, isScopeDefault, normalizeScope, scopeSummary, scopeWindow,
  scopeWindowKey, validateRange, yearsBefore, type DashboardScope,
} from '../src/lib/ui/scope';
import { axisTicks, chartScale } from '../src/lib/ui/chart';
import { fmtSignedPct, fmtUnit, ruleValueText } from '../src/lib/format';
import { LOWEST_12M_LABEL, LOWEST_12M_SHORT, lowestRollingNote } from '../src/lib/ui/figures';

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

// QA 5c / 4.4: the non-default badge and the phone "Filters" count.
const CUSTOM_3Y = { mode: 'custom', start: '2023-11-12', end: '2026-11-12' } as const;
const ONE_FIELD: DashboardScope[] = [
  { ...DEFAULT_SCOPE, period: CUSTOM_3Y },
  { ...DEFAULT_SCOPE, benchmark: 'SPY' },
  { ...DEFAULT_SCOPE, assetGroups: ['equity'] },
  { ...DEFAULT_SCOPE, minWeight: 2 },
  { ...DEFAULT_SCOPE, chartMode: 'drawdown' },
  { ...DEFAULT_SCOPE, chartMode: 'indexed' },
];

test('isScopeDefault is true only for the default scope', () => {
  assert.equal(isScopeDefault(DEFAULT_SCOPE), true);
  assert.equal(isScopeDefault(normalizeScope(null)), true);
  for (const scope of ONE_FIELD) assert.equal(isScopeDefault(scope), false, JSON.stringify(scope));
});

test('scopeSummary names each non-default field, in both languages', () => {
  assert.deepEqual(scopeSummary(DEFAULT_SCOPE, 'en'), []);
  const scope: DashboardScope = { ...DEFAULT_SCOPE, period: CUSTOM_3Y, assetGroups: ['equity'] };
  assert.deepEqual(scopeSummary(scope, 'en'), ['Nov 12, 2023 to Nov 12, 2026', 'Equity only']);
  assert.deepEqual(scopeSummary(scope, 'fr'), ['du 12 nov. 2023 au 12 nov. 2026', 'Actions seulement']);
  // Asset classes in the fixed ASSET_GROUPS order, whatever the order they were chosen in.
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, assetGroups: ['commodity', 'equity'] }, 'en'), ['Equity + Commodities only']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, minWeight: 2 }, 'en'), ['positions ≥ 2 %']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, benchmark: 'SPY' }, 'en'), ['benchmark SPY']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, benchmark: 'SPY' }, 'fr'), ['indice SPY']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, chartMode: 'indexed' }, 'en'), ['Base 100 chart']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, chartMode: 'indexed' }, 'fr'), ['graphique Base 100']);
  assert.deepEqual(scopeSummary({ ...DEFAULT_SCOPE, chartMode: 'drawdown' }, 'fr'), ['graphique Repli']);
});

test('scopeSummary is empty exactly when isScopeDefault', () => {
  for (const scope of [DEFAULT_SCOPE, ...ONE_FIELD]) {
    for (const lang of ['en', 'fr'] as const) assert.equal(scopeSummary(scope, lang).length === 0, isScopeDefault(scope));
  }
});

test('hiddenFilterCount counts the active filters folded on phones, not the period', () => {
  assert.equal(hiddenFilterCount(DEFAULT_SCOPE), 0);
  assert.equal(hiddenFilterCount({ ...DEFAULT_SCOPE, benchmark: 'SPY', assetGroups: ['equity'] }), 2);
  assert.equal(hiddenFilterCount({ ...DEFAULT_SCOPE, minWeight: 5, chartMode: 'drawdown' }), 2);
  assert.equal(hiddenFilterCount({ ...DEFAULT_SCOPE, period: CUSTOM_3Y }), 0);
});

// QA 5a / 5b / 4.4: the scope bar says what each control changes; phones fold the filters (source text:
// no DOM in node tests, the layout itself needs the browser smoke).
test('scope bar copy matches what the controls change, and phones fold the filters', () => {
  const bar = readFileSync(new URL('../src/features/home/ScopeBar.tsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/styles/dashboard.css', import.meta.url), 'utf8');
  assert.ok(bar.includes("'Filters Allocation and Positions only'") && bar.includes("'Ne filtre que Répartition et Positions'"));
  assert.ok(bar.includes("'Filters Positions only'") && bar.includes("'Ne filtre que Positions'"));
  // The tooltip no longer claims a 1-year fixed horizon, a benchmark effect on risk, or a weight filter on Allocation.
  assert.ok(!bar.includes('1, 3, 5'));
  assert.ok(bar.includes('minimum weight filters Positions only') && bar.includes('Benchmark adds a comparison line to Past performance'));
  assert.ok(bar.includes("'Saved in this browser.'") && bar.includes("'Enregistré dans ce navigateur.'"));
  assert.ok(!bar.includes('threeYearsBefore'));
  const phone = css.slice(css.indexOf('@media (max-width: 767px)'));
  assert.match(css, /\.scope-filters \{ display: contents; \}/);
  assert.match(phone, /\.scope-filters:not\(\[data-open\]\) \{ display: none; \}/);
  assert.match(phone, /\.scope-filters-toggle \{ display: inline-flex;/);
  assert.match(css, /\.scope-bar \.segment \{ flex-shrink: 0; \}/);
  assert.match(css, /\.scope-bar \.segmented \{ flex-wrap: wrap;/);
});

// QA 5d: a new custom Range starts from the window on screen.
test('defaultRange follows the period of the window on screen', () => {
  assert.deepEqual(defaultRange('3y', '2026-11-12', { start: '2023-11-10', end: '2026-11-12' }), { start: '2023-11-10', end: '2026-11-12' });
  // All: the resolved full period from the overview.
  assert.deepEqual(defaultRange('full', '2026-11-12', { start: '2021-11-12', end: '2026-11-12' }), { start: '2021-11-12', end: '2026-11-12' });
});

test('defaultRange counts the preset back from the data date when no period is shown', () => {
  assert.deepEqual(defaultRange('1y', '2026-11-12'), { start: '2025-11-12', end: '2026-11-12' });
  assert.deepEqual(defaultRange('3y', '2026-11-12', null), { start: '2023-11-12', end: '2026-11-12' });
  assert.deepEqual(defaultRange('5y', '2026-11-12'), { start: '2021-11-12', end: '2026-11-12' });
  assert.deepEqual(defaultRange('ytd', '2026-11-12'), { start: '2025-12-31', end: '2026-11-12' });
  assert.deepEqual(defaultRange('full', '2026-11-12'), { start: '2023-11-12', end: '2026-11-12' }); // documented fallback
});

test('defaultRange ignores an unusable shown period', () => {
  const preset = { start: '2025-11-12', end: '2026-11-12' };
  assert.deepEqual(defaultRange('1y', '2026-11-12', { start: '2025-11-12', end: '2026-11-13' }), preset); // after the data date
  assert.deepEqual(defaultRange('1y', '2026-11-12', { start: '2026-11-12', end: '2026-11-12' }), preset); // start not before end
  assert.deepEqual(defaultRange('1y', '2026-11-12', { start: 'bad', end: '2026-11-12' }), preset);
});

test('yearsBefore clamps 29 February like the engine, so Range works on a leap-day data date', () => {
  assert.equal(yearsBefore('2028-02-29', 1), '2027-02-28');
  assert.equal(yearsBefore('2028-02-29', 3), '2025-02-28');
  assert.equal(yearsBefore('2028-02-29', 4), '2024-02-29');
  assert.equal(yearsBefore('2026-11-12', 3), '2023-11-12');
  const range = defaultRange('3y', '2028-02-29');
  assert.equal(validateRange(range.start, range.end, '2028-02-29'), null);
  assert.equal(normalizeScope({ period: { mode: 'custom', ...range } }).period.mode, 'custom');
});

// QA 6.1: the value chart starts at the fictional capital; its padded top is not a data peak.
test('periodEnds returns the first and last plotted points', () => {
  assert.deepEqual(periodEnds([{ date: '2021-11-12', value: 600000 }, { date: '2026-11-12', value: 900096.11 }]),
    { first: { date: '2021-11-12', value: 600000 }, last: { date: '2026-11-12', value: 900096.11 } });
  assert.equal(periodEnds([{ date: '2021-11-12', value: 600000 }]), null);
  assert.equal(periodEnds([]), null);
});

test('axisTicks puts labels on round values inside the padded range', () => {
  // Robert, full window (QA 6.1): the old top label was the padded bound 918,942.
  const { lo, hi } = chartScale([554290.24, 901578.09]);
  assert.deepEqual(axisTicks(lo, hi, 0), [600000, 700000, 800000, 900000]);
  for (const [a, b, digits] of [[lo, hi, 0], [99, 101, 0], [-8.4, 0.4, 1], [95, 160, 0], [0.001, 0.0042, 4]] as const) {
    const ticks = axisTicks(a, b, digits);
    assert.ok(ticks.length >= 2 && ticks.length <= 6, `${a}..${b}: ${ticks}`);
    for (const t of ticks) {
      assert.ok(t >= a && t <= b, `${t} outside ${a}..${b}`);
      assert.equal(Number(t.toFixed(digits)), t, `${t} is not round at ${digits} digits`);
    }
  }
  assert.deepEqual(axisTicks(99, 101, 0), [99, 100, 101]);
  assert.deepEqual(axisTicks(-8.4, 0.4, 1), [-7.5, -5, -2.5, 0]);
});

// QA 6.2: positive "worst 12 months" is explained.
test('lowest rolling 12-month return: label and positive-value note', () => {
  assert.match(LOWEST_12M_LABEL.en, /^Lowest rolling 12-month return/);
  assert.match(LOWEST_12M_SHORT.fr, /^Plus faible rendement glissant sur 12 mois/);
  assert.equal(lowestRollingNote(-4.157759714223541), null);
  assert.equal(lowestRollingNote(null), null);
  assert.equal(lowestRollingNote(0), null);
  const note = lowestRollingNote(8.65430917934531);
  assert.ok(note && note.en.startsWith('Positive') && note.fr.startsWith('Positif'));
});

// QA 6.3: R10's informational return is signed with two decimals, never "0.0%".
test('ruleValueText: informational returns are signed with two decimals; other checks keep their unit format', () => {
  const r10 = { comparator: 'none', threshold: null, unit: 'pct', value: -0.019448840688596203 } as const;
  assert.equal(ruleValueText(r10, 'en'), '−0.02%');
  assert.equal(ruleValueText(r10, 'fr'), fmtSignedPct(-0.019448840688596203, 'fr', 2));
  assert.equal(ruleValueText({ ...r10, value: 3.456 }, 'en'), '+3.46%');
  assert.equal(ruleValueText({ ...r10, value: null }, 'en'), '—');
  // A cap row, and a conditional policy (comparator "none" with a threshold), are unchanged.
  assert.equal(ruleValueText({ comparator: '<=', threshold: 55, unit: 'pct', value: 5 }, 'en'), '5.0%');
  assert.equal(ruleValueText({ comparator: 'none', threshold: 10, unit: 'pct', value: -0.0194 }, 'en'), fmtUnit(-0.0194, 'pct', 'en'));
  assert.equal(ruleValueText({ comparator: 'none', threshold: null, unit: 'pts', value: 1.25 }, 'en'), fmtUnit(1.25, 'pts', 'en'));
});
