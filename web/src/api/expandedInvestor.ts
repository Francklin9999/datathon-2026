import { validateContract } from '../contracts/validate';
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type ModelResult = { [key: string]: Json };
function object(value: unknown): value is ModelResult { return !!value && typeof value === 'object' && !Array.isArray(value); }
function finiteTree(value: unknown, depth = 0): boolean {
  if (depth > 30) return false;
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  return Array.isArray(value) ? value.every(v => finiteTree(v, depth + 1)) : object(value) && Object.values(value).every(v => finiteTree(v, depth + 1));
}
const required: Record<string, string[]> = {
  joint: ['state', 'capital', 'goals', 'events', 'missingInputs', 'assumptions'],
  compare: ['portfolios', 'sameSample', 'currency', 'limitations'],
  positions: ['positions', 'currency', 'limitations'],
};
export function expandedResult(kind: keyof typeof required, value: unknown): ModelResult {
  if (!object(value) || !finiteTree(value) || !required[kind]?.every(key => key in value)) throw new Error('Invalid investor model response');
  const inspect = (row: ModelResult) => {
    if (row.facts !== undefined) {
      if (!object(row.facts)) throw new Error('Invalid fact map');
      for (const [id, fact] of Object.entries(row.facts)) if (validateContract('Fact', fact).id !== id) throw new Error('Mismatched fact identity');
    }
  };
  inspect(value);
  if (Array.isArray(value.portfolios)) for (const row of value.portfolios) { if (!object(row)) throw new Error('Invalid portfolio'); inspect(row); }
  return value;
}
export function record(value: Json | undefined): ModelResult { return object(value) ? value : {}; }
export function rows(value: Json | undefined): ModelResult[] { return Array.isArray(value) ? value.filter(object) : []; }
export function texts(value: Json | undefined): string[] { return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []; }
export function scalar(value: Json | undefined): string { return value === null || value === undefined ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value); }
export function numeric(value: Json | undefined): number | null { return typeof value === 'number' && Number.isFinite(value) ? value : null; }
