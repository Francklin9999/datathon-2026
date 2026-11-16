'use client';
/**
 * Dependency-free SVG line chart with legend and units outside any tooltip, plus a table
 * alternative (DESIGN.md "accessible table alternative for charts"). Values are drawn as given.
 * Gradient area under the first series, recessive grid, crosshair + tooltip on hover. `fill` sizes the
 * drawing to its container (a dashboard widget) instead of a fixed aspect ratio; `compact` keeps the
 * caption for screen readers only and moves the unit into the legend line.
 */
import { useId, useMemo, useRef, useState, type PointerEvent, type ReactNode } from 'react';
import { useElementSize } from '../ui/useElementSize';
import { useFresh } from '../ui/useFresh';
import type { Lang } from '../../contracts/types';
import { fmtDate, fmtNumber } from '../../lib/format';
import { areaPath, axisTicks, chartLineProps, chartScale, linePath, nearestIndex } from '../../lib/ui/chart';

export interface Series { label: string; points: readonly { date: string; value: number }[]; color: string; dashed?: boolean }

const BASE = { w: 720, h: 260 };
const PAD = { l: 60, r: 14, t: 14, b: 30 };

/** Paths that draw themselves once when they appear (or when the series changes: re-keyed). */
function Drawn({ children }: { children: ReactNode }) {
  const fresh = useFresh(1900);
  return <g className="chart-anim" data-fresh={fresh ? 'true' : undefined}>{children}</g>;
}
const time = (date: string) => Date.parse(`${date}T00:00:00Z`);

