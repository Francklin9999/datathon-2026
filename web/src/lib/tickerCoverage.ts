/**
 * Ticker coverage on the pages that take tickers outside the move form: Labs instrument discovery,
 * the account and target-allocation editors (Portfolio, Decide) and the Replay run gate.
 * Built on lib/universe.ts; every check returns "no issue" until the universe read has completed
 * (useAssetUniverse().ready), so a slow or failed read never blocks input.
 *
 * Every server path refuses a ticker outside the current snapshot whatever the on-demand flag:
 * profile and account writes (422 `details.unknown`), /rebalance (404), /check and /runs (404).
 * With `on_demand_tickers` on, a ticker can be added first from the Decide move check, so the
 * editors only warn; with it off nothing can add it, so they block.
 */
import type { Asset, I18NText } from '../contracts/types';
import type { MoveFormIssue } from './move';
import {
  isCashTicker, normalizeTicker, unsupportedTickerMessage, unsupportedTickers, unsupportedTickersMessage,
} from './universe';

/** What useAssetUniverse() returns, reduced to what the checks read. */
export interface UniverseView {
  ready: boolean;
  assets: readonly Pick<Asset, 'ticker'>[];
  total: number;
  dataVersion: string | null;
}

export interface TickerCheck {
  /** Normalized, de-duplicated, in input order. */
  unsupported: string[];
  /** True when submit must stay disabled. */
  blocking: boolean;
  /** Shown under the field: an error when blocking, a hint otherwise. */
  message: I18NText | null;
}

const NO_ISSUE: TickerCheck = { unsupported: [], blocking: false, message: null };

/** The ticker of each non-empty `TICKER PERCENT` line (the first word, upper case). */
export function targetLineTickers(text: string): string[] {
  return text.split('\n').map(line => line.trim().split(/\s+/)[0] ?? '').filter(Boolean).map(normalizeTicker);
}

/** On-demand on: the editors cannot fetch, the Decide move check can. */
function fetchFirstHint(tickers: readonly string[], dataVersion: string): I18NText {
  const list = tickers.join(', ');
  return {
    en: `Not in snapshot ${dataVersion} yet: ${list}. Saving is refused until each one is added: check it as a move on the Decide page to fetch it on demand.`,
    fr: `Pas encore dans l’instantané ${dataVersion} : ${list}. L’enregistrement est refusé tant que chacun n’est pas ajouté : vérifiez-le comme mouvement dans la page Décider pour le récupérer à la demande.`,
  };
}

/** Tickers typed into an editor (account holding, final targets) against the supported universe. */
export function checkTickers(tickers: readonly string[], universe: UniverseView, onDemand: boolean): TickerCheck {
  if (!universe.ready || !universe.dataVersion) return NO_ISSUE;
  const unsupported = unsupportedTickers(tickers, universe.assets);
  const [first] = unsupported;
  if (first === undefined) return NO_ISSUE;
  if (onDemand) return { unsupported, blocking: false, message: fetchFirstHint(unsupported, universe.dataVersion) };
  return {
    unsupported,
    blocking: true,
    message: unsupported.length === 1
      ? unsupportedTickerMessage(first, universe.total, universe.dataVersion)
      : unsupportedTickersMessage(unsupported, universe.dataVersion),
  };
}

/**
 * Replay: the run is refused for a ticker outside the current snapshot (api/runtime.py
 * `_check_request`) and the page has no preview, so the ticker blocks Run even with on-demand
 * fetching on (the message then points to the Decide fetch). Held tickers and cash are left to
 * the server, as is a ticker without a price at the cutoff.
 */
export function replayTickerIssue(ticker: string, universe: UniverseView, held: readonly string[], onDemand: boolean): MoveFormIssue | null {
  if (!universe.ready || !universe.dataVersion) return null;
  const wanted = normalizeTicker(ticker);
  if (!wanted || isCashTicker(wanted) || held.some(t => normalizeTicker(t) === wanted)) return null;
  if (unsupportedTickers([wanted], universe.assets).length === 0) return null;
  const message = onDemand
    ? {
      en: `${wanted} is not in snapshot ${universe.dataVersion}: a replay uses only instruments of the snapshot. Check it as a move on the Decide page to fetch it on demand first.`,
      fr: `${wanted} n’est pas dans l’instantané ${universe.dataVersion} : un rejeu n’utilise que les instruments de l’instantané. Vérifiez-le d’abord comme mouvement dans la page Décider pour le récupérer à la demande.`,
    }
    : unsupportedTickerMessage(wanted, universe.total, universe.dataVersion);
  return { field: 'ticker', message };
}

/** Replay: beside a disabled Run button when the move form has an issue. */
export const REPLAY_FIX_MOVE: I18NText = {
  en: 'Fix the move details above to run the replay.',
  fr: 'Corrigez les détails du mouvement ci-dessus pour lancer le rejeu.',
};

/** Instrument discovery (Labs): the count, e.g. "31 of 31 instruments · snapshot snap-…". */
export function instrumentCountLine(shown: number, total: number, dataVersion: string | null): I18NText {
  const noun = total === 1 ? 'instrument' : 'instruments';
  return {
    en: `${shown} of ${total} ${noun}${dataVersion ? ` · snapshot ${dataVersion}` : ''}`,
    fr: `${shown} sur ${total} ${noun}${dataVersion ? ` · instantané ${dataVersion}` : ''}`,
  };
}

/** Instrument discovery (Labs): a search with no match says what the snapshot covers, from the loaded data. */
export function noMatchingInstrument(query: string, total: number, dataVersion: string | null, markets: readonly string[]): I18NText {
  const q = query.trim();
  const covers = total === 1 ? 'instrument' : 'instruments';
  const where = markets.length ? markets.join(', ') : null;
  const en = `No supported instrument matches “${q}”.`
    + (dataVersion ? ` Snapshot ${dataVersion} covers ${total} ${covers}${where ? ` on these markets: ${where}` : ''}.` : '')
    + ' Listings on other exchanges are not loaded.';
  const fr = `Aucun instrument pris en charge ne correspond à « ${q} ».`
    + (dataVersion ? ` L’instantané ${dataVersion} couvre ${total} ${covers}${where ? ` sur ces marchés : ${where}` : ''}.` : '')
    + ' Les titres cotés sur d’autres bourses ne sont pas chargés.';
  return { en, fr };
}

/** Instrument discovery (Labs): clears the search. */
export function showAllInstruments(total: number): I18NText {
  return { en: `Show all ${total}`, fr: `Tout afficher (${total})` };
}
