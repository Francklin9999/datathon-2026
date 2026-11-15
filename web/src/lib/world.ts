/**
 * Pure World Explorer logic (T15, web/page-specs/world-explorer.md): filter → query building, date-range
 * clamping (≤ 366 days, inside the dataset coverage), page merging, pin thinning and layer availability.
 * Nothing here estimates an impact or reassigns an unknown exposure bucket.
 */
import type {
  CountryExposure, EventBriefResult, EventCategory, Fact, I18NText, Period, WorldEvent, WorldEventItem, WorldLayer,
} from '../contracts/types';
import type { WorldEventsQuery } from '../api/client';

export const EVENT_CATEGORIES: readonly EventCategory[] = [
  'monetary_policy', 'macro_release', 'geopolitical', 'trade_regulation', 'corporate',
  'energy_commodities', 'markets', 'natural_disaster', 'other',
];
export const EVENT_ORIGINS: readonly WorldEvent['origin'][] = ['official', 'curated', 'gdelt', 'usgs', 'firms', 'live'];

/** api.md 6.2: "range ≤ 366 days". Enforced as at most 366 calendar dates, both ends included. */
export const MAX_RANGE_DAYS = 366;
export const FEED_PAGE_SIZE = 100;
export const MAX_PINS = 300;

const DAY_MS = 86_400_000;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function isIsoDate(value: string): boolean {
  if (!ISO_DATE.test(value)) return false;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

/** Whole days from `from` to `to` (0 when equal, negative when `to` is earlier). */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS);
}

export interface DateRange { from: string; to: string }

/** Default interval: the dataset coverage, shortened from its start when it is longer than the limit. */
export function defaultRange(coverage: Period): DateRange {
  const earliest = addDays(coverage.end, -(MAX_RANGE_DAYS - 1));
  return { from: coverage.start > earliest ? coverage.start : earliest, to: coverage.end };
}

export type RangeIssue = 'format' | 'order' | 'too_long' | 'outside_coverage';

/** Why an interval cannot be sent, or null. `coverage` null = coverage not known yet (no bound check). */
export function rangeIssue(range: DateRange, coverage: Period | null): RangeIssue | null {
  if (!isIsoDate(range.from) || !isIsoDate(range.to)) return 'format';
  if (range.from > range.to) return 'order';
  if (daysBetween(range.from, range.to) + 1 > MAX_RANGE_DAYS) return 'too_long';
  if (coverage && (range.to < coverage.start || range.from > coverage.end)) return 'outside_coverage';
  return null;
}

/**
 * Bring an interval inside the coverage and under the length limit. The end date is kept when
 * possible (the user usually moves the start); `changed` tells the UI to say what was adjusted.
 */
export function clampRange(range: DateRange, coverage: Period | null): DateRange & { changed: boolean } {
  let { from, to } = range;
  if (from > to) [from, to] = [to, from];
  if (coverage) {
    if (to > coverage.end) to = coverage.end;
    if (to < coverage.start) to = coverage.start;
    if (from < coverage.start) from = coverage.start;
    if (from > to) from = to;
  }
  if (daysBetween(from, to) + 1 > MAX_RANGE_DAYS) from = addDays(to, -(MAX_RANGE_DAYS - 1));
  return { from, to, changed: from !== range.from || to !== range.to };
}

export interface WorldFilters {
  /** Empty strings = let the API apply its documented default interval. */
  from: string;
  to: string;
  categories: EventCategory[];
  origins: WorldEvent['origin'][];
  /** ISO3 code, or '' for all countries. */
  country: string;
  ticker: string;
  theme: string;
  q: string;
  sort: 'importance' | 'date';
}

export const EMPTY_FILTERS: WorldFilters = {
  from: '', to: '', categories: [], origins: [], country: '', ticker: '', theme: '', q: '', sort: 'importance',
};

