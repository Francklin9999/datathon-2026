/**
 * Layout and shell guards (QA 4.1, 4.2, 4.6, 4.8): the dock clearance, legend and plan-health
 * lines that wrap instead of an ellipsis, one always-visible label per
 * rail link, the rail's place under the top bar and
 * the 404 page's list of pages. Geometry itself needs a browser (tests/browser-smoke.mjs); these pin
 * the rules and the pure logic.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fitHeights, fitRowsWithMore } from '../src/lib/ui/layout';
import { FOOTER_ENTRIES, NAV_ENTRIES, isActivePath, visibleNavEntries, visibleNavGroups } from '../src/lib/ui/nav';

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8');
const shellCss = read('../src/styles/shell.css');
const baseCss = read('../src/styles/base.css');
const dashboardCss = read('../src/styles/dashboard.css');

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
  // The top bar is fixed from 768 px only (on phones it scrolls with the page).
  assert.doesNotMatch(rule(baseCss, 'html'), /scroll-padding-top/);
  assert.match(baseCss, /@media \(min-width: 768px\) \{\s*html \{ scroll-padding-top: 96px; \}/);
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

test('4.6 rail: each link holds its label once, always visible (no tooltip copy)', () => {
  const source = read('../src/components/shell/NavLink.tsx');
  const link = source.slice(source.indexOf('export function NavLink'));
  assert.equal(link.match(/\{tr\(item\.label\)\}/g)?.length, 1);
  assert.match(link, /<span className="nav-text">\{tr\(item\.label\)\}<\/span>/);
  assert.match(link, /aria-current=\{active \? 'page' : undefined\}/);
  assert.doesNotMatch(link, /nav-tip/);
  // Compact rail: a 12 px caption under the icon that wraps instead of being cut.
  const caption = rule(shellCss, '.rail .nav-text');
  assert.match(caption, /font-size:\s*12px/);
  assert.match(caption, /white-space:\s*normal/);
  assert.doesNotMatch(caption, /ellipsis|nowrap/);
  assert.match(rule(shellCss, '.rail .nav-link'), /flex-direction:\s*column/);
});

test('4.6 rail: under the top bar, scrolling inside, and covered by the top bar and its popovers', () => {
  const rail = rule(shellCss, '.rail');
  assert.doesNotMatch(rail, /top:\s*50%|translateY/);
  assert.match(rail, /top:\s*var\(--rail-top\)/);
  assert.match(rail, /max-height:\s*calc\(100dvh - var\(--rail-top\) - var\(--gap-shell\)\)/);
  assert.match(rule(shellCss, '.rail-scroll'), /overflow-y:\s*auto/);
  const z = (decls: string) => Number(decls.match(/z-index:\s*(\d+)/)?.[1]);
  const topbar = z(rule(shellCss, '.topbar'));
  assert.ok(topbar > z(rail), 'top bar above the rail');
  assert.ok(topbar > z(rule(shellCss, '.dock')), 'top bar above the dock');
  assert.match(rule(shellCss, '.page'), /margin:\s*16px 0 0 calc\(var\(--rail-current\) \+ var\(--gap-shell\)\)/);
});

test('4.6 isActivePath: Home only on itself, other pages on their subpaths', () => {
  assert.equal(isActivePath('/', '/'), true);
  assert.equal(isActivePath('/portfolio/', '/'), false);
  assert.equal(isActivePath('/portfolio/', '/portfolio/'), true);
  assert.equal(isActivePath('/portfolio/x', '/portfolio/'), true);
  assert.equal(isActivePath('/markets/', '/portfolio/'), false);
});

test('4.8 visibleNavEntries: flagged pages hide only once /meta reports them off', () => {
  const all = visibleNavEntries({ metaLoaded: false, feature: () => false, withFooter: true });
  assert.deepEqual(all.map(e => e.href), [...NAV_ENTRIES.map(e => e.href), ...FOOTER_ENTRIES.map(e => e.href)]);
  const off = (flag: string) => flag !== 'world_explorer' && flag !== 'time_machine';
  const hrefs = visibleNavEntries({ metaLoaded: true, feature: off }).map(e => e.href);
  assert.ok(!hrefs.includes('/world-explorer/'));
  assert.ok(!hrefs.includes('/time-machine/'));
  assert.ok(hrefs.includes('/') && hrefs.includes('/decision-desk/'));
  assert.ok(!hrefs.includes('/sources/') && !hrefs.includes('/labs/'));
  // A group left without pages disappears (Explore holds only World).
  assert.ok(!visibleNavGroups({ metaLoaded: true, feature: off }).some(group => group.id === 'explore'));
  for (const entry of [...NAV_ENTRIES, ...FOOTER_ENTRIES]) {
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
