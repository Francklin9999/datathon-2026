/** Pure profile-creator form logic (web/page-specs/profile-creator.md, api.md 3.3/3.4). */
import type {
  AssetClass, CreateProfileRequest, Currency, Experience, Objective, PartialProfile, Position, Preferences1,
  Profile, RiskLevel, ThemeTag,
} from '../contracts/types';
import { validateHoldings, type HoldingsIssue } from './holdings';

export interface ProfileForm {
  investorContext?: Profile["investorContext"];
  name: string;
  age: string;
  riskLevel: RiskLevel | '';
  horizonMin: string;
  horizonMax: string;
  objective: Objective | '';
  experience: Experience | '';
  reportingCurrency: Currency | '';
  themesOfInterest: ThemeTag[];
  excludedSectors: string;
  excludedAssetClasses: AssetClass[];
  esgFocus: boolean;
  avoidControversies: boolean;
  avoidSpeculative: boolean;
  cryptoInterest: 'none' | 'low' | 'open';
  wantsDiversification: boolean;
  notes: string;
  /** false → the server proposes a starting portfolio (api.md 3.3 portfolio: null). */
  ownHoldings: boolean;
  capital: string;
  positions: { ticker: string; weightPct: string }[];
}

export const EMPTY_PROFILE_FORM: ProfileForm = {
  name: '', age: '', riskLevel: '', horizonMin: '', horizonMax: '', objective: '', experience: '', reportingCurrency: '',
  themesOfInterest: [], excludedSectors: '', excludedAssetClasses: [], esgFocus: false, avoidControversies: false,
  avoidSpeculative: false, cryptoInterest: 'none', wantsDiversification: true, notes: '', ownHoldings: false,
  capital: '', positions: [],
};

type PreferenceFields = Pick<ProfileForm, 'themesOfInterest' | 'excludedSectors' | 'excludedAssetClasses' | 'esgFocus'
  | 'avoidControversies' | 'avoidSpeculative' | 'cryptoInterest' | 'wantsDiversification' | 'notes'>;

function prefsToForm(p: Preferences1): PreferenceFields {
  return {
    themesOfInterest: [...p.themesOfInterest], excludedSectors: p.excludedSectors.join(', '),
    excludedAssetClasses: [...p.excludedAssetClasses], esgFocus: p.esgFocus, avoidControversies: p.avoidControversies,
    avoidSpeculative: p.avoidSpeculative, cryptoInterest: p.cryptoInterest, wantsDiversification: p.wantsDiversification,
    notes: p.notes,
  };
}

/** Form pre-filled from an existing profile; saving a copy of a default creates a new ID (api.md 3.3). */
export function formFromProfile(profile: Profile, copySuffix = ''): ProfileForm {
  return {
    investorContext: profile.investorContext ? structuredClone(profile.investorContext) : profile.investorContext,
    name: `${profile.name}${copySuffix}`.slice(0, 40),
    age: profile.age === null ? '' : String(profile.age),
    riskLevel: profile.riskLevel,
    horizonMin: String(profile.horizonYears.min),
    horizonMax: profile.horizonYears.max === null ? '' : String(profile.horizonYears.max),
    objective: profile.objective,
    experience: profile.experience,
    reportingCurrency: profile.reportingCurrency,
    ...prefsToForm(profile.preferences),
    ownHoldings: true,
    capital: String(profile.portfolio.totalValue),
    positions: profile.portfolio.positions.map(p => ({ ticker: p.ticker, weightPct: String(p.weightPct) })),
  };
}

/** Apply a profile_draft result. Returns the fields it filled, which the UI marks provisional. */
export function applyDraft(form: ProfileForm, draft: PartialProfile): { form: ProfileForm; filled: string[] } {
  const next: ProfileForm = { ...form };
  const filled: string[] = [];
  if (draft.name !== undefined) { next.name = draft.name.slice(0, 40); filled.push('name'); }
  if (draft.age !== undefined) { next.age = draft.age === null ? '' : String(draft.age); filled.push('age'); }
  if (draft.riskLevel !== undefined) { next.riskLevel = draft.riskLevel; filled.push('riskLevel'); }
  if (draft.horizonYears !== undefined) {
    next.horizonMin = String(draft.horizonYears.min);
    next.horizonMax = draft.horizonYears.max === null ? '' : String(draft.horizonYears.max);
    filled.push('horizonYears');
  }
  if (draft.objective !== undefined) { next.objective = draft.objective; filled.push('objective'); }
  if (draft.experience !== undefined) { next.experience = draft.experience; filled.push('experience'); }
  if (draft.reportingCurrency !== undefined) { next.reportingCurrency = draft.reportingCurrency; filled.push('reportingCurrency'); }
  if (draft.investorContext !== undefined) { next.investorContext = structuredClone(draft.investorContext); filled.push('investorContext'); }
  if (draft.preferences !== undefined) { Object.assign(next, prefsToForm(draft.preferences)); filled.push('preferences'); }
  if (draft.portfolio !== undefined) {
    next.ownHoldings = true;
    next.capital = String(draft.portfolio.totalValue);
    next.positions = draft.portfolio.positions.map(p => ({ ticker: p.ticker, weightPct: String(p.weightPct) }));
    filled.push('portfolio');
  }
  return { form: next, filled };
}

