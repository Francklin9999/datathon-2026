'use client';
/** Dashboard scope as a stored UI preference (read after mount; written on every change). */
import { useCallback, useState } from 'react';
import { readPref, writePref } from '../../lib/session';
import { DEFAULT_SCOPE, normalizeScope, type DashboardScope } from '../../lib/ui/scope';

const SCOPE_PREF = 'dashboard.scope.v1';

function readScope(): DashboardScope {
  try {
    const raw = readPref(SCOPE_PREF);
    return normalizeScope(raw ? JSON.parse(raw) : null);
  } catch {
    return DEFAULT_SCOPE;
  }
}

/** Read on the first render: Home content only renders client-side (after profiles load), so the
 *  stored scope is used for the very first queries (no default-then-stored double fetch). */
export function useDashboardScope(): [DashboardScope, (update: (scope: DashboardScope) => DashboardScope) => void] {
  const [scope, setScope] = useState<DashboardScope>(readScope);
  const update = useCallback((fn: (scope: DashboardScope) => DashboardScope) => {
    setScope(current => {
      const next = normalizeScope(fn(current));
      writePref(SCOPE_PREF, JSON.stringify(next));
      return next;
    });
  }, []);
  return [scope, update];
}
