/**
 * Colours and pin shape shared by the globe and its legend. Kept apart from GlobeView.tsx so the legend
 * can be rendered without loading three.js (GlobeView is only ever imported dynamically).
 *
 * The globe sits in a dark "space" stage in both themes. Land is drawn as hexagons: neutral slate, or a
 * cobalt ramp by the portfolio's weight in that country (where the money is). Events stand up from the
 * ground as spikes whose height is their importance, in a colour per category; arcs run from an event
 * to the exposed countries it names; earthquakes are small dots sized by magnitude.
 */
import type { EventCategory, I18nText, WorldEventItem, WorldObservation, WorldPortfolioAssessment } from '../../contracts/types';

export interface GlobePin {
  id: string;
  kind: 'event' | 'facility' | 'hazard' | 'airport' | 'cluster' | 'observation';
  lat: number;
  lng: number;
  /** Plain text shown in the caption on hover. */
  label: string;
  /** Event located only at country level: drawn at the returned centroid. */
  countryLevel: boolean;
  /** 0–1: spike height of an event. */
  weight: number;
  category?: EventCategory;
  /** The source event, used for the hover preview. */
  event?: WorldEventItem;
  observation?: WorldObservation;
  /** Source fields for optional reference-layer popups. */
  reference?: {
    sourceName: I18nText;
    sourceUrl: string;
    datasetId: string;
    summary: I18nText;
    countryIso3: string | null;
    occurredAt?: string;
    capturedAt?: string | null;
    assessment?: WorldPortfolioAssessment | null;
  };
  /** ISO3 codes the event names; arcs go to the ones where the portfolio has weight. */
  related?: readonly string[];
  /** Earthquake magnitude, for the dot size. */
  magnitude?: number;
  members?: readonly GlobePin[];
  /** Original provider GeoJSON, used only for the selected source overlay. */
  geometry?: Record<string, unknown> | null;
}

/** React-rendered hover content; coordinates are local to the globe canvas. */
export interface GlobeHover {
  label: string;
  pin?: GlobePin;
  x?: number;
  y?: number;
  width?: number;
}

/** Reference markers stay above the selected country's raised surface and source overlays. */
export const REFERENCE_PIN_ALTITUDE = 0.03;

export interface SourceGeometry {
  polygon: { geometry: Record<string, unknown> } | null;
  paths: number[][][];
}
/** Keep source ordering and coordinates. Reject unsupported, invalid or unbounded geometry. */
export function sourceGeometry(geometry: Record<string, unknown> | null | undefined): SourceGeometry {
  const empty = { polygon: null, paths: [] };
  if (!geometry) return empty;
  let count = 0;
  const line = (value: unknown, closed = false): value is number[][] => {
    if (!Array.isArray(value) || value.length < (closed ? 4 : 2)) return false;
    for (const point of value) {
      if (++count > 20000 || !Array.isArray(point) || point.length < 2
        || typeof point[0] !== 'number' || typeof point[1] !== 'number'
        || !Number.isFinite(point[0]) || !Number.isFinite(point[1])
        || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90) return false;
    }
    return !closed || (value[0][0] === value[value.length - 1][0] && value[0][1] === value[value.length - 1][1]);
  };
  const polygon = (value: unknown): boolean => Array.isArray(value) && value.length > 0 && value.every(ring => line(ring, true));
  const coordinates = geometry.coordinates;
  if (geometry.type === 'Polygon' && polygon(coordinates)) return { polygon: { geometry }, paths: [] };
  if (geometry.type === 'MultiPolygon' && Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(polygon)) return { polygon: { geometry }, paths: [] };
  if (geometry.type === 'LineString' && line(coordinates)) return { polygon: null, paths: [coordinates] };
  if (geometry.type === 'MultiLineString' && Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(part => line(part))) return { polygon: null, paths: coordinates as number[][][] };
  return empty;
}

