/**
 * Typed HTTP client for contracts/api.md v1. Every successful body is validated against the
 * generated JSON Schema before it reaches a component; every failure is an ApiRequestError.
 */
import { validateContract, ContractValidationError } from '../contracts/validate';
import type {
  AplombContracts, ApiError, BatchCheckRequest, CheckRequest, CreateProfileRequest,
  CreateRunRequest, DeriveRulesRequest, Lang, ParseRequest, RebalanceRequest, RulePatchRequest,
  SabotageRequest, UpdatePortfolioRequest, UpdateProfileRequest, WindowCode, AnswerRequest,
  RunKind, RevealRequest, WindowSpec,
} from '../contracts/types';
import { ApiRequestError } from './errors';

export interface ClientConfig {
  /** Base including `/v1`, without trailing slash. */
  baseUrl: string;
  /** Returns the bearer session capability; null only before bootstrap. */
  getSessionId: () => string | null;
  fetchImpl?: typeof fetch;
}

type QueryValue = string | number | boolean | readonly string[] | null | undefined;
type Query = Record<string, QueryValue>;

interface CallOptions {
  query?: Query | undefined;
  body?: unknown;
  signal?: AbortSignal | undefined;
  /** Endpoints that do not take the session header (`/health`, `/meta`). */
  anonymous?: boolean;
  headers?: Record<string, string>;
}

/** Query of GET /world/events (api.md 6.2). Array values are sent as repeated keys. */
export interface WorldEventsQuery {
  from?: string; to?: string;
  category?: readonly string[]; country?: readonly string[]; origin?: readonly string[];
  bbox?: string; q?: string; ticker?: string; theme?: string; profileId?: string;
  sort?: 'importance' | 'date'; limit?: number; cursor?: string;
}
export interface WorldCountryQuery { profileId?: string; from?: string; to?: string }
export interface WorldFacilitiesQuery { bbox?: string; country?: readonly string[]; ticker?: string; minEmissions?: number; limit?: number }
export interface WorldHazardsQuery { from?: string; to?: string; type?: 'earthquake' | 'wildfire'; bbox?: string; limit?: number }
export interface WorldObservationsQuery { mode?: string; bbox?: string; country?: readonly string[]; q?: string; from?: string; to?: string; asOf?: string; limit?: number; cursor?: string }

export interface ResponseMeta { requestId: string | null; dataVersion: string | null; status: number }

/** Read-endpoint window query: a preset code, or `custom` with its ISO start and end (api.md 3.9/3.10). */
export function windowQuery(window: WindowCode | WindowSpec): Record<string, string> {
  const spec = typeof window === 'string' ? { code: window } : window;
  return spec.code === 'custom' && spec.start && spec.end
    ? { window: 'custom', start: spec.start, end: spec.end }
    : { window: spec.code === 'custom' ? 'full' : spec.code };
}

