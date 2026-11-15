/**
 * Standing strategies (api.md §3.13): what the investor saves in this browser and how it is shown.
 * Pure: storage goes through the injected read/write functions so it can be tested. The server only
 * simulates; a saved strategy is a UI preference (at most three per profile), never an order.
 */
import type { I18NText, StrategyConfig } from '../contracts/types';

export type StrategyKind = StrategyConfig['kind'];
export const MAX_STRATEGIES = 3;
export const STRATEGY_KINDS: readonly StrategyKind[] = ['rebalance', 'contribute', 'risk_guard'];

/** A strategy as saved: a name, whether it is active (shown on Home) and its configuration. */
export interface SavedStrategy { id: string; name: string; active: boolean; config: StrategyConfig }

export function defaultConfig(kind: StrategyKind): StrategyConfig {
  if (kind === 'rebalance') return { kind, trigger: 'calendar', frequency: 'quarterly', bandPts: 5, costBps: 10 };
  if (kind === 'contribute') return { kind, amount: 500, frequency: 'monthly', allocation: 'underweight', costBps: 0 };
  return { kind, triggerDrawdownPct: 8, shiftPct: 50, reentryDrawdownPct: 3, safeTicker: null, costBps: 10 };
}

export const KIND_NAME: Record<StrategyKind, I18NText> = {
  rebalance: { en: 'Rebalancing', fr: 'Rééquilibrage' },
  contribute: { en: 'Regular contributions', fr: 'Versements programmés' },
  risk_guard: { en: 'Risk guard', fr: 'Garde-fou de risque' },
};

/** What each kind automates, in one sentence (the card under the kind picker). */
export const KIND_PURPOSE: Record<StrategyKind, I18NText> = {
  rebalance: { en: 'Brings the weights back to today’s target on a schedule or when one drifts too far.', fr: 'Ramène les pondérations à la cible actuelle selon un calendrier ou quand l’une s’écarte trop.' },
  contribute: { en: 'Invests a fixed amount every period, into the positions furthest below target if you wish.', fr: 'Investit un montant fixe à chaque période, dans les positions les plus sous leur cible si vous le souhaitez.' },
  risk_guard: { en: 'After a fall from the peak, moves part of the stocks and crypto to a defensive asset; moves back once it recovers.', fr: 'Après une baisse depuis le sommet, déplace une partie des actions et de la crypto vers un actif défensif ; revient une fois remis.' },
};

const FREQ: Record<string, I18NText> = {
  monthly: { en: 'monthly', fr: 'mensuel' },
  quarterly: { en: 'quarterly', fr: 'trimestriel' },
  yearly: { en: 'yearly', fr: 'annuel' },
};

/** One line describing a configuration ("Quarterly rebalance, 10 bps"). */
export function describe(config: StrategyConfig, tr: (t: I18NText) => string, money: (n: number) => string): string {
  const cost = config.costBps ? tr({ en: `, ${config.costBps} bps per trade`, fr: `, ${config.costBps} pb par opération` }) : '';
  if (config.kind === 'rebalance') {
    return config.trigger === 'calendar'
      ? tr({ en: `Rebalance, ${tr(FREQ[config.frequency ?? 'quarterly']!)}`, fr: `Rééquilibrage ${tr(FREQ[config.frequency ?? 'quarterly']!)}` }) + cost
      : tr({ en: `Rebalance past a ${config.bandPts ?? 5}-pt drift`, fr: `Rééquilibrage au-delà de ${config.bandPts ?? 5} pts d’écart` }) + cost;
  }
  if (config.kind === 'contribute') {
    const where = config.allocation === 'underweight'
      ? tr({ en: 'to the most underweight', fr: 'vers les plus sous-pondérées' })
      : tr({ en: 'by target weights', fr: 'selon les cibles' });
    return tr({ en: `${money(config.amount)} ${tr(FREQ[config.frequency]!)}, ${where}`, fr: `${money(config.amount)} ${tr(FREQ[config.frequency]!)}, ${where}` }) + cost;
  }
  return tr({
    en: `At −${config.triggerDrawdownPct}% from the peak, move ${config.shiftPct}% of growth to safety; back under −${config.reentryDrawdownPct}%`,
    fr: `À −${config.triggerDrawdownPct} % du sommet, mettre ${config.shiftPct} % de la croissance à l’abri ; retour sous −${config.reentryDrawdownPct} %`,
  }) + cost;
}

