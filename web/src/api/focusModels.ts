import type { Fact } from '../contracts/types';
import { validateContract } from '../contracts/validate';
interface FocusCandidate {
  candidateId: string; kind: string; severity: string; label: string; factIds: string[]; evidenceIds: string[];
  affectedHoldings: string[]; investigation: string; navigationTarget: string; missingInputs: string[]; claimIds: string[];
}
interface FocusResult { asOf: string; candidates: FocusCandidate[]; facts: Record<string, Fact>; limitations: string[] }
interface TargetsResult {
  asOf: string; targets: { dimension: string; key: string; targetPct: number; actualPct: number | null; driftPct: number | null; driftThresholdPct: number | null; state: string; factId: string | null; origin: string; unavailableReason: string | null }[];
  facts: Record<string, Fact>; limitations: string[];
}
function obj(v: unknown): v is Record<string, unknown> { return !!v && typeof v === 'object' && !Array.isArray(v); }
function strings(v: unknown): v is string[] { return Array.isArray(v) && v.every(x => typeof x === 'string'); }
function finite(v: unknown) { return typeof v === 'number' && Number.isFinite(v); }
function nullable(v: unknown) { return v === null || finite(v); }
function common(v: unknown): v is Record<string, unknown> & { facts: Record<string, Fact> } {
  if (!obj(v) || typeof v.asOf !== 'string' || !strings(v.limitations) || !obj(v.facts)) return false;
  return Object.entries(v.facts).every(([id, fact]) => validateContract('Fact', fact).id === id);
}
export function focusResult(v: unknown): FocusResult {
  if (!common(v) || !Array.isArray(v.candidates) || v.candidates.length > 3 || !v.candidates.every(c => obj(c) && ['candidateId', 'kind', 'severity', 'label', 'investigation', 'navigationTarget'].every(k => typeof c[k] === 'string') && ['factIds', 'evidenceIds', 'affectedHoldings', 'missingInputs', 'claimIds'].every(k => strings(c[k])) && (c.factIds as string[]).every(id => id in v.facts))) throw new Error('Invalid strategic candidates');
  return v as unknown as FocusResult;
}
export function targetsResult(v: unknown): TargetsResult {
  if (!common(v) || !Array.isArray(v.targets) || !v.targets.every(t => obj(t) && typeof t.key === 'string' && typeof t.dimension === 'string' && typeof t.state === 'string' && typeof t.origin === 'string' && finite(t.targetPct) && nullable(t.actualPct) && nullable(t.driftPct) && nullable(t.driftThresholdPct) && (t.factId === null || typeof t.factId === 'string' && t.factId in v.facts))) throw new Error('Invalid allocation targets');
  return v as unknown as TargetsResult;
}
