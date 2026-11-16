/**
 * Readable bilingual labels for the portfolio editors' codes (origins, rule dimensions, review
 * frequency, scenario states), so a select or a summary never shows a raw enum such as
 * `system_default`. `labelOf` humanises any code a newer API adds.
 */
import type { I18NText } from '../../contracts/types';
import type { Labels } from '../../lib/labels';

const l = (en: string, fr: string): I18NText => ({ en, fr });

export type OriginCode = 'user' | 'imported' | 'system_default' | 'assumption' | 'regulatory' | 'derived'
  | 'profile_preference' | 'system';

export const ORIGIN: Labels<OriginCode> = {
  user: l('Entered by you', 'Saisie par vous'),
  imported: l('Imported', 'Importée'),
  system_default: l('App default', 'Valeur par défaut de l’app'),
  assumption: l('Assumption', 'Hypothèse'),
  regulatory: l('Regulatory reference', 'Référence réglementaire'),
  derived: l('Derived from the profile', 'Dérivée du profil'),
  profile_preference: l('Profile preference', 'Préférence du profil'),
  system: l('App rule', 'Règle de l’app'),
};

export type DimensionCode = 'position' | 'sector' | 'asset_class' | 'country' | 'currency' | 'theme' | 'volatility' | 'drawdown';

export const DIMENSION: Labels<DimensionCode> = {
  position: l('Holding', 'Position'),
  sector: l('Sector', 'Secteur'),
  asset_class: l('Asset class', 'Catégorie d’actif'),
  country: l('Listing country', 'Pays de cotation'),
  currency: l('Quote currency', 'Devise de cotation'),
  theme: l('Theme', 'Thème'),
  volatility: l('Portfolio volatility', 'Volatilité du portefeuille'),
  drawdown: l('Maximum drawdown', 'Baisse maximale'),
};

export const FREQUENCY: Labels<'none' | 'monthly' | 'quarterly' | 'semiannual' | 'annual' | 'custom'> = {
  none: l('No set review', 'Aucune révision prévue'),
  monthly: l('Monthly', 'Mensuelle'),
  quarterly: l('Quarterly', 'Trimestrielle'),
  semiannual: l('Twice a year', 'Semestrielle'),
  annual: l('Yearly', 'Annuelle'),
  custom: l('Custom', 'Personnalisée'),
};

export const TARGET_STATE: Labels<'within_drift_threshold' | 'outside_drift_threshold' | 'no_drift_threshold' | 'unavailable'> = {
  within_drift_threshold: l('Within the drift band', 'Dans la marge de dérive'),
  outside_drift_threshold: l('Outside the drift band', 'Hors de la marge de dérive'),
  no_drift_threshold: l('No drift band set', 'Aucune marge de dérive'),
  unavailable: l('Unavailable', 'Indisponible'),
};

export const REQUIREMENT_STATE: Labels<'missing_assumptions' | 'scenario_funded' | 'scenario_shortfall'> = {
  missing_assumptions: l('Missing assumptions', 'Hypothèses manquantes'),
  scenario_funded: l('Funded in this scenario', 'Financé dans ce scénario'),
  scenario_shortfall: l('Shortfall in this scenario', 'Déficit dans ce scénario'),
};
