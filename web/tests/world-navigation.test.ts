import assert from 'node:assert/strict';
import test from 'node:test';
import { EMPTY_FILTERS, GEOGRAPHIC_AREAS, WORLD_MODES, buildEventsQuery, filtersKey, geographicCountries, insideBbox, spatialReferencePins, validBbox, viewportBounds } from '../src/lib/world';
import { clusterPins, sourceGeometry, type GlobePin } from '../src/features/world/globeStyle';

test('geographic search includes uncovered countries in both languages without remote lookup', () => {
  for (const lang of ['en', 'fr'] as const) {
    const rows = geographicCountries(lang);
    assert.ok(rows.length >= 249);
    assert.ok(rows.some(row => row.iso3 === 'JPN' && row.label.includes('JPN')));
    assert.ok(rows.some(row => row.iso3 === 'BRA'));
    assert.ok(rows.some(row => row.iso3 === 'FJI'));
    assert.ok(!rows.some(row => row.iso3 === 'ZZZ'));
  }
});

test('all ten modes have bilingual coverage limits and reference modes request actual reference layers', () => {
  assert.equal(WORLD_MODES.length, 10);
  assert.equal(new Set(WORLD_MODES.map(mode => mode.id)).size, 10);
  for (const mode of WORLD_MODES) {
    assert.ok(mode.title.en && mode.title.fr && mode.note.en && mode.note.fr);
  }
  assert.deepEqual(WORLD_MODES.find(mode => mode.id === 'aviation')?.layers, ['airports']);
});

test('selected source geometry preserves original shapes and refuses invalid or unbounded coordinates', () => {
  const polygon = { type: 'Polygon', coordinates: [[[1, 2], [3, 2], [3, 4], [1, 2]]] };
  assert.equal(sourceGeometry(polygon).polygon?.geometry, polygon);
  const paths = [[[-179, 5], [179, 6]]];
  assert.equal(sourceGeometry({ type: 'MultiLineString', coordinates: paths }).paths, paths);
  assert.equal(sourceGeometry({ type: 'Polygon', coordinates: [[[1, 2], [3, 2], [3, 4], [4, 5]]] }).polygon, null, 'an open source ring must not acquire an invented closing segment');
  assert.deepEqual(sourceGeometry({ type: 'LineString', coordinates: [[1, 2], [190, 4]] }).paths, []);
  assert.deepEqual(sourceGeometry({ type: 'LineString', coordinates: Array.from({ length: 20001 }, () => [1, 2]) }).paths, []);
  assert.equal(sourceGeometry({ type: 'Circle', coordinates: [1, 2] }).polygon, null);
});

test('region and custom geographic boxes validate boundaries and cross the date line', () => {
  for (const region of GEOGRAPHIC_AREAS) {
    assert.ok(validBbox(region.bbox));
    assert.ok(insideBbox(region.lat, region.lng, region.bbox));
  }
  assert.ok(insideBbox(-20, 179, '110,-55,-120,25'));
  assert.ok(insideBbox(-20, -150, '110,-55,-120,25'));
  assert.ok(!insideBbox(-20, 0, '110,-55,-120,25'));
  for (const box of ['0,0,0', '0,,1,1', '0,2,1,1', '181,0,1,1', '0,-91,1,1', '0,0,NaN,1']) assert.ok(!validBbox(box));
  const query = buildEventsQuery({ ...EMPTY_FILTERS, bbox: '170,-10,-170,10' }, 'robert');
  assert.equal(query.bbox, '170,-10,-170,10');
  assert.notEqual(filtersKey({ ...EMPTY_FILTERS, bbox: '0,0,1,1' }, 'robert'), filtersKey(EMPTY_FILTERS, 'robert'));
});

const pin = (id: string, lat: number, lng: number, kind: GlobePin['kind'] = 'event'): GlobePin => ({
  id, lat, lng, kind, label: id, countryLevel: false, weight: .2,
});
test('zoom clustering retains selected source pins and separates reference layers', () => {
  const rows = [pin('a', 1, 1), pin('b', 2, 2), pin('c', 3, 3), pin('airport', 1, 1, 'airport')];
  const grouped = clusterPins(rows, 2.1, 'a');
  assert.equal(grouped.find(row => row.id === 'a'), rows[0]);
  const cluster = grouped.find(row => row.kind === 'cluster');
  assert.deepEqual(cluster?.members?.map(row => row.id), ['b', 'c']);
  assert.ok(grouped.some(row => row.id === 'airport'));
  assert.deepEqual(clusterPins(rows, .8, null), rows);
  assert.deepEqual(rows.map(row => [row.lat, row.lng]), [[1, 1], [2, 2], [3, 3], [1, 1]]);
});

test('invalid reference coordinates and pin limits cannot escape the bounded renderer', () => {
  const rows = [{ lat: NaN, lon: 0 }, { lat: 91, lon: 0 }, { lat: 0, lon: 181 }, { lat: 0, lon: 0 }];
  assert.deepEqual(spatialReferencePins(rows, 300), [{ lat: 0, lon: 0 }]);
  assert.deepEqual(spatialReferencePins(rows, NaN), []);
  assert.deepEqual(spatialReferencePins(rows, -1), []);
  assert.deepEqual(clusterPins([pin('invalid', NaN, 2), pin('valid', 2, 2)], 2, null).map(row => row.id), ['valid']);
});

test('visible-area query surrounds sampled points with the smallest longitude arc', () => {
  const points = [{ lat: -30, lng: 170 }, { lat: -20, lng: -179 }, { lat: 10, lng: -150 }];
  const bbox = viewportBounds(points)!;
  assert.equal(bbox, '170.000,-30.000,-150.000,10.000');
  for (const point of points) assert.ok(insideBbox(point.lat, point.lng, bbox));
  assert.equal(viewportBounds([]), null);
  assert.equal(viewportBounds([{ lat: NaN, lng: 1 }]), null);
});