export function LineChart({ series, lang, unitLabel, caption, digits = 0, area = true, fill = false, compact = false }: {
  series: readonly Series[]; lang: Lang; unitLabel: string; caption: string; digits?: number;
  /** Gradient area under the first series (off for views that live below zero, like drawdown). */
  area?: boolean;
  /** Fill the container's height (the container must have one). */
  fill?: boolean;
  /** Caption for screen readers only; the unit joins the legend. */
  compact?: boolean;
}) {
  const id = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const { ref: frameRef, size } = useElementSize<HTMLDivElement>(fill);
  const W = fill && size ? size.w : BASE.w;
  const H = fill && size ? Math.max(120, size.h) : BASE.h;

  const model = useMemo(() => {
    const all = series.flatMap(s => s.points);
    if (all.length < 2) return null;
    const times = all.map(p => time(p.date));
    const tMin = Math.min(...times);
    const tMax = Math.max(...times);
    const { lo, hi } = chartScale(all.map(p => p.value));
    const x = (t: number) => PAD.l + ((t - tMin) / Math.max(1, tMax - tMin)) * (W - PAD.l - PAD.r);
    const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
    const plotted = series.map(s => {
      const xy = s.points.map(p => ({ x: x(time(p.date)), y: y(p.value) }));
      const byDate = new Map(s.points.map((p, i) => [p.date, { ...xy[i]!, value: p.value }]));
      return { ...s, xy, byDate };
    });
    const base = plotted[0];
    return { lo, hi, y, plotted, baseXs: base ? base.xy.map(p => p.x) : [] };
  }, [series, W, H]);

  if (!model) return null;
  const { lo, hi, y, plotted, baseXs } = model;
  // Round values inside the padded range: the padded top is not a value the series reached.
  const ticks = axisTicks(lo, hi, digits);
  const base = plotted[0];
  const basePoints = series[0]?.points ?? [];
  const first = basePoints[0];
  const last = basePoints[basePoints.length - 1];
  const baseline = H - PAD.b;
  const hoverPoint = hover === null ? undefined : basePoints[hover];
  const hoverX = hover === null ? undefined : baseXs[hover];
  const animKey = `${first?.date}|${last?.date}|${basePoints.length}`;

  const onMove = (event: PointerEvent<SVGRectElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    const vx = ((event.clientX - rect.left) / rect.width) * W;
    const i = nearestIndex(baseXs, vx);
    setHover(i < 0 ? null : i);
  };

  const legend = (
    <div className="legend">
      {series.map(s => (
        <span key={s.label}><span className={`swatch${s.dashed ? ' swatch-dashed' : ''}`} style={s.dashed ? { color: s.color } : { background: s.color }} aria-hidden="true" />{s.label}</span>
      ))}
      {compact && <span className="legend-unit" aria-hidden="true">{unitLabel}</span>}
    </div>
  );

  return (
    <figure className="line-chart" {...(fill ? { 'data-fill': 'true' } : {})}>
      <div className="chart-frame" ref={frameRef}>
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby={`${id}-cap`}>
          <defs>
            <linearGradient id={`${id}-area`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" style={{ stopColor: 'var(--chart-area-top)' }} />
              <stop offset="100%" style={{ stopColor: 'var(--chart-area-bottom)' }} />
            </linearGradient>
          </defs>
          {ticks.map((tick, i) => (
            <g key={i}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(tick)} y2={y(tick)} className="chart-grid" />
              <text x={PAD.l - 8} y={y(tick) + 4} textAnchor="end" className="chart-axis">{fmtNumber(tick, lang, digits)}</text>
            </g>
          ))}
          {first && <text x={PAD.l} y={H - 8} className="chart-axis">{fmtDate(first.date, lang)}</text>}
          {last && <text x={W - PAD.r} y={H - 8} textAnchor="end" className="chart-axis">{fmtDate(last.date, lang)}</text>}
          <Drawn key={animKey}>
            {area && base && <path d={areaPath(base.xy, baseline)} fill={`url(#${id}-area)`} className="chart-area" />}
            {plotted.map(s => (
              <path key={s.label} d={linePath(s.xy)} fill="none" {...chartLineProps(Boolean(s.dashed))}
                className={`chart-line${s.dashed ? ' chart-line-dashed' : ''}`} style={{ stroke: s.color }} />
            ))}
          </Drawn>
          {hoverX !== undefined && (
            <g className="chart-cursor" aria-hidden="true">
              <line x1={hoverX} x2={hoverX} y1={PAD.t} y2={baseline} />
              {plotted.map(s => {
                const p = hoverPoint ? s.byDate.get(hoverPoint.date) : undefined;
                return p ? <circle key={s.label} cx={p.x} cy={p.y} r={4.5} style={{ fill: s.color }} /> : null;
              })}
            </g>
          )}
          <rect x={PAD.l} y={PAD.t} width={W - PAD.l - PAD.r} height={baseline - PAD.t} fill="transparent"
            onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
        {hoverPoint && hoverX !== undefined && (
          <div className="chart-tip" aria-hidden="true"
            style={{ left: `${(hoverX / W) * 100}%`, transform: `translateX(${hoverX > W * 0.7 ? '-100%' : hoverX < W * 0.3 ? '0%' : '-50%'})` }}>
            <span className="chart-tip-date">{fmtDate(hoverPoint.date, lang)}</span>
            {plotted.map(s => {
              const v = s.byDate.get(hoverPoint.date)?.value;
              return v === undefined ? null : (
                <span key={s.label} className="chart-tip-row">
                  <span className={`swatch${s.dashed ? ' swatch-dashed' : ''}`} style={s.dashed ? { color: s.color } : { background: s.color }} />
                  <span className="chart-tip-label">{s.label}</span>
                  <strong className="num">{fmtNumber(v, lang, digits)}</strong>
                </span>
              );
            })}
          </div>
        )}
      </div>
      <figcaption id={`${id}-cap`} className={compact ? 'sr-only' : 'small muted'}>{caption} ({unitLabel})</figcaption>
      {legend}
    </figure>
  );
}

/** Table alternative; long series are sampled to month-ends to stay readable, endpoints kept. */
export function SeriesTable({ series, lang, unitLabel, caption, digits = 0 }: {
  series: readonly Series[]; lang: Lang; unitLabel: string; caption: string; digits?: number;
}) {
  const base = series[0]?.points ?? [];
  const rows = base.filter((point, i) => {
    if (i === 0 || i === base.length - 1) return true;
    const next = base[i + 1];
    return next !== undefined && next.date.slice(0, 7) !== point.date.slice(0, 7);
  });
  const lookups = series.map(s => new Map(s.points.map(p => [p.date, p.value])));
  return (
    <div className="table-scroll series-table" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            {series.map(s => <th scope="col" key={s.label} className="num-col">{s.label} ({unitLabel})</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.date}>
              <th scope="row">{row.date}</th>
              {lookups.map((lookup, i) => {
                const value = lookup.get(row.date);
                return <td key={i} className="num-col num">{value === undefined ? '—' : fmtNumber(value, lang, digits)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
