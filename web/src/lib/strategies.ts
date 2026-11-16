/**
 * Standing strategies (api.md §3.13): what the investor saves in this browser and how it is shown.
 * Pure: storage goes through the injected read/write functions so it can be tested. The server only
 * simulates; a saved strategy is a UI preference (at most three per profile), never an order.
 */
import type { I18NText, Meta, StrategyConfig } from '../contracts/types';
import { FEATURE_MIN_CONTRACT, NEEDS_NEWER_API, apiCompatibility, apiVersionLine, type ApiCompatibility } from './apiCompat';
import { describeFailure, type FailureDescription } from './failure';

export type StrategyKind = StrategyConfig['kind'];
export const MAX_STRATEGIES = 3;
export const STRATEGY_KINDS: readonly StrategyKind[] = ['rebalance', 'contribute', 'risk_guard'];

/** A strategy as saved: a name, whether it is active or paused, and its configuration. */
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

// ----- Site/API version skew (the site deploys on every push, the API separately) -----

/** Whether the connected API can simulate strategies; `unknown` while /meta loads. */
export function strategiesCompatibility(meta: Pick<Meta, 'contractVersion'> | null | undefined): ApiCompatibility {
  return apiCompatibility(meta, FEATURE_MIN_CONTRACT.strategies);
}

/**
 * The simulate request for `config` and its query key, or null when nothing may be sent: the API
 * cannot simulate strategies (or /meta has not answered), there is no session/profile key yet, or
 * the settings have problems the form already shows.
 */
export function simulationRequest(compat: ApiCompatibility, base: string | null, windowCode: string, config: StrategyConfig | null): { key: string; body: StrategyConfig } | null {
  if (compat !== 'supported' || !base || !config || configIssues(config).length > 0) return null;
  const body = wireConfig(config);
  return { key: `strategy|${base}|${windowCode}|${JSON.stringify(body)}`, body };
}

export interface StrategiesUnavailable {
  /** The notice on the Strategies page. */
  title: I18NText;
  body: I18NText;
  /** Which contract the feature needs and which one the API reports. */
  version: I18NText;
  /** Short status on a saved strategy (Strategies list). */
  badge: I18NText;
  /** On a "create" card (kind picker): what creating one will not do yet. */
  createNote: I18NText;
}

/**
 * The copy shown when the connected API cannot simulate strategies, or null when it can (or when
 * /meta has not answered yet: nothing is shown then). Saved strategies stay editable and deletable.
 */
export function strategiesUnavailable(compat: ApiCompatibility, apiVersion: string | null | undefined): StrategiesUnavailable | null {
  if (compat !== 'older' && compat !== 'incompatible') return null;
  const version = apiVersionLine(FEATURE_MIN_CONTRACT.strategies, apiVersion);
  if (compat === 'older') {
    return {
      title: { en: 'Strategy simulations need the newer API release.', fr: 'Les simulations de stratégies exigent la nouvelle version de l’API.' },
      body: {
        en: 'The connected API does not offer strategy simulations yet. Your strategies are kept in this browser: you can still create, edit and delete them, and they will be simulated once the API is updated.',
        fr: 'L’API connectée ne propose pas encore les simulations de stratégies. Vos stratégies sont conservées dans ce navigateur : vous pouvez toujours les créer, les modifier et les supprimer, et elles seront simulées dès la mise à jour de l’API.',
      },
      version,
      badge: NEEDS_NEWER_API,
      createNote: { en: 'Simulation needs the newer API release', fr: 'La simulation exige la nouvelle version de l’API' },
    };
  }
  return {
    title: { en: 'Strategy simulations are not available with the connected API.', fr: 'Les simulations de stratégies ne sont pas disponibles avec l’API connectée.' },
    body: {
      en: 'The connected API runs a contract version this site cannot use. Your strategies are kept in this browser: you can still create, edit and delete them.',
      fr: 'L’API connectée utilise une version de contrat que ce site ne peut pas exploiter. Vos stratégies sont conservées dans ce navigateur : vous pouvez toujours les créer, les modifier et les supprimer.',
    },
    version,
    badge: { en: 'Simulation unavailable', fr: 'Simulation indisponible' },
    createNote: { en: 'Simulation unavailable with this API', fr: 'Simulation indisponible avec cette API' },
  };
}

