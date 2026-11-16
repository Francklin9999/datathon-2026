/**
 * Narrow runtime validation for two read routes outside the generated contract registry:
 * GET /profiles/{id}/account-valuations (api.md A1.1, profiles/service.py account_valuation_summary)
 * and GET /runs/{id}/trace (api.md §5.9, agents/trace.py build_trace). Only the fields the web
 * displays are checked and returned; anything else in the body is dropped.
 */

export interface AccountValuationRow {
  /** null only for the single "Primary" row of a profile without accounts. */
  accountId: string | null;
  name: string;
  modeledTradedValue: number;
  privateValue: number;
  combinedValue: number;
}

export interface AccountValuations {
  profileId: string;
  currency: string;
  accounts: AccountValuationRow[];
  combinedValue: number;
  limitations: string[];
}

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);

export function accountValuationsResult(value: unknown): AccountValuations {
  if (!record(value)) throw new Error('Invalid account valuations response');
  const { profileId, currency, accounts, combinedValue, limitations } = value;
  if (typeof profileId !== 'string' || typeof currency !== 'string' || !finite(combinedValue)
    || !Array.isArray(accounts) || !Array.isArray(limitations) || !limitations.every(l => typeof l === 'string')) {
    throw new Error('Invalid account valuations response');
  }
  const rows = accounts.map(row => {
    if (!record(row) || (row.accountId !== null && typeof row.accountId !== 'string') || typeof row.name !== 'string'
      || !finite(row.modeledTradedValue) || !finite(row.privateValue) || !finite(row.combinedValue)) {
      throw new Error('Invalid account valuation row');
    }
    return {
      accountId: row.accountId as string | null, name: row.name, modeledTradedValue: row.modeledTradedValue,
      privateValue: row.privateValue, combinedValue: row.combinedValue,
    };
  });
  return { profileId, currency, accounts: rows, combinedValue, limitations: limitations as string[] };
}

/** One `{ name, used, limit }` entry of a run trace (run-events.md §4). */
export interface TraceBudget { name: string; used: number; limit: number }

/** The part of GET /runs/{id}/trace the web reads today: the run id and its budgets. */
export interface RunTraceSummary { runId: string; budgets: TraceBudget[] }

export function runTraceResult(value: unknown): RunTraceSummary {
  if (!record(value) || typeof value.runId !== 'string' || !Array.isArray(value.budgets)) {
    throw new Error('Invalid run trace response');
  }
  const budgets = value.budgets.map(item => {
    if (!record(item) || typeof item.name !== 'string' || !finite(item.used) || !finite(item.limit)
      || item.used < 0 || item.limit < 0) throw new Error('Invalid run trace budget');
    return { name: item.name, used: item.used, limit: item.limit };
  });
  return { runId: value.runId, budgets };
}
