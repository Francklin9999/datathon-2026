'use client';
/**
 * Historical tail-loss (one-day 95% VaR and Expected Shortfall) and variance-contribution diagnostics
 * for the Portfolio Risk tab (`risk|…|window` cache key; /risk-intelligence/ now redirects here).
 */
import type { Profile, RiskDiagnosticsResponse } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { FactChip, FactScopeProvider } from '../../components/common/FactDrawer';
import { Note } from '../../components/common/Note';
import { fmtPct } from '../../lib/format';
import { labelOf } from '../../lib/labels';

const METRIC_LABEL: Record<string, { en: string; fr: string }> = {
  'risk.var95': { en: 'Value at risk, 95%, one day', fr: 'Valeur à risque, 95 %, un jour' },
  'risk.es95': { en: 'Expected shortfall, 95%, one day', fr: 'Perte attendue au-delà, 95 %, un jour' },
};

export function RiskDiagnostics({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang, windowCode } = app;
  const base = profileKey(app);
  const risk = useQuery<RiskDiagnosticsResponse>(base ? `risk|${base}|${windowCode}` : null,
    signal => getApiClient().riskDiagnostics(profile.profileId, windowCode, signal));
  if (risk.loading) return <Loading />;
  if (risk.error) {
    return <ErrorState error={risk.error} onRetry={risk.reload}
      title={tr({ en: 'Tail-loss and variance diagnostics are unavailable', fr: 'Le diagnostic des pertes extrêmes et de la variance est indisponible' })} />;
  }
  if (!risk.data) return null;
  const data = risk.data;
  const contributions = Object.entries(data.contributions);
  return (
    <FactScopeProvider scope={{ kind: 'local', label: { en: 'Historical tail and variance diagnostics', fr: 'Diagnostic de queue historique et de variance' }, facts: data.facts }}>
      <div className="grid-2">
        <Card id="tail-loss" tour="tail-loss" title={tr({ en: 'Bad-day losses', fr: 'Pertes des mauvais jours' })}
          info={tr({ en: 'One-day 95% historical VaR and Expected Shortfall use the worst 5% of observed daily returns, rounding the tail count up. Positive values are losses; a gains-only sample shows zero. At least 100 daily observations are needed. No scaling to longer horizons is applied.', fr: 'La VaR et l’Expected Shortfall historiques à 95 % sur un jour utilisent les 5 % pires rendements journaliers, avec un nombre d’observations arrondi vers le haut. Les valeurs positives sont des pertes ; un échantillon uniquement positif donne zéro. Au moins 100 observations sont requises. Aucune extrapolation à un horizon plus long n’est appliquée.' })}>
          <p className="small muted">{tr({ en: 'How much the portfolio lost on its worst 5% of days in this period.', fr: 'Ce que le portefeuille a perdu lors de ses 5 % pires jours sur cette période.' })}</p>
          <dl className="kv-list">
            {Object.entries(data.metrics).map(([key, m]) => (
              <div className="kv" key={key}>
                <dt className="k">{METRIC_LABEL[key] ? tr(METRIC_LABEL[key]) : labelOf({}, key.replace(/^risk\./, ''), lang)}</dt>
                <dd className="v">{m.value !== null && m.factId
                  ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} />
                  : <span className="small muted">{tr({ en: 'Unavailable', fr: 'Indisponible' })}{m.unavailableReason ? ` · ${labelOf({}, m.unavailableReason, lang)}` : ''}</span>}</dd>
              </div>
            ))}
          </dl>
          <Note>{tr({ en: 'This describes the past sample, not the most you could lose or a forecast.', fr: 'Cela décrit l’échantillon passé, ni la perte maximale possible ni une prévision.' })}</Note>
        </Card>
        <Card id="variance-contribution" tour="variance-contribution" title={tr({ en: 'Where the swings come from', fr: 'D’où viennent les variations' })}
          info={tr({ en: 'Signed Euler shares of portfolio variance from aligned daily returns and current constant weights. Defined shares sum to 100%; zero-variance samples have undefined shares.', fr: 'Parts signées de variance (Euler) à partir des rendements journaliers alignés et des pondérations actuelles constantes. Les parts définies totalisent 100 % ; elles sont indéfinies si la variance est nulle.' })}>
          <p className="small muted">{tr({ en: 'Share of the portfolio’s day-to-day variance from each holding. A negative share means it steadied the rest.', fr: 'Part de la variance quotidienne du portefeuille due à chaque position. Une part négative signifie qu’elle a stabilisé le reste.' })}</p>
          {contributions.length === 0
            ? <p className="small muted">{tr({ en: 'No contributions for this period', fr: 'Aucune contribution pour cette période' })}</p>
            : (
              <dl className="kv-list">
                {contributions.map(([ticker, m]) => (
                  <div className="kv" key={ticker}>
                    <dt className="k"><span className="ticker">{ticker}</span></dt>
                    <dd className="v">{m.value !== null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : <span className="small muted">{tr({ en: 'Undefined', fr: 'Indéfini' })}</span>}</dd>
                  </div>
                ))}
              </dl>
            )}
        </Card>
      </div>
    </FactScopeProvider>
  );
}
