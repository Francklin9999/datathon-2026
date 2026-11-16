/** Portfolio editor helpers (web/page-specs/portfolio.md). */
import type { I18NText, Profile } from '../contracts/types';
import type { AccountValuationRow, AccountValuations } from '../api/readModels';

/** Goal-funding scenarios exist only for stated objectives: without any, no request is sent. */
export function goalFundingKey(base: string | null, profile: Pick<Profile, 'investorContext'>): string | null {
  return base && profile.investorContext?.objectives?.length ? `goals|${base}` : null;
}

export interface ValuationTotals {
  /** `server`: GET /profiles/{id}/account-valuations; `local`: summed from the loaded profile. */
  source: 'server' | 'local';
  currency: string;
  traded: number;
  privateValue: number;
  combined: number;
  /** Per-account rows from the server; empty for the local fallback and for a profile without accounts. */
  rows: AccountValuationRow[];
  limitations: string[];
}

type ValuedProfile = Pick<Profile, 'profileId' | 'reportingCurrency' | 'portfolio' | 'accounts'>;

/**
 * The totals the private-asset card shows. The server summary is used when it belongs to this
 * profile; otherwise (loading, error, fixture mode) the same sums are taken from the profile.
 */
export function valuationTotals(profile: ValuedProfile, summary: AccountValuations | null | undefined): ValuationTotals {
  if (summary && summary.profileId === profile.profileId) {
    return {
      source: 'server', currency: summary.currency,
      traded: summary.accounts.reduce((n, row) => n + row.modeledTradedValue, 0),
      privateValue: summary.accounts.reduce((n, row) => n + row.privateValue, 0),
      combined: summary.combinedValue,
      rows: summary.accounts.filter(row => row.accountId !== null),
      limitations: summary.limitations,
    };
  }
  const accounts = profile.accounts ?? [];
  const traded = accounts.length ? accounts.reduce((n, a) => n + a.portfolio.totalValue, 0) : profile.portfolio.totalValue;
  const privateValue = accounts.flatMap(a => a.privateAssets ?? []).reduce((n, a) => n + a.valuation.conversion.reportingValue, 0);
  return { source: 'local', currency: profile.reportingCurrency, traded, privateValue, combined: traded + privateValue, rows: [], limitations: [] };
}

/** The English limitation account_valuation_summary returns today (profiles/service.py), with its French. */
const KNOWN_VALUATION_LIMITATIONS: Record<string, I18NText> = {
  'Private values are user or imported estimates, converted at the receipt date; they are excluded from traded portfolio weights, returns and risk. Do not also include the same assets in the traded portfolio.': {
    en: 'Private values are user or imported estimates, converted at the receipt date; they are excluded from traded portfolio weights, returns and risk. Do not also include the same assets in the traded portfolio.',
    fr: 'Les valeurs privées sont des estimations saisies ou importées, converties à la date du reçu ; elles sont exclues des poids, des rendements et du risque du portefeuille coté. N’incluez pas aussi ces actifs dans le portefeuille coté.',
  },
};

/** A known server limitation in both languages, or null for a sentence this build does not know (shown as sent). */
export function valuationLimitationText(sentence: string): I18NText | null {
  return KNOWN_VALUATION_LIMITATIONS[sentence] ?? null;
}
