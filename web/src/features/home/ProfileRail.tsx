'use client';
/**
 * Right-hand column of the Home dashboard: longer horizons, stress test and diversification.
 * Window-independent context that complements the KPI row; figures with factIds stay FactChips.
 */
import { Hourglass, Layers, ShieldAlert, type LucideIcon } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import type { OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { FactChip } from '../../components/common/FactDrawer';
import { factIdFor, fmtNumber, fmtSignedPct } from '../../lib/format';

function RailCard({ icon: Icon, title, accent = false, children, note }: {
  icon: LucideIcon; title: string; accent?: boolean; children: ReactNode; note?: string;
}) {
  return (
    <section className={`card rail-card${accent ? ' rail-accent' : ''}`}>
      <h2 className="rail-title"><Icon aria-hidden="true" size={16} strokeWidth={1.75} />{title}</h2>
      <dl className="rail-figures">{children}</dl>
      {note && <p className="rail-note">{note}</p>}
    </section>
  );
}

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rail-figure">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function ProfileRail({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const missing = <span className="kpi-missing">{tr({ en: 'Unavailable', fr: 'Indisponible' })}</span>;
  const signed = (value: number | null, map: Record<string, string>, key: string) => {
    if (value === null) return missing;
    const text = fmtSignedPct(value, lang);
    const factId = factIdFor(map, key);
    return factId ? <FactChip factId={factId} display={text} /> : <span className="num">{text}</span>;
  };
  const { returns, risk, concentration } = overview;
  return (
    <div className="dash-rail reveal" style={{ '--i': 2 } as CSSProperties}>
      <RailCard icon={Hourglass} accent title={tr({ en: 'Longer horizons', fr: 'Horizons plus longs' })}
        note={tr({ en: 'Total change over each period, not annualized. Today’s weights held constant, historical in this sample.', fr: 'Variation totale sur chaque période, non annualisée. Pondérations actuelles maintenues, historique dans cet échantillon.' })}>
        <Figure label={tr({ en: 'Total, 3 years', fr: 'Total sur 3 ans' })}>{signed(returns.y3Pct, returns.factIds, 'y3Pct')}</Figure>
        <Figure label={tr({ en: 'Total, 5 years', fr: 'Total sur 5 ans' })}>{signed(returns.y5Pct, returns.factIds, 'y5Pct')}</Figure>
      </RailCard>
      <RailCard icon={ShieldAlert} title={tr({ en: 'Stress test', fr: 'Test de résistance' })}
        note={tr({ en: 'Today’s weights replayed through past markets.', fr: 'Pondérations actuelles rejouées sur les marchés passés.' })}>
        <Figure label={tr({ en: '2022 replay', fr: 'Rejeu 2022' })}>{signed(risk.stress2022Pct, risk.factIds, 'stress2022Pct')}</Figure>
        {risk.worst12mPct !== null && (
          <Figure label={tr({ en: 'Worst 12 months', fr: 'Pires 12 mois' })}>{signed(risk.worst12mPct, risk.factIds, 'worst12mPct')}</Figure>
        )}
      </RailCard>
      <RailCard icon={Layers} title={tr({ en: 'Diversification', fr: 'Diversification' })}
        note={tr({ en: 'Effective number of equal-weight positions; HHI is the sum of squared weights.', fr: 'Nombre effectif de positions équipondérées ; le HHI est la somme des poids au carré.' })}>
        <Figure label={tr({ en: 'Effective positions', fr: 'Positions effectives' })}><span className="num">{fmtNumber(concentration.effectiveN, lang, 1)}</span></Figure>
        <Figure label="HHI"><span className="num">{fmtNumber(concentration.hhi, lang, 3)}</span></Figure>
      </RailCard>
    </div>
  );
}
