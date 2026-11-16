/** Pure profile-creator form logic (web/page-specs/profile-creator.md, api.md 3.3/3.4). */
import type {
  Asset, AssetClass, CreateProfileRequest, Currency, Experience, I18NText, MissingField, Objective, PartialProfile,
  Position, Preferences1, Profile, ProfileDraftResult, RiskLevel, ThemeTag,
} from '../contracts/types';
import { ContractValidationError, validateContract } from '../contracts/validate';
import { validateHoldings, type HoldingsIssue } from './holdings';
import { EXPERIENCE, OBJECTIVE, RISK_LEVEL } from './labels';
import { unsupportedTickers } from './universe';

/** Labels of form fields and of the fields a profile draft can propose or withhold. */
export const PROFILE_FIELD_LABEL: Record<string, I18NText> = {
  name: { en: 'Name', fr: 'Nom' },
  age: { en: 'Age', fr: 'Âge' },
  occupation: { en: 'Occupation', fr: 'Profession' },
  riskLevel: { en: 'Risk level', fr: 'Niveau de risque' },
  horizonYears: { en: 'Horizon (years)', fr: 'Horizon (années)' },
  horizonMin: { en: 'Horizon minimum', fr: 'Horizon minimum' },
  horizonMax: { en: 'Horizon maximum', fr: 'Horizon maximum' },
  objective: { en: 'Objective', fr: 'Objectif' },
  experience: { en: 'Experience', fr: 'Expérience' },
  investorContext: { en: 'Investor policy inputs', fr: 'Entrées du plan investisseur' },
  'investorContext.country': { en: 'Country', fr: 'Pays' },
  'investorContext.riskCapacity': { en: 'Risk capacity', fr: 'Capacité de risque' },
  'investorContext.objectives': { en: 'Goals', fr: 'Objectifs' },
  'investorContext.investorType': { en: 'Investor type', fr: 'Type d’investisseur' },
  reportingCurrency: { en: 'Reporting currency', fr: 'Devise de présentation' },
  preferences: { en: 'Preferences', fr: 'Préférences' },
  rules: { en: 'Policy rules', fr: 'Règles du plan' },
  portfolio: { en: 'Holdings', fr: 'Positions' },
  capital: { en: 'Fictional capital', fr: 'Capital fictif' },
  positions: { en: 'Holdings', fr: 'Positions' },
};

/** A field's label; an unknown key reads as itself in both languages. */
export function profileFieldLabel(field: string): I18NText {
  return PROFILE_FIELD_LABEL[field] ?? { en: field, fr: field };
}

export interface ProfileForm {
  /** Local baseline for identifying user edits when copying or replacing a profile. */
  sourceProfile?: Profile;
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
  positions: { ticker: string; weightPct: string; sourcePosition?: Position }[];
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
    sourceProfile: structuredClone(profile),
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
    positions: profile.portfolio.positions.map(p => ({ ticker: p.ticker, weightPct: String(p.weightPct), sourcePosition: structuredClone(p) })),
  };
}

/**
 * Keep every unsaved field but compare the form against `latest` from now on. Used after a
 * stale-version 409: the replace request then targets the stored version and its input origins
 * are computed against what is actually stored. A form editing another profile is returned as is.
 */
export function rebaseForm(form: ProfileForm, latest: Profile): ProfileForm {
  if (form.sourceProfile?.profileId !== latest.profileId) return form;
  return { ...form, sourceProfile: structuredClone(latest) };
}

/**
 * Apply a profile_draft result onto the current form (drafts are additive: fields the draft does not
 * propose keep their value, and investorContext is merged key by key). Returns the fields it filled,
 * which the UI marks provisional; nested context keys read as `investorContext.<key>`.
 */
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
  if (draft.investorContext) {
    // Merged key by key: context the user entered (goals, notes, type…) stays.
    next.investorContext = { ...form.investorContext, ...structuredClone(draft.investorContext) };
    for (const [key, value] of Object.entries(draft.investorContext)) {
      if (value !== undefined) filled.push(`investorContext.${key}`);
    }
  }
  if (draft.preferences !== undefined) { Object.assign(next, prefsToForm(draft.preferences)); filled.push('preferences'); }
  if (draft.portfolio !== undefined) {
    next.ownHoldings = true;
    next.capital = String(draft.portfolio.totalValue);
    next.positions = draft.portfolio.positions.map(p => ({ ticker: p.ticker, weightPct: String(p.weightPct) }));
    filled.push('portfolio');
  }
  return { form: next, filled };
}

