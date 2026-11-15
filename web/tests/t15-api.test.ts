/** T15 API client methods: World Explorer, Time Machine presets and reveal (contracts/api.md §5.8, §6, §7). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Fact, Run, WorldEvent } from '../src/contracts/types';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';
import { createFixtureFetch } from '../src/api/fixtures';

const SESSION = 's_00000000-0000-4000-8000-000000000001';

interface Captured { url: string; init: RequestInit | undefined }

function fakeFetch(status: number, body: unknown, captured: Captured[]): typeof fetch {
  return async (input, init) => {
    captured.push({ url: String(input), init });
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'req_test' } });
  };
}
const header = (init: RequestInit | undefined, name: string) => (init?.headers as Record<string, string> | undefined)?.[name];
const clientFor = (status: number, body: unknown, captured: Captured[] = []) =>
  createApiClient({ baseUrl: 'http://api.test/v1', getSessionId: () => SESSION, fetchImpl: fakeFetch(status, body, captured) });

const read = (name: string) => JSON.parse(readFileSync(new URL(`../../contracts/fixtures/${name}`, import.meta.url), 'utf8'));
const eventsPage = read('world.events.sample.json') as { items: WorldEvent[]; dataVersion: string };
const event = eventsPage.items[0] as WorldEvent;
const run = read('run.decision.robert-tsla-25.json') as Run;
const fact = Object.values(run.facts)[0] as Fact;
const text = (en: string) => ({ en, fr: en });

async function invalid(promise: Promise<unknown>): Promise<void> {
  const error = await promise.catch((e: unknown) => e);
  assert.ok(error instanceof ApiRequestError, 'expected an ApiRequestError');
  assert.equal(error.code, 'invalid_response');
}

test('worldLayers validates WorldLayersResponse', async () => {
  const captured: Captured[] = [];
  const body = { items: [{ layerId: 'events', title: text('Events'), tier: 'P1', available: true, datasetIds: ['world_events'], legend: [{ label: text('Event'), color: '#E3A53B' }], count: 1, coverage: { start: '2023-07-13', end: '2023-07-13' } },
    { layerId: 'hazards', title: text('Hazards'), tier: 'P2', available: false, datasetIds: ['natural_hazards'], legend: [], count: null, coverage: null }] };
  const layers = await clientFor(200, body, captured).worldLayers();
  assert.equal(layers.items[1]?.available, false);
  assert.equal(captured[0]?.url, 'http://api.test/v1/world/layers');
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), SESSION);
  assert.equal(header(captured[0]?.init, 'Content-Type'), undefined);
  await invalid(clientFor(200, { items: [{ layerId: 'tiles' }] }).worldLayers());
});

test('worldEvents sends repeatable filters as repeated keys and validates the page', async () => {
  const captured: Captured[] = [];
  const page = await clientFor(200, eventsPage, captured).worldEvents({
    from: '2023-07-01', to: '2023-07-31', category: ['monetary_policy', 'macro_release'], country: ['CAN', 'USA'], origin: ['curated'],
    q: 'target rate', ticker: 'RY.TO', theme: 'banks', profileId: 'robert', sort: 'date', limit: 100, cursor: 'c2',
  });
  assert.equal(page.items[0]?.eventId, event.eventId);
  const url = new URL(captured[0]?.url ?? '');
  assert.equal(url.pathname, '/v1/world/events');
  assert.deepEqual(url.searchParams.getAll('category'), ['monetary_policy', 'macro_release']);
  assert.deepEqual(url.searchParams.getAll('country'), ['CAN', 'USA']);
  assert.deepEqual(url.searchParams.getAll('origin'), ['curated']);
  assert.equal(url.searchParams.get('q'), 'target rate');
  assert.equal(url.searchParams.get('profileId'), 'robert');
  assert.equal(url.searchParams.get('cursor'), 'c2');
  assert.equal(url.searchParams.get('limit'), '100');

  const bare: Captured[] = [];
  await clientFor(200, eventsPage, bare).worldEvents({ category: [], q: '' });
  assert.equal(bare[0]?.url, 'http://api.test/v1/world/events', 'empty filters add no query string');
  await invalid(clientFor(200, { ...eventsPage, total: 'many' }).worldEvents({}));
  await invalid(clientFor(200, { ...eventsPage, items: [{ ...event, sources: [] }] }).worldEvents({}));
});

test('worldEvent, worldExposure and worldCountry validate their responses and encode path parameters', async () => {
  const captured: Captured[] = [];
  const exposure = { ticker: 'RY.TO', weightPct: 6, linkType: 'listing_country', evidenceIds: [], impact: 'not_established', impactFactId: null, note: text('Listed in Canada') };
  const detail = await clientFor(200, { event, related: [event], exposures: [exposure] }, captured).worldEvent(event.eventId, 'robert');
  assert.equal(detail.exposures[0]?.impact, 'not_established');
  assert.equal(captured[0]?.url, `http://api.test/v1/world/events/${event.eventId}?profileId=robert`);
  await clientFor(200, { event, related: [], exposures: [] }, captured).worldEvent(event.eventId);
  assert.equal(captured[1]?.url, `http://api.test/v1/world/events/${event.eventId}`);
  await invalid(clientFor(200, { event, related: [], exposures: [{ ...exposure, impact: 'estimated_loss' }] }).worldEvent(event.eventId), );

  const row = { countryIso3: 'CAN', weightPct: 62.5, basis: 'listing_country', holdings: [{ ticker: 'RY.TO', weightPct: 6 }] };
  const unknown = { countryIso3: 'UNK', weightPct: 7.5, basis: 'mixed', holdings: [] };
  const exposureBody = { items: [row, unknown], basisNote: text('By listing country'), limitations: ['LIM_ETF_NO_LOOKTHROUGH'], facts: { [fact.id]: fact } };
  const byCountry = await clientFor(200, exposureBody, captured).worldExposure('robert');
  assert.deepEqual(byCountry.items.map(item => item.countryIso3), ['CAN', 'UNK'], 'the unknown bucket arrives as returned');
  assert.equal(captured[2]?.url, 'http://api.test/v1/world/exposure?profileId=robert');
  await invalid(clientFor(200, { ...exposureBody, items: [{ ...row, basis: 'guess' }] }).worldExposure('robert'));

  const countryBody = { countryIso3: 'CAN', name: { en: 'Canada', fr: 'Canada' }, exposure: row, events: [event], macro: [fact] };
  const country = await clientFor(200, countryBody, captured).worldCountry('CAN', { profileId: 'robert', from: '2023-07-01', to: '2023-07-31' });
  assert.equal(country.exposure?.weightPct, 62.5);
  assert.equal(captured[3]?.url, 'http://api.test/v1/world/countries/CAN?profileId=robert&from=2023-07-01&to=2023-07-31');
  const none = await clientFor(200, { ...countryBody, exposure: null, macro: [] }, captured).worldCountry('a/b');
  assert.equal(none.exposure, null);
  assert.equal(captured[4]?.url, 'http://api.test/v1/world/countries/a%2Fb');
});

test('worldFacilities and worldHazards validate their responses', async () => {
  const captured: Captured[] = [];
  const facility = {
    facilityId: 'G10001', name: 'Plant', operator: 'Operator Inc.', ticker: null, matchConfidence: 'none', lat: 53.5, lon: -113.5, countryIso3: 'CAN',
    reportingYear: 2023, emissionsTco2e: 1234567, registry: 'eccc_ghgrp', sourceUrl: 'https://example.org/registry', dataVersion: eventsPage.dataVersion,
  };
  const facilities = await clientFor(200, { items: [facility], total: 1, reportingYear: 2023, limitations: ['LIM_REGISTRY_MATCH'] }, captured)
    .worldFacilities({ country: ['CAN'], ticker: 'CNQ.TO', minEmissions: 50000, limit: 500 });
  assert.equal(facilities.items[0]?.matchConfidence, 'none');
  assert.equal(captured[0]?.url, 'http://api.test/v1/world/facilities?country=CAN&ticker=CNQ.TO&minEmissions=50000&limit=500');
  await invalid(clientFor(200, { items: [{ ...facility, matchConfidence: 'certain' }], total: 1, reportingYear: 2023, limitations: [] }).worldFacilities());

  const hazard = { hazardId: 'us7000abcd', type: 'earthquake', occurredAt: '2026-10-01T12:00:00Z', lat: 35, lon: 139, magnitude: null, title: 'M 5.1 - offshore', origin: 'usgs', sourceUrl: 'https://example.org/quake' };
  const hazards = await clientFor(200, { items: [hazard], total: 1 }, captured).worldHazards({ from: '2026-10-01', to: '2026-10-31', type: 'earthquake', limit: 200 });
  assert.equal(hazards.items[0]?.magnitude, null);
  assert.equal(captured[1]?.url, 'http://api.test/v1/world/hazards?from=2026-10-01&to=2026-10-31&type=earthquake&limit=200');
  await invalid(clientFor(200, { items: [{ ...hazard, type: 'flood' }], total: 1 }).worldHazards());
});

test('replayPresets validates ReplayPresetsResponse', async () => {
  const captured: Captured[] = [];
  const body = { earliestAsOf: '2022-11-14', latestAsOf: '2026-08-18', presets: [{ asOf: '2024-03-28', label: text('Before a drawdown'), why: text('Computed from the data') }], notices: ['LIM_LLM_KNOWLEDGE', 'LIM_SAMPLE_WINDOW'] };
  const presets = await clientFor(200, body, captured).replayPresets();
  assert.equal(presets.presets[0]?.asOf, '2024-03-28');
  assert.equal(captured[0]?.url, 'http://api.test/v1/replay/presets');
  assert.equal(header(captured[0]?.init, 'X-Aplomb-Session'), SESSION);
  await invalid(clientFor(200, { ...body, notices: ['LIM_INVENTED'] }).replayPresets());
  await invalid(clientFor(200, { ...body, earliestAsOf: 'early' }).replayPresets());
});

test('reveal posts RevealRequest to /runs/{id}/reveal and validates RevealResult', async () => {
  const captured: Captured[] = [];
  const body = {
    asOf: '2024-03-28', until: '2025-03-28',
    outcomes: [{ scenarioId: 'sc_requested', label: text('Requested'), returnPct: -12.4, maxDrawdownPct: 18.9, series: [{ date: '2024-03-28', value: 100 }, { date: '2025-03-28', value: 87.6 }], factIds: [fact.id] }],
    facts: { [fact.id]: fact }, statement: text('Observed hypothetical outcomes; not evidence of a prediction.'),
  };
  const client = clientFor(200, body, captured);
  const reveal = await client.reveal('run_01JCQ000000000000000000001', { until: '2025-03-28' });
  assert.equal(reveal.outcomes[0]?.series[0]?.value, 100);
  assert.equal(captured[0]?.url, 'http://api.test/v1/runs/run_01JCQ000000000000000000001/reveal');
  assert.equal(captured[0]?.init?.method, 'POST');
  assert.equal(header(captured[0]?.init, 'Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(String(captured[0]?.init?.body)), { until: '2025-03-28' });
  await client.reveal('run_01JCQ000000000000000000001');
  assert.deepEqual(JSON.parse(String(captured[1]?.init?.body)), {}, 'no until: the API uses the last date in the snapshot');
  await invalid(clientFor(200, { ...body, outcomes: [{ ...body.outcomes[0], maxDrawdownPct: -1 }] }).reveal('run_x'));

  const conflict = await clientFor(409, { error: { code: 'conflict', message: 'run is not a succeeded replay', requestId: 'req_7' } }).reveal('run_x').catch((e: unknown) => e);
  assert.ok(conflict instanceof ApiRequestError);
  assert.equal(conflict.code, 'conflict');
  assert.equal(conflict.requestId, 'req_7');
});

test('feature-disabled and provider-unavailable answers stay typed errors for the pages', async () => {
  const disabled = await clientFor(501, { error: { code: 'feature_disabled', message: 'world_explorer is off', requestId: 'req_1' } }).worldLayers().catch((e: unknown) => e);
  assert.ok(disabled instanceof ApiRequestError);
  assert.equal(disabled.code, 'feature_disabled');
  const unavailable = await clientFor(503, { error: { code: 'upstream_unavailable', message: 'event-brief provider is not configured', requestId: 'req_2' } })
    .createRun({ kind: 'event_brief', profileId: 'robert', lang: 'en', eventId: event.eventId }).catch((e: unknown) => e);
  assert.ok(unavailable instanceof ApiRequestError);
  assert.equal(unavailable.code, 'upstream_unavailable');
  assert.equal(unavailable.status, 503);
});

test('fixture mode invents no world or replay data: every T15 endpoint answers 503 upstream_unavailable', async () => {
  const client = createApiClient({ baseUrl: 'http://fixture.local/v1', getSessionId: () => SESSION, fetchImpl: createFixtureFetch() });
  const calls: [string, () => Promise<unknown>][] = [
    ['worldLayers', () => client.worldLayers()],
    ['worldEvents', () => client.worldEvents({ profileId: 'robert' })],
    ['worldEvent', () => client.worldEvent(event.eventId, 'robert')],
    ['worldExposure', () => client.worldExposure('robert')],
    ['worldCountry', () => client.worldCountry('CAN', { profileId: 'robert' })],
    ['worldFacilities', () => client.worldFacilities()],
    ['worldHazards', () => client.worldHazards()],
    ['replayPresets', () => client.replayPresets()],
    ['reveal', () => client.reveal('run_01JCQ000000000000000000001')],
    ['createRun replay', () => client.createRun({
      kind: 'replay', profileId: 'robert', lang: 'en', asOf: '2024-03-28',
      request: { type: 'move', move: { ticker: 'TSLA', sizePct: 25, funding: { mode: 'pro_rata' } } },
    })],
    ['createRun event_brief', () => client.createRun({ kind: 'event_brief', profileId: 'robert', lang: 'en', eventId: event.eventId })],
  ];
  for (const [name, call] of calls) {
    const error = await call().catch((e: unknown) => e);
    assert.ok(error instanceof ApiRequestError, name);
    assert.equal(error.code, 'upstream_unavailable', name);
    assert.equal(error.status, 503, name);
  }
  const meta = await client.meta();
  assert.equal(meta.features.world_explorer, false);
  assert.equal(meta.features.time_machine, false);
});
