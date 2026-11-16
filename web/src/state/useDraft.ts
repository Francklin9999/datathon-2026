'use client';
import { useEffect, useState } from 'react';
import { dropDraft, peekDraft } from '../lib/draftStore';

/**
 * The draft an editor stashed before a conflict reload (lib/draftStore.ts), read once on mount
 * against the current profile version. The entry is dropped after the mount so a later remount,
 * for example after a successful save, starts from the saved profile again.
 */
export function useRestoredDraft<T>(key: string, version: number): T | null {
  const [draft] = useState(() => peekDraft<T>(key, version));
  useEffect(() => { if (draft) dropDraft(key); }, [draft, key]);
  return draft;
}