/** Query for GET /world/events. Repeatable params stay arrays (sent as repeated keys); blanks are omitted. */
export function buildEventsQuery(
  filters: WorldFilters, profileId: string | null, cursor: string | null = null, limit: number = FEED_PAGE_SIZE,
): WorldEventsQuery {
  const query: WorldEventsQuery = { sort: filters.sort, limit };
  if (filters.from && filters.to) { query.from = filters.from; query.to = filters.to; }
  if (filters.categories.length) query.category = [...filters.categories];
  if (filters.origins.length) query.origin = [...filters.origins];
  const country = filters.country.trim().toUpperCase();
  if (country) query.country = [country];
  const ticker = filters.ticker.trim().toUpperCase();
  if (ticker) query.ticker = ticker;
  if (filters.theme) query.theme = filters.theme;
  const q = filters.q.trim();
  if (q) query.q = q;
  if (profileId) query.profileId = profileId;
  if (cursor) query.cursor = cursor;
  return query;
}

/** Stable identity of a filter set (cursor pages are only merged while this is unchanged). */
export function filtersKey(filters: WorldFilters, profileId: string | null): string {
  return JSON.stringify(buildEventsQuery(filters, profileId, null, 0));
}

/** Append a page; an event already loaded keeps its first position (stable order across cursors). */
export function mergeEventPages(loaded: readonly WorldEventItem[], page: readonly WorldEventItem[]): WorldEventItem[] {
  const seen = new Set(loaded.map(event => event.eventId));
  const merged = [...loaded];
  for (const event of page) {
    if (!seen.has(event.eventId)) { seen.add(event.eventId); merged.push(event); }
  }
  return merged;
}

/**
 * "Relevant to this portfolio" uses the API's documented `portfolioRelevant` match. It is applied
 * to the loaded events only; the API has no server-side relevance filter.
 */
export function visibleEvents(loaded: readonly WorldEventItem[], relevantOnly: boolean): WorldEventItem[] {
  return relevantOnly ? loaded.filter(event => event.portfolioRelevant === true) : [...loaded];
}

export function hasCoordinates(event: Pick<WorldEvent, 'location'>): boolean {
  const { lat, lon } = event.location;
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
}

export interface PinSelection<T> {
  pins: T[];
  /** Events with usable coordinates among those offered. */
  eligible: number;
  /** Events offered that have no usable coordinates (they stay in the feed only). */
  unlocated: number;
  thinned: boolean;
}

/**
 * Cap the pins drawn on the globe. Kept: highest importance first, then most recent, then event ID,
 * so the same input always thins the same way. `alwaysInclude` keeps the selected event visible.
 */
export function thinPins<T extends Pick<WorldEvent, 'eventId' | 'importance' | 'occurredAt' | 'location'>>(
  events: readonly T[], cap: number = MAX_PINS, alwaysInclude: string | null = null,
): PinSelection<T> {
  const located = events.filter(hasCoordinates);
  const ranked = [...located].sort((a, b) =>
    (b.importance - a.importance) || b.occurredAt.localeCompare(a.occurredAt) || a.eventId.localeCompare(b.eventId));
  const limit = Math.max(0, Math.floor(cap));
  let pins = ranked.slice(0, limit);
  if (alwaysInclude && limit > 0 && !pins.some(event => event.eventId === alwaysInclude)) {
    const selected = ranked.find(event => event.eventId === alwaysInclude);
    if (selected) pins = [...pins.slice(0, limit - 1), selected];
  }
  return { pins, eligible: located.length, unlocated: events.length - located.length, thinned: located.length > pins.length };
}

export type LayerId = WorldLayer['layerId'];
export const LAYER_IDS: readonly LayerId[] = ['events', 'exposure', 'facilities', 'hazards'];
/** Feature flag gating a layer, when it has one (api.md 6.6, 6.7). */
export const LAYER_FLAG: Partial<Record<LayerId, string>> = {
  facilities: 'world_layer_facilities', hazards: 'world_layer_hazards',
};

export type LayerUnavailable = 'flag_off' | 'not_listed' | 'dataset_missing';

