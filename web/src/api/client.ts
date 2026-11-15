/**
 * Typed HTTP client for contracts/api.md v1. Every successful body is validated against the
 * generated JSON Schema before it reaches a component; every failure is an ApiRequestError.
 */
import { validateContract, ContractValidationError } from '../contracts/validate';
import type {
  AplombContracts, ApiError, BatchCheckRequest, CheckRequest, CreateProfileRequest,
  CreateRunRequest, DeriveRulesRequest, Lang, ParseRequest, RebalanceRequest, RulePatchRequest,
  SabotageRequest, UpdatePortfolioRequest, UpdateProfileRequest, WindowCode, AnswerRequest,
  RunKind, RevealRequest, StrategySimulateRequest, WindowSpec,
} from '../contracts/types';
import { expandedResult } from './expandedInvestor';
import { focusResult, targetsResult } from './focusModels';
import { factorFitResult, fundLookThroughResult } from './investorModels';
import { sensitivityScenarioResult, type SensitivityScenarioRequest } from './riskModels';
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
export interface WorldFacilitiesQuery { bbox?: string; country?: readonly string[]; ticker?: string; minEmissions?: number; limit?: number; profileId?: string }
export interface WorldHazardsQuery { from?: string; to?: string; type?: 'earthquake' | 'wildfire'; bbox?: string; limit?: number; profileId?: string }
export interface WorldObservationsQuery {
  mode?: string; bbox?: string; country?: readonly string[]; q?: string; from?: string; to?: string; asOf?: string;
  scope?: 'all' | 'providers'; order?: 'date' | 'coverage'; mapOnly?: boolean; limit?: number; cursor?: string;
  profileId?: string;
}

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

    addConditionRule: (profileId: string, body: unknown) => call('Profile', 'POST', `/profiles/${enc(profileId)}/condition-rules`, { body }),
    removeConditionRule: (profileId: string, ruleId: string, version: number) => call('Profile', 'DELETE', `/profiles/${enc(profileId)}/condition-rules/${enc(ruleId)}`, { query: { version } }),
    editAccount: (profileId: string, accountId: string, body: unknown) => call('Profile', 'PUT', `/profiles/${enc(profileId)}/accounts/${enc(accountId)}`, { body }),
    jointPlan: async (profileId: string, body: unknown) => {
      const result = await raw('POST', `/profiles/${enc(profileId)}/joint-plan`, { body });
      try { return expandedResult('joint', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid joint plan response' }); }
    },
    comparePortfolios: async (body: unknown) => {
      const result = await raw('POST', '/portfolios/compare', { body });
      try { return expandedResult('compare', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid comparison response' }); }
    },
    covariance: async (body: unknown) => {
      const result = await raw('POST', '/risk/covariance', { body });
      try { return expandedResult('covariance', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid covariance response' }); }
    },
    liquidityAnalysis: async (profileId: string, body: unknown) => {
      const result = await raw('POST', `/profiles/${enc(profileId)}/liquidity-analysis`, { body });
      try { return expandedResult('liquidity', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid liquidity response' }); }
    },
    activeFactorExposure: async (profileId: string, body: unknown) => {
      const result = await raw('POST', `/profiles/${enc(profileId)}/factor-exposure`, { body });
      try { return expandedResult('factor', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid active factor response' }); }
    },
    nestedFundExposure: async (body: unknown) => {
      const result = await raw('POST', '/risk/nested-fund-look-through', { body });
      try { return expandedResult('nested', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid nested fund response' }); }
    },
    positionDetails: async (profileId: string, body: unknown) => {
      const result = await raw('POST', `/profiles/${enc(profileId)}/position-details`, { body });
      try { return expandedResult('positions', result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid position details response' }); }
    },
    strategicCandidates: async (profileId: string, signal?: AbortSignal) => {
      const { body } = await raw('GET', `/profiles/${enc(profileId)}/strategic-candidates`, { signal });
      try { return focusResult(body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid strategic candidate response' }); }
    },
    allocationTargets: async (profileId: string, signal?: AbortSignal) => {
      const { body } = await raw('GET', `/profiles/${enc(profileId)}/allocation-targets`, { signal });
      try { return targetsResult(body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid allocation target response' }); }
    },
    factorFit: async (body: unknown) => {
      const result = await raw('POST', '/risk/factor-fit', { body });
      try { return factorFitResult(result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid factor fit response' }); }
    },
    fundLookThrough: async (body: unknown) => {
      const result = await raw('POST', '/risk/fund-look-through', { body });
      try { return fundLookThroughResult(result.body); } catch { throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid fund look-through response' }); }
    },
    requirementsScenario: async (profileId: string, body: { asOf: string; through: string; liquidCapital: number; annualReturnPct: number; cashflows: { date: string; amount: number }[] }) => {
      const result = await raw('POST', `/profiles/${enc(profileId)}/requirements-scenario`, { body });
      const r = result.body as { state: string; currency: string; endingValue: number | null; shortfall: number | null; shortfallDate: string | null; missingInputs: string[]; events: { date: string; balance: number; reserve: number; shortfall: number; requirements: string[] }[]; assumptions: string[] };
      if (!r || typeof r.state !== 'string' || !Array.isArray(r.missingInputs) || !Array.isArray(r.events) || !Array.isArray(r.assumptions)) throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid requirement scenario response' });
      return r;
    },
    targetFunding: async (body: { totalValue: number; before: Record<string, number>; target: Record<string, number>; externalFlow: number }) => {
      const result = await raw('POST', '/decision/target-funding', { body });
      const r = result.body as { beforeValue: number; afterValue: number; externalFlow: number; purchases: number; sales: number; changes: { ticker: string; beforeValue: number; targetValue: number; changeValue: number; beforeWeight: number; targetWeight: number }[]; assumptions: string[] };
      if (!r || ![r.beforeValue, r.afterValue, r.externalFlow, r.purchases, r.sales].every(Number.isFinite) || !Array.isArray(r.changes) || !r.changes.every(c => typeof c.ticker === 'string' && [c.beforeValue, c.targetValue, c.changeValue].every(Number.isFinite)) || !Array.isArray(r.assumptions)) throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid target funding response' });
      return r;
    },
    sensitivityScenario: async (body: SensitivityScenarioRequest) => {
      const result = await raw('POST', '/risk/scenario', { body });
      try { return sensitivityScenarioResult(result.body); }
      catch { throw new ApiRequestError({ status: result.meta.status, code: 'invalid_response', message: 'Invalid sensitivity scenario response' }); }
    },
    riskDiagnostics: (profileId: string, window: WindowCode | WindowSpec, signal?: AbortSignal) =>
      call('RiskDiagnosticsResponse', 'GET', `/profiles/${enc(profileId)}/risk`, { query: windowQuery(window), signal }),
    profiles: (signal?: AbortSignal) => call('ProfilesResponse', 'GET', '/profiles', { signal }),
    profile: (profileId: string, signal?: AbortSignal) =>
      call('Profile', 'GET', `/profiles/${enc(profileId)}`, { signal }),
    createProfile: (body: CreateProfileRequest) => call('Profile', 'POST', '/profiles', { body }),
    updateProfile: (profileId: string, body: UpdateProfileRequest) =>
      call('Profile', 'PUT', `/profiles/${enc(profileId)}`, { body }),
    duplicateProfile: (profileId: string) => call('Profile', 'POST', `/profiles/${enc(profileId)}/duplicate`, { body: {} }),
    addCustomRule: (profileId: string, body: { dimension: 'position' | 'sector' | 'asset_class' | 'country' | 'currency' | 'theme'; key: string; operation: 'cap' | 'floor'; threshold: number; version: number }) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/custom-rules`, { body }),
    financialProviders: async (signal?: AbortSignal) => {
      const { body } = await raw('GET', '/risk/providers', { signal });
      const r = body as { providers: { id: string; name: string; status: string; limitation: string; documentation: string; terms: string }[]; setAside: { id: string; name: string; status: string; reason: string }[]; scope: string; limitations: string[] };
      if (!r || !Array.isArray(r.providers) || !r.providers.every(p => typeof p.id === 'string' && typeof p.status === 'string') || !Array.isArray(r.setAside)) throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid financial provider status' });
      return r;
    },
    captureFinancialProvider: async (providerId: string, body: { asOf: string; symbol: string; sheet: string; limit: number }) => {
      const result = await raw('POST', `/risk/providers/${enc(providerId)}/capture`, { body });
      const r = result.body as { provider: string; label: string; status: string; captureId: string; version: string; unit: string; asOf: string; availableAt: string; source: { sourceUrl: string; retrievedAt: string; rawSha256: string }; records: Record<string, unknown>[]; limitations: string[] };
      if (!r || typeof r.captureId !== 'string' || typeof r.unit !== 'string' || !Array.isArray(r.records) || !r.source || typeof r.source.rawSha256 !== 'string' || !Array.isArray(r.limitations)) throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid financial provider capture' });
      return r;
    },
    sourceInputs: async (signal?: AbortSignal) => {
      const { body } = await raw('GET', '/risk/source-inputs', { signal });
      if (!body || typeof body !== 'object' || !Array.isArray((body as { sources?: unknown }).sources)) throw new ApiRequestError({ status: 200, code: 'invalid_response', message: 'Invalid financial source inputs' });
      return body as { asOf: string; knownAt: string; sources: { id: string; label?: string; status: string; observation: Record<string, string | number> | null; sourceUrl?: string; retrievedAt?: string; sha256?: string; rights?: string; limitation: string }[] };
    },
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
    savePrivateAsset: (profileId: string, accountId: string, body: { version: number; assetId?: string; name: string; assetType: string; liquidityNotes: string; valuationDate: string; origin: 'user' | 'imported'; sourceDescription: string; nativeCurrency: string; nativeValue: number }) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/accounts/${enc(accountId)}/private-assets`, { body }),
    refreshAccount: (profileId: string, accountId: string, version: number, asOf?: string) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/accounts/${enc(accountId)}/refresh`, { body: { version, ...(asOf ? { asOf } : {}) } }),
    transferAccount: (profileId: string, sourceAccountId: string, destinationAccountId: string, amountReporting: number, version: number) =>
      call('Profile', 'POST', `/profiles/${enc(profileId)}/accounts/${enc(sourceAccountId)}/transfer`, { body: { version, destinationAccountId, amountReporting } }),
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
    simulateStrategy: (profileId: string, body: StrategySimulateRequest, signal?: AbortSignal) =>
      call('StrategySimulation', 'POST', `/profiles/${enc(profileId)}/strategies/simulate`, { body, signal }),

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
    worldAirports: (query: { country?: readonly string[]; q?: string; bbox?: string; limit?: number; profileId?: string }, signal?: AbortSignal) =>
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
