'use client';
/**
 * Part-to-whole donut with a legend list. The legend carries every label and value (the accessible
 * alternative and the precise reading); the ring gives the at-a-glance shape. Hovering a slice or a
 * legend row highlights the pair. Colours come from the caller (fixed per entity).
 */
import { useEffect, useMemo, useState } from 'react';
import { donutArcs } from '../../lib/ui/donut';

export interface DonutItem { key: string; label: string; value: number; color: string }

const GEOM = { cx: 100, cy: 100, r: 92, thickness: 20, gapDeg: 2.4 };

export function DonutChart({ items, centerValue, centerLabel, label, format }: {
  items: readonly DonutItem[];
  centerValue: string;
  centerLabel: string;
  label: string;
  format: (pct: number) => string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const arcs = useMemo(() => donutArcs(items, GEOM), [items]);
  const byKey = useMemo(() => new Map(items.map(item => [item.key, item])), [items]);
  const max = Math.max(1e-9, ...items.map(item => item.value));
  // A view switch (e.g. by keyboard while the pointer rests on the ring) must not keep a stale highlight.
  const itemsKey = items.map(item => item.key).join('|');
  useEffect(() => { setActive(null); }, [itemsKey]);

  return (
    <div className="donut" onPointerLeave={() => setActive(null)}>
      <div className="donut-figure">
        {/* The ring is decoration for sighted readers; the legend list below is the text version. */}
        <svg viewBox="0 0 200 200" aria-hidden="true" focusable="false" className="donut-svg">
          {arcs.map(arc => (
            <path key={arc.key} d={arc.d} fillRule="evenodd" className="donut-slice"
              data-dim={active !== null && active !== arc.key ? 'true' : undefined}
              style={{ fill: byKey.get(arc.key)?.color }}
              onPointerEnter={() => setActive(arc.key)} />
          ))}
        </svg>
        <div className="donut-center">
          <span className="donut-center-value">{centerValue}</span>
          <span className="donut-center-label">{centerLabel}</span>
        </div>
      </div>
      <ul className="meter-list" aria-label={label}>
        {items.map(item => {
          return (
            <li key={item.key} className="meter-row" data-active={active === item.key ? 'true' : undefined}
              onPointerEnter={() => setActive(item.key)}>
              <span className="meter-dot" style={{ background: item.color }} aria-hidden="true" />
              <span className="meter-name">{item.label}</span>
              <span className="meter-bar" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, (item.value / max) * 100))}%`, background: item.color }} /></span>
              <span className="meter-value num">{format(item.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
