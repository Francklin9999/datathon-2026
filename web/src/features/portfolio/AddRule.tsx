'use client';
/**
 * One "Add a rule" card for the three rule builders (exposure cap, cap or floor, conditional): a kind
 * selector shows one form at a time instead of three stacked cards. Saved rules join the Plan rules
 * table above. Default personas are read-only templates, so they get a one-line pointer to duplicate.
 */
import Link from 'next/link';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { ExposureLimits } from './ExposureLimits';
import { CustomPolicies } from './CustomPolicies';
import { ConditionalPolicies } from './ConditionalPolicies';

type RuleKind = 'exposure' | 'weight' | 'conditional';

export function AddRule({ profile }: { profile: Profile }) {
  const { tr, feature } = useApp();
  const [kind, setKind] = useState<RuleKind>('exposure');
  // Every builder is a profile_creator write; with the flag off saved rules stay readable in Plan rules.
  if (!feature('profile_creator')) return null;
  const title = tr({ en: 'Add a rule', fr: 'Ajouter une règle' });
  const info = tr({ en: 'Rules you add are your own assumptions, checked by code in the portfolio and in every decision. They are not regulation or advice.', fr: 'Les règles ajoutées sont vos propres hypothèses, vérifiées par le code dans le portefeuille et dans chaque décision. Ce n’est ni une réglementation ni un conseil.' });
  if (profile.isDefault) {
    return (
      <Card id="add-rule" tour="add-rule" title={title} info={info}>
        <p className="small muted">
          {tr({ en: 'Example profiles cannot be changed. Duplicate this one in', fr: 'Les profils d’exemple ne sont pas modifiables. Dupliquez celui-ci dans' })}{' '}
          <Link href="/profiles/">{tr({ en: 'Profiles', fr: 'Profils' })}</Link>{' '}
          {tr({ en: 'to add your own rules', fr: 'pour ajouter vos propres règles' })}
        </p>
      </Card>
    );
  }
  return (
    <Card id="add-rule" section={title} tour="add-rule" title={title} info={info}>
      <SegmentedControl<RuleKind> label={tr({ en: 'Kind of rule', fr: 'Type de règle' })} value={kind} onChange={setKind} options={[
        { value: 'exposure', label: tr({ en: 'Exposure cap', fr: 'Plafond d’exposition' }), title: tr({ en: 'Most the portfolio may hold in one currency or country', fr: 'Maximum détenu dans une devise ou un pays' }) },
        { value: 'weight', label: tr({ en: 'Cap or floor', fr: 'Plafond ou plancher' }), title: tr({ en: 'Maximum or minimum weight for a holding, sector, class or theme', fr: 'Poids maximal ou minimal pour une position, un secteur, une catégorie ou un thème' }) },
        { value: 'conditional', label: tr({ en: 'Conditional', fr: 'Conditionnelle' }), title: tr({ en: 'Limits that apply only in a given situation', fr: 'Limites qui s’appliquent seulement dans une situation donnée' }) },
      ]} />
      {/* All three stay mounted so typed input survives a switch of kind; only the chosen one shows. */}
      <div className="add-rule-body" hidden={kind !== 'exposure'}><ExposureLimits profile={profile} /></div>
      <div className="add-rule-body" hidden={kind !== 'weight'}><CustomPolicies key={`policies|${profile.profileId}|${profile.version}`} profile={profile} /></div>
      <div className="add-rule-body" hidden={kind !== 'conditional'}><ConditionalPolicies key={`conditions|${profile.profileId}|${profile.version}`} profile={profile} /></div>
    </Card>
  );
}
