/**
 * The Labs tools as data: each has an id (the ?tool= value), a category, a plain name and purpose in
 * English and French, an icon and a loader that fetches its code only when it is opened.
 * `needsProfile` wraps the tool in ProfileGate like its original page.
 * Pure data apart from the lazy loaders, so tests/labs-registry.test.ts can import it under node.
 */
import { createElement, type ComponentType } from 'react';
import { BadgeCheck, ClipboardList, GitCompare, PiggyBank, Search, Target, type LucideIcon } from 'lucide-react';
import type { I18NText, Profile } from '../../contracts/types';

export type LabCategoryId = 'instruments' | 'planning' | 'comparison';

export interface LabCategory { id: LabCategoryId; label: I18NText }

/** What the Labs page hands every tool. `profile` is set whenever the tool needs one. */
export interface ToolContext {
  profile: Profile | null;
  profiles: Profile[];
}

export interface LabTool {
  id: string;
  category: LabCategoryId;
  label: I18NText;
  purpose: I18NText;
  icon: LucideIcon;
  loader: () => Promise<ComponentType<ToolContext>>;
  needsProfile: boolean;
  /** Reset the tool when the analysis period changes (its figures depend on it). */
  periodBound?: boolean;
}

export const LAB_CATEGORIES: readonly LabCategory[] = [
  { id: 'instruments', label: { en: 'Instruments', fr: 'Instruments' } },
  { id: 'planning', label: { en: 'Planning', fr: 'Planification' } },
  { id: 'comparison', label: { en: 'Comparison', fr: 'Comparaison' } },
];

type Loader = LabTool['loader'];

/** A tool without props. */
const plain = (load: () => Promise<ComponentType>): Loader => () =>
  load().then(Tool => function LabTool() { return createElement(Tool); });

/** A tool that reads the selected profile (the page renders it inside ProfileGate). */
const withProfile = (load: () => Promise<ComponentType<{ profile: Profile }>>): Loader => () =>
  load().then(Tool => function LabTool({ profile }: ToolContext) { return profile ? createElement(Tool, { profile }) : null; });

export const LAB_TOOLS: readonly LabTool[] = [
  // Instruments
  {
    id: 'instruments', category: 'instruments', icon: Search, needsProfile: false,
    label: { en: 'Instrument discovery', fr: 'Recherche de titres' },
    purpose: { en: 'Search the supported instruments and read their history', fr: 'Chercher les titres pris en charge et lire leur historique' },
    loader: plain(() => import('./InstrumentDiscovery').then(m => m.InstrumentDiscovery)),
  },

  // Planning
  {
    id: 'target-drift', category: 'planning', icon: Target, needsProfile: true,
    label: { en: 'Target drift', fr: 'Écart à la cible' },
    purpose: { en: 'How far your holdings sit from your target mix', fr: 'L’écart entre vos positions et la répartition visée' },
    loader: withProfile(() => import('../portfolio/AllocationTargets').then(m => m.AllocationTargets)),
  },
  {
    id: 'joint-plan', category: 'planning', icon: ClipboardList, needsProfile: true,
    label: { en: 'Goals, spending and liquidity plan', fr: 'Plan des objectifs, dépenses et liquidités' },
    purpose: { en: 'Check goals, spending and cash needs together', fr: 'Vérifier ensemble objectifs, dépenses et besoins de liquidités' },
    loader: withProfile(() => import('../planning/JointPlan').then(m => m.JointPlan)),
  },
  {
    id: 'goal-funding', category: 'planning', icon: PiggyBank, needsProfile: true,
    label: { en: 'Goal funding', fr: 'Financement des objectifs' },
    purpose: { en: 'Whether your contributions could fund each goal', fr: 'Si vos versements pourraient financer chaque objectif' },
    loader: withProfile(() => import('../portfolio/GoalFunding').then(m => m.GoalFunding)),
  },
  {
    id: 'requirements', category: 'planning', icon: BadgeCheck, needsProfile: true,
    label: { en: 'Spending and liquidity scenario', fr: 'Scénario de dépenses et de liquidité' },
    purpose: { en: 'Whether planned withdrawals stay covered over time', fr: 'Si les retraits prévus restent couverts dans le temps' },
    loader: withProfile(() => import('../portfolio/RequirementsScenario').then(m => m.RequirementsScenario)),
  },

  // Comparison
  {
    id: 'profile-compare', category: 'comparison', icon: GitCompare, needsProfile: true,
    label: { en: 'Compare profiles', fr: 'Comparer des profils' },
    purpose: { en: 'Put two saved profiles side by side', fr: 'Mettre deux profils enregistrés côte à côte' },
    loader: () => import('../profiles/ProfileCompare').then(m => function LabTool({ profiles }: ToolContext) {
      return createElement(m.ProfileCompare, { profiles });
    }),
  },
];

export const LAB_TOOL_IDS: readonly string[] = LAB_TOOLS.map(tool => tool.id);

/**
 * The tool shown when ?tool= is missing or unknown, including an old link to a tool that left Labs
 * (?tool=covariance): it needs no profile.
 */
export const DEFAULT_LAB_TOOL = 'instruments';

/** The tools of one category, in list order. */
export function toolsOf(category: LabCategoryId): LabTool[] {
  return LAB_TOOLS.filter(tool => tool.category === category);
}