/** Problems a form value has before it is sent (the server validates again). */
export function configIssues(config: StrategyConfig): I18NText[] {
  const out: I18NText[] = [];
  const within = (v: number | undefined | null, lo: number, hi: number) => v !== undefined && v !== null && Number.isFinite(v) && v >= lo && v <= hi;
  if (!within(config.costBps ?? 0, 0, 100)) out.push({ en: 'Costs must be between 0 and 100 bps.', fr: 'Les frais doivent être entre 0 et 100 pb.' });
  if (config.kind === 'rebalance' && config.trigger === 'band' && !within(config.bandPts, 1, 25)) {
    out.push({ en: 'The band must be between 1 and 25 points.', fr: 'La bande doit être entre 1 et 25 points.' });
  }
  if (config.kind === 'contribute' && !(Number.isFinite(config.amount) && config.amount > 0 && config.amount <= 1_000_000)) {
    out.push({ en: 'The amount must be above 0 and at most 1,000,000.', fr: 'Le montant doit être supérieur à 0 et au plus 1 000 000.' });
  }
  if (config.kind === 'risk_guard') {
    if (!within(config.triggerDrawdownPct, 2, 50)) out.push({ en: 'The trigger must be between 2% and 50%.', fr: 'Le seuil doit être entre 2 % et 50 %.' });
    if (!within(config.shiftPct, 10, 100)) out.push({ en: 'The share moved must be between 10% and 100%.', fr: 'La part déplacée doit être entre 10 % et 100 %.' });
    if (!within(config.reentryDrawdownPct, 0, 50) || config.reentryDrawdownPct >= config.triggerDrawdownPct) {
      out.push({ en: 'The return level must be below the trigger.', fr: 'Le niveau de retour doit être sous le seuil.' });
    }
  }
  return out;
}

/** The body sent to the API: only the fields of the chosen trigger. */
export function wireConfig(config: StrategyConfig): StrategyConfig {
  if (config.kind === 'rebalance') {
    const { bandPts, frequency, ...rest } = config;
    return config.trigger === 'band' ? { ...rest, bandPts: bandPts ?? 5 } : { ...rest, frequency: frequency ?? 'quarterly' };
  }
  if (config.kind === 'risk_guard' && !config.safeTicker) {
    const { safeTicker: _ignored, ...rest } = config;
    return rest;
  }
  return config;
}

// ----- Saved strategies (UI preference per profile) -----

const PREF = (profileId: string) => `strategies.v1.${profileId}`;

function isConfig(value: unknown): value is StrategyConfig {
  return Boolean(value) && typeof value === 'object' && STRATEGY_KINDS.includes((value as { kind?: StrategyKind }).kind as StrategyKind);
}

/** Saved strategies of a profile; anything unreadable is dropped, never more than three. */
export function readStrategies(profileId: string, read: (key: string) => string | null): SavedStrategy[] {
  try {
    const raw = JSON.parse(read(PREF(profileId)) ?? '[]') as unknown;
    if (!Array.isArray(raw)) return [];
    return raw.filter((s): s is SavedStrategy => Boolean(s) && typeof s.id === 'string' && typeof s.name === 'string' && isConfig(s.config))
      .map(s => ({ id: s.id, name: s.name.slice(0, 60), active: s.active === true, config: s.config }))
      .slice(0, MAX_STRATEGIES);
  } catch {
    return [];
  }
}

export function writeStrategies(profileId: string, list: readonly SavedStrategy[], write: (key: string, value: string) => void): void {
  write(PREF(profileId), JSON.stringify(list.slice(0, MAX_STRATEGIES)));
}

/** A new strategy of `kind`, named after it (numbered when the name is taken). */
export function newStrategy(kind: StrategyKind, existing: readonly SavedStrategy[], tr: (t: I18NText) => string, id: string): SavedStrategy {
  const base = tr(KIND_NAME[kind]);
  let name = base;
  for (let n = 2; existing.some(s => s.name === name); n++) name = `${base} ${n}`;
  return { id, name, active: true, config: defaultConfig(kind) };
}