/** Spatial display grouping only. It never merges source records or changes source coordinates. */
export function clusterPins(pins: readonly GlobePin[], altitude: number, selectedId: string | null): GlobePin[] {
  const degrees = altitude >= 2 ? 12 : altitude >= 1.2 ? 6 : 0;
  const valid = pins.filter(pin => Number.isFinite(pin.lat) && Number.isFinite(pin.lng) && Math.abs(pin.lat) <= 90 && Math.abs(pin.lng) <= 180);
  if (!degrees) return valid;
  const cells = new Map<string, GlobePin[]>();
  const singles: GlobePin[] = [];
  for (const pin of valid) {
    if (pin.id === selectedId) { singles.push(pin); continue; }
    const key = `${pin.kind}:${Math.floor((pin.lat + 90) / degrees)}:${Math.floor((pin.lng + 180) / degrees)}`;
    const cell = cells.get(key) ?? [];
    cell.push(pin);
    cells.set(key, cell);
  }
  return [...singles, ...[...cells.entries()].map(([cell, members]) => members.length === 1 ? members[0]! : ({
    id: `cluster:${degrees}:${cell}`, kind: 'cluster' as const,
    lat: members.reduce((sum, pin) => sum + pin.lat, 0) / members.length,
    lng: members.reduce((sum, pin) => sum + pin.lng, 0) / members.length,
    label: `${members.length} · ${members[0]!.kind}`, countryLevel: false, weight: 0, members,
  }))];
}

/** Category colours: the categorical palette of the app, in a fixed order (colour follows the category). */
export const CATEGORY_COLORS: Record<EventCategory, string> = {
  monetary_policy: '#5B8CFF',
  macro_release: '#2EC4B6',
  geopolitical: '#F2667A',
  trade_regulation: '#B28CFF',
  corporate: '#FFB347',
  energy_commodities: '#F28C38',
  markets: '#7FD1FF',
  natural_disaster: '#FF7A59',
  other: '#C5CAD6',
};

export const OBSERVATION_COLORS: Record<WorldObservation['mode'], string> = {
  news: '#7FD1FF', macro: '#2EC4B6', trade: '#B28CFF', energy: '#F28C38',
  hazards: '#FFC27A', conflicts: '#F2667A', aviation: '#BCA9F5',
  environment: '#6FD0C5', infrastructure: '#D0D8E8',
};

export const PIN_COLORS = {
  selected: '#FFFFFF', facility: '#6FD0C5', hazard: '#FFC27A', airport: '#BCA9F5',
} as const;

export function pinColor(pin: GlobePin, selectedId: string | null): string {
  if (pin.id === selectedId) return PIN_COLORS.selected;
  if (pin.kind === 'cluster') return '#D8E8FF';
  if (pin.kind === 'observation') return OBSERVATION_COLORS[pin.observation?.mode ?? 'news'];
  if (pin.kind === 'facility') return PIN_COLORS.facility;
  if (pin.kind === 'hazard') return PIN_COLORS.hazard;
  if (pin.kind === 'airport') return PIN_COLORS.airport;
  return CATEGORY_COLORS[pin.category ?? 'other'] ?? CATEGORY_COLORS.other;
}

/** Stage and sphere */
export const SPHERE_COLOR = '#0B1222';
export const ATMOSPHERE_COLOR = '#4C6EF5';
const LAND_COLOR = 'rgba(148, 163, 196, 0.42)';
export const LAND_HOVER_COLOR = 'rgba(214, 222, 240, 0.75)';

/** Cobalt ramp for exposure, light to strong, by the share of the portfolio in a country. */
export const EXPOSURE_COLORS = ['#3D5AFE', '#5B7CFF', '#8EA6FF', '#C3D0FF'] as const;
/** Upper bounds (percent) of the first three exposure shades. */
export const EXPOSURE_BREAKS = [5, 15, 40] as const;

export function exposureColor(weightPct: number | undefined): string {
  if (weightPct === undefined || !(weightPct > 0)) return LAND_COLOR;
  if (weightPct < EXPOSURE_BREAKS[0]) return EXPOSURE_COLORS[0];
  if (weightPct < EXPOSURE_BREAKS[1]) return EXPOSURE_COLORS[1];
  if (weightPct < EXPOSURE_BREAKS[2]) return EXPOSURE_COLORS[2];
  return EXPOSURE_COLORS[3];
}

/** Events closer than this (degrees) share a spot. */
const STACK_PRECISION = 0.05;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/**
 * Events that share a spot (every event known only at country level sits on that country's centre) would
 * draw as a single spike. They are fanned out in a small sunflower around the spot instead, the most
 * important nearest the centre, so each one can be seen, hovered and clicked. Other pins keep their place.
 */