export type ProfileFormIssue =
  | { field: Exclude<keyof ProfileForm, 'positions'>; code: 'required' | 'too_long' | 'invalid' | 'range' }
  | { field: 'positions'; code: 'holdings'; issue: HoldingsIssue };

function num(value: string): number | null {
  if (value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NaN;
}

export function formPositions(form: ProfileForm): Position[] {
  return form.positions
    .filter(p => p.ticker.trim() !== '' || p.weightPct.trim() !== '')
    .map(p => ({ ticker: p.ticker.trim().toUpperCase(), weightPct: Number(p.weightPct) }));
}

export function validateProfileForm(form: ProfileForm): ProfileFormIssue[] {
  const issues: ProfileFormIssue[] = [];
  const name = form.name.trim();
  if (!name) issues.push({ field: 'name', code: 'required' });
  else if (name.length > 40) issues.push({ field: 'name', code: 'too_long' });
  const context = form.investorContext;
  if (context?.country && !/^[A-Z]{2}$/.test(context.country)) issues.push({ field: 'investorContext', code: 'invalid' });
  if (context?.objectives?.some(g => !g.name.trim() || !Number.isFinite(g.horizonYears) || g.horizonYears <= 0 || g.horizonYears > 150)) issues.push({ field: 'investorContext', code: 'invalid' });
  const age = num(form.age);
  if (age !== null && (Number.isNaN(age) || age < 0 || age > 120 || !Number.isInteger(age))) issues.push({ field: 'age', code: 'invalid' });
  for (const field of ['riskLevel', 'objective', 'experience', 'reportingCurrency'] as const) {
    if (!form[field]) issues.push({ field, code: 'required' });
  }
  const min = num(form.horizonMin);
  const max = num(form.horizonMax);
  if (min === null) issues.push({ field: 'horizonMin', code: 'required' });
  else if (Number.isNaN(min) || min < 0) issues.push({ field: 'horizonMin', code: 'invalid' });
  if (max !== null && (Number.isNaN(max) || (min !== null && !Number.isNaN(min) && max < min))) issues.push({ field: 'horizonMax', code: 'range' });
  if (form.ownHoldings) {
    const capital = num(form.capital);
    if (capital === null || Number.isNaN(capital)) issues.push({ field: 'capital', code: 'required' });
    for (const issue of validateHoldings(formPositions(form), capital === null || Number.isNaN(capital) ? 1 : capital)) {
      issues.push({ field: 'positions', code: 'holdings', issue });
    }
  }
  return issues;
}

export function toCreateRequest(form: ProfileForm, fromDraftRunId: string | null): CreateProfileRequest {
  const max = num(form.horizonMax);
  const age = num(form.age);
  return {
    name: form.name.trim(),
    age: age === null || Number.isNaN(age) ? null : age,
    riskLevel: form.riskLevel as RiskLevel,
    horizonYears: { min: Number(form.horizonMin), max: max === null || Number.isNaN(max) ? null : max },
    objective: form.objective as Objective,
    experience: form.experience as Experience,
    reportingCurrency: form.reportingCurrency as Currency,
    preferences: {
      themesOfInterest: [...form.themesOfInterest],
      excludedSectors: form.excludedSectors.split(',').map(s => s.trim()).filter(Boolean),
      excludedAssetClasses: [...form.excludedAssetClasses],
      esgFocus: form.esgFocus, avoidControversies: form.avoidControversies, avoidSpeculative: form.avoidSpeculative,
      cryptoInterest: form.cryptoInterest, wantsDiversification: form.wantsDiversification, notes: form.notes,
    },
    portfolio: form.ownHoldings ? { totalValue: Number(form.capital), positions: formPositions(form) } : null,
    rules: null,
    fromDraftRunId,
    ...(form.investorContext ? { investorContext: structuredClone(form.investorContext) } : {}),
  };
}
