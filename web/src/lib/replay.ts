/**
 * Pure Time Machine logic (T15, web/page-specs/time-machine.md): which as-of dates may be requested,
 * when a run can be revealed, and which `until` dates the reveal accepts (asOf < until ≤ snapshot end).
 */
import type { I18NText, ReplayPresetsResponse, ReplayResult, RevealResult, Run } from '../contracts/types';
import { addDays, isIsoDate } from './world';

export type AsOfIssue = 'missing' | 'format' | 'before_earliest' | 'after_latest';

/** Why an as-of date cannot be sent, or null. The server stays authoritative (api.md 5.1: 422). */
export function asOfIssue(value: string, presets: Pick<ReplayPresetsResponse, 'earliestAsOf' | 'latestAsOf'>): AsOfIssue | null {
  if (!value) return 'missing';
  if (!isIsoDate(value)) return 'format';
  if (value < presets.earliestAsOf) return 'before_earliest';
  if (value > presets.latestAsOf) return 'after_latest';
  return null;
}

export const AS_OF_ISSUE: Record<AsOfIssue, I18NText> = {
  missing: { en: 'Choose an information cutoff date.', fr: 'Choisissez une date limite d’information.' },
  format: { en: 'The date must be a calendar date (YYYY-MM-DD).', fr: 'La date doit être une date du calendrier (AAAA-MM-JJ).' },
  before_earliest: { en: 'Too early: there is not enough history before this date in the loaded data.', fr: 'Trop tôt : l’historique avant cette date est insuffisant dans les données chargées.' },
  after_latest: { en: 'Too late: too little data remains after this date to reveal an outcome.', fr: 'Trop tard : trop peu de données subsistent après cette date pour révéler un résultat.' },
};

export interface ReplayRefusal { earliestAsOf: string | null; latestAsOf: string | null; unknownAtAsOf: string[] }

/**
 * What a `422` on replay creation says in `error.details`: the supported range when the date is
 * outside it, and the portfolio assets that have no price at the date (`unknownAtAsOf`).
 * Only well-formed values are kept; anything else is ignored rather than displayed.
 */
export function replayRefusal(details: Record<string, unknown> | null | undefined): ReplayRefusal | null {
  if (!details) return null;
  const date = (value: unknown) => (typeof value === 'string' && isIsoDate(value) ? value : null);
  const tickers = Array.isArray(details.unknownAtAsOf)
    ? details.unknownAtAsOf.filter((item): item is string => typeof item === 'string' && /^[A-Z0-9][A-Z0-9.^=-]{0,19}$/.test(item))
    : [];
  const refusal = { earliestAsOf: date(details.earliestAsOf), latestAsOf: date(details.latestAsOf), unknownAtAsOf: tickers };
  return refusal.earliestAsOf || refusal.latestAsOf || tickers.length > 0 ? refusal : null;
}

/** The replay result of a run that is a succeeded replay; null for anything else (no reveal offered). */
export function revealableReplay(run: Pick<Run, 'kind' | 'status' | 'result'> | null): ReplayResult | null {
  if (!run || run.kind !== 'replay' || run.status !== 'succeeded') return null;
  return run.result?.kind === 'replay' ? run.result.replay : null;
}

export interface RevealBounds { min: string; max: string }

/** `until` must be strictly after the cutoff and no later than the last date in the snapshot. */
export function revealBounds(replay: Pick<ReplayResult, 'asOf' | 'revealAvailableUntil'>): RevealBounds | null {
  const min = addDays(replay.asOf, 1);
  return min <= replay.revealAvailableUntil ? { min, max: replay.revealAvailableUntil } : null;
}

export type UntilIssue = 'format' | 'not_after_cutoff' | 'after_snapshot' | 'no_later_data';

/** Empty `until` is valid: the API then uses the last date in the snapshot. */
export function untilIssue(value: string, replay: Pick<ReplayResult, 'asOf' | 'revealAvailableUntil'>): UntilIssue | null {
  if (!revealBounds(replay)) return 'no_later_data';
  if (!value) return null;
  if (!isIsoDate(value)) return 'format';
  if (value <= replay.asOf) return 'not_after_cutoff';
  if (value > replay.revealAvailableUntil) return 'after_snapshot';
  return null;
}

export const UNTIL_ISSUE: Record<UntilIssue, I18NText> = {
  format: { en: 'The date must be a calendar date (YYYY-MM-DD).', fr: 'La date doit être une date du calendrier (AAAA-MM-JJ).' },
  not_after_cutoff: { en: 'The reveal date must be after the information cutoff.', fr: 'La date de révélation doit être postérieure à la date limite d’information.' },
  after_snapshot: { en: 'The reveal date cannot be later than the last date in the data snapshot.', fr: 'La date de révélation ne peut dépasser la dernière date de l’instantané de données.' },
  no_later_data: { en: 'The snapshot holds no data after this cutoff, so nothing can be revealed.', fr: 'L’instantané ne contient aucune donnée après cette date limite ; rien ne peut être révélé.' },
};

/** Request body for POST /runs/{id}/reveal: `until` only when the user chose one. */
export function revealRequest(until: string): { until?: string } {
  return until ? { until } : {};
}

const SERIES_COLORS = ['#0B5E66', '#B4530A', '#5B4B9A', '#8A1B12', '#334759', '#7A6A00'];

/** Chart series for the reveal, one per fixed scenario, values as returned (index, 100 at the cutoff). */
export function revealSeries(reveal: Pick<RevealResult, 'outcomes'>, tr: (text: I18NText) => string) {
  return reveal.outcomes.map((outcome, i) => ({
    label: tr(outcome.label),
    points: outcome.series,
    color: SERIES_COLORS[i % SERIES_COLORS.length] ?? '#0B5E66',
    dashed: i % 2 === 1,
  }));
}

/**
 * Among an outcome's reveal facts, the one whose numeric value is the figure shown, so the figure can
 * open its own source. No match = the figure is shown as plain text next to the outcome's fact list.
 */
export function factForValue(
  facts: RevealResult['facts'], factIds: readonly string[], value: number, exclude: string | null = null,
): string | null {
  for (const id of factIds) {
    if (id === exclude) continue;
    const fact = facts[id];
    if (fact && typeof fact.value === 'number' && Math.abs(fact.value - value) < 1e-9) return id;
  }
  return null;
}

/** Signed ledger hash of a run's main brief, used to show that a reveal left it unchanged. */
export function signedLedgerHash(run: Pick<Run, 'result'> | null): string | null {
  const result = run?.result;
  if (!result) return null;
  if (result.kind === 'replay') return result.replay.decision.brief.audit.ledgerHash;
  if (result.kind === 'decision') return result.decision.brief.audit.ledgerHash;
  return null;
}
