/** Binance Vision entry of GET /intelligence/crypto-markets/venues (backend crypto_markets.venue_catalog). */
export type VisionVenue = { symbols: string[]; licence: string; limitations: string[] };

/** Used while the venue list loads or when it cannot be read; mirrors MARKETS['binance_vision'] in crypto_markets.py. */
export const VISION_FALLBACK_SYMBOLS = ['BTCUSDT', 'BTCUSDC', 'BTCEUR', 'ETHUSDT', 'ETHUSDC', 'ETHEUR', 'SOLUSDT', 'SOLUSDC'];

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

/** Reads the binance_vision venue; null when it is absent, has no exact market symbols or is malformed. */
export function visionVenue(body: unknown): VisionVenue | null {
  if (!isRecord(body) || !Array.isArray(body.venues)) return null;
  const venue = body.venues.find(item => isRecord(item) && item.venue === 'binance_vision');
  if (!isRecord(venue) || !Array.isArray(venue.markets) || typeof venue.licence !== 'string'
    || !Array.isArray(venue.limitations) || !venue.limitations.every(note => typeof note === 'string')) return null;
  const symbols: string[] = [];
  for (const market of venue.markets) {
    if (!isRecord(market) || typeof market.venue_symbol !== 'string' || !market.venue_symbol) return null;
    if (!symbols.includes(market.venue_symbol)) symbols.push(market.venue_symbol);
  }
  if (!symbols.length) return null;
  return { symbols, licence: venue.licence, limitations: venue.limitations as string[] };
}
