'use client';
/** Home KPI row: five deterministic figures; each one with a factId opens its source (FactChip). */
import { Activity, CalendarRange, TrendingDown, TrendingUp, Wallet, type LucideIcon } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { FactChip } from '../../components/common/FactDrawer';
import { RollingText } from '../../components/ui/RollingText';
import { Skeleton } from '../../components/ui/Skeleton';
import { RISK_LEVEL, labelOf } from '../../lib/labels';
import { factIdFor, fmtMoney, fmtPct, fmtSignedPct } from '../../lib/format';

function Kpi({ icon: Icon, label, note, children }: { icon: LucideIcon; label: string; note?: string; children: ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-head">
        <span className="kpi-icon" aria-hidden="true"><Icon size={16} strokeWidth={1.75} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <div className="kpi-value">{children}</div>
      {note && <p className="kpi-note">{note}</p>}
    </div>
  );
}

export function KpiTiles({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const unavailable = <span className="kpi-missing">{tr({ en: 'Unavailable for this period.', fr: 'Indisponible pour cette période.' })}</span>;
  const pct = (value: number | null, factId: string | undefined, signed: boolean) => {
    if (value === null) return unavailable;
    const text = signed ? fmtSignedPct(value, lang) : fmtPct(value, lang);
    return factId
      ? <FactChip factId={factId} display={text}><RollingText text={text} /></FactChip>
      : <span className="num"><RollingText text={text} /></span>;
  };
  return (
    <section className="kpis-block reveal" style={{ '--i': 1 } as CSSProperties} aria-label={tr({ en: 'Current fictional portfolio', fr: 'Portefeuille fictif actuel' })}>
      <div className="kpis">
        <Kpi icon={Wallet} label={tr({ en: 'Fictional value', fr: 'Valeur fictive' })} note={overview.snapshot.currency}>
          <span className="num"><RollingText text={fmtMoney(overview.snapshot.totalValue, overview.snapshot.currency, lang)} /></span>
        </Kpi>
        <Kpi icon={CalendarRange} label={tr({ en: 'Year to date (historical)', fr: 'Depuis le début de l’année (historique)' })}>
          {pct(overview.returns.ytdPct, factIdFor(overview.returns.factIds, 'ytdPct'), true)}
        </Kpi>
        <Kpi icon={TrendingUp} label={tr({ en: 'Trailing 1 year (historical)', fr: 'Sur 1 an (historique)' })}>
          {pct(overview.returns.y1Pct, factIdFor(overview.returns.factIds, 'y1Pct'), true)}
        </Kpi>
        <Kpi icon={Activity} label={tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })}>
          {pct(overview.risk.volatilityPct, factIdFor(overview.risk.factIds, 'volatilityPct'), false)}
        </Kpi>
        <Kpi icon={TrendingDown} label={tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })} note={tr({ en: 'Peak-to-trough fall, shown as a positive number', fr: 'Baisse du sommet au creux, en valeur positive' })}>
          {pct(overview.risk.maxDrawdownPct, factIdFor(overview.risk.factIds, 'maxDrawdownPct'), false)}
        </Kpi>
      </div>
      <p className="kpis-caption small muted">
        {tr({ en: 'Constant-weight historical figures for today’s fictional holdings, not account gains.', fr: 'Chiffres historiques à pondérations constantes pour les positions fictives actuelles, pas des gains de compte.' })}
        {' '}{tr({ en: 'Measured risk category', fr: 'Catégorie de risque mesurée' })}: {labelOf(RISK_LEVEL, overview.risk.riskCategory, lang)}.
      </p>
    </section>
  );
}

/** Same footprint as the KPI row while the overview loads; announces once for screen readers. */
export function KpiSkeleton({ label }: { label: string }) {
  return (
    <div className="kpis" role="status">
      <span className="sr-only">{label}</span>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} className="kpi" aria-hidden="true">
          <div className="kpi-head"><Skeleton width={30} height={30} radius={10} /><Skeleton width="55%" height={12} /></div>
          <div className="kpi-value"><Skeleton width="70%" height={30} /></div>
        </div>
      ))}
    </div>
  );
}
