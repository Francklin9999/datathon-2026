/**
 * Wording of the window-based "worst 12 months" figure (OverviewRisk.worst12mPct). It is the lowest
 * return over any 252 consecutive trading days inside the selected period
 * (backend/aplomb/quant/metrics.py::worst_rolling_return_pct), so it is positive when every such
 * stretch gained: the label says "lowest rolling", and a positive value carries a short explanation.
 */
import type { I18NText } from '../../contracts/types';

/** Home Stress test widget. */
export const LOWEST_12M_LABEL: I18NText = { en: 'Lowest rolling 12-month return in the period', fr: 'Plus faible rendement glissant sur 12 mois de la période' };
/** Portfolio / Risk tiles (the card already names the period). */
export const LOWEST_12M_SHORT: I18NText = { en: 'Lowest rolling 12-month return', fr: 'Plus faible rendement glissant sur 12 mois' };
export const LOWEST_12M_INFO: I18NText = {
  en: 'Lowest rolling 12-month return: the weakest return over any 252 consecutive trading days (about 12 months) inside the selected period. It is positive when every such stretch gained.',
  fr: 'Plus faible rendement glissant sur 12 mois : le rendement le plus faible sur toute suite de 252 jours de bourse consécutifs (environ 12 mois) dans la période choisie. Il est positif quand chacune de ces suites a progressé.',
};

/** Short explanation shown next to a positive value; null otherwise (a loss needs none, a missing value has its own text). */
export function lowestRollingNote(value: number | null): I18NText | null {
  return value !== null && value > 0
    ? { en: 'Positive: every 12-month stretch in this period gained.', fr: 'Positif : chaque période de 12 mois de cet intervalle a progressé.' }
    : null;
}