export function buildUrl(base: string, path: string, query?: Query): string {
  const url = `${base}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue;
    if (Array.isArray(value)) for (const item of value) params.append(key, String(item));
    else params.append(key, String(value));
  }
  const text = params.toString();
  return text ? `${url}?${text}` : url;
}

function parseRetryAfter(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds * 1000 : null;
}

const enc = encodeURIComponent;

export function createApiClient(config: ClientConfig) {
  const fetchImpl: typeof fetch = config.fetchImpl ?? ((input, init) => globalThis.fetch(input, init));

  async function raw(method: string, path: string, options: CallOptions = {}): Promise<{ body: unknown; meta: ResponseMeta }> {
    const headers: Record<string, string> = { Accept: 'application/json', ...options.headers };
    if (!options.anonymous) {
      const session = config.getSessionId();
      if (!session) {
        throw new ApiRequestError({ status: 0, code: 'invalid_response', message: 'Session not initialised' });
      }
      headers['X-Aplomb-Session'] = session;
    }
    const init: RequestInit = { method, headers };
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    if (options.signal) init.signal = options.signal;
    let response: Response;
    try {
      response = await fetchImpl(buildUrl(config.baseUrl, path, options.query), init);
    } catch (error) {
      if (options.signal?.aborted) {
        throw new ApiRequestError({ status: 0, code: 'aborted', message: 'Request cancelled' });
      }
      throw new ApiRequestError({
        status: 0, code: 'network',
        message: error instanceof Error ? error.message : 'Network request failed',
      });
    }
    const meta: ResponseMeta = {
      requestId: response.headers.get('X-Request-Id'),
      dataVersion: response.headers.get('X-Aplomb-Data-Version'),
      status: response.status,
    };
    if (response.status === 204) return { body: null, meta };
    let body: unknown = null;
    const text = await response.text();
    if (text) {
      try { body = JSON.parse(text); } catch {
        throw new ApiRequestError({
          status: response.status, code: 'invalid_response', requestId: meta.requestId,
          message: `Response from ${path} was not JSON`,
        });
      }
    }
    if (!response.ok) {
      let parsed: ApiError | null = null;
      try { parsed = validateContract('ApiError', body); } catch { parsed = null; }
      throw new ApiRequestError({
        status: response.status,
        code: parsed?.error.code ?? 'invalid_response',
        message: parsed?.error.message ?? `HTTP ${response.status} from ${path}`,
        requestId: parsed?.error.requestId ?? meta.requestId,
        details: (parsed?.error.details as Record<string, unknown> | undefined) ?? null,
        retryAfterMs: parseRetryAfter(response.headers.get('Retry-After')),
      });
    }
    return { body, meta };
  }

  async function call<K extends keyof AplombContracts>(
    contract: K, method: string, path: string, options: CallOptions = {},
  ): Promise<AplombContracts[K]> {
    const { body, meta } = await raw(method, path, options);
    try {
      return validateContract(contract, body);
    } catch (error) {
      if (error instanceof ContractValidationError) {
        throw new ApiRequestError({
          status: meta.status, code: 'invalid_response', requestId: meta.requestId,
          message: `Response from ${path} does not match ${String(contract)}: ${error.message}`,
        });
      }
      throw error;
    }
  }

  return {
    health: (signal?: AbortSignal) => call('HealthResponse', 'GET', '/health', { anonymous: true, signal }),
    meta: (signal?: AbortSignal) => call('Meta', 'GET', '/meta', { anonymous: true, signal }),

    entityCandidates: (q: string, signal?: AbortSignal) =>
      call('EntitySearchResponse', 'GET', '/intelligence/entities', { query: { q, limit: 10 }, signal }),
    assets: (query: { q?: string; limit?: number }, signal?: AbortSignal) =>
      call('AssetsResponse', 'GET', '/assets', { query, signal }),
    asset: (ticker: string, signal?: AbortSignal) =>
      call('Asset', 'GET', `/assets/${enc(ticker)}`, { signal }),
    assetAnalytics: (ticker: string, currency: string, window: WindowCode | WindowSpec, signal?: AbortSignal) =>
      call('AssetAnalyticsResponse', 'GET', `/assets/${enc(ticker)}/analytics`, { query: { ...windowQuery(window), currency }, signal }),
    fetchAsset: (ticker: string) =>
      call('FetchAssetResponse', 'POST', `/assets/${enc(ticker)}/fetch`, { body: {} }),

    riskDiagnostics: (profileId: string, window: WindowCode | WindowSpec, signal?: AbortSignal) =>
      call('RiskDiagnosticsResponse', 'GET', `/profiles/${enc(profileId)}/risk`, { query: windowQuery(window), signal }),
    profiles: (signal?: AbortSignal) => call('ProfilesResponse', 'GET', '/profiles', { signal }),
    profile: (profileId: string, signal?: AbortSignal) =>
      call('Profile', 'GET', `/profiles/${enc(profileId)}`, { signal }),
    createProfile: (body: CreateProfileRequest) => call('Profile', 'POST', '/profiles', { body }),
    updateProfile: (profileId: string, body: UpdateProfileRequest) =>
      call('Profile', 'PUT', `/profiles/${enc(profileId)}`, { body }),
    duplicateProfile: (profileId: string) => call('Profile', 'POST', `/profiles/${enc(profileId)}/duplicate`, { body: {} }),
    addExposureLimit: (profileId: string, dimension: 'country' | 'currency', key: string, threshold: number, version: number) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/exposure-limits`, { body: { dimension, key, threshold, version } }),
    rebalance: (request: RebalanceRequest, signal?: AbortSignal) =>
      call('RebalanceResponse', 'POST', '/rebalance/check', { body: request, signal }),
    goalFunding: (profileId: string, signal?: AbortSignal) =>
      call('GoalFundingResponse', 'GET', `/profiles/${enc(profileId)}/goals`, { signal }),
    archivedProfiles: (signal?: AbortSignal) => call('ProfilesResponse', 'GET', '/profiles/archived', { signal }),
    archiveProfile: (profileId: string, archived: boolean, version: number) =>
      call('Profile', 'PATCH', `/profiles/${enc(profileId)}/archive`, { body: { archived, version } }),
    createAccount: (profileId: string, name: string, version: number, portfolio: { totalValue: number; positions: { ticker: string; weightPct: number }[] }, currency?: string) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/accounts`, { body: { name, version, portfolio, ...(currency ? { currency } : {}) } }),
    selectAccount: (profileId: string, accountId: string, version: number) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/accounts/${enc(accountId)}/select`, { body: { version } }),
    deleteProfile: async (profileId: string): Promise<void> => {
      await raw('DELETE', `/profiles/${enc(profileId)}`);
    },
    patchRule: (profileId: string, ruleId: string, body: RulePatchRequest) =>
      call('RulePatchResponse', 'PATCH', `/profiles/${enc(profileId)}/rules/${enc(ruleId)}`, { body }),
    deriveRules: (profileId: string, body: DeriveRulesRequest) =>
      call('DeriveRulesResponse', 'POST', `/profiles/${enc(profileId)}/rules/derive`, { body }),
    updatePortfolio: (profileId: string, body: UpdatePortfolioRequest) =>
      call('Profile', 'PUT', `/profiles/${enc(profileId)}/portfolio`, { body }),
    overview: (profileId: string, window: WindowCode | WindowSpec, signal?: AbortSignal) =>
      call('OverviewResponse', 'GET', `/profiles/${enc(profileId)}/overview`, { query: windowQuery(window), signal }),
    performance: (profileId: string, window: WindowCode | WindowSpec, signal?: AbortSignal, benchmark?: string | null) =>
      call('PerformanceResponse', 'GET', `/profiles/${enc(profileId)}/performance`, {
        query: { ...windowQuery(window), ...(benchmark ? { benchmark } : {}) }, signal,
      }),
    frontier: (profileId: string, window: WindowCode | WindowSpec, signal?: AbortSignal) =>
      call('FrontierResponse', 'GET', `/profiles/${enc(profileId)}/frontier`, { query: windowQuery(window), signal }),
    brief: (profileId: string, lang: Lang, signal?: AbortSignal) =>
      call('CachedBriefResponse', 'GET', `/profiles/${enc(profileId)}/brief`, { query: { lang }, signal }),

    parse: (body: ParseRequest, signal?: AbortSignal) =>
      call('ParsedRequest', 'POST', '/requests/parse', { body, signal }),
    check: (body: CheckRequest, signal?: AbortSignal) =>
      call('CheckResult', 'POST', '/check', { body, signal }),
    checkBatch: (body: BatchCheckRequest, signal?: AbortSignal) =>
      call('BatchCheckResponse', 'POST', '/check/batch', { body, signal }),

    /** 202 → queued; 200 → cached succeeded brief. Both carry `runId`. */
    createRun: async (body: CreateRunRequest, idempotencyKey?: string) => {
      const headers: Record<string, string> = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {};
      const { body: result, meta } = await raw('POST', '/runs', { body, headers });
      try {
        return meta.status === 200
          ? validateContract('CachedRunResponse', result)
          : validateContract('QueuedRunResponse', result);
      } catch (error) {
        throw new ApiRequestError({
          status: meta.status, code: 'invalid_response', requestId: meta.requestId,
          message: error instanceof Error ? error.message : 'Invalid run creation response',
        });
      }
    },
    run: (runId: string, since: number | null, signal?: AbortSignal) =>
      call('Run', 'GET', `/runs/${enc(runId)}`, { query: { since: since ?? undefined }, signal }),
    runs: (query: { profileId?: string; kind?: RunKind; limit?: number; cursor?: string }, signal?: AbortSignal) =>
      call('RunsResponse', 'GET', '/runs', { query, signal }),
    answer: (runId: string, body: AnswerRequest) =>
      call('AnswerResponse', 'POST', `/runs/${enc(runId)}/answers`, { body }),
    cancel: (runId: string) => call('CancelResponse', 'POST', `/runs/${enc(runId)}/cancel`, { body: {} }),
    fact: (runId: string, factId: string, signal?: AbortSignal) =>
      call('FactResponse', 'GET', `/runs/${enc(runId)}/facts/${enc(factId)}`, { signal }),
    sabotage: (runId: string, body: SabotageRequest) =>
      call('QueuedRunResponse', 'POST', `/runs/${enc(runId)}/sabotage`, { body }),

    /** Deterministic Time Machine reveal (api.md 5.8). `until` omitted = last date in the snapshot. */
    reveal: (runId: string, body: RevealRequest = {}, signal?: AbortSignal) =>
      call('RevealResult', 'POST', `/runs/${enc(runId)}/reveal`, { body, signal }),

    worldLayers: (signal?: AbortSignal) => call('WorldLayersResponse', 'GET', '/world/layers', { signal }),
    worldObservations: (query: WorldObservationsQuery = {}, signal?: AbortSignal) =>
      call('WorldObservationsResponse', 'GET', '/world/observations', { query: { ...query }, signal }),
    worldEvents: (query: WorldEventsQuery, signal?: AbortSignal) =>
      call('WorldEventsResponse', 'GET', '/world/events', { query: { ...query }, signal }),
    worldEvent: (eventId: string, profileId?: string, signal?: AbortSignal) =>
      call('WorldEventResponse', 'GET', `/world/events/${enc(eventId)}`, { query: { profileId }, signal }),
    worldExposure: (profileId: string, signal?: AbortSignal) =>
      call('WorldExposureResponse', 'GET', '/world/exposure', { query: { profileId }, signal }),
    worldCountry: (iso3: string, query: WorldCountryQuery = {}, signal?: AbortSignal) =>
      call('WorldCountryResponse', 'GET', `/world/countries/${enc(iso3)}`, { query: { ...query }, signal }),
    worldFacilities: (query: WorldFacilitiesQuery = {}, signal?: AbortSignal) =>
      call('FacilitiesResponse', 'GET', '/world/facilities', { query: { ...query }, signal }),
    worldAirports: (query: { country?: readonly string[]; q?: string; limit?: number }, signal?: AbortSignal) =>
      call('AirportsResponse', 'GET', '/world/airports', { query: { ...query }, signal }),
    worldHazards: (query: WorldHazardsQuery = {}, signal?: AbortSignal) =>
      call('HazardsResponse', 'GET', '/world/hazards', { query: { ...query }, signal }),

    replayPresets: (signal?: AbortSignal) => call('ReplayPresetsResponse', 'GET', '/replay/presets', { signal }),

    datasets: (signal?: AbortSignal) => call('DatasetsResponse', 'GET', '/datasets', { signal }),
    dataset: (datasetId: string, signal?: AbortSignal) =>
      call('DatasetPassport', 'GET', `/datasets/${enc(datasetId)}`, { signal }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
