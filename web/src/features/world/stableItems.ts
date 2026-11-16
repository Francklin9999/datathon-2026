/**
 * globe.gl binds each drawn object (a pin's cylinder, an arc) to its data item by identity. A new item, even
 * one equal to the old, is removed and drawn again with its entrance transition: cylinders grow back from the
 * ground and arcs redraw from their start. Rebuilding the pin or arc lists (a selection, a regrouping) must
 * therefore hand back the same object for every item that did not change.
 */
import { useMemo, useRef } from 'react';

/**
 * Same own fields. Arrays are compared item by item (a cluster's members, an arc's two colours). Keys that
 * start with "__" are skipped: globe.gl stores its own bookkeeping on the data items.
 */
export function sameFields(a: object, b: object): boolean {
  const own = (value: object) => Object.keys(value).filter(key => !key.startsWith('__'));
  const keysA = own(a);
  if (keysA.length !== own(b).length) return false;
  const recordA = a as Record<string, unknown>;
  const recordB = b as Record<string, unknown>;
  return keysA.every(key => {
    if (!Object.prototype.hasOwnProperty.call(b, key)) return false;
    const valueA = recordA[key];
    const valueB = recordB[key];
    if (valueA === valueB) return true;
    return Array.isArray(valueA) && Array.isArray(valueB) && valueA.length === valueB.length
      && valueA.every((item, index) => item === valueB[index]);
  });
}

/**
 * The items, with each one replaced by the object kept from the previous list when it has the same id and the
 * same fields. Pure apart from `cache`, which only remembers the last list.
 */
export function keepStable<T extends { id: string }>(items: readonly T[], cache: Map<string, T>): { items: T[]; cache: Map<string, T> } {
  const next = new Map<string, T>();
  const out = items.map(item => {
    // A repeated id keeps its own object: one drawn object cannot belong to two items.
    if (next.has(item.id)) return item;
    const previous = cache.get(item.id);
    const kept = previous !== undefined && (previous === item || sameFields(previous, item)) ? previous : item;
    next.set(item.id, kept);
    return kept;
  });
  return { items: out, cache: next };
}

/** `keepStable` across renders. */
export function useStableItems<T extends { id: string }>(items: readonly T[]): T[] {
  const cache = useRef(new Map<string, T>());
  return useMemo(() => {
    const result = keepStable(items, cache.current);
    cache.current = result.cache;
    return result.items;
  }, [items]);
}
