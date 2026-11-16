/**
 * World globe: rebuilding the pin or arc lists hands back the same object for every unchanged item, so
 * globe.gl does not draw it again with its entrance transition (cylinders growing back, arcs redrawing).
 * The grouping level only changes when the zoom crosses a threshold, not on every camera move.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { keepStable, sameFields } from '../src/features/world/stableItems';
import { clusterDegrees, clusterPins, spreadStacked, type GlobePin } from '../src/features/world/globeStyle';

const pin = (id: string, lat: number, lng: number, kind: GlobePin['kind'] = 'event'): GlobePin =>
  ({ id, kind, lat, lng, label: id, countryLevel: false, weight: 0.5 });

test('an equal rebuilt item keeps the previous object; a changed one is replaced', () => {
  const first = keepStable([{ id: 'a', lat: 1, colors: ['#111', '#222'] }, { id: 'b', lat: 2, colors: ['#333', '#444'] }], new Map());
  const second = keepStable([{ id: 'a', lat: 1, colors: ['#111', '#222'] }, { id: 'b', lat: 3, colors: ['#333', '#444'] }], first.cache);
  assert.equal(second.items[0], first.items[0]);
  assert.notEqual(second.items[1], first.items[1]);
  assert.equal(second.items[1]!.lat, 3);
});

test('globe.gl bookkeeping on a drawn item does not count as a change', () => {
  const drawn = { id: 'a', lat: 1, __threeObj: {} };
  assert.equal(sameFields(drawn, { id: 'a', lat: 1 }), true);
  assert.equal(sameFields(drawn, { id: 'a', lat: 1, extra: true }), false);
});

test('a repeated id never shares one object between two items', () => {
  const first = keepStable([{ id: 'a', lat: 1 }], new Map());
  const second = keepStable([{ id: 'a', lat: 1 }, { id: 'a', lat: 1 }], first.cache);
  assert.notEqual(second.items[0], second.items[1]);
});

test('fanned-out events and clusters come back as the same objects when nothing moved', () => {
  const pins = [pin('e1', 10, 10), pin('e2', 10, 10), pin('e3', 40, 40), pin('e4', 40.5, 40.5)];
  // 2.1: two clusters (new objects on every grouping); 0.8: no grouping, e1 and e2 fanned out (copies).
  for (const altitude of [2.1, 0.8]) {
    const build = () => spreadStacked(clusterPins(pins, altitude, null));
    const before = keepStable(build(), new Map());
    const after = keepStable(build(), before.cache);
    assert.equal(after.items.length, before.items.length);
    after.items.forEach((item, index) => assert.equal(item, before.items[index], `${altitude} ${item.id}`));
  }
});

test('the grouping level changes only across its thresholds', () => {
  assert.equal(clusterDegrees(2.1), clusterDegrees(2.0004));
  assert.equal(clusterDegrees(1.5), clusterDegrees(1.9));
  assert.notEqual(clusterDegrees(2.1), clusterDegrees(1.5));
  assert.equal(clusterDegrees(0.8), 0);
});
