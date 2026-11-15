/**
 * Colours and pin shape shared by the globe and its text legend. Kept apart from GlobeView.tsx so the
 * legend can be rendered without loading three.js (GlobeView is only ever imported dynamically).
 */
export interface GlobePin {
  id: string;
  kind: 'event' | 'facility' | 'hazard';
  lat: number;
  lng: number;
  /** Plain text shown under the globe on hover. */
  label: string;
  /** Event located only at country level: drawn at the returned centroid, in its own colour. */
  countryLevel: boolean;
  /** 0–1, used for the pin radius only. */
  weight: number;
}

export const PIN_COLORS = {
  event: '#E3A53B', eventCountry: '#F6E3B4', facility: '#6FD0C5', hazard: '#F2907F', selected: '#FFFFFF',
} as const;
export const LAND_COLOR = '#4A6880';
export const OCEAN_COLOR = '#14304A';
export const EXPOSURE_COLORS = ['#2E8F87', '#48B5AA', '#8ADFD2'] as const;
/** Upper bounds (percent of the portfolio) of the first two exposure shades. */
export const EXPOSURE_BREAKS = [5, 20] as const;

export function exposureColor(weightPct: number | undefined): string {
  if (weightPct === undefined || !(weightPct > 0)) return LAND_COLOR;
  if (weightPct < EXPOSURE_BREAKS[0]) return EXPOSURE_COLORS[0];
  if (weightPct < EXPOSURE_BREAKS[1]) return EXPOSURE_COLORS[1];
  return EXPOSURE_COLORS[2];
}