/** A layer can be toggled only when its flag (if any) is on and the API lists it as available. */
export function layerState(
  layerId: LayerId, layers: readonly WorldLayer[] | null, flagOn: (flag: string) => boolean,
): { enabled: boolean; reason: LayerUnavailable | null; layer: WorldLayer | null } {
  const layer = layers?.find(item => item.layerId === layerId) ?? null;
  const flag = LAYER_FLAG[layerId];
  if (flag && !flagOn(flag)) return { enabled: false, reason: 'flag_off', layer };
  if (!layer) return { enabled: false, reason: 'not_listed', layer: null };
  if (!layer.available) return { enabled: false, reason: 'dataset_missing', layer };
  return { enabled: true, reason: null, layer };
}

/** ISO user-assigned code the API uses for portfolio weight without a listing country (crypto, cash, unknown). */
export const NO_LISTING_COUNTRY = 'ZZZ';

/**
 * Residual exposure rows: the API's `ZZZ` bucket, and defensively any other code that is not an
 * ISO 3166-1 alpha-3 country. They are shown as returned, never drawn on the globe, never opened
 * as a country panel and never reassigned to a country.
 */
export function isResidualExposure(row: Pick<CountryExposure, 'countryIso3'>, isKnownIso3: (code: string) => boolean): boolean {
  return !isKnownIso3(row.countryIso3);
}

// ----- selection kept in the URL (?eventId=&country=&runId=) -----

export interface WorldSelection { eventId: string | null; country: string | null; runId: string | null }
export type WorldSelectionPatch = Partial<WorldSelection>;

/** Apply a change to the latest selection. A key left out (or undefined) keeps its current value. */
export function mergeSelection(current: WorldSelection, patch: WorldSelectionPatch): WorldSelection {
  return {
    eventId: patch.eventId === undefined ? current.eventId : patch.eventId,
    country: patch.country === undefined ? current.country : patch.country,
    runId: patch.runId === undefined ? current.runId : patch.runId,
  };
}

/** Query string of a selection, without the leading "?"; empty when nothing is selected. */
export function selectionQuery(selection: WorldSelection): string {
  const query = new URLSearchParams();
  if (selection.eventId) query.set('eventId', selection.eventId);
  if (selection.country) query.set('country', selection.country);
  if (selection.runId) query.set('runId', selection.runId);
  return query.toString();
}

/** A brief belongs to one event: opening another event drops the run unless the caller keeps it. */
export function eventSelectionPatch(current: WorldSelection, eventId: string, keepRun = false): WorldSelectionPatch {
  return keepRun || eventId === current.eventId ? { eventId } : { eventId, runId: null };
}

// ----- event brief -----

/**
 * Profile an event brief was written for, when it is not the profile now selected; null when the
 * brief belongs to the selected profile (or the run states no profile). The page labels such a
 * brief instead of showing another investor's holdings under the current name.
 */
export function briefOtherProfileId(runProfileId: string | null, selectedProfileId: string): string | null {
  return runProfileId && runProfileId !== selectedProfileId ? runProfileId : null;
}

/** Shown instead of the run's statement when the code matched no holding: nothing was "identified". */
export const NO_LINK_STATEMENT: I18NText = {
  en: 'No documented link between this event and a holding was found by the code matches. Financial impact not established.',
  fr: 'Aucun lien documenté entre cet événement et une position n’a été trouvé par les correspondances du code. Impact financier non établi.',
};

/**
 * Statement heading an event brief. Decided from the exposures the code returned, not from the
 * wording of the run: a brief with no linked holding never announces an identified exposure.
 */
export function briefImpactStatement(result: Pick<EventBriefResult, 'exposures' | 'impactStatement'>): I18NText {
  return result.exposures.length === 0 ? NO_LINK_STATEMENT : result.impactStatement;
}

/** Fact carrying a country's exposure weight, when the response includes one for that country. */
export function exposureFactId(facts: Record<string, Fact>, countryIso3: string): string | null {
  for (const fact of Object.values(facts)) {
    if (fact.subject.type === 'country' && fact.subject.id === countryIso3) return fact.id;
  }
  return null;
}
