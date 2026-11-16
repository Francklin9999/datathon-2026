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
import { CountUp } from '../../components/ui/CountUp';
import { factIdFor, fmtNumber, fmtSignedPct } from '../../lib/format';
import { LOWEST_12M_INFO, LOWEST_12M_LABEL, lowestRollingNote } from '../../lib/ui/figures';

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
    <Card title={tr({ en: 'Longer horizons', fr: 'Horizons plus longs' })}
      info={tr({ en: 'Total change over each period, not annualized.', fr: 'Variation totale sur chaque période, non annualisée.' })}>
      <dl className="figure-list">
        <Figure label={tr({ en: 'Total, 3 years', fr: 'Total sur 3 ans' })}>{signed(returns.y3Pct, returns.factIds, 'y3Pct')}</Figure>
        <Figure label={tr({ en: 'Total, 5 years', fr: 'Total sur 5 ans' })}>{signed(returns.y5Pct, returns.factIds, 'y5Pct')}</Figure>
      </dl>
    </Card>
  );
}

export function StressCard({ overview }: { overview: OverviewResponse }) {
  const { tr } = useApp();
  const signed = useSigned();
  const { risk } = overview;
  const note = lowestRollingNote(risk.worst12mPct);
  return (
    <Card title={tr({ en: 'Stress test', fr: 'Test de résistance' })}
      info={`${tr({ en: 'Today’s weights replayed through past markets.', fr: 'Pondérations actuelles rejouées sur les marchés passés.' })} ${tr(LOWEST_12M_INFO)}`}>
      <dl className="figure-list">
        <Figure label={tr({ en: '2022 replay', fr: 'Rejeu 2022' })}>{signed(risk.stress2022Pct, risk.factIds, 'stress2022Pct')}</Figure>
        {risk.worst12mPct !== null && (
          <Figure label={tr(LOWEST_12M_LABEL)}>{signed(risk.worst12mPct, risk.factIds, 'worst12mPct')}</Figure>
        )}
      </dl>
      {note && <p className="figure-note">{tr(note)}</p>}
    </Card>
  );
}

export function DiversificationCard({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const { concentration } = overview;
  return (
    <Card title={tr({ en: 'Diversification', fr: 'Diversification' })}
      info={tr({ en: `The weights behave like this many equal positions (HHI ${fmtNumber(concentration.hhi, lang, 3)}).`, fr: `Les poids se comportent comme ce nombre de positions égales (HHI ${fmtNumber(concentration.hhi, lang, 3)}).` })}>
      <dl className="figure-list">
        <Figure label={tr({ en: 'Effective positions', fr: 'Positions effectives' })}><span className="num"><CountUp text={fmtNumber(concentration.effectiveN, lang, 1)} /></span></Figure>
      </dl>
    </Card>
  );
}
