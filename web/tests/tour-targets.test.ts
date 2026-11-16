/**
 * Every step of every tour points at something the app renders: its target is a `data-tour` (or a
 * component `tour`) attribute value in web/src, its route is a page under src/app, and every page of
 * the navigation (plus Profiles) has its own short tour, listed by the help menu.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ALL_TOURS, BASIC_TOUR } from '../src/features/tour/tours';
import { NAV_GROUPS } from '../src/lib/ui/nav';

const SRC = fileURLToPath(new URL('../src/', import.meta.url));

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

/**
 * Anchor values: `data-tour="x"` on elements, `tour="x"` on components that forward it (Card,
 * PageHeader, ChromeMenu), and `tour: 'x'` on the navigation entries that NavLink renders as data-tour.
 */
function anchors(): Set<string> {
  const found = new Set<string>();
  for (const file of sourceFiles(SRC)) {
    if (file.endsWith(join('features', 'tour', 'tours.ts'))) continue; // the scripts themselves are not anchors
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(/\b(?:data-tour|tour)="([a-z0-9-]+)"|\btour: '([a-z0-9-]+)'/g)) found.add(match[1] ?? match[2]!);
  }
  return found;
}

test('tour targets: every step target exists as a data-tour or tour attribute in web/src', () => {
  const present = anchors();
  assert.ok(present.size > 20, 'anchor scan found too few attributes');
  const missing: string[] = [];
  for (const tour of ALL_TOURS) {
    for (const step of tour.steps) {
      if (step.target && !present.has(step.target)) missing.push(`${tour.id}/${step.id} -> ${step.target}`);
    }
  }
  assert.deepEqual(missing, [], `targets with no element: ${missing.join(', ')}`);
});

test('tour targets: every route is a page of the app', () => {
  const pageOf = (route: string) => join(SRC, 'app', route.replace(/^\/|\/$/g, ''), 'page.tsx');
  for (const tour of ALL_TOURS) {
    assert.ok(existsSync(pageOf(tour.route)), `${tour.id}: no page for ${tour.route}`);
    for (const step of tour.steps) {
      if (step.route) assert.ok(existsSync(pageOf(step.route)), `${tour.id}/${step.id}: no page for ${step.route}`);
    }
  }
});

test('tour targets: each page of the menu, and Profiles, has one short tour', () => {
  const pages = [...NAV_GROUPS.flatMap(group => group.entries.map(entry => entry.href)), '/profiles/'];
  const pageTours = ALL_TOURS.filter(tour => tour !== BASIC_TOUR);
  for (const href of pages) {
    const forPage = pageTours.filter(tour => tour.route === href);
    assert.equal(forPage.length, 1, `${href} should have exactly one tour`);
  }
  for (const tour of pageTours) {
    assert.ok(tour.steps.length >= 3 && tour.steps.length <= 5, `${tour.id} has ${tour.steps.length} steps (3 to 5)`);
  }
});

test('tour targets: one sentence per step, in both languages', () => {
  for (const tour of ALL_TOURS) {
    for (const step of tour.steps) {
      for (const lang of ['en', 'fr'] as const) {
        assert.doesNotMatch(step.body[lang], /[.!?]\s+\p{Lu}/u, `${tour.id}/${step.id} (${lang}) has more than one sentence`);
      }
    }
  }
});

test('tour targets: the basic tour covers the shell and the help menu lists every tour', () => {
  const targets = new Set(BASIC_TOUR.steps.map(step => step.target));
  for (const target of ['persona', 'command', 'rail', 'nav-world', 'scope', 'disclaimer', 'settings', 'help']) {
    assert.ok(targets.has(target), `basics omits ${target}`);
  }
  const provider = readFileSync(join(SRC, 'features/tour/TourProvider.tsx'), 'utf8');
  assert.match(provider, /tours: ALL_TOURS/, 'the help menu reads ALL_TOURS through TourProvider');
  const menu = readFileSync(join(SRC, 'features/tour/HelpMenu.tsx'), 'utf8');
  assert.match(menu, /useTours\(\)/);
  assert.doesNotMatch(menu, /tours\.filter|pages\.filter/, 'the help menu does not hide tours');
});
