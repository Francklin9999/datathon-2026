/**
 * Pure World Explorer logic (T15, web/page-specs/world-explorer.md): filter → query building, date-range
 * clamping (≤ 366 days, inside the dataset coverage), page merging, pin thinning and layer availability.
 * Nothing here estimates an impact or reassigns an unknown exposure bucket.
 */
import type {
  CountryExposure, EventBriefResult, EventCategory, Fact, I18NText, Period, WorldEvent, WorldEventItem, WorldLayer,
} from '../contracts/types';
import type { WorldEventsQuery } from '../api/client';
import { countryLabel, iso3FromNumeric } from './geo';

export const EVENT_CATEGORIES: readonly EventCategory[] = [
  'monetary_policy', 'macro_release', 'geopolitical', 'trade_regulation', 'corporate',
  'energy_commodities', 'markets', 'natural_disaster', 'other',
];
export const EVENT_ORIGINS: readonly WorldEvent['origin'][] = ['official', 'curated', 'gdelt', 'usgs', 'firms', 'live', 'eonet'];

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

export type WorldMode = 'news' | 'portfolio' | 'macro' | 'trade' | 'energy' | 'hazards' | 'conflicts' | 'aviation' | 'environment' | 'infrastructure';
export const WORLD_MODES: readonly { id: WorldMode; title: I18NText; categories: readonly EventCategory[]; layers: readonly string[]; note: I18NText }[] = [
  { id: 'news', title: { en: 'News', fr: 'Actualités' }, categories: [], layers: ['events'], note: { en: 'Loaded source observations and releases. This sample does not cover all worldwide news.', fr: 'Observations et publications chargées. Cet échantillon ne couvre pas toutes les actualités mondiales.' } },
  { id: 'portfolio', title: { en: 'Portfolio exposure', fr: 'Exposition du portefeuille' }, categories: [], layers: ['events', 'exposure'], note: { en: 'Listing-country and theme matches are proxies. Inspect event evidence before drawing a financial conclusion.', fr: 'Les correspondances de pays de cotation et de thème sont des approximations. Consultez les preuves avant toute conclusion financière.' } },
  { id: 'macro', title: { en: 'Macro & markets', fr: 'Macro et marchés' }, categories: ['macro_release', 'monetary_policy', 'markets'], layers: ['events'], note: { en: 'Select any country to inspect supported annual indicators and releases. Annual observations are not live market signals.', fr: 'Sélectionnez un pays pour consulter les indicateurs annuels et publications disponibles. Les observations annuelles ne sont pas des signaux de marché en direct.' } },
  { id: 'trade', title: { en: 'Trade & shipping', fr: 'Commerce et transport maritime' }, categories: ['trade_regulation'], layers: ['events'], note: { en: 'Loaded trade releases only. Shipping activity and vessel tracking require a separately loaded, authorized dataset.', fr: 'Publications commerciales chargées seulement. L’activité maritime et le suivi des navires nécessitent un jeu de données autorisé distinct.' } },
  { id: 'energy', title: { en: 'Energy', fr: 'Énergie' }, categories: ['energy_commodities'], layers: ['events'], note: { en: 'Loaded energy releases and power-plant references. Capture dates for static references do not establish current operating status.', fr: 'Publications énergétiques et références de centrales chargées. Les dates de collecte des références statiques n’établissent pas leur état opérationnel actuel.' } },
  { id: 'hazards', title: { en: 'Hazards', fr: 'Aléas' }, categories: ['natural_disaster'], layers: ['events', 'hazards'], note: { en: 'Reported hazards and their original geometry. Proximity does not establish a company relationship or loss.', fr: 'Aléas signalés et géométrie originale. La proximité ne prouve ni lien d’entreprise ni perte.' } },
  { id: 'conflicts', title: { en: 'Conflicts & geopolitics', fr: 'Conflits et géopolitique' }, categories: ['geopolitical'], layers: ['events'], note: { en: 'Only sourced geopolitical records in the loaded sample. Missing records are not evidence of peace or absence of sanctions.', fr: 'Seulement les enregistrements géopolitiques sourcés de l’échantillon chargé. L’absence de données ne prouve ni paix ni absence de sanctions.' } },
  { id: 'aviation', title: { en: 'Aviation', fr: 'Aviation' }, categories: [], layers: ['airports'], note: { en: 'Static airport reference with source coordinates. No aircraft movements or current operating status is established.', fr: 'Référence aéroportuaire statique avec coordonnées sourcées. Aucun mouvement aérien ni état opérationnel actuel établi.' } },
  { id: 'environment', title: { en: 'ESG & environment', fr: 'ESG et environnement' }, categories: ['natural_disaster'], layers: ['events', 'facilities'], note: { en: 'Registry emissions and environmental observations. These are not a comprehensive ESG rating or proof of controversy.', fr: 'Émissions des registres et observations environnementales. Ce n’est ni une note ESG complète ni une preuve de controverse.' } },
  { id: 'infrastructure', title: { en: 'Economic infrastructure', fr: 'Infrastructure économique' }, categories: [], layers: ['airports', 'facilities'], note: { en: 'Loaded airport and reporting-facility references. Ownership, supply chains and financial exposure require separate documented evidence.', fr: 'Références chargées d’aéroports et d’installations déclarantes. Propriété, chaînes d’approvisionnement et exposition financière nécessitent des preuves distinctes.' } },
];