/**
 * The values already entered in the form, sent with a text draft as its confirmed `fields`
 * (api.md 5.1): the server keeps a drafted value equal to one of them. Only non-empty values that
 * are valid on their own are sent, so a half-typed field never makes the draft request invalid.
 */
export function partialFromForm(form: ProfileForm): PartialProfile {
  const candidates: [string, unknown][] = [];
  const name = form.name.trim();
  if (name && name.length <= 40) candidates.push(['name', name]);
  const age = num(form.age);
  if (age !== null && Number.isInteger(age) && age >= 0 && age <= 120) candidates.push(['age', age]);
  if (form.riskLevel) candidates.push(['riskLevel', form.riskLevel]);
  const min = num(form.horizonMin);
  const max = num(form.horizonMax);
  if (min !== null && !Number.isNaN(min) && min >= 0 && (max === null || (!Number.isNaN(max) && max >= min))) {
    candidates.push(['horizonYears', { min, max }]);
  }
  if (form.objective) candidates.push(['objective', form.objective]);
  if (form.experience) candidates.push(['experience', form.experience]);
  if (/^[A-Z]{3}$/.test(form.reportingCurrency)) candidates.push(['reportingCurrency', form.reportingCurrency]);
  const context: Record<string, unknown> = {};
  if (form.investorContext?.country && /^[A-Z]{2}$/.test(form.investorContext.country)) context.country = form.investorContext.country;
  if (form.investorContext?.riskCapacity) context.riskCapacity = form.investorContext.riskCapacity;
  if (Object.keys(context).length > 0) candidates.push(['investorContext', context]);
  const fields: Record<string, unknown> = {};
  for (const [key, value] of candidates) {
    try { validateContract('PartialProfile', { [key]: value }); fields[key] = value; } catch { /* not sent */ }
  }
  try { return validateContract('PartialProfile', fields); } catch { return {}; }
}

/** Fields applyDraft writes into the form; any other drafted key (e.g. occupation) has no form field. */
const APPLIED_DRAFT_FIELDS = new Set(['name', 'age', 'riskLevel', 'horizonYears', 'objective', 'experience', 'reportingCurrency', 'preferences', 'portfolio']);
/** Review order: what most changes the analysis first (the same order the server uses for questions). */
const DRAFT_PRIORITY = ['investorContext.riskCapacity', 'reportingCurrency', 'horizonYears', 'riskLevel', 'objective', 'investorContext.country'];

/** "10–15 years" / "10 à 15 ans"; "15+ years" / "15 ans et plus". */
export function horizonLabel(horizon: { min: number; max: number | null }): I18NText {
  if (horizon.max === null) return { en: `${horizon.min}+ years`, fr: `${horizon.min} ans et plus` };
  if (horizon.max === horizon.min) return { en: `${horizon.min} years`, fr: `${horizon.min} ans` };
  return { en: `${horizon.min}–${horizon.max} years`, fr: `${horizon.min} à ${horizon.max} ans` };
}

function draftValueLabel(field: string, value: unknown): I18NText | null {
  if ((field === 'riskLevel' || field === 'investorContext.riskCapacity') && typeof value === 'string' && value in RISK_LEVEL) return RISK_LEVEL[value as RiskLevel];
  if (field === 'objective' && typeof value === 'string' && value in OBJECTIVE) return OBJECTIVE[value as Objective];
  if (field === 'experience' && typeof value === 'string' && value in EXPERIENCE) return EXPERIENCE[value as Experience];
  if (field === 'horizonYears' && value && typeof value === 'object' && typeof (value as { min?: unknown }).min === 'number') {
    const { min, max } = value as { min: number; max?: number | null };
    return horizonLabel({ min, max: max ?? null });
  }
  if (typeof value === 'string' || typeof value === 'number') return { en: String(value), fr: String(value) };
  return null;
}

