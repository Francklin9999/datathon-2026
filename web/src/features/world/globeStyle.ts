/**
 * Colours and pin shape shared by the globe and its legend. Kept apart from GlobeView.tsx so the legend
 * can be rendered without loading three.js (GlobeView is only ever imported dynamically).
 *
 * The globe sits in a dark "space" stage in both themes. Land is drawn as hexagons: neutral slate, or a
 * cobalt ramp by the portfolio's weight in that country (where the money is). Events stand up from the
 * ground as spikes whose height is their importance, in a colour per category; arcs run from an event
 * to the exposed countries it names; earthquakes are small dots sized by magnitude.
 */
import type { EventCategory } from '../../contracts/types';

export interface GlobePin {
  id: string;
  kind: 'event' | 'facility' | 'hazard' | 'airport';
  lat: number;
  lng: number;
  /** Plain text shown in the caption on hover. */
  label: string;
  /** Event located only at country level: drawn at the returned centroid. */
  countryLevel: boolean;
  /** 0–1: spike height of an event. */
  weight: number;
  category?: EventCategory;
  /** ISO3 codes the event names; arcs go to the ones where the portfolio has weight. */
  related?: readonly string[];
  /** Earthquake magnitude, for the dot size. */
  magnitude?: number;
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

export const PIN_COLORS = {
  selected: '#FFFFFF', facility: '#6FD0C5', hazard: '#FFC27A', airport: '#BCA9F5',
} as const;

export function pinColor(pin: GlobePin, selectedId: string | null): string {
  if (pin.id === selectedId) return PIN_COLORS.selected;
  if (pin.kind === 'facility') return PIN_COLORS.facility;
  if (pin.kind === 'hazard') return PIN_COLORS.hazard;
  if (pin.kind === 'airport') return PIN_COLORS.airport;
  return CATEGORY_COLORS[pin.category ?? 'other'] ?? CATEGORY_COLORS.other;
}

/** Stage and sphere */
export const STAGE_BACKGROUND = '#070A12';
export const SPHERE_COLOR = '#0B1222';
export const ATMOSPHERE_COLOR = '#4C6EF5';
export const LAND_COLOR = 'rgba(148, 163, 196, 0.42)';
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
export const STACK_PRECISION = 0.05;
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
    const radius = Math.min(6, Math.max(0.9, 0.65 * Math.sqrt(n)));
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

/** Spike height (globe radii) of an event from its 0–1 importance. */
export function spikeAltitude(weight: number): number {
  return 0.04 + 0.32 * Math.max(0, Math.min(1, weight));
}

/** Dot radius (degrees) of an earthquake from its magnitude. */
export function quakeRadius(magnitude: number | undefined): number {
  const m = magnitude ?? 4;
  return Math.max(0.12, Math.min(0.9, (m - 3.5) * 0.22));
}
