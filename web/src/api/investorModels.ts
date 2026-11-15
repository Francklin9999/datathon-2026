/** Runtime validation for the separately versioned, caller-supplied model interfaces. */
export interface FactorFitResult {
  alphaPerPeriod: number;
  betas: Record<string, number>;
  residualStdev: number | null;
  rSquared: number | null;
  observations: number;
  firstStart: string;
  lastEnd: string;
  sourceIds: string[];
  excludedReturns: number;
  excludedFactors: number;
  limitations: string[];
}

export interface FundLookThroughResult {
  direct: Record<string, number>;
  indirect: Record<string, number>;
  unresolvedWeight: number;
  snapshotDates: Record<string, string>;
  sourceIds: Record<string, string>;
  sources: Record<string, FundEvidence>;
  overlap: { firstIsin: string; secondIsin: string; weight: number }[];
  limitations: string[];
}

export interface FundEvidence {
  source_id: string;
  url: string;
  content_sha256: string;
  observed_at: string | null;
  published_at: string | null;
  available_at: string;
  retrieved_at: string;
  licence: string;
  limitations: string[];
}

const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const string = (v: unknown): v is string => typeof v === 'string';
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(string);
const date = (v: unknown): v is string => string(v) && /^\d{4}-\d{2}-\d{2}$/.test(v);
const count = (v: unknown): v is number => finite(v) && Number.isInteger(v) && v >= 0;
const numbers = (v: unknown): v is Record<string, number> => object(v) && Object.values(v).every(finite);
const stringMap = (v: unknown): v is Record<string, string> => object(v) && Object.values(v).every(string);
const fraction = (v: unknown): v is number => finite(v) && v >= 0 && v <= 1 + 1e-9;
const fractionMap = (v: unknown): v is Record<string, number> => object(v) && Object.values(v).every(fraction);
const timestamp = (v: unknown): v is string => string(v) && Number.isFinite(Date.parse(v)) && /(?:Z|[+-]\d\d:\d\d)$/.test(v);

/** Reject malformed or non-finite results before any UI renders them. */
export function factorFitResult(value: unknown): FactorFitResult {
  if (!object(value) || !finite(value.alphaPerPeriod) || !numbers(value.betas) ||
      !(value.residualStdev === null || finite(value.residualStdev) && value.residualStdev >= 0) ||
      !(value.rSquared === null || finite(value.rSquared)) || !count(value.observations) ||
      !date(value.firstStart) || !date(value.lastEnd) || value.firstStart > value.lastEnd ||
      !strings(value.sourceIds) || !count(value.excludedReturns) || !count(value.excludedFactors) ||
      !strings(value.limitations)) throw new Error('Invalid factor fit response');
  return value as unknown as FactorFitResult;
}

function isEvidence(value: unknown): value is FundEvidence {
  return object(value) && string(value.source_id) && string(value.url) &&
    string(value.content_sha256) && /^[0-9a-f]{64}$/.test(value.content_sha256) &&
    (value.observed_at === null || timestamp(value.observed_at)) &&
    (value.published_at === null || timestamp(value.published_at)) &&
    timestamp(value.available_at) && timestamp(value.retrieved_at) &&
    string(value.licence) && strings(value.limitations);
}

/** Disclosed overlap is a lower bound, with unresolved portfolio weight retained separately. */
export function fundLookThroughResult(value: unknown): FundLookThroughResult {
  if (!object(value) || !fractionMap(value.direct) || !fractionMap(value.indirect) ||
      !fraction(value.unresolvedWeight) || !stringMap(value.snapshotDates) ||
      !Object.values(value.snapshotDates).every(date) || !stringMap(value.sourceIds) ||
      !object(value.sources) || !Object.values(value.sources).every(isEvidence) ||
      !Array.isArray(value.overlap) || !value.overlap.every(row => object(row) &&
        string(row.firstIsin) && string(row.secondIsin) && fraction(row.weight)) ||
      !strings(value.limitations)) throw new Error('Invalid fund look-through response');
  const total = Object.values(value.direct).reduce((a, b) => a + b, 0) +
    Object.values(value.indirect).reduce((a, b) => a + b, 0) + value.unresolvedWeight;
  if (Math.abs(total - 1) > 1e-7) throw new Error('Fund look-through weights do not conserve portfolio value');
  return value as unknown as FundLookThroughResult;
}

/** Parse data only; no executable user code is accepted. */
export function parseModelInput(text: string): Record<string, unknown> {
  if (new TextEncoder().encode(text).length > 240_000) throw new Error('Input exceeds 240 kB');
  const value: unknown = JSON.parse(text);
  if (!object(value)) throw new Error('Input must be a JSON object');
  return value;
}
