'use client';
/**
 * Positions in scope (snapshot.positions filtered by asset class and minimum weight), largest first.
 * The widget shows as many rows as its height holds (resizing it shows more); "Show all N" and the
 * details button open the whole list with values and the link to the portfolio.
 */
import Link from 'next/link';
import type { Currency, OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { Sheet, useSheet } from '../../components/common/Sheet';
import { CountUp } from '../../components/ui/CountUp';
import { useElementSize } from '../../components/ui/useElementSize';
import { ASSET_CLASS, labelOf } from '../../lib/labels';
import { fmtMoney, fmtPct } from '../../lib/format';
import { fitCount } from '../../lib/ui/layout';
import { filterPositions, type DashboardScope } from '../../lib/ui/scope';

/** Row, header and "Show all N" heights in px (dashboard.css .rank-table, .more-row), a pixel of slack for borders. */
const ROW_PX = 45;
const HEAD_PX = 26;
const MORE_PX = 36;

type Position = OverviewResponse['snapshot']['positions'][number];

function PositionsTable({ rows, currency, withValue }: { rows: readonly Position[]; currency: Currency; withValue: boolean }) {
  const { tr, lang } = useApp();
  return (
    <table className="rank-table">
      <caption className="sr-only">{tr({ en: 'Positions in scope by weight', fr: 'Positions du périmètre par poids' })}</caption>
      <thead>
        <tr>
          <th scope="col" className="rank-n"><span className="sr-only">{tr({ en: 'Rank', fr: 'Rang' })}</span></th>
          <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
          <th scope="col" className="rank-class">{tr({ en: 'Class', fr: 'Classe' })}</th>
          <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
          {withValue && <th scope="col" className="num-col">{tr({ en: 'Value', fr: 'Valeur' })}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => (
          <tr key={p.ticker}>
            <td className="rank-n">{i + 1}</td>
            <th scope="row" className="rank-id">
              <span className="rank-ticker">{p.ticker}</span>
              <span className="rank-name" title={p.name}>{p.name}</span>
            </th>
            <td className="rank-class">{labelOf(ASSET_CLASS, p.assetClass, lang)}</td>
            <td className="num-col"><CountUp text={fmtPct(p.weightPct, lang)} /></td>
            {withValue && <td className="num-col">{fmtMoney(p.marketValue, currency, lang)}</td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PositionsCard({ overview, scope }: { overview: OverviewResponse; scope: DashboardScope }) {
  const { tr, lang } = useApp();
  const all = overview.snapshot.positions;
  const shown = filterPositions(all, scope);
  const share = shown.reduce((sum, p) => sum + p.weightPct, 0);
  const { ref, size } = useElementSize<HTMLDivElement>();
  const sheet = useSheet();
  // Rows that fit; when some are left out, keep room for the "Show all N" button.
  const fitAll = size ? fitCount(size.h - HEAD_PX, ROW_PX, shown.length) : Math.min(shown.length, 5);
  const visible = fitAll < shown.length && size ? fitCount(size.h - HEAD_PX - MORE_PX, ROW_PX, shown.length) : fitAll;
  const hidden = shown.length - visible;
  const summary = shown.length === all.length
    ? tr({ en: `${all.length} positions`, fr: `${all.length} positions` })
    : tr({ en: `${shown.length} of ${all.length} positions, ${fmtPct(share, lang)} of the portfolio`, fr: `${shown.length} positions sur ${all.length}, ${fmtPct(share, lang)} du portefeuille` });
  const full = () => (
    <>
      <p className="figure-note">{summary}</p>
      <PositionsTable rows={shown} currency={overview.snapshot.currency} withValue />
      <p><Link href="/portfolio/" className="btn ghost btn-sm">{tr({ en: 'All holdings', fr: 'Toutes les positions' })}</Link></p>
    </>
  );
  return (
    <Card title={tr({ en: 'Positions', fr: 'Positions' })} tour="positions" details={{ render: full }}>
      {shown.length === 0
        ? <p className="small muted">{tr({ en: 'No position matches this scope', fr: 'Aucune position ne correspond à ce périmètre' })}</p>
        : (
          <div ref={ref} className="fit-box">
            <PositionsTable rows={shown.slice(0, visible)} currency={overview.snapshot.currency} withValue={false} />
            {hidden > 0 && (
              <div className="more-row">
                <button type="button" className="more-btn" aria-haspopup="dialog" onClick={event => sheet.show(event.currentTarget)}
                  title={tr({ en: `${hidden} more not shown here`, fr: `${hidden} de plus non affichées ici` })}>
                  {tr({ en: `Show all ${shown.length}`, fr: `Tout afficher (${shown.length})` })}
                </button>
              </div>
            )}
          </div>
        )}
      <Sheet open={sheet.open} origin={sheet.origin} onClose={sheet.hide} title={tr({ en: 'Positions', fr: 'Positions' })}>
        {sheet.open && full()}
      </Sheet>
    </Card>
  );
}