/**
 * A failed simulation, worded for the Strategies page (lib/failure.ts does the classification and
 * the retry budget). Strategy-specific wording replaces the generic one when the server sent no
 * bilingual reason: a validation error means "change the settings", insufficient data "pick a longer
 * period".
 */
export function strategyFailure(error: unknown, failures: number): FailureDescription {
  const failure = describeFailure(error, { failures });
  if (failure.kind !== 'edit' || failure.reason) return failure;
  const code = (error as { code?: string }).code;
  const message: I18NText = code === 'insufficient_data'
    ? { en: 'Not enough market history for this period. Choose a longer period, such as 1Y or All.', fr: 'Historique de marché insuffisant pour cette période. Choisissez une période plus longue, par exemple 1A ou Tout.' }
    : { en: 'These settings cannot be simulated. Change them above; the simulation runs again on its own.', fr: 'Ces réglages ne peuvent pas être simulés. Modifiez-les ci-dessus ; la simulation se relance d’elle-même.' };
  return { ...failure, message };
}

/**
 * The body sent to the API: only the fields of the chosen trigger. Trigger `band` is labelled
 * "On drift" in the UI; `bandPts` is sent only for it and `frequency` only for `calendar` (the saved
 * config keeps both, so the value survives switching the trigger back and forth).
 */
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

/** A deleted strategy and where it was, so Undo can put it back. */
export interface RemovedStrategy { strategy: SavedStrategy; index: number }

/** How long the "deleted · Undo" notice stays on screen. */
export const UNDO_DELETE_MS = 10_000;

/** `list` without strategy `id`, plus what Undo needs; null when it is not in the list. */
export function removeStrategy(list: readonly SavedStrategy[], id: string): { next: SavedStrategy[]; removed: RemovedStrategy } | null {
  const index = list.findIndex(s => s.id === id);
  if (index < 0) return null;
  return { next: list.filter(s => s.id !== id), removed: { strategy: list[index]!, index } };
}

/**
 * Undo a delete: the strategy back at its old place (or last, if the list got shorter). Null when it
 * cannot come back: the list is already full, or a strategy with that id is present.
 */
export function restoreStrategy(list: readonly SavedStrategy[], removed: RemovedStrategy): SavedStrategy[] | null {
  if (list.length >= MAX_STRATEGIES || list.some(s => s.id === removed.strategy.id)) return null;
  const at = Math.max(0, Math.min(removed.index, list.length));
  return [...list.slice(0, at), removed.strategy, ...list.slice(at)];
}

/**
 * When the Undo notice expires while Undo holds focus, focus moves to the first control still on the
 * page (`candidates` in order of preference), so a keyboard user does not land on <body>. Returns
 * whether focus moved; it never moves when focus is elsewhere.
 */
export function moveFocusFromExpiredUndo(
  active: unknown, undo: unknown, candidates: readonly ({ focus(): void } | null | undefined)[],
): boolean {
  if (undo == null || active !== undo) return false;
  const target = candidates.find(c => c != null);
  target?.focus();
  return Boolean(target);
}

/** A new strategy of `kind`, named after it (numbered when the name is taken). */
export function newStrategy(kind: StrategyKind, existing: readonly SavedStrategy[], tr: (t: I18NText) => string, id: string): SavedStrategy {
  const base = tr(KIND_NAME[kind]);
  let name = base;
  for (let n = 2; existing.some(s => s.name === name); n++) name = `${base} ${n}`;
  return { id, name, active: true, config: defaultConfig(kind) };
}
