/** Narrow runtime validation for the additive risk model port; core contracts stay version 1.4.0. */
export interface SensitivityScenarioRequest {
  asOf: string;
  weights: Record<string, number>;
  shock: { kind: 'interest_rate' | 'credit_spread' | 'currency' | 'commodity' | 'factor'; key: string; change: number; assumption: string };
  sensitivities: Record<string, { value: number; source: string; asOf: string }>;
}
export interface SensitivityScenarioResult {
  impactFraction: number | null;
  knownImpactFraction: number;
  contributions: Record<string, number>;
  missing: string[];
  model: string;
  unit: 'fraction';
  asOf: string;
}
export function sensitivityScenarioResult(value: unknown): SensitivityScenarioResult {
  if (!value || typeof value !== 'object') throw new Error('Invalid sensitivity scenario response');
  const r = value as Record<string, unknown>;
  if ((r.impactFraction !== null && (typeof r.impactFraction !== 'number' || !Number.isFinite(r.impactFraction))) ||
    typeof r.knownImpactFraction !== 'number' || !Number.isFinite(r.knownImpactFraction) ||
    typeof r.model !== 'string' || r.unit !== 'fraction' || typeof r.asOf !== 'string' ||
    !Array.isArray(r.missing) || !r.missing.every(v => typeof v === 'string') ||
    !r.contributions || typeof r.contributions !== 'object' || Array.isArray(r.contributions) ||
    !Object.values(r.contributions).every(v => typeof v === 'number' && Number.isFinite(v))) throw new Error('Invalid sensitivity scenario response');
  return r as unknown as SensitivityScenarioResult;
}
