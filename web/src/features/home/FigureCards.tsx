'use client';
/**
 * Small figure widgets: longer horizons, stress test and diversification. Real overview data;
 * figures with factIds stay FactChips (dotted underline opens the source).
 */
import type { ReactNode } from 'react';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { FactChip } from '../../components/common/FactDrawer';
import { factIdFor, fmtNumber, fmtSignedPct } from '../../lib/format';

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function useSigned() {
  const { tr, lang } = useApp();
  return (value: number | null, map: Record<string, string>, key: string) => {
    if (value === null) return <span className="kpi-missing">{tr({ en: 'Unavailable', fr: 'Indisponible' })}</span>;
    const text = fmtSignedPct(value, lang);
    const factId = factIdFor(map, key);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
}

export function HorizonsCard({ overview }: { overview: OverviewResponse }) {
  const { tr } = useApp();
  const signed = useSigned();
  const { returns } = overview;
  return (
    <Card title={tr({ en: 'Longer horizons', fr: 'Horizons plus longs' })}>
      <dl className="figure-list">
        <Figure label={tr({ en: 'Total, 3 years', fr: 'Total sur 3 ans' })}>{signed(returns.y3Pct, returns.factIds, 'y3Pct')}</Figure>
        <Figure label={tr({ en: 'Total, 5 years', fr: 'Total sur 5 ans' })}>{signed(returns.y5Pct, returns.factIds, 'y5Pct')}</Figure>
      </dl>
      <p className="figure-note">{tr({ en: 'Total change over each period, not annualized. Today’s weights held constant, historical in this sample.', fr: 'Variation totale sur chaque période, non annualisée. Pondérations actuelles maintenues, historique dans cet échantillon.' })}</p>
    </Card>
  );
}

export function StressCard({ overview }: { overview: OverviewResponse }) {
  const { tr } = useApp();
  const signed = useSigned();
  const { risk } = overview;
  return (
    <Card title={tr({ en: 'Stress test', fr: 'Test de résistance' })}>
      <dl className="figure-list">
        <Figure label={tr({ en: '2022 replay', fr: 'Rejeu 2022' })}>{signed(risk.stress2022Pct, risk.factIds, 'stress2022Pct')}</Figure>
        {risk.worst12mPct !== null && (
          <Figure label={tr({ en: 'Worst 12 months in the period', fr: 'Pires 12 mois de la période' })}>{signed(risk.worst12mPct, risk.factIds, 'worst12mPct')}</Figure>
        )}
      </dl>
      <p className="figure-note">{tr({ en: 'Today’s weights replayed through past markets.', fr: 'Pondérations actuelles rejouées sur les marchés passés.' })}</p>
    </Card>
  );
}

export function DiversificationCard({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const { concentration } = overview;
  return (
    <Card title={tr({ en: 'Diversification', fr: 'Diversification' })}>
      <dl className="figure-list">
        <Figure label={tr({ en: 'Effective positions', fr: 'Positions effectives' })}><span className="num">{fmtNumber(concentration.effectiveN, lang, 1)}</span></Figure>
        <Figure label="HHI"><span className="num">{fmtNumber(concentration.hhi, lang, 3)}</span></Figure>
      </dl>
      <p className="figure-note">{tr({ en: 'Effective number of equal-weight positions; HHI is the sum of squared weights.', fr: 'Nombre effectif de positions équipondérées ; le HHI est la somme des poids au carré.' })}</p>
    </Card>
  );
}
