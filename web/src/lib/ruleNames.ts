/**
 * Short human names of plan rules, by rule ID (backend/aplomb/rules/definitions.py). A rule token in
 * a brief carries the profile-local code ("R3"), which means a different rule in each profile; the
 * name leads and the code stays as a secondary label. Exact IDs first, then the parameterized
 * families; an unknown ID has no name and the caller keeps the code.
 */
import type { I18NText, Lang } from '../contracts/types';
import { pick } from './labels';

const n = (en: string, fr: string): I18NText => ({ en, fr });

const EXACT: Readonly<Record<string, I18NText>> = {
  'cap.position': n('Single-asset limit', 'Limite par actif'),
  'cap.sector': n('Sector limit', 'Limite par secteur'),
  'cap.growth_assets': n('Growth-asset limit', 'Limite des actifs de croissance'),
  'floor.fixed_income': n('Bonds-and-cash floor', 'Plancher obligations et encaisse'),
  'floor.diversifiers': n('Diversifier floor', 'Plancher des actifs diversifiants'),
  'cap.asset_class.crypto': n('Crypto limit', 'Limite crypto'),
  'limit.volatility': n('Volatility limit', 'Limite de volatilité'),
  'limit.stress_2022': n('2022 replay limit', 'Limite du scénario 2022'),
  'limit.drawdown': n('Largest-fall limit', 'Limite de plus forte baisse'),
  'exclude.asset_class.crypto': n('No-crypto rule', 'Règle sans crypto'),
  'evidence.controversy': n('Controversy screen', 'Filtre des controverses'),
  'flag.attention': n('Public-attention check', 'Contrôle de l’attention publique'),
  'flag.rate_cycle': n('Rate-rise history', 'Historique de hausse des taux'),
  'sim.only': n('Simulation-only rule', 'Règle de simulation seulement'),
};

/** Longest prefix first, so `cap.asset_class.` is tried before a shorter family would be. */
const FAMILIES: readonly (readonly [string, I18NText])[] = [
  ['custom.condition.', n('Conditional rule', 'Règle conditionnelle')],
  ['exclude.asset_class.', n('Asset-class exclusion', 'Exclusion de catégorie d’actifs')],
  ['exclude.sector.', n('Sector exclusion', 'Exclusion de secteur')],
  ['exclude.ticker.', n('Excluded holding', 'Titre exclu')],
  ['cap.asset_class.', n('Asset-class limit', 'Limite par catégorie d’actifs')],
  ['floor.asset_class.', n('Asset-class floor', 'Plancher par catégorie d’actifs')],
  ['cap.position.', n('Position limit', 'Limite par position')],
  ['floor.position.', n('Position floor', 'Plancher par position')],
  ['cap.currency.', n('Currency limit', 'Limite par devise')],
  ['floor.currency.', n('Currency floor', 'Plancher par devise')],
  ['cap.country.', n('Country limit', 'Limite par pays')],
  ['floor.country.', n('Country floor', 'Plancher par pays')],
  ['cap.sector.', n('Sector limit', 'Limite par secteur')],
  ['floor.sector.', n('Sector floor', 'Plancher par secteur')],
  ['cap.theme.', n('Theme limit', 'Limite par thème')],
  ['floor.theme.', n('Theme floor', 'Plancher par thème')],
];

/** Bilingual short name of a rule, or null when the ID is not a known rule or family. */
export function ruleNameText(ruleId: string): I18NText | null {
  if (Object.hasOwn(EXACT, ruleId)) return EXACT[ruleId]!;
  const family = FAMILIES.find(([prefix]) => ruleId.startsWith(prefix) && ruleId.length > prefix.length);
  return family ? family[1] : null;
}

/** Short name of a rule in the display language, or null (the caller then shows the rule code). */
export function ruleName(ruleId: string, lang: Lang): string | null {
  const text = ruleNameText(ruleId);
  return text ? pick(text, lang) : null;
}