/** An old API's "Confirm <field>" question has no French; this replaces it in both languages. */
const GENERIC_QUESTION: I18NText = {
  en: 'Not found in your description. Confirm or enter it in the form.',
  fr: 'Absent de votre description. Confirmez-le ou saisissez-le dans le formulaire.',
};

export interface DraftProposedRow {
  field: string;
  label: I18NText;
  /** Null for a value without a short text form (e.g. preferences). */
  value: I18NText | null;
  explanation: I18NText | null;
  /** The form has no field for it (e.g. occupation): shown, not applied. */
  applied: boolean;
  /** Equal to a value the form already held when the draft was requested. */
  alreadyInForm: boolean;
}

export interface DraftWithheldRow { field: string; label: I18NText; question: I18NText }

/**
 * The draft review: every proposed field with its value (nested investorContext keys listed one by
 * one) and every withheld field with its question, both in the same priority order.
 */
export function draftReviewRows(draft: ProfileDraftResult, sent: PartialProfile = {}): { proposed: DraftProposedRow[]; withheld: DraftWithheldRow[] } {
  const explanations = new Map(draft.explanations.map(e => [e.field, e.text]));
  const sentWire = new Map<string, unknown>(Object.entries(sent));
  const sentContext = new Map<string, unknown>(Object.entries(sent.investorContext ?? {}));
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  const proposed: DraftProposedRow[] = [];
  for (const [key, value] of Object.entries(draft.profile)) {
    if (value === undefined) continue;
    if (key === 'investorContext' && value && typeof value === 'object') {
      for (const [sub, subValue] of Object.entries(value)) {
        if (subValue === undefined) continue;
        const field = `investorContext.${sub}`;
        proposed.push({ field, label: profileFieldLabel(field), value: draftValueLabel(field, subValue),
          explanation: explanations.get(field) ?? null, applied: true,
          alreadyInForm: sentContext.has(sub) && same(sentContext.get(sub), subValue) });
      }
      continue;
    }
    proposed.push({ field: key, label: profileFieldLabel(key), value: draftValueLabel(key, value),
      explanation: explanations.get(key) ?? null, applied: APPLIED_DRAFT_FIELDS.has(key),
      alreadyInForm: sentWire.has(key) && same(sentWire.get(key), value) });
  }
  const withheld = draft.unresolved.map((item: MissingField) => ({
    field: item.field, label: profileFieldLabel(item.field), question: draftQuestion(item),
  }));
  const rank = (field: string) => { const i = DRAFT_PRIORITY.indexOf(field); return i === -1 ? DRAFT_PRIORITY.length : i; };
  proposed.sort((a, b) => rank(a.field) - rank(b.field));
  withheld.sort((a, b) => rank(a.field) - rank(b.field));
  return { proposed, withheld };
}

/** The question of an unresolved draft field, with a bilingual fallback for an old API's "Confirm <field>". */
export function draftQuestion(item: MissingField): I18NText {
  const { en, fr } = item.question;
  return en.trim() === fr.trim() && /^Confirm \S+$/.test(en.trim()) ? GENERIC_QUESTION : item.question;
}

export type ProfileFormIssue =
  | { field: Exclude<keyof ProfileForm, 'positions' | 'sourceProfile'>; code: 'required' | 'too_long' | 'invalid' | 'range'; detail?: string }
  | { field: 'positions'; code: 'holdings'; issue: HoldingsIssue }
  | { field: 'positions'; code: 'unsupported'; tickers: string[] };

