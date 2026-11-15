'use client';
/**
 * Automations widget: the active standing strategies of this profile (saved on the Strategies page)
 * with what each would do next, from the same deterministic simulation (shared through the query
 * cache). Nothing is executed; a strategy is a proposal the investor can inspect.
 */
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { readPref } from '../../lib/session';
import { readStrategies, type SavedStrategy } from '../../lib/strategies';
import { KIND_ICON, useStrategySimulation } from '../strategies/StrategiesPage';

function Automation({ profile, strategy }: { profile: Profile; strategy: SavedStrategy }) {
  const { tr } = useApp();
  const sim = useStrategySimulation(profile, strategy.config);
  const Icon = KIND_ICON[strategy.config.kind];
  const next = sim.data?.nextAction;
  return (
    <li className="auto-item">
      <span className={`strategy-icon kind-${strategy.config.kind}`} aria-hidden="true"><Icon size={17} strokeWidth={2} /></span>
      <span className="auto-name">{strategy.name}</span>
      <span className="auto-next" {...(next?.due ? { 'data-due': 'true' } : {})}>
        {next ? tr(next.summary) : sim.error ? tr({ en: 'Simulation unavailable', fr: 'Simulation indisponible' }) : tr({ en: 'Simulating…', fr: 'Simulation…' })}
      </span>
    </li>
  );
}

export function AutomationsCard({ profile }: { profile: Profile }) {
  const { tr } = useApp();
  const [list, setList] = useState<SavedStrategy[]>([]);
  useEffect(() => { setList(readStrategies(profile.profileId, readPref)); }, [profile.profileId]);
  const active = list.filter(s => s.active);
  return (
    <Card title={tr({ en: 'Automations', fr: 'Automatisations' })} tour="automations"
      info={tr({ en: 'Standing strategies simulated on this portfolio’s history. Proposals only: no order is placed.', fr: 'Stratégies permanentes simulées sur l’historique de ce portefeuille. Propositions seulement : aucun ordre n’est passé.' })}
      actions={list.length > 0 ? <Link href="/strategies/" className="btn ghost btn-sm">{tr({ en: 'Manage', fr: 'Gérer' })}</Link> : undefined}>
      {active.length > 0 ? (
        <ul className="auto-list">{active.map(s => <Automation key={s.id} profile={profile} strategy={s} />)}</ul>
      ) : (
        <div className="auto-empty">
          <p className="small muted">{list.length > 0
            ? tr({ en: 'Every strategy is paused.', fr: 'Toutes les stratégies sont en pause.' })
            : tr({ en: 'Rebalance, invest regularly or protect against a fall, tested on history.', fr: 'Rééquilibrer, investir régulièrement ou se protéger d’une baisse, testé sur l’historique.' })}</p>
          <Link href="/strategies/" className="btn btn-sm ink"><Plus aria-hidden="true" size={14} strokeWidth={2.25} />{tr({ en: 'Create a strategy', fr: 'Créer une stratégie' })}</Link>
        </div>
      )}
    </Card>
  );
}
