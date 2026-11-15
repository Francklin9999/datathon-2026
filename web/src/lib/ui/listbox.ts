/** Keyboard model of a single-select listbox (WAI-ARIA APG): bounded arrows, Home/End, typeahead. */

/** Next active option for a navigation key, or null when the key does not navigate. */
export function listboxNext(active: number, key: string, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case 'ArrowDown': return Math.min(count - 1, Math.max(0, active + 1));
    case 'ArrowUp': return Math.max(0, active - 1);
    case 'Home': return 0;
    case 'End': return count - 1;
    default: return null;
  }
}

/** First label after `from` (wrapping) that starts with `query`, case-insensitive; -1 when none. */
export function typeaheadIndex(labels: readonly string[], query: string, from: number): number {
  const q = query.trim().toLocaleLowerCase();
  if (!q || labels.length === 0) return -1;
  for (let step = 1; step <= labels.length; step++) {
    const i = (from + step) % labels.length;
    if ((labels[i] ?? '').toLocaleLowerCase().startsWith(q)) return i;
  }
  return -1;
}
