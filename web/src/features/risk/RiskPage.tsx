'use client';
import type { Profile, RiskDiagnosticsResponse, OverviewResponse } from '../../contracts/types';
import { useApp, profileKey } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { Risk } from '../portfolio/PortfolioPage';
import { FinancialProviders } from './FinancialProviders';
import { FocusCandidates } from './FocusCandidates';
import { ModelInputs } from './ModelInputs';
import { FinancialInputs } from './FinancialInputs';
import { SensitivityScenario } from './SensitivityScenario';
import { fmtPct } from '../../lib/format';

export function RiskPage() { return <ProfileGate>{profile => <RiskContent key={profile.profileId} profile={profile} />}</ProfileGate>; }
function RiskContent({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang, windowCode } = app;
  const base = profileKey(app);
  const risk = useQuery<RiskDiagnosticsResponse>(base ? `risk|${base}|${windowCode}` : null,
    signal => getApiClient().riskDiagnostics(profile.profileId, windowCode, signal));
  const overview = useQuery<OverviewResponse>(base ? `overview|${base}|${windowCode}` : null,
    signal => getApiClient().overview(profile.profileId, windowCode, signal));
  return <>
    <PageHeader title={tr({ en: `${profile.name}: Risk Intelligence`, fr: `${profile.name} : Analyse des risques` })}>
      <p className="page-sub">{profile.reportingCurrency} · {tr({ en: 'Historical samples, deterministic calculations, inspectable evidence.', fr: 'Échantillons historiques, calculs déterministes, preuves consultables.' })}</p>
    </PageHeader>
    <FocusCandidates profile={profile} />
    <FinancialInputs />
    <FinancialProviders />
    <ModelInputs />
    <SensitivityScenario key={`${profile.profileId}|${profile.version}`} profile={profile} />
    {overview.loading && <Loading />}{overview.error && <ErrorState error={overview.error} onRetry={overview.reload} />}
    {overview.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Portfolio risk overview', fr: 'Aperçu du risque' }, facts: overview.data.facts }}><Risk overview={overview.data} /></FactScopeProvider>}
    {risk.loading && <Loading />}{risk.error && <ErrorState error={risk.error} onRetry={risk.reload} />}
    {risk.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Historical tail and variance diagnostics', fr: 'Diagnostic de queue historique et de variance' }, facts: risk.data.facts }}>
      <Card title={tr({ en: 'Historical tail losses', fr: 'Pertes historiques extrêmes' })}>
        <p>{tr({ en: 'One-day 95% historical VaR and Expected Shortfall use the worst 5% of observed daily returns, rounding the tail count up. Positive values are losses; gains-only samples show zero. At least 100 daily observations are required.', fr: 'La VaR et l’Expected Shortfall historiques à 95 % utilisent les 5 % pires rendements journaliers, avec un nombre d’observations arrondi vers le haut. Les valeurs positives sont des pertes; un échantillon uniquement positif donne zéro. Au moins 100 observations sont requises.' })}</p>
        <dl className="kv-list">{Object.entries(risk.data.metrics).map(([key, m]) => <div className="kv" key={key}><dt className="k">{key === 'risk.var95' ? 'VaR 95%' : 'Expected Shortfall 95%'}</dt><dd className="v">{m.value !== null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : <span>{tr({ en: 'Unavailable', fr: 'Indisponible' })} · {m.unavailableReason}</span>}</dd></div>)}</dl>
        <p className="small muted">{tr({ en: 'These describe this sample, not a maximum possible loss or a forecast. No square-root scaling to longer horizons is applied.', fr: 'Ces mesures décrivent cet échantillon, sans prédire ni plafonner les pertes futures. Aucune extrapolation à un horizon plus long n’est appliquée.' })}</p>
      </Card>
      <Card title={tr({ en: 'Contributions to sample variance', fr: 'Contributions à la variance de l’échantillon' })}>
        <p>{tr({ en: 'Signed Euler shares of portfolio variance from aligned daily returns and current constant weights. Defined shares sum to 100%; negative values indicate diversification in this sample. Zero-variance samples have undefined shares.', fr: 'Parts signées de variance à partir des rendements journaliers alignés et des pondérations actuelles constantes. Les parts définies totalisent 100 %; une part négative indique une diversification dans cet échantillon. Les parts sont indéfinies si la variance est nulle.' })}</p>
        <dl className="kv-list">{Object.entries(risk.data.contributions).map(([ticker, m]) => <div className="kv" key={ticker}><dt className="k">{ticker}</dt><dd className="v">{m.value !== null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : tr({ en: 'Undefined', fr: 'Indéfini' })}</dd></div>)}</dl>
      </Card>
    </FactScopeProvider>}
  </>;
}
