/**
 * Opt-in cross-language check: the web API client (with its runtime contract validation) against a
 * RUNNING backend. Not part of `npm run check` (file name does not match `*.test.ts`).
 *
 *   npx tsx web/tests/live-api.check.ts http://127.0.0.1:8000/v1 [--runs]
 *
 * Every 2xx body is validated by the same `validateContract` the pages use, so a shape mismatch
 * between the Python models and the generated TypeScript contract fails here. Runs are created
 * only when the server reports configured models (or with --runs); otherwise their 503 is asserted.
 * Calls are spaced to stay under the 30 requests per second session limit.
 */
import { randomUUID } from 'node:crypto';
import { createApiClient } from '../src/api/client';
import { ApiRequestError } from '../src/api/errors';

const base = process.argv[2] ?? 'http://127.0.0.1:8000/v1';
let session = `s_${randomUUID()}`;
const paced: typeof fetch = async (input, init) => {
  await new Promise(resolve => setTimeout(resolve, 45));
  return fetch(input, init);
};
const api = createApiClient({ baseUrl: base, getSessionId: () => session, fetchImpl: paced });
const results: { name: string; ok: boolean; note: string }[] = [];

async function step<T>(name: string, run: () => Promise<T>, describe: (value: T) => string = () => ''): Promise<T | null> {
  try {
    const value = await run();
    results.push({ name, ok: true, note: describe(value) });
    return value;
  } catch (error) {
    const note = error instanceof ApiRequestError ? `${error.status} ${error.code}: ${error.message}` : String(error);
    results.push({ name, ok: false, note });
    return null;
  }
}

async function expectStatus(name: string, status: number, run: () => Promise<unknown>): Promise<void> {
  try {
    await run();
    results.push({ name, ok: false, note: `expected HTTP ${status}, got a success` });
  } catch (error) {
    const got = error instanceof ApiRequestError ? error.status : -1;
    results.push({ name, ok: got === status, note: error instanceof ApiRequestError ? `${error.status} ${error.code}` : String(error) });
  }
}

async function finish(runId: string) {
  for (let i = 0; i < 240; i += 1) {
    const run = await api.run(runId, null);
    if (!['queued', 'running'].includes(run.status)) return run;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`run ${runId} did not finish`);
}

const move = { ticker: 'TSLA', sizePct: 25, funding: { mode: 'pro_rata' as const } };
const meta = await step('GET /meta', () => api.meta(), m => `${m.dataVersion}, models ${m.models.strong ? 'configured' : 'not configured'}`);
if (!meta) { console.error(`Cannot reach ${base}`); process.exit(2); }
const features = meta.features as Record<string, boolean>;
const hasModel = process.argv.includes('--runs') || Boolean(meta.models.strong && meta.models.fast);

await step('GET /health', () => api.health());
const profiles = await step('GET /profiles', () => api.profiles(), p => `${p.items.length} profiles`);
for (const profile of profiles?.items ?? []) {
  const id = profile.profileId;
  await step(`GET /profiles/${id}/overview`, () => api.overview(id, 'full'), o => `${o.verdict}`);
  await step(`GET /profiles/${id}/performance`, () => api.performance(id, 'full'), p => `${p.series.length} points`);
  if (features.frontier_chart) await step(`GET /profiles/${id}/frontier`, () => api.frontier(id, 'full'));
  await step(`GET /profiles/${id}/brief`, () => api.brief(id, 'en'), b => (b.run ? 'cached' : 'none'));
  await step(`POST /check ${id}`, () => api.check({ profileId: id, move }), c => `${c.verdict}, boundary ${c.maxCompatibleSizePct}`);
}
for (const window of ['1y', '3y', '5y', 'ytd'] as const) {
  await step(`GET /profiles/robert/overview?window=${window}`, () => api.overview('robert', window));
}
await step('POST /check/batch', () => api.checkBatch({ items: [{ profileId: 'robert', move }, { profileId: 'amira', move }, { profileId: 'p_aaaaaaaaaa', move }] }),
  b => `${b.results.length} results`);
await step('POST /check (auto funding)', () => api.check({ profileId: 'robert', move: { ...move, funding: { mode: 'auto' } } }),
  c => `${c.fundingOptions.length} options`);
await step('POST /check (historical asOf)', () => api.check({ profileId: 'robert', move, asOf: '2023-06-30' }), c => c.asOf);
await step('PATCH rule', () => api.patchRule('robert', 'cap.position', { threshold: 12 }), r => `version ${r.profileVersion}`);
await step('POST derive', () => api.deriveRules('robert', { reset: true }), r => `${r.rules.length} rules`);
await step('GET /assets', () => api.assets({ limit: 50 }), a => `${a.total} assets`);
await step('GET /assets/TSLA', () => api.asset('TSLA'));
const datasets = await step('GET /datasets', () => api.datasets(), d => `${d.items.length} passports`);
for (const passport of datasets?.items ?? []) await step(`GET /datasets/${passport.datasetId}`, () => api.dataset(passport.datasetId));
await step('GET /runs', () => api.runs({}), r => `${r.items.length} runs`);