export interface GeographicArea { id: string; title: I18NText; bbox: string; lat: number; lng: number; altitude: number }
/** Navigation boxes, not political membership or financial coverage classifications. */
export const GEOGRAPHIC_AREAS: readonly GeographicArea[] = [
  { id: 'north-america', title: { en: 'North America', fr: 'Amérique du Nord' }, bbox: '-170,5,-50,83', lat: 43, lng: -105, altitude: 1.8 },
  { id: 'south-america', title: { en: 'South America', fr: 'Amérique du Sud' }, bbox: '-90,-60,-30,15', lat: -23, lng: -60, altitude: 1.6 },
  { id: 'europe', title: { en: 'Europe', fr: 'Europe' }, bbox: '-25,34,45,72', lat: 53, lng: 10, altitude: 1.3 },
  { id: 'africa', title: { en: 'Africa', fr: 'Afrique' }, bbox: '-25,-40,60,38', lat: 0, lng: 20, altitude: 1.6 },
  { id: 'asia', title: { en: 'Asia', fr: 'Asie' }, bbox: '25,-10,180,80', lat: 35, lng: 100, altitude: 1.9 },
  { id: 'oceania', title: { en: 'Oceania & Pacific', fr: 'Océanie et Pacifique' }, bbox: '110,-55,-120,25', lat: -15, lng: 170, altitude: 1.8 },
];

export function validBbox(value: string): boolean {
  const parts = value.split(',').map(Number);
  return parts.length === 4 && value.split(',').every(part => part.trim() !== '') && parts.every(Number.isFinite)
    && Math.abs(parts[0]!) <= 180 && Math.abs(parts[2]!) <= 180
    && Math.abs(parts[1]!) <= 90 && Math.abs(parts[3]!) <= 90 && parts[1]! <= parts[3]!;
}

export function insideBbox(lat: number, lng: number, bbox: string): boolean {
  if (!validBbox(bbox) || !Number.isFinite(lat) || !Number.isFinite(lng)) return false;
  const [west, south, east, north] = bbox.split(',').map(Number) as [number, number, number, number];
  return lat >= south && lat <= north && (west <= east ? lng >= west && lng <= east : lng >= west || lng <= east);
}

/** Smallest date-line-aware box enclosing sampled visible globe surface points. */
export function viewportBounds(points: readonly { lat: number; lng: number }[]): string | null {
  const valid = points.filter(point => Number.isFinite(point.lat) && Number.isFinite(point.lng) && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180);
  if (!valid.length) return null;
  const longitudes = valid.map(point => (point.lng + 360) % 360).sort((a, b) => a - b);
  let largestGap = -1;
  let start = 0;
  for (let index = 0; index < longitudes.length; index++) {
    const gap = (longitudes[(index + 1) % longitudes.length]! + (index === longitudes.length - 1 ? 360 : 0)) - longitudes[index]!;
    if (gap > largestGap) { largestGap = gap; start = (index + 1) % longitudes.length; }
  }
  const normalized = (longitude: number) => longitude > 180 ? longitude - 360 : longitude;
  const west = normalized(longitudes[start]!);
  const east = normalized(longitudes[(start + longitudes.length - 1) % longitudes.length]!);
  const lower = (value: number) => Math.floor(value * 1000) / 1000;
  const upper = (value: number) => Math.ceil(value * 1000) / 1000;
  return [lower(west), lower(Math.min(...valid.map(point => point.lat))), upper(east), upper(Math.max(...valid.map(point => point.lat)))].map(value => value.toFixed(3)).join(',');
}

