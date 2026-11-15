'use client';
/** Positions in scope (snapshot.positions filtered by asset class and minimum weight), largest first. */
import Link from 'next/link';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { CountUp } from '../../components/ui/CountUp';
import { ASSET_CLASS, labelOf } from '../../lib/labels';
import { fmtMoney, fmtPct } from '../../lib/format';
import { filterPositions, type DashboardScope } from '../../lib/ui/scope';

export function PositionsCard({ overview, scope }: { overview: OverviewResponse; scope: DashboardScope }) {
  const { tr, lang } = useApp();
  const all = overview.snapshot.positions;
  const shown = filterPositions(all, scope);
  const share = shown.reduce((sum, p) => sum + p.weightPct, 0);
  return (
    <Card title={tr({ en: 'Positions', fr: 'Positions' })} tour="positions"
      actions={<Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'All holdings', fr: 'Toutes les positions' })}</Link>}>
      {shown.length === 0
        ? <p className="small muted">{tr({ en: 'No position matches this scope', fr: 'Aucune position ne correspond à ce périmètre' })}</p>
        : (
          <table className="rank-table">
            <caption className="sr-only">{tr({ en: 'Positions in scope by weight', fr: 'Positions du périmètre par poids' })}</caption>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">{tr({ en: 'Rank', fr: 'Rang' })}</span></th>
                <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
                <th scope="col">{tr({ en: 'Class', fr: 'Classe' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
                <th scope="col" className="num-col">{tr({ en: 'Value', fr: 'Valeur' })}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p, i) => (
                <tr key={p.ticker}>
                  <td className="rank-n">{i + 1}</td>
                  <th scope="row" className="rank-id">
                    <span className="rank-ticker">{p.ticker}</span>
                    <span className="rank-name" title={p.name}>{p.name}</span>
                  </th>
                  <td>{labelOf(ASSET_CLASS, p.assetClass, lang)}</td>
                  <td className="num-col"><CountUp text={fmtPct(p.weightPct, lang)} /></td>
                  <td className="num-col"><CountUp text={fmtMoney(p.marketValue, overview.snapshot.currency, lang)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      <p className="list-count">
        {shown.length === all.length
          ? tr({ en: `${all.length} positions`, fr: `${all.length} positions` })
          : tr({ en: `${shown.length} of ${all.length} positions, ${fmtPct(share, lang)} of the portfolio`, fr: `${shown.length} positions sur ${all.length}, ${fmtPct(share, lang)} du portefeuille` })}
      </p>
    </Card>
  );
}
