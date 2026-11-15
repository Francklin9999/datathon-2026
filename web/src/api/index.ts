/** Single client instance per page load. Mode is fixed at build time (web/SPEC.md §5, WEB-09). */
import { createApiClient, type ApiClient } from './client';
import { createFixtureFetch } from './fixtures';
import { getSessionId } from '../lib/session';

export const FIXTURES_ENABLED = process.env.NEXT_PUBLIC_APLOMB_FIXTURES === 'true';
export const API_BASE = (process.env.NEXT_PUBLIC_APLOMB_API_BASE ?? 'http://localhost:8000/v1').replace(/\/+$/, '');

let client: ApiClient | null = null;

export function getApiClient(): ApiClient {
  client ??= createApiClient({
    baseUrl: FIXTURES_ENABLED ? 'http://fixture.local/v1' : API_BASE,
    getSessionId,
    ...(FIXTURES_ENABLED ? { fetchImpl: createFixtureFetch() } : {}),
  });
  return client;
}

export type { ApiClient } from './client';
export { ApiRequestError, asApiError, isAbort } from './errors';
