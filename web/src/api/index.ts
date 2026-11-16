/** Single client instance per page load. Mode is fixed at build time (web/SPEC.md §5, WEB-09). */
import { createApiClient, type ApiClient } from './client';
import { createFixtureFetch } from './fixtures';
import { getSessionId } from '../lib/session';
import { API_MAX_IN_FLIGHT, createLimitedFetch } from './limit';
import { createResearchFetch } from './research';

export const FIXTURES_ENABLED = process.env.NEXT_PUBLIC_APLOMB_FIXTURES === 'true';
export const API_BASE = (process.env.NEXT_PUBLIC_APLOMB_API_BASE ?? 'http://localhost:8000/v1').replace(/\/+$/, '');

const BASE_URL = FIXTURES_ENABLED ? 'http://fixture.local/v1' : API_BASE;
/** One fetch for every API call, so the in-flight limit covers the typed and the research calls. */
const sharedFetch: typeof fetch = FIXTURES_ENABLED
  ? createFixtureFetch()
  : createLimitedFetch((input, init) => globalThis.fetch(input, init), API_MAX_IN_FLIGHT);

let client: ApiClient | null = null;

export function getApiClient(): ApiClient {
  client ??= createApiClient({ baseUrl: BASE_URL, getSessionId, fetchImpl: sharedFetch });
  return client;
}

/** Routes without contract models (api/research.ts): the 13F filings and comparison, and the World investor map. */
export const researchFetch = createResearchFetch({ baseUrl: BASE_URL, getSessionId, fetchImpl: sharedFetch });
