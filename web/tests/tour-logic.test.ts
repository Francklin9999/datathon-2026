import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  BUBBLE_GAP, EMPTY_PROGRESS, holeRect, isVisibleRect, markDone, maskPath, onRoute, parseProgress, placeBubble, VIEWPORT_MARGIN,
} from '../src/lib/tour/engine';
import { ALL_TOURS, BASIC_TOUR } from '../src/features/tour/tours';

const VP = { width: 1280, height: 800 };
const BUBBLE = { width: 360, height: 180 };
const SRC = fileURLToPath(new URL('../src/', import.meta.url));

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

test('tour: the bubble goes on the preferred side when it fits', () => {
  const pos = placeBubble({ top: 100, left: 400, width: 200, height: 40 }, BUBBLE, VP, 'bottom');
  assert.equal(pos.placement, 'bottom');
  assert.equal(pos.top, 100 + 40 + BUBBLE_GAP);
  assert.equal(pos.left, 400 + 100 - 180);
});

test('tour: the bubble flips when the preferred side has no room', () => {
  const pos = placeBubble({ top: 700, left: 400, width: 200, height: 60 }, BUBBLE, VP, 'bottom');
  assert.equal(pos.placement, 'top');
  assert.ok(pos.top + BUBBLE.height <= 700);
});

test('tour: the bubble stays inside the viewport horizontally', () => {
  const pos = placeBubble({ top: 100, left: 1240, width: 30, height: 30 }, BUBBLE, VP, 'bottom');
  assert.ok(pos.left + BUBBLE.width <= VP.width - VIEWPORT_MARGIN);
  const left = placeBubble({ top: 100, left: 2, width: 30, height: 30 }, BUBBLE, VP, 'bottom');
  assert.ok(left.left >= VIEWPORT_MARGIN);
});

test('tour: no target, or a target filling the screen, centres the bubble', () => {
  assert.equal(placeBubble(null, BUBBLE, VP).placement, 'center');
  assert.equal(placeBubble({ top: 0, left: 0, width: 1280, height: 800 }, BUBBLE, VP).placement, 'center');
});

test('tour: the hole hugs the target and stays on screen', () => {
  const hole = holeRect({ top: 2, left: 10, width: 100, height: 40 }, VP, 8);
  assert.equal(hole.top, 4);
  assert.equal(hole.left, 4);
  assert.ok(maskPath(VP, hole).includes('A'));
  assert.equal(maskPath(VP, null), 'M0 0H1280V800H0Z');
});

test('tour: hidden targets count as missing and routes ignore the trailing slash', () => {
  assert.equal(isVisibleRect(null), false);
  assert.equal(isVisibleRect({ top: 0, left: 0, width: 0, height: 20 }), false);
  assert.equal(isVisibleRect({ top: 0, left: 0, width: 10, height: 20 }), true);
  assert.ok(onRoute('/portfolio', '/portfolio/'));
  assert.ok(onRoute('/', '/'));
  assert.ok(!onRoute('/portfolio/', '/'));
});

test('tour: stored progress survives bad values and records finished tours once', () => {
  assert.deepEqual(parseProgress(null), EMPTY_PROGRESS);
  assert.deepEqual(parseProgress('{not json'), EMPTY_PROGRESS);
  assert.deepEqual(parseProgress('{"welcomed":true,"done":["a",3]}'), { welcomed: true, done: ['a'] });
  const once = markDone(EMPTY_PROGRESS, 'basics');
  assert.deepEqual(markDone(once, 'basics'), { welcomed: true, done: ['basics'] });
});

test('tour scripts: unique ids, both languages, valid routes', () => {
  const tourIds = new Set<string>();
  assert.equal(ALL_TOURS[0], BASIC_TOUR);
  for (const tour of ALL_TOURS) {
    assert.ok(!tourIds.has(tour.id), `duplicate tour ${tour.id}`);
    tourIds.add(tour.id);
    assert.ok(tour.title.en && tour.title.fr && tour.summary.en && tour.summary.fr, tour.id);
    assert.ok(tour.steps.length >= 3, `${tour.id} is too short`);
    const stepIds = new Set<string>();
    for (const step of tour.steps) {
      assert.ok(!stepIds.has(step.id), `${tour.id}: duplicate step ${step.id}`);
      stepIds.add(step.id);
      assert.ok(step.title.en.trim() && step.title.fr.trim() && step.body.en.trim() && step.body.fr.trim(), `${tour.id}/${step.id}`);
      if (step.route) assert.match(step.route, /^\/([a-z-]+\/)?$/, `${tour.id}/${step.id} route`);
      if (step.target) assert.match(step.target, /^[a-z0-9-]+$/, `${tour.id}/${step.id} target`);
    }
  }
});

test('tour scripts: every step target is an anchor rendered somewhere in the app', () => {
  const anchors = new Set<string>();
  for (const file of sourceFiles(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const match of text.matchAll(/(?:data-tour|tour)="([a-z0-9-]+)"|tour: '([a-z0-9-]+)'/g)) anchors.add(match[1] ?? match[2]!);
  }
  for (const tour of ALL_TOURS) {
    for (const step of tour.steps) {
      if (!step.target) continue;
      assert.ok(anchors.has(step.target), `${tour.id}/${step.id}: no element carries data-tour="${step.target}"`);
    }
  }
});

test('tour scripts: a step that opens a tab names a tab the app renders', () => {
  const texts = sourceFiles(SRC).map(file => readFileSync(file, 'utf8'));
  let opens = 0;
  for (const tour of ALL_TOURS) {
    for (const step of tour.steps) {
      if (!step.open) continue;
      opens += 1;
      assert.ok(step.target, `${tour.id}/${step.id}: a tab is opened only to reach a target`);
      // Tabs ids are `${idBase}-tab-${id}` (components/ui/Tabs.tsx tabId).
      const match = /^([a-z0-9-]+?)-tab-([a-z0-9-]+)$/.exec(step.open);
      assert.ok(match, `${tour.id}/${step.id}: open must be a tab id, {idBase}-tab-{id}`);
      const [, base, id] = match;
      assert.ok(texts.some(text => text.includes(`idBase="${base}"`) && text.includes(`id: '${id}'`)),
        `${tour.id}/${step.id}: no Tabs with idBase="${base}" and a tab '${id}'`);
    }
  }
  assert.ok(opens > 0, 'the Portfolio tour opens its tabs');
});

test('tour scripts: the rail step names every page of the rail', () => {
  const rail = BASIC_TOUR.steps.find(step => step.id === 'rail');
  assert.ok(rail);
  // The rail's entries (NavRail.tsx attaches the icons).
  const nav = readFileSync(join(SRC, 'lib/ui/nav.ts'), 'utf8');
  const labels = [...nav.matchAll(/label: \{ en: '([^']+)', fr: '([^']+)' \}/g)];
  assert.ok(labels.length >= 10, 'NavRail labels not found');
  for (const [, en, fr] of labels) {
    assert.ok(rail.body.en.includes(en!), `rail step (en) omits ${en}`);
    assert.ok(rail.body.fr.includes(fr!), `rail step (fr) omits ${fr}`);
  }
});