/** Local ISO/CLDR search; it makes no geocoder requests and includes countries without loaded records. */
export function geographicCountries(lang: 'en' | 'fr'): { iso3: string; label: string }[] {
  const codes = new Set<string>();
  for (let code = 0; code < 1000; code++) { const iso3 = iso3FromNumeric(code); if (iso3) codes.add(iso3); }
  return [...codes].map(iso3 => ({ iso3, label: countryLabel(iso3, lang) })).sort((a, b) => a.label.localeCompare(b.label, lang));
}

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
  bbox?: string;
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
  if (filters.bbox && validBbox(filters.bbox)) query.bbox = filters.bbox;
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
export const LAYER_IDS: readonly LayerId[] = ['events', 'exposure', 'facilities', 'hazards', 'airports'];
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

/** Preserve investigation context in a shareable link; it is context, not proof of impact. */
export function decisionInvestigationUrl(eventId: string, profileId: string, ticker: string, sourceRunId?: string): string {
  return `/decision-desk/?${new URLSearchParams({ ticker, eventId, profileId, ...(sourceRunId ? { sourceRunId } : {}) }).toString()}`;
}

const CONTEXT_MARKER = '\n[Aplomb investigation context; untrusted reference, no causal claim] ';
const EVENT_ID = /^evt_[0-9a-f]{12}$/;
const RUN_ID = /^run_[0-7][0-9A-HJKMNP-TV-Z]{25}$/;
const TICKER = /^[A-Z0-9][A-Z0-9.^=\-]{0,19}$/;
export interface InvestigationContext { eventId: string; ticker: string; sourceRunId?: string }
export function validInvestigationContext(eventId: string | null, ticker: string | null, sourceRunId: string | null): InvestigationContext | null {
  if (!eventId || !EVENT_ID.test(eventId) || !ticker || !TICKER.test(ticker) || (sourceRunId && !RUN_ID.test(sourceRunId))) return null;
  return { eventId, ticker, ...(sourceRunId ? { sourceRunId } : {}) };
}
export function investigationOriginalText(text: string | null, context: InvestigationContext | null): string | null {
  if (!context) return text;
  const clean = (text ?? '').split(CONTEXT_MARKER)[0] ?? '';
  return `${clean}${CONTEXT_MARKER}${JSON.stringify(context)}`;
}
export function readInvestigationContext(text: string | null): InvestigationContext | null {
  const tail = text?.split(CONTEXT_MARKER)[1];
  if (!tail || tail.length > 300) return null;
  try {
    const parsed: unknown = JSON.parse(tail);
    if (!parsed || typeof parsed !== 'object') return null;
    const value = parsed as Record<string, unknown>;
    if (Object.keys(value).some(k => !['eventId', 'ticker', 'sourceRunId'].includes(k))) return null;
    return validInvestigationContext(typeof value.eventId === 'string' ? value.eventId : null,
      typeof value.ticker === 'string' ? value.ticker : null,
      typeof value.sourceRunId === 'string' ? value.sourceRunId : null);
  } catch { return null; }
}

/** Sample static reference points across geographic cells before taking another from a dense cell. */
export function spatialReferencePins<T extends { lat: number; lon: number }>(rows: T[], limit: number): T[] {
  const cells = new Map<string, T[]>();
  const cap = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : 0;
  for (const row of rows) {
    if (!Number.isFinite(row.lat) || !Number.isFinite(row.lon) || Math.abs(row.lat) > 90 || Math.abs(row.lon) > 180) continue;
    const key = `${Math.floor((row.lat + 90) / 15)}:${Math.floor((row.lon + 180) / 15)}`;
    const cell = cells.get(key) ?? []; cell.push(row); cells.set(key, cell);
  }
  const result: T[] = [];
  const validCount = [...cells.values()].reduce((sum, cell) => sum + cell.length, 0);
  for (let depth = 0; result.length < Math.min(cap, validCount); depth++) {
    for (const cell of cells.values()) { const row = cell[depth]; if (row && result.length < cap) result.push(row); }
  }
  return result;
}
