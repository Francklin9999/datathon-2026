'use client';
/**
 * Dependency-free SVG line chart with legend and units outside any tooltip, plus a table
 * alternative (DESIGN.md "accessible table alternative for charts"). Values are drawn as given.
 */
import { useId } from 'react';
import type { Lang } from '../../contracts/types';
import { fmtDate, fmtNumber } from '../../lib/format';

export interface Series { label: string; points: readonly { date: string; value: number }[]; color: string; dashed?: boolean }

const W = 720;
const H = 240;
const PAD = { l: 64, r: 16, t: 12, b: 28 };
const time = (date: string) => Date.parse(`${date}T00:00:00Z`);

export function LineChart({ series, lang, unitLabel, caption }: {
  series: readonly Series[]; lang: Lang; unitLabel: string; caption: string;
}) {
  const id = useId();
  const all = series.flatMap(s => s.points);
  if (all.length < 2) return null;
  const times = all.map(p => time(p.date));
  const values = all.map(p => p.value);
  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const vMin = Math.min(...values);
  const vMax = Math.max(...values);
  const vPad = (vMax - vMin) * 0.05 || 1;
  const lo = vMin - vPad;
  const hi = vMax + vPad;
  const x = (t: number) => PAD.l + ((t - tMin) / Math.max(1, tMax - tMin)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const ticks = [lo, (lo + hi) / 2, hi];
  const basePoints = series[0]?.points ?? [];
  const first = basePoints[0];
  const last = basePoints[basePoints.length - 1];
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-labelledby={`${id}-cap`}>
        {ticks.map((tick, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(tick)} y2={y(tick)} stroke="#E6EBEF" />
            <text x={PAD.l - 6} y={y(tick) + 4} textAnchor="end" className="chart-axis">{fmtNumber(tick, lang, 0)}</text>
          </g>
        ))}
        {first && <text x={PAD.l} y={H - 8} className="chart-axis">{fmtDate(first.date, lang)}</text>}
        {last && <text x={W - PAD.r} y={H - 8} textAnchor="end" className="chart-axis">{fmtDate(last.date, lang)}</text>}
        {series.map(s => (
          <polyline key={s.label} fill="none" stroke={s.color} strokeWidth={2}
            {...(s.dashed ? { strokeDasharray: '5 4' } : {})}
            points={s.points.map(p => `${x(time(p.date)).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')} />
        ))}
      </svg>
      <figcaption id={`${id}-cap`} className="small muted">{caption} ({unitLabel})</figcaption>
      <div className="legend">
        {series.map(s => (
          <span key={s.label}><span className="swatch" style={{ background: s.color }} aria-hidden="true" />{s.label}</span>
        ))}
      </div>
    </figure>
  );
}

/** Table alternative; long series are sampled to month-ends to stay readable, endpoints kept. */
export function SeriesTable({ series, lang, unitLabel, caption }: {
  series: readonly Series[]; lang: Lang; unitLabel: string; caption: string;
}) {
  const base = series[0]?.points ?? [];
  const rows = base.filter((point, i) => {
    if (i === 0 || i === base.length - 1) return true;
    const next = base[i + 1];
    return next !== undefined && next.date.slice(0, 7) !== point.date.slice(0, 7);
  });
  const lookups = series.map(s => new Map(s.points.map(p => [p.date, p.value])));
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
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
                return <td key={i} className="num-col num">{value === undefined ? '—' : fmtNumber(value, lang, 0)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