function num(value: string): number | null {
  if (value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : Number.NaN;
}

export function formPositions(form: ProfileForm): Position[] {
  return form.positions
    .filter(p => p.ticker.trim() !== '' || p.weightPct.trim() !== '')
    .map(p => ({ ...(p.sourcePosition?.ticker === p.ticker.trim().toUpperCase() ? p.sourcePosition : {}), ticker: p.ticker.trim().toUpperCase(), weightPct: Number(p.weightPct) }));
}

/**
 * `universe` is the snapshot's complete instrument list (pass it only once useAssetUniverse().ready):
 * a holding outside it blocks Save, as the server refuses it (422 `details.unknown`). Omitted, the
 * tickers are not checked.
 */
export function validateProfileForm(form: ProfileForm, universe?: readonly Pick<Asset, 'ticker'>[]): ProfileFormIssue[] {
  const issues: ProfileFormIssue[] = [];
  const name = form.name.trim();
  if (!name) issues.push({ field: 'name', code: 'required' });
  else if (name.length > 40) issues.push({ field: 'name', code: 'too_long' });
  const context = form.investorContext;
  if (context) {
    try { validateContract('InvestorContext', context); }
    catch (error) {
      const detail = error instanceof ContractValidationError ? error.issues.slice(0, 4).map(issue => `${issue.instancePath || '/'}: ${issue.message}`).join('; ') : 'Invalid investor context';
      issues.push({ field: 'investorContext', code: 'invalid', detail });
    }
  }
  if (context?.country && !/^[A-Z]{2}$/.test(context.country)) issues.push({ field: 'investorContext', code: 'invalid' });
  if (context?.objectives?.some(g => !g.name.trim() || !Number.isFinite(g.horizonYears) || g.horizonYears <= 0 || g.horizonYears > 150)) issues.push({ field: 'investorContext', code: 'invalid' });
  if (context?.horizons?.some(h => !h.name.trim() || (h.startDate && ((h.endDate && h.startDate > h.endDate) || (h.deadline && h.startDate > h.deadline))))) issues.push({ field: 'investorContext', code: 'invalid' });
  if (context?.requirements?.some(r => !r.name.trim() || !Number.isFinite(r.amount) || r.amount < 0)) issues.push({ field: 'investorContext', code: 'invalid' });
  const age = num(form.age);
  if (age !== null && (Number.isNaN(age) || age < 0 || age > 120 || !Number.isInteger(age))) issues.push({ field: 'age', code: 'invalid' });
  for (const field of ['riskLevel', 'objective', 'experience', 'reportingCurrency'] as const) {
    if (!form[field]) issues.push({ field, code: 'required' });
  }
  if (form.reportingCurrency && !/^[A-Z]{3}$/.test(form.reportingCurrency)) issues.push({ field: 'reportingCurrency', code: 'invalid' });
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
    const unknown = universe ? unsupportedTickers(formPositions(form).map(p => p.ticker), universe) : [];
    if (unknown.length > 0) issues.push({ field: 'positions', code: 'unsupported', tickers: unknown });
  }
  return issues;
}

export function toCreateRequest(form: ProfileForm, fromDraftRunId: string | null): CreateProfileRequest {
  const max = num(form.horizonMax);
  const age = num(form.age);
  const request: CreateProfileRequest = {
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
  const previous = form.sourceProfile;
  if (previous) {
    const context = request.investorContext ?? {};
    const origins = { ...context.inputOrigins };
    let changed = false;
    for (const key of ['name', 'age', 'riskLevel', 'horizonYears', 'objective', 'experience', 'reportingCurrency', 'preferences'] as const) {
      if (JSON.stringify(request[key]) !== JSON.stringify(previous[key])) {
        origins[key] = 'user'; changed = true;
      }
    }
    const oldPortfolio = { totalValue: previous.portfolio.totalValue, positions: previous.portfolio.positions };
    if (JSON.stringify(request.portfolio) !== JSON.stringify(oldPortfolio)) {
      origins.portfolio = request.portfolio ? 'user' : 'assumption'; changed = true;
    }
    if (request.riskLevel !== previous.riskLevel) context.riskToleranceOrigin = 'user';
    if (context.investorType !== previous.investorContext?.investorType) context.investorTypeOrigin = 'user';
    for (const key of ['country', 'language'] as const) {
      if (context[key] !== previous.investorContext?.[key]) { origins[key] = 'user'; changed = true; }
    }
    if (changed) { context.inputOrigins = origins; request.investorContext = context; }
  }
  return request;
}
