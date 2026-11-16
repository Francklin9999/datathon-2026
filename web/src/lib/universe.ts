/**
 * The supported universe: the instruments of the pinned snapshot (`GET /assets`). Ticker fields check
 * against it before a request, and say which snapshot they mean, instead of letting the API refuse
 * the ticker after submit. Every write checks the same set on the server (an unknown ticker is a
 * 422 `validation_error` with `details.unknown` on profile writes, a 404 `not_found` on /check and
 * /runs), so the client check only moves that refusal earlier.
 *
 * Callers check only once the universe read has completed (useAssetUniverse().ready): an empty list
 * means "not loaded", never "nothing supported", so a failed read never blocks input.
 */
import type { Asset, AssetsResponse, I18NText } from '../contracts/types';

/**
 * Whether one `/assets` page of at most `limit` items is the whole universe, so a ticker missing from
 * it is unsupported. The API's `total` counts matches after its own 500 cap (datastore/service.py),
 * so `items >= total` alone is always true: a full page or a next cursor means it may be partial.
 */
export function universeComplete(data: Pick<AssetsResponse, 'items' | 'total' | 'nextCursor'>, limit: number): boolean {
  return data.nextCursor == null && data.items.length < limit && data.items.length >= data.total;
}

/**
 * Cash pseudo-assets (CASH.CAD, CASH.USD…) are valid positions but are not listed by /assets
 * (backend datastore/universe.py `__contains__`; constants.CASH_TICKERS). The server checks the
 * currency against its catalog; the client only recognises the shape.
 */
const CASH_TICKER = /^CASH\.[A-Z]{3}$/;

type Listed = Pick<Asset, 'ticker'>;

/** The form the API expects: trimmed, upper case. */
export function normalizeTicker(ticker: string): string {
  return ticker.trim().toUpperCase();
}

export function isCashTicker(ticker: string): boolean {
  return CASH_TICKER.test(normalizeTicker(ticker));
}

/** True when `ticker` is a listed instrument of `universe` or a cash pseudo-asset; false when empty. */
export function isSupportedTicker(universe: readonly Listed[], ticker: string): boolean {
  const wanted = normalizeTicker(ticker);
  if (!wanted) return false;
  return isCashTicker(wanted) || universe.some(asset => asset.ticker === wanted);
}

/**
 * The tickers of `tickers` that `universe` does not support, normalized, de-duplicated, in input
 * order; empty strings are skipped. An empty universe (not loaded) returns [].
 */
export function unsupportedTickers(tickers: readonly string[], universe: readonly Listed[]): string[] {
  if (universe.length === 0) return [];
  const known = new Set(universe.map(asset => asset.ticker));
  const out: string[] = [];
  for (const raw of tickers) {
    const ticker = normalizeTicker(raw);
    if (!ticker || isCashTicker(ticker) || known.has(ticker) || out.includes(ticker)) continue;
    out.push(ticker);
  }
  return out;
}

/** The markets the universe covers, unique and sorted (computed from the data, never hard-coded). */
export function universeMarkets(universe: readonly Pick<Asset, 'market'>[]): string[] {
  return [...new Set(universe.map(asset => asset.market).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

/** Under a ticker field whose value is not supported (the field blocks submit). */
export function unsupportedTickerMessage(ticker: string, total: number, dataVersion: string): I18NText {
  const t = normalizeTicker(ticker);
  return {
    en: `${t} is not one of the ${total} supported instruments of snapshot ${dataVersion}. Choose one from the list.`,
    fr: `${t} ne fait pas partie des ${total} instruments pris en charge de l’instantané ${dataVersion}. Choisissez-en un dans la liste.`,
  };
}

/** For a list of holdings (several tickers at once). */
export function unsupportedTickersMessage(tickers: readonly string[], dataVersion: string): I18NText {
  const list = tickers.map(normalizeTicker).join(', ');
  return {
    en: `Not supported in snapshot ${dataVersion}: ${list}. Use instruments from the list.`,
    fr: `Non pris en charge dans l’instantané ${dataVersion} : ${list}. Utilisez des instruments de la liste.`,
  };
}

/**
 * When on-demand fetching is on, an unlisted ticker does not block: the move check offers the
 * fetch (Decision Desk), so this is a hint, not an error.
 */
export function onDemandTickerHint(ticker: string, dataVersion: string): I18NText {
  const t = normalizeTicker(ticker);
  return {
    en: `${t} is not in snapshot ${dataVersion} yet. Check the move to see whether it can be fetched on demand.`,
    fr: `${t} n’est pas encore dans l’instantané ${dataVersion}. Vérifiez le mouvement pour voir s’il peut être récupéré à la demande.`,
  };
}

/** Summary of the supported-universe disclosure, e.g. "31 supported instruments". */
export function supportedCountLabel(total: number): I18NText {
  return total === 1
    ? { en: '1 supported instrument', fr: '1 instrument pris en charge' }
    : { en: `${total} supported instruments`, fr: `${total} instruments pris en charge` };
}

/** One line naming the snapshot and its markets, e.g. "Supported: the 31 instruments of snapshot … (NASDAQ, TSX)." */
export function supportedUniverseHint(total: number, dataVersion: string, markets: readonly string[]): I18NText {
  const where = markets.length ? ` (${markets.join(', ')})` : '';
  return {
    en: `Supported: the ${total} instruments of snapshot ${dataVersion}${where}.`,
    fr: `Pris en charge : les ${total} instruments de l’instantané ${dataVersion}${where}.`,
  };
}

/** Shown with the list when the deployment cannot add tickers (feature `on_demand_tickers` off). */
export const ON_DEMAND_OFF: I18NText = {
  en: 'Other tickers cannot be added in this deployment: on-demand fetching is turned off.',
  fr: 'D’autres symboles ne peuvent pas être ajoutés dans ce déploiement : la récupération à la demande est désactivée.',
};
