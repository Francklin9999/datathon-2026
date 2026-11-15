'use client';
/** Key figures: a label, the figure and what it covers. Each figure with a factId opens its source. */
import type { ReactNode } from 'react';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { FactChip } from '../../components/common/FactDrawer';
import { RollingText } from '../../components/ui/RollingText';
import { Skeleton } from '../../components/ui/Skeleton';
import { RISK_LEVEL, labelOf } from '../../lib/labels';
import { factIdFor, fmtMoney, fmtPct, fmtSignedPct } from '../../lib/format';

function Figure({ label, note, children }: { label: string; note?: string; children: ReactNode }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
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
      ? <FactChip factId={factId} display={text}><RollingText text={text} /></FactChip>
      : <RollingText text={text} />;
  };
  const fixed = tr({ en: 'Fixed horizon', fr: 'Horizon fixe' });
  return (
    <Card title={tr({ en: 'Key figures', fr: 'Chiffres clés' })}>
      <div className="kpis">
        <Figure label={tr({ en: 'Fictional value', fr: 'Valeur fictive' })} note={overview.snapshot.currency}>
          <RollingText text={fmtMoney(overview.snapshot.totalValue, overview.snapshot.currency, lang)} />
        </Figure>
        <Figure label={tr({ en: 'Year to date', fr: 'Depuis janvier' })} note={fixed}>
          {pct(overview.returns.ytdPct, factIdFor(overview.returns.factIds, 'ytdPct'), true)}
        </Figure>
        <Figure label={tr({ en: 'Trailing 1 year', fr: 'Sur 1 an' })} note={fixed}>
          {pct(overview.returns.y1Pct, factIdFor(overview.returns.factIds, 'y1Pct'), true)}
        </Figure>
        <Figure label={tr({ en: 'Annualized volatility', fr: 'Volatilité annualisée' })} note={period}>
          {pct(overview.risk.volatilityPct, factIdFor(overview.risk.factIds, 'volatilityPct'), false)}
        </Figure>
        <Figure label={tr({ en: 'Maximum drawdown', fr: 'Baisse maximale' })} note={`${period}, ${tr({ en: 'peak to trough', fr: 'du sommet au creux' })}`}>
          {pct(overview.risk.maxDrawdownPct, factIdFor(overview.risk.factIds, 'maxDrawdownPct'), false)}
        </Figure>
      </div>
      <p className="kpis-caption">
        {tr({ en: 'Constant-weight historical figures for today’s fictional holdings, not account gains.', fr: 'Chiffres historiques à pondérations constantes pour les positions fictives actuelles, pas des gains de compte.' })}
        {' '}{tr({ en: 'Measured risk category', fr: 'Catégorie de risque mesurée' })} ({period}): {labelOf(RISK_LEVEL, overview.risk.riskCategory, lang).toLowerCase()}
      </p>
    </Card>
  );
}

/** Same footprint while the overview loads; announced once for screen readers. */
export function KeyFiguresSkeleton({ label }: { label: string }) {
  return (
    <div className="card" role="status">
      <span className="sr-only">{label}</span>
      <div className="kpis" aria-hidden="true">
        {[0, 1, 2, 3, 4].map(i => (
          <div key={i} className="kpi">
            <Skeleton width="55%" height={12} />
            <Skeleton width="70%" height={26} />
          </div>
        ))}
      </div>
    </div>
  );
}
