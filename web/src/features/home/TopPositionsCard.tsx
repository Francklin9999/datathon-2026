'use client';
/** Largest positions (concentration.topPositions), ranked by weight. Display values, no factIds. */
import Link from 'next/link';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { fmtPct, fmtSignedPct } from '../../lib/format';

export function TopPositionsCard({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const top = overview.concentration.topPositions;
  const maxWeight = Math.max(1e-9, ...top.map(p => p.weightPct));
  return (
    <Card title={tr({ en: 'Largest positions', fr: 'Principales positions' })} className="dash-card"
      actions={<Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'All holdings', fr: 'Toutes les positions' })}</Link>}>
      {top.length === 0
        ? <p className="small muted">{tr({ en: 'No positions returned.', fr: 'Aucune position retournée.' })}</p>
        : (
          <table className="rank-table">
            <caption className="sr-only">{tr({ en: 'Largest positions by weight', fr: 'Principales positions par poids' })}</caption>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">{tr({ en: 'Rank', fr: 'Rang' })}</span></th>
                <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
                <th scope="col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
                <th scope="col" className="num-col">{tr({ en: '1-year return', fr: 'Rendement 1 an' })}</th>
              </tr>
            </thead>
            <tbody>
              {top.map((p, i) => (
                <tr key={p.ticker}>
                  <td className="rank-n num">{i + 1}</td>
                  <th scope="row" className="rank-id">
                    <span className="rank-ticker">{p.ticker}</span>
                    <span className="rank-name" title={p.name}>{p.name}</span>
                  </th>
                  <td className="rank-weight">
                    <span className="meter-track" aria-hidden="true"><span className="meter-fill" style={{ width: `${(p.weightPct / maxWeight) * 100}%` }} /></span>
                    <span className="num">{fmtPct(p.weightPct, lang)}</span>
                  </td>
                  <td className="num-col num">{p.return1yPct === null ? '—' : fmtSignedPct(p.return1yPct, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      <p className="small muted card-foot">{tr({ en: 'Return is historical, in this sample, for each asset alone.', fr: 'Rendement historique, dans cet échantillon, pour chaque actif seul.' })}</p>
    </Card>
  );
}
