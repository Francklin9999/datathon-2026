'use client';
/**
 * The country the navigation mini globe faces (ISO3): the World Explorer's `?country`, the listing
 * country of Decide's `?ticker` (from the asset universe, read only then), otherwise Canada.
 * Uses useSearchParams: render it inside a <Suspense> boundary (static export).
 */
import { usePathname, useSearchParams } from 'next/navigation';
import { isKnownIso3, regionIso3 } from '../lib/geo';
import { useAssetUniverse } from './useAssetUniverse';

export const DEFAULT_FOCUS_COUNTRY = 'CAN';

/** An ISO3 code the globe can draw, or null (lower case and region codes are normalised). */
export function focusIso3(code: string | null | undefined): string | null {
  const upper = code?.trim().toUpperCase();
  if (!upper || !/^[A-Z]{3}$/.test(upper) || !isKnownIso3(upper)) return null;
  return regionIso3(upper);
}

export interface FocusCountry {
  iso3: string;
  /** The page named the country (the World Explorer link keeps `?country=` then). */
  known: boolean;
}

export function useFocusCountry(): FocusCountry {
  const pathname = usePathname() ?? '/';
  const params = useSearchParams();
  const onWorld = pathname.startsWith('/world-explorer');
  const ticker = pathname.startsWith('/decision-desk') ? (params?.get('ticker') ?? '').trim().toUpperCase() : '';
  // Asset.country is the ISO 3166-1 alpha-3 code of the listing market (contracts/schemas.md).
  const { assets } = useAssetUniverse(ticker !== '');
  const fromPage = onWorld
    ? focusIso3(params?.get('country'))
    : ticker ? focusIso3(assets.find(asset => asset.ticker.toUpperCase() === ticker)?.country) : null;
  return fromPage ? { iso3: fromPage, known: true } : { iso3: DEFAULT_FOCUS_COUNTRY, known: false };
}
