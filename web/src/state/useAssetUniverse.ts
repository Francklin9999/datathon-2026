'use client';
/**
 * The asset universe for suggestions and completion: read once per data version (one request, cached
 * by useQuery and shared by every field), then searched locally on each keystroke. Holdings stay
 * suggestible from the profile alone when this read fails.
 */
import { useEffect } from 'react';
import type { Asset, AssetsResponse } from '../contracts/types';
import { getApiClient } from '../api/index';
import { universeComplete } from '../lib/universe';
import { useApp } from './app';
import { invalidateQueries, useQuery } from './useQuery';

/** The API pages at most this many assets (backend cap); the pinned universe is far smaller. */
export const ASSET_UNIVERSE_LIMIT = 500;
const CHANGED = 'aplomb:assets-changed';
const NONE: readonly Asset[] = [];

/** Cache key of the universe read: pages that list the universe themselves (Labs instrument discovery) share it. */
export function assetUniverseKey(dataVersion: string): string {
  return `assets|universe|${dataVersion}`;
}

export interface AssetUniverse {
  assets: readonly Asset[];
  loading: boolean;
  /**
   * The read completed: `assets` is the snapshot's whole universe, so a ticker missing from it is
   * unsupported. False while loading, when disabled and after a failed read; validate tickers
   * against the universe (lib/universe.ts) only when this is true.
   */
  ready: boolean;
  /** Instruments in the snapshot (the response's `total`); 0 until ready. */
  total: number;
  /** The snapshot the universe belongs to; null until ready. */
  dataVersion: string | null;
}

/** `enabled` false waits (Ask Aplomb reads it on first focus); every caller shares one request. */
export function useAssetUniverse(enabled = true): AssetUniverse {
  const { sessionId, meta } = useApp();
  const key = enabled && sessionId && meta ? assetUniverseKey(meta.dataVersion) : null;
  const query = useQuery<AssetsResponse>(key, signal => getApiClient().assets({ limit: ASSET_UNIVERSE_LIMIT }, signal));
  const { reload } = query;
  useEffect(() => {
    if (!key) return undefined;
    window.addEventListener(CHANGED, reload);
    return () => window.removeEventListener(CHANGED, reload);
  }, [key, reload]);
  const data = query.data;
  const ready = data !== null && universeComplete(data, ASSET_UNIVERSE_LIMIT);
  return {
    assets: data?.items ?? NONE,
    loading: query.loading,
    ready,
    total: ready ? data.total : 0,
    dataVersion: ready && meta ? meta.dataVersion : null,
  };
}

/** After an on-demand fetch adds an asset: forget cached universes and re-read the shown one. */
export function assetsChanged(): void {
  invalidateQueries(key => key.startsWith('assets|'));
  window.dispatchEvent(new Event(CHANGED));
}
