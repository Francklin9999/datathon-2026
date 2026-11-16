/**
 * The mini globe's orthographic projection (lib/ui/orthographic.ts): the view centre lands on the
 * disc centre, the antipode is hidden, 90 degrees east lands on the rim, hidden rings are skipped,
 * and the turn uses the design curve along the shortest way round.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  easeCurve, geometryPath, graticule, linePath, lonDelta, polygonPath, project, ringPath, rotate, type LonLat, type OrthoView,
} from '../src/lib/ui/orthographic';

const view: OrthoView = { lambda0: -96, phi0: 45, r: 40, cx: 50, cy: 50 };
const close = (a: number, b: number, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('project: the view centre maps to the disc centre', () => {
  const p = project([view.lambda0, view.phi0], view);
  close(p.x, 50);
  close(p.y, 50);
  assert.equal(p.visible, true);
  close(rotate([10, 20], 10, 20).cosC, 1);
});

test('project: the antipode is hidden', () => {
  const p = project([view.lambda0 + 180, -view.phi0], view);
  assert.equal(p.visible, false);
  close(rotate([view.lambda0 + 180, -view.phi0], view.lambda0, view.phi0).cosC, -1);
});

test('project: 90 degrees east on the equator lands on the rim (right edge); north is up', () => {
  const equator: OrthoView = { ...view, lambda0: 0, phi0: 0 };
  const east = project([90, 0], equator);
  close(east.x, 90);
  close(east.y, 50);
  assert.equal(east.visible, true);
  const north = project([0, 45], equator);
  assert.ok(north.y < 50, 'north is drawn above the centre');
  const west = project([-90, 0], equator);
  close(west.x, 10);
});

test('ringPath: a ring facing the viewer is drawn and closed; a ring wholly behind is skipped', () => {
  const equator: OrthoView = { ...view, lambda0: 0, phi0: 0 };
  const front: LonLat[] = [[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]];
  const back: LonLat[] = front.map(([lon, lat]) => [lon + 180, lat] as const);
  const path = ringPath(front, equator);
  assert.ok(path && path.startsWith('M') && path.endsWith('Z'));
  assert.equal(ringPath(back, equator), null);
  assert.equal(ringPath([[0, 0], [1, 1]], equator), null);
  assert.equal(polygonPath([back], equator), '');
  assert.equal(geometryPath({ type: 'MultiPolygon', coordinates: [[back], [front]] }, equator), path);
});

test('ringPath: hidden points of a ring across the horizon are pushed to the rim', () => {
  const equator: OrthoView = { ...view, lambda0: 0, phi0: 0 };
  const across: LonLat[] = [[60, -10], [120, -10], [120, 10], [60, 10]];
  const path = ringPath(across, equator);
  assert.ok(path);
  for (const [x, y] of [...path.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map(m => [Number(m[1]), Number(m[2])] as const)) {
    assert.ok(Math.hypot(x - 50, y - 50) <= 40.1, `point ${x},${y} outside the disc`);
  }
});

test('linePath: an open line breaks where it goes behind the globe', () => {
  const equator: OrthoView = { ...view, lambda0: 0, phi0: 0 };
  const line: LonLat[] = [];
  for (let lon = -180; lon <= 180; lon += 10) line.push([lon, 0]);
  const path = linePath(line, equator);
  assert.equal(path.match(/M/g)?.length, 1);
  assert.ok(graticule(30, 5).length > 0);
});

test('lonDelta: the shortest way round; easeCurve: the design curve from 0 to 1', () => {
  assert.equal(lonDelta(170, -170), 20);
  assert.equal(lonDelta(-170, 170), -20);
  assert.equal(lonDelta(0, 90), 90);
  assert.equal(lonDelta(-96, -96), 0);
  assert.equal(easeCurve(0), 0);
  assert.equal(easeCurve(1), 1);
  const mid = easeCurve(0.5);
  assert.ok(mid > 0.8 && mid < 1, `ease-out curve at half time: ${mid}`);
  for (let t = 0.1; t < 1; t += 0.1) assert.ok(easeCurve(t) >= easeCurve(t - 0.1));
});
