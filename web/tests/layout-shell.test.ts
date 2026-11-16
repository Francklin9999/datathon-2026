/**
 * Layout and shell guards (QA 4.1, 4.2, 4.3, 4.6, 4.8): the dock clearance, legend and plan-health
 * lines that wrap instead of an ellipsis, the covariance number format, one label per rail link and
 * the 404 page's list of pages. Geometry itself needs a browser (tests/browser-smoke.mjs); these pin
 * the rules and the pure logic.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fmtExact, fmtSci } from '../src/lib/format';
import { fitHeights, fitRowsWithMore } from '../src/lib/ui/layout';
import { NAV_ENTRIES, SOURCES_ENTRY, isActivePath, visibleNavEntries } from '../src/lib/ui/nav';

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
const shellCss = read('../src/styles/shell.css');
const baseCss = read('../src/styles/base.css');
const dashboardCss = read('../src/styles/dashboard.css');
const pagesCss = read('../src/styles/pages.css');

/** The declarations of the first rule whose selector is exactly `selector` (outside or inside a media block). */
function rule(css: string, selector: string, from = 0): string {
  const re = new RegExp(`(^|[\\n}])\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`, 'g');
  re.lastIndex = from;
  const m = re.exec(css);
  assert.ok(m, `rule ${selector} not found`);
  return m[2]!;
}
const px = (decls: string, prop: string) => {
  const m = decls.match(new RegExp(`(?:^|[;\\s])${prop}:\\s*(\\d+)px`));
  assert.ok(m, `${prop} not in px`);
  return Number(m[1]);
};

