'use client';
import type { GoalFundingResponse, Profile } from '../../contracts/types';
import { useApp, profileKey } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactChip, FactScopeProvider } from '../../components/common/FactDrawer';
import { fmtMoney } from '../../lib/format';

export function GoalFunding({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang } = app;
  const goals = useQuery<GoalFundingResponse>(profileKey(app) ? `goals|${profileKey(app)}` : null,
    signal => getApiClient().goalFunding(profile.profileId, signal));
  if (!profile.investorContext?.objectives?.length) return null;
  return <Card title={tr({ en: 'Goal funding scenarios', fr: 'Scénarios de financement des objectifs' })}>
    <p>{tr({ en: 'These scenarios use only the capital, contribution and return assumptions you enter in Profiles. They are nominal illustrations, not forecasts or proof of feasibility. Taxes, fees, inflation and future withdrawals are excluded. Contributions occur at each complete year-end.', fr: 'Ces scénarios utilisent uniquement vos hypothèses de capital, contribution et rendement saisies dans Profils. Ce sont des illustrations nominales, sans prévision ni garantie de faisabilité. Fiscalité, frais, inflation et retraits sont exclus. Les contributions ont lieu à chaque fin d’année complète.' })}</p>
    {goals.loading && <Loading />}{goals.error && <ErrorState error={goals.error} onRetry={goals.reload} />}
    {goals.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Explicit-assumption scenarios', fr: 'Scénarios fondés sur vos hypothèses' }, facts: goals.data.facts }}>
      {goals.data.overallocated && <p role="alert">{tr({ en: 'Allocated capital exceeds this portfolio value. Projections are withheld to avoid counting the same capital twice.', fr: 'Le capital affecté dépasse la valeur du portefeuille. Les projections sont retenues pour éviter un double comptage.' })}</p>}
      {goals.data.goals.map((g, i) => <div className="kv" key={i}><dt className="k">{g.name}</dt><dd className="v">
        {g.projectedValue === null ? tr({ en: 'Enter target, allocated capital, yearly contribution and assumed return to calculate.', fr: 'Saisissez la cible, le capital affecté, la contribution et le rendement supposé pour calculer.' }) : <>
          {tr({ en: 'Scenario balance', fr: 'Solde du scénario' })}{' '}<FactChip factId={g.factIds['goal.projected_value']!} display={fmtMoney(g.projectedValue, goals.data!.currency, lang)} />{' · '}
          {tr({ en: 'Remaining funding gap', fr: 'Écart de financement restant' })}{' '}<FactChip factId={g.factIds['goal.funding_gap']!} display={fmtMoney(g.fundingGap!, goals.data!.currency, lang)} />
        </>}
      </dd></div>)}
    </FactScopeProvider>}
  </Card>;
}