if (features.world_explorer) {
  await step('GET /world/layers', () => api.worldLayers(), l => l.items.map(i => `${i.layerId}:${i.available}`).join(' '));
  const page = await step('GET /world/events', () => api.worldEvents({ profileId: 'robert', limit: 50 }), p => `${p.items.length} of ${p.total}`);
  await step('GET /world/events (filters)', () => api.worldEvents({
    from: '2025-11-13', to: '2026-11-12', category: ['monetary_policy', 'macro_release'], country: ['CAN', 'USA'], origin: ['official'], sort: 'date', limit: 20,
  }), p => `${p.total} matches`);
  if (page?.nextCursor) await step('GET /world/events (cursor)', () => api.worldEvents({ profileId: 'robert', limit: 50, cursor: page.nextCursor! }));
  for (const event of (page?.items ?? []).slice(0, 5)) {
    await step(`GET /world/events/${event.eventId}`, () => api.worldEvent(event.eventId, 'robert'), d => `${d.exposures.length} links`);
  }
  for (const id of ['robert', 'amira', 'mateo']) {
    await step(`GET /world/exposure ${id}`, () => api.worldExposure(id), e => e.items.map(i => `${i.countryIso3} ${i.weightPct}`).join(', '));
  }
  for (const iso3 of ['CAN', 'USA', 'JPN']) await step(`GET /world/countries/${iso3}`, () => api.worldCountry(iso3, { profileId: 'robert' }));
  if (features.world_layer_hazards) await step('GET /world/hazards', () => api.worldHazards({ limit: 100 }), h => `${h.total}`);
  if (!features.world_layer_facilities) await expectStatus('GET /world/facilities is 501', 501, () => api.worldFacilities());
}

if (features.time_machine) {
  const presets = await step('GET /replay/presets', () => api.replayPresets(), p => `${p.earliestAsOf}..${p.latestAsOf}, ${p.presets.length} presets`);
  if (presets && hasModel) {
    await expectStatus('replay outside the range is 422', 422, () => api.createRun({
      kind: 'replay', profileId: 'robert', lang: 'en', request: { type: 'move', move }, asOf: '2022-01-03' }));
    const created = await step('POST /runs replay', () => api.createRun({
      kind: 'replay', profileId: 'robert', lang: 'en', request: { type: 'move', move }, asOf: presets.presets[0]!.asOf }));
    if (created) {
      const run = await step('replay run finishes', () => finish(created.runId), r => r.status);
      if (run?.status === 'succeeded') {
        await step('POST reveal', () => api.reveal(run.runId), r => r.outcomes.map(o => `${o.scenarioId} ${o.returnPct.toFixed(1)}%`).join(', '));
        await step('POST reveal (until)', () => api.reveal(run.runId, { until: presets.latestAsOf }));
      }
    }
  }
}

if (hasModel) {
  const kinds = [
    ['decision', { kind: 'decision', profileId: 'robert', lang: 'en', request: { type: 'move', move } }],
    ['decision (fr)', { kind: 'decision', profileId: 'amira', lang: 'fr', request: { type: 'move', move } }],
    ['goal', { kind: 'decision', profileId: 'amira', lang: 'en', request: { type: 'goal', goal: {
      themes: ['ai'], assetClasses: [], tickers: [], targetExposurePct: null, maxLossPct: null, maxVolPct: null, notes: '' } } }],
    ['portfolio_brief', { kind: 'portfolio_brief', profileId: 'mateo', lang: 'en' }],
    ['profile_draft', { kind: 'profile_draft', lang: 'en', text: 'I am a teacher and I want low risk over ten years.' }],
  ] as const;
  for (const [name, body] of kinds) {
    // Run creation is limited to six per minute per session: later kinds use a fresh session.
    if (name === 'portfolio_brief') session = `s_${randomUUID()}`;
    const created = await step(`POST /runs ${name}`, () => api.createRun(body as never));
    if (!created) continue;
    const run = await step(`${name} run finishes`, () => finish(created.runId), r => `${r.status}, ${r.steps.length} steps, ${Object.keys(r.facts).length} facts`);
    const factId = run ? Object.keys(run.facts)[0] : undefined;
    if (run && factId) await step(`GET fact ${name}`, () => api.fact(run.runId, factId));
    if (run) await step(`GET /runs/${name}?since=1`, () => api.run(run.runId, 1));
  }
  if (features.world_explorer) {
    const page = await api.worldEvents({ category: ['monetary_policy'], limit: 1, from: '2026-01-01', to: '2026-11-12' });
    const created = await step('POST /runs event_brief', () => api.createRun({ kind: 'event_brief', profileId: 'robert', lang: 'en', eventId: page.items[0]!.eventId }));
    if (created) await step('event_brief run finishes', () => finish(created.runId), r => r.status);
  }
  await step('POST /requests/parse', () => api.parse({ profileId: 'robert', text: '25% into Tesla', lang: 'en' }), p => p.confidence);
  await step('GET /runs (after)', () => api.runs({}), r => r.items.map(i => i.title.en).join(' | '));
} else {
  await expectStatus('POST /runs is 503 without a model', 503, () => api.createRun({ kind: 'decision', profileId: 'robert', lang: 'en', request: { type: 'move', move } }));
  await expectStatus('POST /requests/parse is 503 without a model', 503, () => api.parse({ profileId: 'robert', text: '25% into Tesla', lang: 'en' }));
}

const failed = results.filter(r => !r.ok);
for (const r of results) console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${r.name}${r.note ? `  (${r.note})` : ''}`);
console.log(`\n${results.length - failed.length} of ${results.length} checks passed against ${base}`);
process.exit(failed.length ? 1 : 0);