export function spreadStacked(pins: readonly GlobePin[]): GlobePin[] {
  const groups = new Map<string, GlobePin[]>();
  for (const pin of pins) {
    if (pin.kind !== 'event') continue;
    const key = `${Math.round(pin.lat / STACK_PRECISION)}:${Math.round(pin.lng / STACK_PRECISION)}`;
    const group = groups.get(key);
    if (group) group.push(pin); else groups.set(key, [pin]);
  }
  const moved = new Map<string, GlobePin>();
  for (const group of groups.values()) {
    const n = group.length;
    const first = group[0];
    if (n < 2 || !first) continue;
    const order = [...group].sort((a, b) => (b.weight - a.weight) || a.id.localeCompare(b.id));
    const radius = Math.min(4, Math.max(0.5, 0.42 * Math.sqrt(n)));
    const lngScale = 1 / Math.max(0.2, Math.cos((first.lat * Math.PI) / 180));
    order.forEach((pin, i) => {
      const r = radius * Math.sqrt((i + 0.5) / n);
      const angle = i * GOLDEN_ANGLE;
      moved.set(pin.id, {
        ...pin,
        lat: Math.max(-89.9, Math.min(89.9, first.lat + r * Math.sin(angle))),
        lng: ((first.lng + r * Math.cos(angle) * lngScale + 540) % 360) - 180,
      });
    });
  }
  return moved.size ? pins.map(pin => moved.get(pin.id) ?? pin) : [...pins];
}

/** A spike as seen on screen: from its foot (a) to its top (b), `pad` pixels thick on each side. */
export interface ScreenSpike { ax: number; ay: number; bx: number; by: number; pad: number }
/** A label box on screen, by its centre. */
export interface ScreenBox { x: number; y: number; w: number; h: number }

const SPIKE_SAMPLES = 8;

function overlap(box: ScreenBox, spikes: readonly ScreenSpike[], taken: readonly ScreenBox[]): number {
  let hits = 0;
  for (const s of spikes) {
    const hw = box.w / 2 + s.pad;
    const hh = box.h / 2 + s.pad;
    for (let i = 0; i <= SPIKE_SAMPLES; i++) {
      const t = i / SPIKE_SAMPLES;
      if (Math.abs(s.ax + (s.bx - s.ax) * t - box.x) <= hw && Math.abs(s.ay + (s.by - s.ay) * t - box.y) <= hh) { hits++; break; }
    }
  }
  for (const other of taken) {
    if (Math.abs(other.x - box.x) < (other.w + box.w) / 2 + 4 && Math.abs(other.y - box.y) < (other.h + box.h) / 2 + 4) hits += 2;
  }
  return hits;
}

/**
 * Where a country label goes, as an offset (px) from its anchor: above it by default, else the nearest
 * spot around it (below, beside, diagonals, then one step further) that covers no event spike and no
 * label already placed. When every spot is covered, the least covered one.
 */
export function labelOffset(anchor: { x: number; y: number }, size: { w: number; h: number },
  spikes: readonly ScreenSpike[], taken: readonly ScreenBox[]): { dx: number; dy: number } {
  const ux = size.w / 2 + 8;
  const uy = size.h / 2 + 8;
  const directions: [number, number][] = [[0, -1], [0, 1], [1, 0], [-1, 0], [1, -1], [-1, -1], [1, 1], [-1, 1]];
  let best = { dx: 0, dy: -uy, score: Infinity };
  for (const step of [1, 2]) {
    for (const [x, y] of directions) {
      const dx = x * ux * step;
      const dy = y * uy * step;
      const score = overlap({ x: anchor.x + dx, y: anchor.y + dy, w: size.w, h: size.h }, spikes, taken);
      if (score === 0) return { dx, dy };
      if (score < best.score) best = { dx, dy, score };
    }
  }
  return { dx: best.dx, dy: best.dy };
}

/** Pin radii (degrees): thin enough to leave small islands and coasts visible. */
export const PIN_RADIUS = { event: 0.2, selected: 0.32, facility: 0.14 } as const;

/** Spike height (globe radii) of an event from its 0–1 importance. */
export function spikeAltitude(weight: number): number {
  return 0.015 + 0.13 * Math.max(0, Math.min(1, weight));
}

/** Dot radius (degrees) of an earthquake from its magnitude. */
export function quakeRadius(magnitude: number | undefined): number {
  const m = magnitude ?? 4;
  return Math.max(0.08, Math.min(0.6, (m - 3.5) * 0.16));
}
