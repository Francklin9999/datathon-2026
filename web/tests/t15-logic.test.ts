/** T15 pure logic: World Explorer queries/pins/ranges, Time Machine dates, Agents & System readings. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Fact, ReplayResult, Run, Step, WorldEventItem, WorldLayer } from '../src/contracts/types';
import { FeatureFlag, ThemeTag } from '../src/contracts/catalog';
import { validateContract } from '../src/contracts/validate';
import { buildUrl } from '../src/api/client';
import {
  EVENT_CATEGORY, EVENT_ORIGIN, EXPOSURE_BASIS, EXPOSURE_IMPACT, FEATURE_FLAG, LINK_TYPE, LOCATION_PRECISION, THEME_TAG,
  WORLD_LAYER,
} from '../src/lib/labels';
import {
  spatialReferencePins, EMPTY_FILTERS, EVENT_CATEGORIES, EVENT_ORIGINS, LAYER_IDS, MAX_RANGE_DAYS, NO_LISTING_COUNTRY, addDays, buildEventsQuery, clampRange,
  daysBetween, defaultRange, exposureFactId, filtersKey, isIsoDate, isResidualExposure, layerState, mergeEventPages,
  rangeIssue, thinPins, visibleEvents,
} from '../src/lib/world';
import { countryLabel, countryName, decodeCountries, iso3FromNumeric, isKnownIso3, type Topology } from '../src/lib/geo';
import {
  asOfIssue, factForValue, replayRefusal, revealBounds, revealRequest, revealSeries, revealableReplay, signedLedgerHash, untilIssue,
} from '../src/lib/replay';
import {
  ARCHITECTURE, REDACTED, ROLE_CARDS, STEP_CONTRACT, formatArgs, guardrailReading, redactArgs, runBudget, runGuardrailAudit,
  stepDeviations, stepProduced, workNature,
} from '../src/lib/system';

const fixtureRun = (): Run => validateContract('Run',
  JSON.parse(readFileSync(new URL('../../contracts/fixtures/run.decision.robert-tsla-25.json', import.meta.url), 'utf8')));
const fixtureEvent = (): WorldEventItem => {
  const page = validateContract('WorldEventsResponse',
    JSON.parse(readFileSync(new URL('../../contracts/fixtures/world.events.sample.json', import.meta.url), 'utf8')));
  const event = page.items[0];
  assert.ok(event);
  return event;
};
function event(id: string, patch: Partial<WorldEventItem> = {}): WorldEventItem {
  return { ...fixtureEvent(), eventId: id, ...patch };
}

// ----- World Explorer -----

test('events query: repeatable params are repeated keys, blanks are omitted', () => {
  const query = buildEventsQuery({
    ...EMPTY_FILTERS, from: '2026-01-01', to: '2026-03-31', categories: ['monetary_policy', 'markets'], origins: ['official', 'gdelt'],
    country: ' can ', ticker: ' tsla ', theme: 'ai', q: '  rate cut ', sort: 'date',
  }, 'robert', 'cursor-2', 50);
  const url = buildUrl('http://api.test/v1', '/world/events', { ...query });
  const params = new URL(url).searchParams;
  assert.deepEqual(params.getAll('category'), ['monetary_policy', 'markets']);
  assert.deepEqual(params.getAll('origin'), ['official', 'gdelt']);
  assert.deepEqual(params.getAll('country'), ['CAN']);
  assert.equal(params.get('ticker'), 'TSLA');
  assert.equal(params.get('q'), 'rate cut');
  assert.equal(params.get('from'), '2026-01-01');
  assert.equal(params.get('to'), '2026-03-31');
  assert.equal(params.get('sort'), 'date');
  assert.equal(params.get('limit'), '50');
  assert.equal(params.get('cursor'), 'cursor-2');
  assert.equal(params.get('profileId'), 'robert');

  const bare = new URL(buildUrl('http://api.test/v1', '/world/events', { ...buildEventsQuery(EMPTY_FILTERS, null) })).searchParams;
  assert.deepEqual([...bare.keys()].sort(), ['limit', 'sort'], 'no from/to: the API applies its documented default interval');
  assert.equal(new URL(buildUrl('http://api.test/v1', '/x', { ...buildEventsQuery({ ...EMPTY_FILTERS, from: '2026-01-01' }, null) })).searchParams.get('from'), null,
    'half an interval is never sent');
});

test('the filter identity ignores cursor and page size, so cursor pages merge only within one filter set', () => {
  const a = { ...EMPTY_FILTERS, q: 'x' };
  assert.equal(filtersKey(a, 'robert'), filtersKey({ ...a }, 'robert'));
  assert.notEqual(filtersKey(a, 'robert'), filtersKey(a, 'amira'));
  assert.notEqual(filtersKey(a, 'robert'), filtersKey({ ...a, sort: 'date' }, 'robert'));
});

test('date ranges: default is the dataset coverage, at most 366 days, never an invented current day', () => {
  assert.ok(isIsoDate('2024-02-29'));
  assert.ok(!isIsoDate('2023-02-29'));
  assert.ok(!isIsoDate('2026-1-5'));
  assert.equal(addDays('2026-01-01', -1), '2025-12-31');
  assert.equal(daysBetween('2026-01-01', '2026-01-31'), 30);

  assert.deepEqual(defaultRange({ start: '2023-07-13', end: '2023-07-13' }), { from: '2023-07-13', to: '2023-07-13' });
  const long = defaultRange({ start: '2021-11-12', end: '2026-11-12' });
  assert.equal(long.to, '2026-11-12');
  assert.equal(daysBetween(long.from, long.to) + 1, MAX_RANGE_DAYS);
  assert.equal(rangeIssue(long, { start: '2021-11-12', end: '2026-11-12' }), null);

  const coverage = { start: '2025-01-01', end: '2026-06-30' };
  assert.equal(rangeIssue({ from: '2026-02-01', to: '2026-01-01' }, coverage), 'order');
  assert.equal(rangeIssue({ from: '2025-01-01', to: '2026-01-02' }, coverage), 'too_long');
  assert.equal(rangeIssue({ from: '2025-01-01', to: '2026-01-01' }, coverage), null, 'exactly 366 dates is accepted');
  assert.equal(rangeIssue({ from: '2027-01-01', to: '2027-02-01' }, coverage), 'outside_coverage');
  assert.equal(rangeIssue({ from: 'x', to: '2026-01-01' }, coverage), 'format');
  assert.equal(rangeIssue({ from: '2030-01-01', to: '2030-02-01' }, null), null, 'no bound check before coverage is known');
});

test('range clamping keeps the end date, respects coverage and reports whether it changed anything', () => {
  const coverage = { start: '2025-01-01', end: '2026-06-30' };
  assert.deepEqual(clampRange({ from: '2026-01-01', to: '2026-02-01' }, coverage), { from: '2026-01-01', to: '2026-02-01', changed: false });
  const tooLong = clampRange({ from: '2024-01-01', to: '2026-06-30' }, coverage);
  assert.equal(tooLong.to, '2026-06-30');
  assert.equal(daysBetween(tooLong.from, tooLong.to) + 1, MAX_RANGE_DAYS);
  assert.ok(tooLong.changed);
  assert.deepEqual(clampRange({ from: '2026-03-01', to: '2026-02-01' }, coverage), { from: '2026-02-01', to: '2026-03-01', changed: true });
  const beyond = clampRange({ from: '2026-06-01', to: '2027-01-01' }, coverage);
  assert.deepEqual([beyond.from, beyond.to], ['2026-06-01', '2026-06-30']);
  const outside = clampRange({ from: '2027-01-01', to: '2027-02-01' }, coverage);
  assert.deepEqual([outside.from, outside.to], ['2026-06-30', '2026-06-30']);
  assert.equal(rangeIssue(outside, coverage), null);
});

test('cursor pages merge without duplicates and keep the first position (stable feed order)', () => {
  const merged = mergeEventPages([event('evt_000000000001'), event('evt_000000000002')], [event('evt_000000000002', { title: 'changed' }), event('evt_000000000003')]);
  assert.deepEqual(merged.map(e => e.eventId), ['evt_000000000001', 'evt_000000000002', 'evt_000000000003']);
  assert.notEqual(merged[1]?.title, 'changed');
});

test('portfolio relevance uses only the API flag; an absent flag is not treated as relevant', () => {
  const items = [event('evt_000000000001', { portfolioRelevant: true }), event('evt_000000000002', { portfolioRelevant: false }), event('evt_000000000003')];
  assert.equal(visibleEvents(items, false).length, 3);
  assert.deepEqual(visibleEvents(items, true).map(e => e.eventId), ['evt_000000000001']);
});

test('pin thinning is capped, deterministic, keeps the selected event and counts what it left out', () => {
  const base = fixtureEvent();
  const events = Array.from({ length: 10 }, (_, i) => event(`evt_00000000000${i}`, { importance: i / 10, occurredAt: '2026-01-01' }));
  const noLocation = event('evt_00000000000a', { location: { ...base.location, lat: Number.NaN } });
  const outOfRange = event('evt_00000000000b', { location: { ...base.location, lon: 200 } });
  const all = [...events, noLocation, outOfRange];

  const thinned = thinPins(all, 3);
  assert.deepEqual(thinned.pins.map(e => e.eventId), ['evt_000000000009', 'evt_000000000008', 'evt_000000000007'], 'highest ranking score first');
  assert.equal(thinned.eligible, 10);
  assert.equal(thinned.unlocated, 2, 'events without usable coordinates stay in the feed only');
  assert.ok(thinned.thinned);
  assert.deepEqual(thinPins([...all].reverse(), 3).pins.map(e => e.eventId), thinned.pins.map(e => e.eventId), 'input order does not change the result');

  const withSelected = thinPins(all, 3, 'evt_000000000001');
  assert.equal(withSelected.pins.length, 3);
  assert.ok(withSelected.pins.some(e => e.eventId === 'evt_000000000001'));
  assert.equal(thinPins(all, 3, 'evt_00000000000a').pins.some(e => e.eventId === 'evt_00000000000a'), false, 'an unlocated event is never given a pin');

  const everything = thinPins(events, 300);
  assert.equal(everything.pins.length, 10);
  assert.equal(everything.thinned, false);
  assert.equal(thinPins(events, 0).pins.length, 0);

  const tie = thinPins([event('evt_00000000000d', { importance: 0.5, occurredAt: '2026-01-01' }), event('evt_00000000000c', { importance: 0.5, occurredAt: '2026-02-01' })], 1);
  assert.equal(tie.pins[0]?.eventId, 'evt_00000000000c', 'ties: most recent first');
});

test('layers: a toggle is enabled only with its flag on and the API reporting the layer available', () => {
  const layer = (layerId: WorldLayer['layerId'], available: boolean): WorldLayer => ({
    layerId, title: { en: layerId, fr: layerId }, tier: 'P1', available, datasetIds: [], legend: [], count: null, coverage: null,
  });
  const layers = [layer('events', true), layer('exposure', true), layer('facilities', true), layer('hazards', false)];
  const flags = (on: string[]) => (flag: string) => on.includes(flag);
  assert.deepEqual(LAYER_IDS, ['events', 'exposure', 'facilities', 'hazards', 'airports']);
  assert.equal(layerState('events', layers, flags([])).enabled, true);
  assert.equal(layerState('facilities', layers, flags([])).reason, 'flag_off');
  assert.equal(layerState('facilities', layers, flags(['world_layer_facilities'])).enabled, true);
  assert.equal(layerState('hazards', layers, flags(['world_layer_hazards'])).reason, 'dataset_missing');
  assert.equal(layerState('hazards', layers, flags([])).reason, 'flag_off', 'the flag is reported before the dataset');
  assert.equal(layerState('exposure', [], flags([])).reason, 'not_listed');
  assert.equal(layerState('events', null, flags([])).enabled, false);
});

test('exposure: non-country codes are a residual row; facts are matched only by country subject', () => {
  assert.ok(isKnownIso3('CAN'));
  assert.equal(isResidualExposure({ countryIso3: 'CAN' }, isKnownIso3), false);
  assert.equal(NO_LISTING_COUNTRY, 'ZZZ');
  for (const code of [NO_LISTING_COUNTRY, 'UNK', 'unknown', '']) assert.equal(isResidualExposure({ countryIso3: code }, isKnownIso3), true, code);
  assert.equal(countryName(NO_LISTING_COUNTRY, 'en'), null, 'the no-listing-country bucket is never given a country name');
  const base = Object.values(fixtureRun().facts)[0];
  assert.ok(base);
  const fact = (id: string, type: Fact['subject']['type'], subjectId: string): Fact => ({ ...base, id, subject: { ...base.subject, type, id: subjectId } });
  const facts = { 'F-001': fact('F-001', 'portfolio', 'robert'), 'F-002': fact('F-002', 'country', 'USA'), 'F-003': fact('F-003', 'asset', 'CAN') };
  assert.equal(exposureFactId(facts, 'USA'), 'F-002');
  assert.equal(exposureFactId(facts, 'CAN'), null, 'an asset that happens to be named CAN is not a country fact');
});

test('geography: ISO codes, localized names and the TopoJSON decoder', () => {
  assert.equal(iso3FromNumeric('124'), 'CAN');
  assert.equal(iso3FromNumeric(4), 'AFG');
  assert.equal(iso3FromNumeric('840'), 'USA');
  assert.equal(iso3FromNumeric(undefined), null);
  assert.equal(iso3FromNumeric('999'), null);
  assert.equal(countryName('CAN', 'en'), 'Canada');
  assert.equal(countryName('DEU', 'fr'), 'Allemagne');
  assert.equal(countryName('UNK', 'en'), null);
  assert.equal(countryLabel('USA', 'fr'), 'États-Unis (USA)');
  assert.equal(countryLabel('ZZZ', 'en'), 'ZZZ', 'unknown codes are shown as returned, never guessed');

  // Two arcs forming one square, quantized with a transform; the second arc is used reversed (~1 = -2).
  const topology: Topology = {
    type: 'Topology',
    transform: { scale: [0.5, 0.5], translate: [-10, 40] },
    arcs: [[[0, 0], [4, 0], [0, 4]], [[0, 0], [0, 4], [4, 0]]],
    objects: {
      countries: {
        type: 'GeometryCollection',
        geometries: [
          { type: 'Polygon', arcs: [[0, -2]], id: '124', properties: { name: 'Canada' } },
          { type: 'MultiPolygon', arcs: [[[0, -2]]], properties: { name: 'No id' } },
          { type: 'Point' },
        ],
      },
    },
  };
  const features = decodeCountries(topology);
  assert.equal(features.length, 2, 'unsupported geometry types are skipped');
  assert.equal(features[0]?.iso3, 'CAN');
  assert.equal(features[1]?.iso3, null);
  assert.deepEqual(features[0]?.geometry.coordinates, [[[-10, 40], [-8, 40], [-8, 42], [-10, 42], [-10, 40]]]);
  assert.deepEqual(features[1]?.geometry.coordinates, [[[[-10, 40], [-8, 40], [-8, 42], [-10, 42], [-10, 40]]]]);
  assert.throws(() => decodeCountries({ type: 'Topology', arcs: [], objects: {} }));

  const atlas = JSON.parse(readFileSync(new URL('../public/geo/countries-110m.json', import.meta.url), 'utf8')) as Topology;
  const countries = decodeCountries(atlas);
  assert.equal(countries.length, 177);
  assert.ok(countries.some(country => country.iso3 === 'CAN'));
  assert.deepEqual(countries.filter(country => country.iso3 === null).map(country => country.name).sort(), ['Kosovo', 'N. Cyprus', 'Somaliland']);
  for (const country of countries) {
    const rings = country.geometry.type === 'Polygon' ? country.geometry.coordinates : country.geometry.coordinates.flat();
    for (const ring of rings) {
      assert.ok(ring.length >= 4);
      assert.deepEqual(ring[0], ring[ring.length - 1], `${country.name}: rings are closed`);
      for (const [lon, lat] of ring) assert.ok(Math.abs(lon) <= 180.0001 && Math.abs(lat) <= 90.0001, country.name);
    }
  }
});

test('every World and System code shown has an English and a French label', () => {
  const tables: [Record<string, { en: string; fr: string }>, readonly string[]][] = [
    [EVENT_CATEGORY, EVENT_CATEGORIES], [EVENT_ORIGIN, EVENT_ORIGINS], [WORLD_LAYER, LAYER_IDS],
    [THEME_TAG, Object.values(ThemeTag)], [FEATURE_FLAG, Object.values(FeatureFlag)],
    [LINK_TYPE, ['named_in_source', 'listing_country', 'sector', 'theme', 'documented_exposure', 'etf_lookthrough']],
    [EXPOSURE_IMPACT, ['not_established', 'measured_price_move']], [EXPOSURE_BASIS, ['listing_country', 'etf_lookthrough', 'mixed']],
    [LOCATION_PRECISION, ['point', 'city', 'country']],
  ];
  for (const [table, codes] of tables) {
    for (const code of codes) assert.ok(table[code]?.en.trim() && table[code]?.fr.trim(), `missing label for ${code}`);
  }
  assert.match(EXPOSURE_IMPACT.not_established.en, /not established/i);
  assert.match(LOCATION_PRECISION.country.en, /country-level/i);
});

// ----- Time Machine -----

const replayOf = (patch: Partial<ReplayResult> = {}): Pick<ReplayResult, 'asOf' | 'revealAvailableUntil'> => ({
  asOf: '2024-03-28', revealAvailableUntil: '2026-11-12', ...patch,
});

test('as-of dates are accepted only inside the range the presets endpoint reports', () => {
  const presets = { earliestAsOf: '2022-11-14', latestAsOf: '2026-08-18' };
  assert.equal(asOfIssue('', presets), 'missing');
  assert.equal(asOfIssue('2024-13-01', presets), 'format');
  assert.equal(asOfIssue('2022-11-13', presets), 'before_earliest');
  assert.equal(asOfIssue('2022-11-14', presets), null);
  assert.equal(asOfIssue('2026-08-18', presets), null);
  assert.equal(asOfIssue('2026-08-19', presets), 'after_latest');
});

test('reveal: only a succeeded replay is revealable; until must be after the cutoff and inside the snapshot', () => {
  const run = fixtureRun();
  assert.equal(revealableReplay(run), null, 'a decision run is never revealable');
  assert.equal(revealableReplay(null), null);
  const decision = run.result?.kind === 'decision' ? run.result.decision : null;
  assert.ok(decision);
  const replay: ReplayResult = { asOf: '2024-03-28', decision, gate: { datasets: [] }, notices: ['LIM_LLM_KNOWLEDGE'], revealAvailableUntil: '2026-11-12' };
  const replayRun = { kind: 'replay' as const, status: 'succeeded' as const, result: { kind: 'replay' as const, replay } };
  assert.equal(revealableReplay(replayRun), replay);
  assert.equal(revealableReplay({ ...replayRun, status: 'running' }), null);
  assert.equal(revealableReplay({ ...replayRun, status: 'failed', result: null }), null);
  assert.equal(revealableReplay({ ...replayRun, result: run.result }), null, 'kind and result must both be a replay');

  assert.deepEqual(revealBounds(replayOf()), { min: '2024-03-29', max: '2026-11-12' });
  assert.equal(revealBounds(replayOf({ revealAvailableUntil: '2024-03-28' })), null);
  assert.equal(untilIssue('', replayOf()), null, 'empty = the API default (last date in the snapshot)');
  assert.equal(untilIssue('2024-03-28', replayOf()), 'not_after_cutoff');
  assert.equal(untilIssue('2024-01-01', replayOf()), 'not_after_cutoff');
  assert.equal(untilIssue('2024-03-29', replayOf()), null);
  assert.equal(untilIssue('2026-11-12', replayOf()), null);
  assert.equal(untilIssue('2026-11-13', replayOf()), 'after_snapshot');
  assert.equal(untilIssue('soon', replayOf()), 'format');
  assert.equal(untilIssue('2025-01-01', replayOf({ revealAvailableUntil: '2024-03-28' })), 'no_later_data');
  assert.deepEqual(revealRequest(''), {});
  assert.deepEqual(revealRequest('2025-01-01'), { until: '2025-01-01' });
  assert.doesNotThrow(() => validateContract('RevealRequest', revealRequest('2025-01-01')));

  assert.equal(signedLedgerHash(run), decision.brief.audit.ledgerHash);
  assert.equal(signedLedgerHash({ result: { kind: 'replay', replay } }), decision.brief.audit.ledgerHash);
  assert.equal(signedLedgerHash({ result: null }), null);
});

test('a refused replay shows only well-formed details: supported range and assets unknown at the date', () => {
  assert.equal(replayRefusal(null), null);
  assert.equal(replayRefusal({ fields: [] }), null);
  assert.deepEqual(replayRefusal({ earliestAsOf: '2022-11-14', latestAsOf: '2026-08-18' }), { earliestAsOf: '2022-11-14', latestAsOf: '2026-08-18', unknownAtAsOf: [] });
  assert.deepEqual(replayRefusal({ unknownAtAsOf: ['BTC-USD', 'XIU.TO', 42, '<b>x</b>', ''] }), { earliestAsOf: null, latestAsOf: null, unknownAtAsOf: ['BTC-USD', 'XIU.TO'] });
  assert.equal(replayRefusal({ earliestAsOf: 'soon', unknownAtAsOf: 'TSLA' }), null);
});

test('reveal figures link only to a reveal fact carrying the same value; series are passed through unchanged', () => {
  const base = Object.values(fixtureRun().facts)[0];
  assert.ok(base);
  const facts = { 'F-001': { ...base, id: 'F-001', value: -12.4 }, 'F-002': { ...base, id: 'F-002', value: 18.9 }, 'F-003': { ...base, id: 'F-003', value: 'text' } };
  assert.equal(factForValue(facts, ['F-001', 'F-002'], 18.9), 'F-002');
  assert.equal(factForValue(facts, ['F-001', 'F-002', 'F-003'], 5), null, 'no match: the figure stays plain text');
  assert.equal(factForValue(facts, ['F-009'], 18.9), null, 'IDs absent from the reveal ledger never resolve');
  const same = { 'F-001': { ...base, id: 'F-001', value: 0 }, 'F-002': { ...base, id: 'F-002', value: 0 } };
  assert.equal(factForValue(same, ['F-001', 'F-002'], 0, 'F-001'), 'F-002', 'two equal figures get two different facts');

  const series = revealSeries({
    outcomes: [
      { scenarioId: 'sc_requested', label: { en: 'Requested', fr: 'Demandé' }, returnPct: -12.4, maxDrawdownPct: 18.9, series: [{ date: '2024-03-28', value: 100 }, { date: '2024-06-28', value: 87.6 }], factIds: [] },
      { scenarioId: 'sc_baseline', label: { en: 'No move', fr: 'Sans mouvement' }, returnPct: 3, maxDrawdownPct: 4, series: [{ date: '2024-03-28', value: 100 }], factIds: [] },
    ],
  }, text => text.fr);
  assert.deepEqual(series.map(s => s.label), ['Demandé', 'Sans mouvement']);
  assert.deepEqual(series[0]?.points, [{ date: '2024-03-28', value: 100 }, { date: '2024-06-28', value: 87.6 }]);
  assert.notEqual(series[0]?.color, series[1]?.color);
  assert.notEqual(series[0]?.dashed, series[1]?.dashed, 'series differ by dash as well as colour');
});

// ----- Agents & System -----

test('role map: six roles, model work versus deterministic code, tools as in contracts/tools.md §6', () => {
  assert.deepEqual(ROLE_CARDS.map(card => card.role), ['planner', 'researcher', 'quant', 'risk_officer', 'writer', 'auditor']);
  const nature = Object.fromEntries(ROLE_CARDS.map(card => [card.role, card.nature]));
  assert.deepEqual(nature, { planner: 'model', researcher: 'model', quant: 'code', risk_officer: 'code', writer: 'model', auditor: 'mixed' });
  const tools = Object.fromEntries(ROLE_CARDS.map(card => [card.role, card.tools]));
  assert.deepEqual(tools.writer, []);
  assert.deepEqual(tools.auditor, []);
  assert.ok(tools.planner?.every(tool => !tool.startsWith('quant.') && !tool.startsWith('rules.') && !tool.startsWith('edgar.')), 'the planner only has lookups');
  assert.ok(tools.researcher?.includes('research.save_evidence') && !tools.researcher.some(tool => tool.startsWith('quant.') || tool.startsWith('rules.')));
  assert.ok(tools.quant?.every(tool => tool.startsWith('quant.')));
  assert.ok(tools.risk_officer?.every(tool => tool.startsWith('rules.') || tool.startsWith('optimizer.')));
  for (const card of ROLE_CARDS) {
    assert.ok(card.purpose.en.trim() && card.purpose.fr.trim() && card.toolsNote.en.trim() && card.toolsNote.fr.trim());
    for (const step of card.steps) assert.equal(STEP_CONTRACT[step].agent, card.role, `${step} belongs to ${card.role}`);
  }
  const covered = ROLE_CARDS.flatMap(card => card.steps).sort();
  assert.deepEqual(covered, Object.keys(STEP_CONTRACT).sort(), 'every step type belongs to exactly one role card');
  const ids = new Set(ARCHITECTURE.map(node => node.id));
  for (const node of ARCHITECTURE) for (const edge of node.sendsTo) assert.ok(ids.has(edge.to), `${node.id} → ${edge.to}`);
});

test('step ↔ role/actor mapping follows run-events.md §2 and flags recorded deviations without rewriting them', () => {
  assert.equal(workNature('llm'), 'model');
  assert.equal(workNature('llm+tools'), 'model');
  assert.equal(workNature('code'), 'code');
  assert.equal(workNature('code+llm'), 'mixed');
  for (const step of fixtureRun().steps) assert.deepEqual(stepDeviations(step), [], `fixture step ${step.type}`);
  assert.deepEqual(stepDeviations({ type: 'quant', agent: 'quant', actor: 'llm' }), [{ field: 'actor', recorded: 'llm', contract: 'code' }]);
  assert.deepEqual(stepDeviations({ type: 'write', agent: 'planner', actor: 'llm' }), [{ field: 'agent', recorded: 'planner', contract: 'writer' }]);
  assert.equal(stepDeviations({ type: 'audit', agent: 'auditor', actor: 'code' }).length, 1);
});

test('tool-call arguments are redacted defensively and the session capability never survives', () => {
  const session = 's_00000000-0000-4000-8000-000000000001';
  const redacted = redactArgs({
    ticker: 'TSLA', window: { code: 'full' }, sessionId: session, headers: { Authorization: 'Bearer abc.def', accept: 'json' },
    note: `called for ${session}`, list: ['ok', 'AKIAABCDEFGHIJKLMNOP'], api_key: 'x', n: 3, flag: true, nothing: null,
    long: 'a'.repeat(400),
  }) as Record<string, unknown>;
  assert.equal(redacted.ticker, 'TSLA');
  assert.deepEqual(redacted.window, { code: 'full' });
  assert.equal(redacted.sessionId, REDACTED);
  assert.deepEqual(redacted.headers, { Authorization: REDACTED, accept: 'json' });
  assert.equal(redacted.note, REDACTED);
  assert.deepEqual(redacted.list, ['ok', REDACTED]);
  assert.equal(redacted.api_key, REDACTED);
  assert.equal(redacted.n, 3);
  assert.equal(redacted.flag, true);
  assert.equal(redacted.nothing, null);
  assert.equal(String(redacted.long).length, 301);
  const text = formatArgs({ sessionId: session, q: 'rates' });
  assert.ok(!text.includes(session) && text.includes('rates'));
});

test('run readings come from the payload: produced IDs, budget totals, guardrail configured versus applied', () => {
  const run = fixtureRun();
  const base = run.steps[0];
  assert.ok(base);
  const call = (id: string, ok: boolean, factIds: string[], evidenceIds: string[]) => ({
    id, tool: 'quant.asset_metrics', args: {}, startedAt: base.startedAt, durationMs: 5, ok, resultSummary: 'x', datasetsRead: [], factIds, evidenceIds, error: ok ? null : 'boom',
  });
  const step: Step = { ...base, factIds: ['F-001'], evidenceIds: [], toolCalls: [call('T-001', true, ['F-001', 'F-002'], ['E-001']), call('T-002', false, [], [])] };
  assert.deepEqual(stepProduced(step), { factIds: ['F-001', 'F-002'], evidenceIds: ['E-001'] });

  const budget = runBudget(run);
  assert.equal(budget.llmCalls, run.usage.llmCalls);
  assert.equal(budget.durationMs, run.usage.durationMs);
  assert.equal(budget.stepsRecorded, run.steps.length);
  assert.equal(budget.reviseLoops, 0, 'an absent revise step is absent, not counted');
  const withFailure = runBudget({ usage: run.usage, steps: [{ ...step, type: 'research' }, { ...step, seq: 2, type: 'revise', toolCalls: [] }] });
  assert.equal(withFailure.failedToolCalls, 1);
  assert.equal(withFailure.researchToolCalls, 2);
  assert.equal(withFailure.reviseLoops, 1);

  const audit = runGuardrailAudit(run);
  assert.ok(audit);
  assert.equal(runGuardrailAudit({ result: null }), null);
  assert.equal(guardrailReading(true, null), 'no_brief');
  assert.equal(guardrailReading(false, { applied: false, action: 'none', id: null }), 'not_configured');
  assert.equal(guardrailReading(true, { applied: false, action: 'none', id: null }), 'configured_not_applied');
  assert.equal(guardrailReading(true, { applied: true, action: 'masked', id: 'gr-1' }), 'applied');
  assert.equal(guardrailReading(false, { applied: true, action: 'blocked', id: 'gr-1' }), 'applied_flag_off');
});


test('event investigation link retains selected source and safely encodes context', async () => {
  const { decisionInvestigationUrl } = await import('../src/lib/world');
  const url = new URL(decisionInvestigationUrl('evt_123', 'robert', 'BRK.B', 'run_123'), 'https://example.test');
  assert.equal(url.searchParams.get('eventId'), 'evt_123');
  assert.equal(url.searchParams.get('profileId'), 'robert');
  assert.equal(url.searchParams.get('ticker'), 'BRK.B');
  assert.equal(url.searchParams.get('sourceRunId'), 'run_123');
});


test('persisted event context validates IDs and rejects arbitrary references', async () => {
  const { validInvestigationContext, investigationOriginalText, readInvestigationContext } = await import('../src/lib/world');
  const context = validInvestigationContext('evt_abcdef123456', 'BRK.B', 'run_01M7ERBNQM5DVKQ01XX4DKRJ4D');
  assert.ok(context);
  assert.deepEqual(readInvestigationContext(investigationOriginalText('My request', context)), context);
  assert.equal(validInvestigationContext('https://example.com', 'BRK.B', null), null);
  assert.equal(validInvestigationContext('evt_abcdef123456', 'BRK.B', 'bad'), null);
});


test('site manifest identity rejects invalid or absent release information', async () => {
  const { siteBuildIdentity } = await import('../src/lib/system');
  assert.deepEqual(siteBuildIdentity({ revision: 'a'.repeat(40), built_at: '2026-11-15T05:45:39Z' }), { revision: 'a'.repeat(40), builtAt: '2026-11-15T05:45:39Z' });
  assert.equal(siteBuildIdentity({ revision: 'dev', built_at: '2026-11-15' }), null);
  assert.equal(siteBuildIdentity(null), null);
});


test('reference pin cap preserves sparse regions before adding dense local points', () => {
  const dense = Array.from({ length: 50 }, (_, id) => ({ id, lat: 42, lon: -73 }));
  const distant = { id: 99, lat: -35, lon: 150 };
  const rows = [...dense, distant];
  const pins = spatialReferencePins(rows, 3);
  assert.equal(pins.length, 3);
  assert.ok(pins.includes(distant));
  assert.equal(new Set(pins.map(p => p.id)).size, 3);
  assert.equal(rows.length, 51);
  assert.deepEqual(spatialReferencePins(rows, 0), []);
});

test('globe: degenerate outlines are dropped before hexagons, centroids land inside the country', async () => {
  const { readFileSync } = await import('node:fs');
  const { decodeCountries, hexReadyCountries, countryCentroid } = await import('../src/lib/geo');
  const countries = decodeCountries(JSON.parse(readFileSync('public/geo/countries-110m.json', 'utf8')));
  const ready = hexReadyCountries(countries);
  assert.ok(ready.length >= countries.length - 2, 'only degenerate outlines go');
  for (const feature of ready) {
    const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
    for (const polygon of polygons) {
      const lons = (polygon[0] ?? []).map(p => p[0] ?? 0);
      assert.ok(Math.max(...lons) - Math.min(...lons) > 0, `${feature.iso3 ?? feature.name} has a zero-width ring`);
    }
  }
  const at = (iso3: string) => countryCentroid(countries.find(c => c.iso3 === iso3)!)!;
  const can = at('CAN'); assert.ok(can.lat > 45 && can.lat < 70 && can.lng > -120 && can.lng < -80, JSON.stringify(can));
  const usa = at('USA'); assert.ok(usa.lat > 30 && usa.lat < 45 && usa.lng > -110 && usa.lng < -85, JSON.stringify(usa));
  const fji = at('FJI'); assert.ok(Math.abs(fji.lat + 17.5) < 3 && Math.abs(Math.abs(fji.lng) - 179) < 3, JSON.stringify(fji));
});

test('globe: events sharing a spot are fanned out, each apart, the rest untouched', async () => {
  const { spreadStacked } = await import('../src/features/world/globeStyle');
  const event = (id: string, weight: number, lat = 56.1, lng = -106.3) =>
    ({ id, kind: 'event' as const, lat, lng, label: id, countryLevel: true, weight });
  const stacked = Array.from({ length: 12 }, (_, i) => event(`ca${i}`, i / 12));
  const lone = event('lone', 0.5, 48.85, 2.35);
  const quake = { id: 'hazard:1', kind: 'hazard' as const, lat: 56.1, lng: -106.3, label: 'q', countryLevel: false, weight: 0.2 };
  const out = spreadStacked([...stacked, lone, quake]);
  assert.equal(out.length, 14);
  assert.deepEqual(out.map(p => p.id), [...stacked.map(p => p.id), 'lone', 'hazard:1']);
  assert.deepEqual(out[12], lone);
  assert.deepEqual(out[13], quake);
  const spread = out.slice(0, 12);
  for (let i = 0; i < spread.length; i++) {
    for (let j = i + 1; j < spread.length; j++) {
      const a = spread[i]!, b = spread[j]!;
      const dLng = (a.lng - b.lng) * Math.cos((56.1 * Math.PI) / 180);
      assert.ok(Math.hypot(a.lat - b.lat, dLng) > 2 * 0.2 + 0.05, `${a.id} and ${b.id} overlap`);
    }
    assert.ok(Math.abs(spread[i]!.lat - 56.1) < 6 && Math.abs(spread[i]!.lng + 106.3) < 12);
  }
  // The most important event stays nearest the shared spot.
  const dist = (p: { lat: number; lng: number }) => Math.hypot(p.lat - 56.1, (p.lng + 106.3) * Math.cos((56.1 * Math.PI) / 180));
  const heaviest = spread.find(p => p.id === 'ca11')!;
  assert.ok(spread.every(p => dist(heaviest) <= dist(p)));
  // Across the antimeridian longitudes stay within [-180, 180).
  for (const p of spreadStacked([event('f1', 1, -17.7, 179.9), event('f2', 0.5, -17.7, 179.9)])) assert.ok(p.lng >= -180 && p.lng < 180);
});

test('globe: a country label moves off the event spikes and off other labels', async () => {
  const { labelOffset } = await import('../src/features/world/globeStyle');
  const size = { w: 100, h: 24 };
  const anchor = { x: 200, y: 200 };
  // Nothing around: the label sits above its anchor.
  assert.deepEqual(labelOffset(anchor, size, [], []), { dx: 0, dy: -20 });
  // A spike rising through the spot above: the label goes below.
  const spike = { ax: 205, ay: 195, bx: 210, by: 160, pad: 4 };
  assert.deepEqual(labelOffset(anchor, size, [spike], []), { dx: 0, dy: 20 });
  // Spikes above and below: beside.
  const below = { ax: 200, ay: 215, bx: 200, by: 240, pad: 4 };
  const moved = labelOffset(anchor, size, [spike, below], []);
  assert.equal(moved.dy, 0);
  assert.equal(Math.abs(moved.dx), 58);
  // A label already above: this one goes elsewhere.
  const second = labelOffset(anchor, size, [], [{ x: 200, y: 180, w: 100, h: 24 }]);
  assert.notDeepEqual(second, { dx: 0, dy: -20 });
});

test('globe: islands smaller than a hexagon get one, larger land none', async () => {
  const { islandHexes } = await import('../src/lib/geoHex');
  const { polygonToCells } = await import('h3-js');
  const square = (lng: number, lat: number, d: number): [number, number][][] =>
    [[[lng, lat], [lng + d, lat], [lng + d, lat + d], [lng, lat + d], [lng, lat]]];
  const islands = { iso3: 'USA', name: 'Islands', geometry: { type: 'MultiPolygon' as const, coordinates: [square(-176.7, 51.8, 0.15), square(-100, 40, 8)] } };
  const out = islandHexes([islands], 3);
  assert.equal(out.length, 1);
  assert.equal(out[0]!.iso3, 'USA');
  assert.equal(out[0]!.geometry.type, 'MultiPolygon');
  const hexagons = out[0]!.geometry.coordinates as [number, number][][][];
  assert.equal(hexagons.length, 1);
  // The added hexagon is itself exactly one cell for the hexagon layer, and contains the island.
  assert.equal(polygonToCells(hexagons[0]!, 3, true).length, 1);
  const big = { iso3: 'CAN', name: 'Land', geometry: { type: 'Polygon' as const, coordinates: square(-110, 50, 10) } };
  assert.deepEqual(islandHexes([big], 3), []);
});
