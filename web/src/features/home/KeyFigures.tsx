'use client';
/**
 * Key figures as tiles: an icon, a label, the figure and what it covers. The fictional capital is the
 * one cobalt tile on the page. Each figure with a factId opens its source.
 */
import { Activity, TrendingDown, TrendingUp, Wallet, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { FactChip } from '../../components/common/FactDrawer';
import { CountUp } from '../../components/ui/CountUp';
import { Skeleton } from '../../components/ui/Skeleton';
import { RISK_LEVEL, labelOf } from '../../lib/labels';
import { factIdFor, fmtMoney, fmtPct, fmtSignedPct } from '../../lib/format';

function Figure({ label, note, icon: Icon, accent = false, children }: {
  label: string; note?: string; icon: LucideIcon; accent?: boolean; children: ReactNode;
}) {
  return (
    <div className={`kpi${accent ? ' kpi-accent' : ''}`}>
      <span className="kpi-head">
        <span className="kpi-icon" aria-hidden="true"><Icon size={16} strokeWidth={1.75} /></span>
        <span className="kpi-label">{label}</span>
      </span>
      <span className="kpi-value">{children}</span>
      {note && <span className="kpi-note">{note}</span>}
    </div>
  );
}

export function KeyFigures({ overview, period }: { overview: OverviewResponse; period: string }) {
  const { tr, lang } = useApp();
  const unavailable = <span className="kpi-missing">{tr({ en: 'Unavailable for this period', fr: 'Indisponible pour cette période' })}</span>;
  const pct = (value: number | null, factId: string | undefined, signed: boolean) => {
    if (value === null) return unavailable;
    const text = signed ? fmtSignedPct(value, lang) : fmtPct(value, lang);
    return factId
      ? <FactChip factId={factId} display={text} />
      : <CountUp text={text} />;
  };
  const selectedId = overview.returns.factIds.selectedPct;
  const selectedValue = selectedId ? overview.facts[selectedId]?.value : null;
  const positions = overview.snapshot.positions.length;
  return (
    <Card title={tr({ en: 'Key figures', fr: 'Chiffres clés' })} tour="kpis">
      <div className="kpis">
        {/* The profile's fictional capital (snapshot.totalValue), not a value today: the history chart
            re-bases this same amount to the first day of the period (contracts/api.md, performance). */}
        <Figure accent icon={Wallet} label={tr({ en: 'Fictional capital', fr: 'Capital fictif' })}
          note={tr({ en: `${positions} positions, ${overview.snapshot.currency}`, fr: `${positions} positions, ${overview.snapshot.currency}` })}>
          <CountUp text={fmtMoney(overview.snapshot.totalValue, overview.snapshot.currency, lang)} />
        </Figure>
        <Figure icon={TrendingUp} label={tr({ en: 'Historical return', fr: 'Rendement historique' })} note={period}>
          {pct(typeof selectedValue === 'number' ? selectedValue : null, selectedId, true)}
        </Figure>
        <Figure icon={Activity} label={tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })} note={period}>
          {pct(overview.risk.volatilityPct, factIdFor(overview.risk.factIds, 'volatilityPct'), false)}
        </Figure>
        <Figure icon={TrendingDown} label={tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })} note={tr({ en: `${period}, peak to trough`, fr: `${period}, du sommet au creux` })}>
          {pct(overview.risk.maxDrawdownPct, factIdFor(overview.risk.factIds, 'maxDrawdownPct'), false)}
        </Figure>
      </div>
      <p className="kpis-caption">
        {tr({ en: 'Today’s weights applied to past prices, not account gains.', fr: 'Pondérations actuelles appliquées aux prix passés, pas des gains réels.' })}
        {' '}{tr({ en: 'Measured risk', fr: 'Risque mesuré' })}: {labelOf(RISK_LEVEL, overview.risk.riskCategory, lang).toLowerCase()}.
      </p>
    </Card>
  );
}

/** Same footprint while the overview loads; announced once for screen readers. */
export function KeyFiguresSkeleton({ label }: { label: string }) {
  return (
    <div className="card card-bare" role="status">
      <span className="sr-only">{label}</span>
      <div className="kpis" aria-hidden="true">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="kpi">
            <Skeleton width="55%" height={12} />
            <Skeleton width="70%" height={26} />
          </div>
        ))}
      </div>
    </div>
  );
}
