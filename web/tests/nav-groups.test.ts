/**
 * The grouped navigation model (lib/ui/nav.ts): group order, bilingual labels and headings, one
 * distinct icon and one tour name per page, Markets and Risk gone (their routes redirect), Labs listed.
 */
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { MOVED_ROUTES, currentHref, redirectTarget } from '../src/lib/redirect';
import { FOOTER_ENTRIES, NAV_ENTRIES, NAV_GROUPS, visibleNavGroups } from '../src/lib/ui/nav';

const ALL = NAV_GROUPS.flatMap(group => group.entries);

test('nav groups: Overview, Plan, Explore, Trust, then the footer', () => {
  assert.deepEqual(NAV_GROUPS.map(group => group.id), ['overview', 'plan', 'explore', 'trust', 'footer']);
  const hrefs = (id: string) => NAV_GROUPS.find(group => group.id === id)?.entries.map(entry => entry.href);
  assert.deepEqual(hrefs('overview'), ['/']);
  assert.deepEqual(hrefs('plan'), ['/portfolio/', '/decision-desk/', '/strategies/', '/time-machine/']);
  assert.deepEqual(hrefs('explore'), ['/world-explorer/']);
  assert.deepEqual(hrefs('trust'), ['/evidence-audit/', '/agents-system/']);
  assert.deepEqual(hrefs('footer'), ['/sources/', '/labs/']);
  assert.deepEqual(FOOTER_ENTRIES.map(entry => entry.href), ['/sources/', '/labs/']);
  assert.deepEqual(NAV_ENTRIES.map(entry => entry.href), ALL.filter(entry => !FOOTER_ENTRIES.includes(entry)).map(entry => entry.href));
});

test('nav groups: headings and labels are bilingual and non-empty; only the footer has no heading', () => {
  for (const group of NAV_GROUPS) {
    assert.ok(group.name.en.trim() && group.name.fr.trim(), group.id);
    if (group.id === 'footer') assert.equal(group.heading, null);
    else assert.ok(group.heading?.en.trim() && group.heading.fr.trim(), group.id);
  }
  for (const entry of ALL) {
    assert.ok(entry.label.en.trim() && entry.label.fr.trim(), entry.href);
    assert.doesNotMatch(entry.label.en, /[.!]$/);
    assert.doesNotMatch(entry.label.fr, /[.!]$/);
  }
});

test('nav groups: one distinct icon, one tour name and one address per page', () => {
  const icons = ALL.map(entry => entry.icon);
  assert.equal(new Set(icons).size, icons.length, 'duplicate icon');
  const tours = ALL.map(entry => entry.tour);
  assert.equal(new Set(tours).size, tours.length, 'duplicate tour name');
  for (const tour of tours) assert.match(tour, /^nav-[a-z]+$/);
  assert.deepEqual(tours, ['nav-home', 'nav-portfolio', 'nav-decide', 'nav-strategies', 'nav-replay', 'nav-world', 'nav-evidence', 'nav-system', 'nav-sources', 'nav-labs']);
  assert.equal(new Set(ALL.map(entry => entry.href)).size, ALL.length);
});

test('nav groups: Markets and Risk are gone, Labs is listed', () => {
  const hrefs = ALL.map(entry => entry.href);
  assert.ok(!hrefs.includes('/markets/'));
  assert.ok(!hrefs.includes('/risk-intelligence/'));
  assert.ok(!ALL.some(entry => entry.tour === 'nav-markets' || entry.tour === 'nav-risk'));
  assert.ok(hrefs.includes('/labs/'));
});

test('retired routes: no page links to /markets/ or /risk-intelligence/, which only redirect old bookmarks', () => {
  const src = fileURLToPath(new URL('../src/', import.meta.url));
  const files = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return files(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
  for (const file of files(src)) {
    const route = relative(src, file).split(sep).join('/');
    // The redirect pages and the table of moved routes are the only places that may name them.
    if (route === 'app/markets/page.tsx' || route === 'app/risk-intelligence/page.tsx' || route === 'lib/redirect.ts') continue;
    assert.doesNotMatch(readFileSync(file, 'utf8'), /['"`](?:\/markets|\/risk-intelligence)\/?[?#'"`]/, `${route} links to a retired route`);
  }
});

test('redirectTarget: the old query and hash join the new address without breaking its own query', () => {
  assert.equal(redirectTarget('/decision-desk/', '?ticker=NVDA', ''), '/decision-desk/?ticker=NVDA');
  assert.equal(redirectTarget('/portfolio/?tab=risk', '', ''), '/portfolio/?tab=risk');
  assert.equal(redirectTarget('/portfolio/?tab=risk', '?x=1', '#tail-loss'), '/portfolio/?tab=risk&x=1#tail-loss');
  assert.equal(redirectTarget('/portfolio/?tab=risk', '?tab=holdings', ''), '/portfolio/?tab=risk', 'the new address keeps its own tab');
  assert.equal(redirectTarget('/decision-desk/#asset', '', '#'), '/decision-desk/#asset');
});

test('currentHref: links that arrive as data skip the redirect hop of a moved page', () => {
  // The API's focus candidates still name /risk-intelligence/ and /markets/ (backend/aplomb/quant/candidates.py).
  assert.equal(currentHref('/risk-intelligence/'), MOVED_ROUTES['/risk-intelligence/']);
  assert.equal(currentHref('/risk-intelligence'), '/portfolio/?tab=risk');
  assert.equal(currentHref('/markets/?ticker=NVDA#x'), '/decision-desk/?ticker=NVDA#x');
  assert.equal(currentHref('/portfolio/'), '/portfolio/');
  assert.equal(currentHref('/evidence-audit/?runId=r1'), '/evidence-audit/?runId=r1');
  // Each moved route renders a Redirect to the same table, so a bookmark and a link land alike.
  for (const route of Object.keys(MOVED_ROUTES)) {
    const page = readFileSync(new URL(`../src/app${route}page.tsx`, import.meta.url), 'utf8');
    assert.ok(page.includes(`<Redirect to={MOVED_ROUTES['${route}']}`), `${route} redirects through MOVED_ROUTES`);
  }
});

test('visibleNavGroups: flags hide pages only after /meta loads; the footer only on request', () => {
  const booting = visibleNavGroups({ metaLoaded: false, feature: () => false });
  assert.deepEqual(booting.map(group => group.id), ['overview', 'plan', 'explore', 'trust']);
  const withFooter = visibleNavGroups({ metaLoaded: false, feature: () => false, withFooter: true });
  assert.equal(withFooter.at(-1)?.id, 'footer');
  const loaded = visibleNavGroups({ metaLoaded: true, feature: flag => flag !== 'time_machine' });
  const plan = loaded.find(group => group.id === 'plan');
  assert.ok(plan && !plan.entries.some(entry => entry.href === '/time-machine/'));
  assert.ok(loaded.some(group => group.id === 'explore'));
});