test('4.1 dock: --dock-h is the dock\'s real height (padding + the 44 px "+")', () => {
  const root = rule(shellCss, ':root');
  const dockH = Number(root.match(/--dock-h:\s*(\d+)px/)?.[1]);
  const dock = rule(shellCss, '.dock');
  const plus = rule(shellCss, '.dock-plus');
  assert.equal(dockH, px(dock, 'padding') * 2 + px(plus, 'height'));
  assert.match(root, /--dock-gap:\s*18px/);
  assert.match(root, /--dock-clearance:\s*calc\(var\(--dock-h\) \+ var\(--dock-gap\)/);
  assert.match(dock, /bottom:\s*var\(--dock-gap\)/);
  assert.match(dock, /min-height:\s*var\(--dock-h\)/);
});

test('4.1 dock: the page end and every scroll or focus target clear the dock', () => {
  assert.match(rule(baseCss, 'html'), /scroll-padding-bottom:\s*var\(--dock-clearance\)/);
  assert.match(rule(baseCss, 'html'), /scroll-padding-top:\s*96px/);
  assert.match(rule(shellCss, '.page'), /padding:\s*32px 36px calc\(var\(--dock-clearance\) \+ 30px\)/);
  // Phones hide the dock, so nothing is reserved for it there.
  const phone = shellCss.slice(shellCss.indexOf('@media (max-width: 767px)'));
  assert.match(phone, /:root\s*\{\s*--dock-clearance:\s*0px;\s*\}/);
  assert.match(phone, /\.rail, \.dock \{ display: none; \}/);
});

test('4.2 Allocation legend: names wrap, never an ellipsis; values never wrap', () => {
  const name = rule(dashboardCss, '.meter-name');
  assert.doesNotMatch(name, /ellipsis|nowrap|overflow:\s*hidden/);
  assert.match(name, /white-space:\s*normal/);
  assert.match(rule(dashboardCss, '.meter-row'), /grid-template-columns:\s*subgrid/);
  assert.match(rule(dashboardCss, '.meter-value'), /white-space:\s*nowrap/);
});

test('4.2 Plan health: lines wrap, never an ellipsis or a fixed one-line height', () => {
  const li = rule(dashboardCss, '.limit-lines li');
  assert.doesNotMatch(li, /ellipsis|nowrap|height:\s*30px|overflow:\s*hidden/);
  assert.match(li, /white-space:\s*normal/);
  assert.match(rule(dashboardCss, '.limit-lines li[data-unfit]'), /visibility:\s*hidden/);
});

test('4.2 fitHeights: whole rows of their own height', () => {
  assert.equal(fitHeights(100, [30, 48, 30]), 2);
  assert.equal(fitHeights(108, [30, 48, 30]), 3);
  assert.equal(fitHeights(20, [30]), 0);
  assert.equal(fitHeights(20, [30], 1), 1);
  assert.equal(fitHeights(1000, []), 0);
  assert.equal(fitHeights(-5, [10, 10]), 0);
  assert.equal(fitHeights(1000, [10, 10], 5), 2);
});

test('4.2 fitRowsWithMore: rows beside a "more" button, which shows only when something is left out', () => {
  assert.deepEqual(fitRowsWithMore(200, [44, 44, 44], 36), { shown: 3, more: false });
  assert.deepEqual(fitRowsWithMore(120, [44, 44, 44], 36), { shown: 1, more: true });
  assert.deepEqual(fitRowsWithMore(40, [44, 44], 36), { shown: 0, more: true });
  assert.deepEqual(fitRowsWithMore(30, [44, 44], 36), { shown: 0, more: false });
  assert.deepEqual(fitRowsWithMore(0, [], 36), { shown: 0, more: false });
});

test('4.3 fmtSci: 3 significant digits, true minus, superscript exponent, EN and FR', () => {
  assert.equal(fmtSci(1.199e-5, 'en'), '1.20×10⁻⁵');
  assert.equal(fmtSci(-3.1e-7, 'en'), '−3.10×10⁻⁷');
  assert.equal(fmtSci(3.103e-4, 'en'), '3.10×10⁻⁴');
  assert.equal(fmtSci(1.199e-5, 'fr'), '1,20×10⁻⁵');
  assert.equal(fmtSci(-2.27e-5, 'fr'), '−2,27×10⁻⁵');
  assert.equal(fmtSci(9.9996e-6, 'en'), '1.00×10⁻⁵');
  assert.equal(fmtSci(2.5, 'en'), '2.50');
  assert.equal(fmtSci(12345, 'en'), '1.23×10⁴');
  assert.equal(fmtSci(0, 'en'), '0');
  assert.equal(fmtSci(Number.NaN, 'en'), '—');
  assert.equal(fmtSci(Number.POSITIVE_INFINITY, 'fr'), '—');
});

test('4.3 fmtExact: the full value without an exponent, for the cell title', () => {
  assert.equal(fmtExact(1.199012e-5, 'en'), '0.00001199012');
  assert.equal(fmtExact(-3.1e-7, 'fr'), '-0,00000031');
  assert.equal(fmtExact(Number.NaN, 'en'), '—');
});

test('4.3 covariance table: sticky ticker column and cells that do not wrap', () => {
  assert.match(rule(pagesCss, ".cov-table th[scope='row'], .cov-table thead th:first-child"), /position:\s*sticky;\s*left:\s*0/);
  assert.match(rule(pagesCss, '.cov-table th, .cov-table td'), /white-space:\s*nowrap/);
  const source = read('../src/features/risk/ExpandedRisk.tsx');
  assert.match(source, /className="table-scroll cov-scroll" role="region" tabIndex=\{0\}/);
  assert.match(source, /title=\{fmtExact\(value, lang\)\}>\{fmtSci\(value, lang\)\}/);
  assert.match(source, /href="#risk"/);
  assert.doesNotMatch(source, /fmtNumber\(numeric\(v\)!, lang, 8\)/);
});

test('4.6 rail: each link holds its label once; the tooltip comes from data-label', () => {
  const source = read('../src/components/shell/NavRail.tsx');
  const link = source.slice(source.indexOf('function NavLink'), source.indexOf('export function NavList'));
  // The label as text content: once (.nav-text). The tooltip span has it only as an attribute.
  assert.equal(link.match(/>\{label\}</g)?.length, 1);
  assert.match(link, /<span className="nav-text">\{label\}<\/span>/);
  assert.match(link, /<span className="nav-tip" aria-hidden="true" data-label=\{label\} \/>/);
  assert.match(link, /aria-current=\{active \? 'page' : undefined\}/);
  assert.match(shellCss, /\.nav-tip::after \{ content: attr\(data-label\); \}/);
});

test('4.6 isActivePath: Home only on itself, other pages on their subpaths', () => {
  assert.equal(isActivePath('/', '/'), true);
  assert.equal(isActivePath('/portfolio/', '/'), false);
  assert.equal(isActivePath('/portfolio/', '/portfolio/'), true);
  assert.equal(isActivePath('/portfolio/x', '/portfolio/'), true);
  assert.equal(isActivePath('/markets/', '/portfolio/'), false);
});

test('4.8 visibleNavEntries: flagged pages hide only once /meta reports them off', () => {
  const all = visibleNavEntries({ metaLoaded: false, feature: () => false, withSources: true });
  assert.deepEqual(all.map(e => e.href), [...NAV_ENTRIES.map(e => e.href), SOURCES_ENTRY.href]);
  const off = (flag: string) => flag !== 'world_explorer' && flag !== 'time_machine';
  const hrefs = visibleNavEntries({ metaLoaded: true, feature: off }).map(e => e.href);
  assert.ok(!hrefs.includes('/world-explorer/'));
  assert.ok(!hrefs.includes('/time-machine/'));
  assert.ok(hrefs.includes('/') && hrefs.includes('/decision-desk/'));
  assert.ok(!hrefs.includes('/sources/'));
  for (const entry of [...NAV_ENTRIES, SOURCES_ENTRY]) {
    assert.ok(entry.label.en.trim() && entry.label.fr.trim(), entry.href);
  }
});

test('4.8 404 page: the app page with translated text, not the bare bilingual line', () => {
  const notFound = read('../src/app/not-found.tsx');
  assert.match(notFound, /<NotFoundPage \/>/);
  assert.doesNotMatch(notFound, /Page not found · Page introuvable/);
  const page = read('../src/features/notfound/NotFoundPage.tsx');
  assert.match(page, /tr\(\{ en: 'Page not found', fr: 'Page introuvable' \}\)/);
  assert.match(page, /useNavEntries\(true\)/);
  assert.match(page, /<PageHeader /);
  assert.match(page, /href="\/"/);
});
