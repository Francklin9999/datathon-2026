/**
 * Research and intelligence routes that have no generated contract model yet (contracts/api.md:
 * the branch-local research payloads are still to be reconciled with the client models). They go
 * through the same base URL, session header and fetch as the typed client (api/index.ts), so
 * fixture mode answers them with the adapter's typed 503 and live mode counts them against the
 * shared in-flight limit (limit.ts). The caller checks the status and the body shape.
 */
import type { ApiError } from '../contracts/types';
import { validateContract } from '../contracts/validate';
import { ApiRequestError } from './errors';

interface ResearchInit { method?: 'GET' | 'POST'; signal?: AbortSignal | undefined; body?: unknown }
type ResearchFetch = (path: string, init?: ResearchInit) => Promise<Response>;

export function createResearchFetch(config: {
  /** Base including `/v1`, without trailing slash. */
  baseUrl: string;
  getSessionId: () => string | null;
  fetchImpl: typeof fetch;
}): ResearchFetch {
  return (path, init = {}) => {
    const request: RequestInit = {
      method: init.method ?? 'GET',
      headers: { Accept: 'application/json', 'X-Aplomb-Session': config.getSessionId() ?? '' },
    };
    if (init.signal) request.signal = init.signal;
    if (init.body !== undefined) {
      request.body = JSON.stringify(init.body);
      request.headers = { ...request.headers, 'Content-Type': 'application/json' };
    }
    return config.fetchImpl(`${config.baseUrl}${path}`, request);
  };
}

function retryAfterMs(value: string | null): number | null {
  if (!value) return null;
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds * 1000 : null;
}

/**
 * The JSON body of a research response, or the ApiRequestError the typed client raises for the
 * same response: the server's code, message, request ID and Retry-After for an ApiError body,
 * `invalid_response` for a body that is not JSON or not an ApiError.
 */
export async function researchJson(response: Response, path: string): Promise<unknown> {
  const requestId = response.headers.get('X-Request-Id');
  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try { body = JSON.parse(text); } catch {
      throw new ApiRequestError({ status: response.status, code: 'invalid_response', requestId, message: `Response from ${path} was not JSON` });
    }
  }
  if (response.ok) return body;
  let parsed: ApiError | null = null;
  try { parsed = validateContract('ApiError', body); } catch { parsed = null; }
  throw new ApiRequestError({
    status: response.status,
    code: parsed?.error.code ?? 'invalid_response',
    message: parsed?.error.message ?? `HTTP ${response.status} from ${path}`,
    requestId: parsed?.error.requestId ?? requestId,
    details: (parsed?.error.details as Record<string, unknown> | undefined) ?? null,
    retryAfterMs: retryAfterMs(response.headers.get('Retry-After')),
  });
}
