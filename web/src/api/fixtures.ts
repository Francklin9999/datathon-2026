/**
 * Development-only fetch adapter (web/SPEC.md §5). Serves ONLY what contracts/fixtures contain:
 * profiles and one synthetic succeeded decision run. Every other endpoint answers with a typed
 * `503 upstream_unavailable` naming the missing fixture: no invented overview, check or brief.
 * Selected only when NEXT_PUBLIC_APLOMB_FIXTURES=true; never used as a fallback for a live failure.
 */
import type { Meta, ProfilesResponse, Run, RunSummary } from '../contracts/types';
import { FEATURE_DEFAULTS } from '../contracts/catalog';
import schema from '../../../contracts/generated/schema.json' with { type: 'json' };
import { factUsage } from '../lib/brief';

export const FIXTURE_BANNER = 'Development fixtures — no agents executed.';

interface FixtureData { profiles: ProfilesResponse; runs: Run[] }

let loaded: Promise<FixtureData> | null = null;

async function loadFixtures(): Promise<FixtureData> {
  loaded ??= Promise.all([
    import('../../../contracts/fixtures/profiles.json'),
    import('../../../contracts/fixtures/run.decision.robert-tsla-25.json'),
  ]).then(([profiles, run]) => ({
    profiles: structuredClone(profiles.default) as unknown as ProfilesResponse,
    runs: [structuredClone(run.default) as unknown as Run],
  }));
  return loaded;
}

function fixtureMeta(data: FixtureData): Meta {
  const run = data.runs[0];
  // Every P1 capability is reported off: the fixtures contain nothing that could back them.
  const features = Object.fromEntries(
    Object.keys(FEATURE_DEFAULTS).map(flag => [flag, flag === 'bilingual']),
  ) as Meta['features'];
  return {
    // The version of the generated schema the client validates these responses against.
    contractVersion: schema['x-contract-version'],
    dataVersion: run?.dataVersion ?? 'snap-00000000-fixture',
    dataAsOf: run?.asOf ?? '1970-01-01',
    environment: 'local',
    languages: ['en', 'fr'],
    features,
    models: { strong: null, fast: null },
    universe: { total: 0, byTier: {} },
    disclaimer: {
      en: 'Simulation only. Fictional profiles. Not financial advice.',
      fr: "Simulation uniquement. Profils fictifs. Ceci n'est pas un conseil financier.",
    },
  };
}

let requestCounter = 0;

function respond(status: number, body: unknown, dataVersion: string): Response {
  requestCounter += 1;
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'X-Request-Id': `req_fixture_${requestCounter}`,
      'X-Aplomb-Data-Version': dataVersion,
    },
  });
}

function fail(status: number, code: string, message: string, dataVersion: string): Response {
  return respond(status, { error: { code, message, requestId: `req_fixture_${requestCounter + 1}` } }, dataVersion);
}

function summary(run: Run): RunSummary {
  const verdict = run.result?.kind === 'decision' ? run.result.decision.verdict : null;
  const move = run.input.kind === 'decision' && run.input.request.type === 'move' ? run.input.request.move : null;
  const title = move ? `${move.ticker} +${move.sizePct} (development fixture)` : `${run.kind} (development fixture)`;
  return {
    runId: run.runId, kind: run.kind, status: run.status, profileId: run.profileId,
    createdAt: run.createdAt, title: { en: title, fr: title }, verdict, durationMs: run.usage.durationMs,
  };
}

function requestUrl(input: Parameters<typeof fetch>[0]): URL {
  const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  return new URL(href, 'http://fixture.local');
}

/** A `fetch`-compatible function answering from contract fixtures. */
export function createFixtureFetch(): typeof fetch {
  return async (input, init) => {
    if (init?.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const data = await loadFixtures();
    const dataVersion = data.runs[0]?.dataVersion ?? 'snap-00000000-fixture';
    const method = (init?.method ?? 'GET').toUpperCase();
    const url = requestUrl(input);
    const path = url.pathname.replace(/^.*?\/v1(?=\/)/, '');
    const parts = path.split('/').filter(Boolean).map(decodeURIComponent);

    if (method === 'GET' && path === '/health') return respond(200, { status: 'ok', time: new Date().toISOString() }, dataVersion);
    if (method === 'GET' && path === '/meta') return respond(200, fixtureMeta(data), dataVersion);
    if (method === 'GET' && path === '/profiles') return respond(200, data.profiles, dataVersion);
    // `/profiles/archived` is its own route with no fixture; it falls through to the 503 below.
    if (method === 'GET' && parts[0] === 'profiles' && parts.length === 2 && parts[1] !== 'archived') {
      const profile = data.profiles.items.find(p => p.profileId === parts[1]);
      return profile ? respond(200, profile, dataVersion) : fail(404, 'not_found', `No fixture profile ${parts[1]}`, dataVersion);
    }
    if (method === 'GET' && path === '/runs') {
      const profileId = url.searchParams.get('profileId');
      const kind = url.searchParams.get('kind');
      const items = data.runs
        .filter(run => (!profileId || run.profileId === profileId) && (!kind || run.kind === kind))
        .map(summary);
      return respond(200, { items, nextCursor: null }, dataVersion);
    }
    if (method === 'GET' && parts[0] === 'runs' && parts.length >= 2) {
      const run = data.runs.find(r => r.runId === parts[1]);
      if (!run) return fail(404, 'not_found', `No fixture run ${parts[1]}`, dataVersion);
      if (parts.length === 2) {
        const since = Number(url.searchParams.get('since'));
        if (Number.isFinite(since) && since > 0) {
          return respond(200, { ...run, steps: run.steps.filter(step => step.seq > since) }, dataVersion);
        }
        return respond(200, run, dataVersion);
      }
      if (parts.length === 4 && parts[2] === 'facts') {
        const factId = parts[3] ?? '';
        const fact = run.facts[factId];
        if (!fact) return fail(404, 'not_found', `Fact ${factId} is not in run ${run.runId}`, dataVersion);
        const inputs = fact.inputs.flatMap(id => (run.facts[id] ? [run.facts[id]] : []));
        return respond(200, { fact, inputs, usedBy: factUsage(run, factId) }, dataVersion);
      }
    }
    return fail(503, 'upstream_unavailable',
      `No development fixture exists for ${method} ${path}. Run the API with fixtures disabled to use this flow.`,
      dataVersion);
  };
}
