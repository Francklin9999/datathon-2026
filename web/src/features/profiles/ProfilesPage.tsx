'use client';
/**
 * Profiles — fictional creator and plan confirmation (T13, P1, web/page-specs/profile-creator.md).
 * Form or text draft (profile_draft run); drafted fields stay provisional and unresolved questions
 * must be confirmed before Save. Defaults are copied to a new ID; custom profiles use version
 * checks (409 keeps the unsaved form). No real contact or account information is requested.
 */
import { useMemo, useState, type ReactNode } from 'react';
import type { AssetClass, I18NText, ProfileDraftResult, InvestmentGoal, Profile, ProfilesResponse, Run, ThemeTag } from '../../contracts/types';
import { ThemeTag as THEMES } from '../../contracts/catalog';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card, PageHeader } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { RunStatusBadge } from '../../components/common/Badges';
import { RunTimeline } from '../../components/run/RunTimeline';
import { ASSET_CLASS, EXPERIENCE, OBJECTIVE, RISK_LEVEL, labelOf, THEME_TAG } from '../../lib/labels';
import { fmtMoney } from '../../lib/format';
import { MAX_POSITIONS, weightSum } from '../../lib/holdings';
import {
  EMPTY_PROFILE_FORM, applyDraft, formFromProfile, formPositions, toCreateRequest, validateProfileForm,
  type ProfileForm, type ProfileFormIssue,
} from '../../lib/profileForm';
import { AllocationInputs } from './AllocationInputs';
import { InvestorInputs } from './InvestorInputs';
import { ProfileCompare } from './ProfileCompare';
import { horizonText } from '../home/HomePage';

const RISK_LEVELS = Object.keys(RISK_LEVEL) as (keyof typeof RISK_LEVEL)[];
const OBJECTIVES = Object.keys(OBJECTIVE) as (keyof typeof OBJECTIVE)[];
const EXPERIENCES = Object.keys(EXPERIENCE) as (keyof typeof EXPERIENCE)[];
const ASSET_CLASSES = Object.keys(ASSET_CLASS) as AssetClass[];
const THEME_TAGS = Object.values(THEMES) as ThemeTag[];

const FIELD_LABEL: Record<string, I18NText> = {
  name: { en: 'Name', fr: 'Nom' },
  age: { en: 'Age', fr: 'Âge' },
  riskLevel: { en: 'Risk level', fr: 'Niveau de risque' },
  horizonMin: { en: 'Horizon minimum', fr: 'Horizon minimum' },
  horizonMax: { en: 'Horizon maximum', fr: 'Horizon maximum' },
  objective: { en: 'Objective', fr: 'Objectif' },
  experience: { en: 'Experience', fr: 'Expérience' },
  reportingCurrency: { en: 'Reporting currency', fr: 'Devise de présentation' },
  capital: { en: 'Fictional capital', fr: 'Capital fictif' },
  positions: { en: 'Holdings', fr: 'Positions' },
};

const label = (field: string, tr: (t: I18NText) => string) => tr(FIELD_LABEL[field] ?? { en: field, fr: field });

function issueText(issue: ProfileFormIssue, tr: (t: I18NText) => string): string {
  if (issue.code === 'holdings') {
    const { code, detail } = issue.issue;
    const messages: Record<typeof code, I18NText> = {
      empty: { en: 'Add at least one holding.', fr: 'Ajoutez au moins une position.' },
      too_many: { en: `At most ${MAX_POSITIONS} positions (${detail} entered).`, fr: `Au plus ${MAX_POSITIONS} positions (${detail} saisies).` },
      duplicate: { en: `Ticker ${detail} appears more than once.`, fr: `Le symbole ${detail} apparaît plus d’une fois.` },
      negative: { en: `Weight of ${detail} must be zero or more.`, fr: `Le poids de ${detail} doit être positif ou nul.` },
      sum: { en: `Weights must total 100 ± 0.01; they currently total ${detail}.`, fr: `Les poids doivent totaliser 100 ± 0,01 ; total actuel ${detail}.` },
      capital: { en: 'Fictional capital must be positive.', fr: 'Le capital fictif doit être positif.' },
    };
    return `${label('positions', tr)}: ${tr(messages[code])}`;
  }
  const messages = {
    required: { en: 'required.', fr: 'obligatoire.' },
    too_long: { en: 'at most 40 characters.', fr: '40 caractères au plus.' },
    invalid: { en: 'not a valid value.', fr: 'valeur non valide.' },
    range: { en: 'must be empty or at least the minimum.', fr: 'doit être vide ou au moins égal au minimum.' },
  } as const;
  return `${label(issue.field, tr)}: ${tr(messages[issue.code])}`;
}

export function ProfilesPage() {
  const { tr, feature, meta } = useApp();
  if (meta && !feature('profile_creator')) {
    return (
      <>
        <PageHeader title={tr({ en: 'Profiles', fr: 'Profils' })} />
        <Unavailable title={tr({ en: 'The profile creator is turned off in this deployment.', fr: 'Le créateur de profils est désactivé dans ce déploiement.' })}>
          {tr({ en: 'The default fictional profiles remain available from the persona menu.', fr: 'Les profils fictifs par défaut restent disponibles dans le menu des personas.' })}
        </Unavailable>
      </>
    );
  }
  return <ProfilesContent />;
}

type Editing = { mode: 'create'; fromDraftRunId: string | null } | { mode: 'update'; profileId: string; version: number };

const PREFERENCE_TOGGLES = [
  ['esgFocus', { en: 'ESG focus', fr: 'Accent ESG' }],
  ['avoidControversies', { en: 'Avoid controversies', fr: 'Éviter les controverses' }],
  ['avoidSpeculative', { en: 'Avoid speculative assets', fr: 'Éviter les actifs spéculatifs' }],
  ['wantsDiversification', { en: 'Wants diversification', fr: 'Souhaite diversifier' }],
] as const;

function ProfilesContent() {
  const { tr, lang, profiles, applyProfile, removeProfile, selectProfile, reloadProfiles, announce, sessionId, meta } = useApp();
  const archivedProfiles = useQuery<ProfilesResponse>(sessionId ? `archived|${sessionId}|${profiles.map(p => `${p.profileId}:${p.version}`).join()}` : null, signal => getApiClient().archivedProfiles(signal));
  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [editing, setEditing] = useState<Editing>({ mode: 'create', fromDraftRunId: null });
  const [provisional, setProvisional] = useState<string[]>([]);
  const [unresolved, setUnresolved] = useState<ProfileDraftResult['unresolved']>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<ApiRequestError | null>(null);
  const issues = useMemo(() => validateProfileForm(form), [form]);
  const needsConfirmation = provisional.length > 0 || unresolved.length > 0;

  const set = (patch: Partial<ProfileForm>) => setForm(f => ({ ...f, ...patch }));
  const setGoal = (index: number, patch: Partial<InvestmentGoal>) => setForm(f => ({ ...f, investorContext: { ...f.investorContext,
    objectives: f.investorContext?.objectives?.map((g, i) => i === index ? { ...g, ...patch } : g) ?? [] } }));
  const load = (next: ProfileForm, mode: Editing) => {
    setForm(next); setEditing(mode); setProvisional([]); setUnresolved([]); setConfirmed(false); setSubmitted(false); setSaveError(null);
  };

  const save = async () => {
    setSubmitted(true);
    if (issues.length > 0 || (needsConfirmation && !confirmed)) return;
    setSaving(true); setSaveError(null);
    try {
      const client = getApiClient();
      const body = toCreateRequest(form, editing.mode === 'create' ? editing.fromDraftRunId : null);
      const saved: Profile = editing.mode === 'create'
        ? await client.createProfile(body)
        : await client.updateProfile(editing.profileId, { ...body, version: editing.version });
      applyProfile(saved);
      selectProfile(saved.profileId);
      announce(tr({ en: `Profile ${saved.name} saved.`, fr: `Profil ${saved.name} enregistré.` }));
      load(EMPTY_PROFILE_FORM, { mode: 'create', fromDraftRunId: null });
    } catch (error) {
      setSaveError(asApiError(error));
    } finally { setSaving(false); }
  };

  const duplicate = async (profile: Profile) => {
    try { const saved = await getApiClient().duplicateProfile(profile.profileId); applyProfile(saved); selectProfile(saved.profileId); }
    catch (error) { setSaveError(asApiError(error)); }
  };

  const setArchive = async (profile: Profile, archived: boolean) => {
    try {
      const saved = await getApiClient().archiveProfile(profile.profileId, archived, profile.version);
      if (archived) removeProfile(profile.profileId); else applyProfile(saved);
      archivedProfiles.reload();
    } catch (error) { setSaveError(asApiError(error)); }
  };

  const remove = async (profile: Profile) => {
    try {
      await getApiClient().deleteProfile(profile.profileId);
      removeProfile(profile.profileId);
      announce(tr({ en: `Profile ${profile.name} deleted.`, fr: `Profil ${profile.name} supprimé.` }));
    } catch (error) { setSaveError(asApiError(error)); }
  };

  const fieldIssues = (field: string) => (submitted ? issues.filter(i => i.field === field) : []);
  const sum = weightSum(formPositions(form));
  const updatePosition = (index: number, patch: Partial<{ ticker: string; weightPct: string }>) =>
    set({ positions: form.positions.map((row, j) => (j === index ? { ...row, ...patch } : row)) });

  return (
    <>
      <PageHeader tour="profiles-header" title={tr({ en: 'Fictional profiles', fr: 'Profils fictifs' })}>
        <p className="page-sub">{tr({ en: 'Fictional profiles only: don’t enter real personal details.', fr: 'Profils fictifs seulement : n’entrez aucune donnée personnelle réelle.' })}</p>
      </PageHeader>

      <Card title={tr({ en: 'Profiles in this session', fr: 'Profils de cette session' })}>
        <ul className="list-plain">
          {profiles.map(p => (
            <li key={p.profileId}>
              <strong>{p.name}</strong>{' '}
              <span className="small muted">· {p.isDefault ? tr({ en: 'default (read-only; copy to change)', fr: 'par défaut (lecture seule ; copiez pour modifier)' }) : tr({ en: 'custom', fr: 'personnalisé' })} · {labelOf(RISK_LEVEL, p.riskLevel, lang)} · {horizonText(p, tr)} · {fmtMoney(p.portfolio.totalValue, p.portfolio.currency, lang)}</span>
              <div className="row-actions" style={{ marginTop: 4 }}>
                <button type="button" className="btn ghost btn-sm" onClick={() => load(formFromProfile(p, tr({ en: ' (copy)', fr: ' (copie)' })), { mode: 'create', fromDraftRunId: null })}>{tr({ en: 'Copy', fr: 'Copier' })}</button>
                <button type="button" className="btn ghost btn-sm" onClick={() => void duplicate(p)}>{tr({ en: 'Duplicate exactly', fr: 'Dupliquer à l’identique' })}</button>
                {!p.isDefault && <button type="button" className="btn ghost btn-sm" onClick={() => load(formFromProfile(p), { mode: 'update', profileId: p.profileId, version: p.version })}>{tr({ en: 'Edit', fr: 'Modifier' })}</button>}
                {!p.isDefault && <button type="button" className="btn ghost btn-sm" onClick={() => void setArchive(p, true)}>{tr({ en: 'Archive', fr: 'Archiver' })}</button>}
                {!p.isDefault && <button type="button" className="btn danger btn-sm" onClick={() => void remove(p)}>{tr({ en: 'Delete', fr: 'Supprimer' })}</button>}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={tr({ en: 'Archived profiles', fr: 'Profils archivés' })}>
        {archivedProfiles.loading && <Loading />}
        {archivedProfiles.error && <ErrorState error={archivedProfiles.error} onRetry={archivedProfiles.reload} />}
        {archivedProfiles.data?.items.length === 0 && <p className="small muted">{tr({ en: 'No archived profiles in this session.', fr: 'Aucun profil archivé dans cette session.' })}</p>}
        <ul className="list-plain">{archivedProfiles.data?.items.map(p => <li key={p.profileId}>{p.name}{' '}<button type="button" className="btn ghost btn-sm" onClick={() => void setArchive(p, false)}>{tr({ en: 'Restore', fr: 'Restaurer' })}</button></li>)}</ul>
      </Card>

      <ProfileCompare profiles={profiles} />

      <DraftFromText onApply={(run, draft) => {
        const { form: next, filled } = applyDraft(EMPTY_PROFILE_FORM, draft.profile);
        load(next, { mode: 'create', fromDraftRunId: run.runId });
        setProvisional(filled);
        setUnresolved(draft.unresolved);
      }} />

      <Card id="profile-form" title={editing.mode === 'update'
        ? tr({ en: 'Edit custom profile', fr: 'Modifier le profil' })
        : tr({ en: 'New fictional profile', fr: 'Nouveau profil fictif' })}>
        <form noValidate onSubmit={e => { e.preventDefault(); void save(); }}>
          {submitted && issues.length > 0 && (
            <div className="error-summary" role="alert">
              <p className="state-title">{tr({ en: 'Please fix the following before saving:', fr: 'Veuillez corriger ce qui suit avant d’enregistrer :' })}</p>
              <ul className="bullets small">{issues.map((issue, i) => <li key={i}>{issueText(issue, tr)}</li>)}</ul>
            </div>
          )}
          {provisional.length > 0 && (
            <p className="stale-note">{tr({ en: 'Fields filled from your text are provisional until you confirm them:', fr: 'Les champs remplis à partir de votre texte sont provisoires jusqu’à confirmation :' })} <span className="mono">{provisional.join(', ')}</span></p>
          )}
          <div className="form-grid">
            <Field id="pf-name" text={label('name', tr)} issues={fieldIssues('name')}>
              <input id="pf-name" type="text" maxLength={40} value={form.name} onChange={e => set({ name: e.target.value })} required />
            </Field>
            <Field id="pf-age" text={`${label('age', tr)} (${tr({ en: 'optional', fr: 'facultatif' })})`} issues={fieldIssues('age')}>
              <input id="pf-age" type="number" min={0} max={120} value={form.age} onChange={e => set({ age: e.target.value })} />
            </Field>
            <Field id="pf-risk" text={label('riskLevel', tr)} issues={fieldIssues('riskLevel')}>
              <select id="pf-risk" value={form.riskLevel} onChange={e => set({ riskLevel: e.target.value as ProfileForm['riskLevel'] })}>
                <option value="">—</option>
                {RISK_LEVELS.map(r => <option key={r} value={r}>{labelOf(RISK_LEVEL, r, lang)}</option>)}
              </select>
            </Field>
            <Field id="pf-hmin" text={`${label('horizonMin', tr)} (${tr({ en: 'years', fr: 'ans' })})`} issues={fieldIssues('horizonMin')}>
              <input id="pf-hmin" type="number" min={0} step="any" value={form.horizonMin} onChange={e => set({ horizonMin: e.target.value })} />
            </Field>
            <Field id="pf-hmax" text={`${label('horizonMax', tr)} (${tr({ en: 'empty = open-ended', fr: 'vide = sans fin' })})`} issues={fieldIssues('horizonMax')}>
              <input id="pf-hmax" type="number" min={0} step="any" value={form.horizonMax} onChange={e => set({ horizonMax: e.target.value })} />
            </Field>
            <Field id="pf-obj" text={label('objective', tr)} issues={fieldIssues('objective')}>
              <select id="pf-obj" value={form.objective} onChange={e => set({ objective: e.target.value as ProfileForm['objective'] })}>
                <option value="">—</option>
                {OBJECTIVES.map(o => <option key={o} value={o}>{labelOf(OBJECTIVE, o, lang)}</option>)}
              </select>
            </Field>
            <Field id="pf-exp" text={label('experience', tr)} issues={fieldIssues('experience')}>
              <select id="pf-exp" value={form.experience} onChange={e => set({ experience: e.target.value as ProfileForm['experience'] })}>
                <option value="">—</option>
                {EXPERIENCES.map(x => <option key={x} value={x}>{labelOf(EXPERIENCE, x, lang)}</option>)}
              </select>
            </Field>
            <Field id="pf-cur" text={label('reportingCurrency', tr)} issues={fieldIssues('reportingCurrency')}>
              <input id="pf-cur" maxLength={3} pattern="[A-Z]{3}" list="reporting-currencies" value={form.reportingCurrency} onChange={e => set({ reportingCurrency: e.target.value.toUpperCase() })} />
              <datalist id="reporting-currencies">{(meta?.reportingCurrencies ?? ['CAD', 'USD']).map(c => <option key={c} value={c} />)}</datalist>
            </Field>
          </div>

          <fieldset style={{ marginTop: 16 }}>
            <legend>{tr({ en: 'Investor context and multiple objectives', fr: 'Contexte et objectifs multiples' })}</legend>
            <div className="form-grid">
              <div className="field"><label htmlFor="pf-country">{tr({ en: 'Country (ISO two-letter code, optional)', fr: 'Pays (code ISO à deux lettres, facultatif)' })}</label>
                <input id="pf-country" maxLength={2} pattern="[A-Z]{2}" value={form.investorContext?.country ?? ''} onChange={e => set({ investorContext: { ...form.investorContext, country: e.target.value.toUpperCase() || null } })} /></div>
              <div className="field"><label htmlFor="pf-type">{tr({ en: 'Investor type', fr: 'Type d’investisseur' })}</label>
                <input id="pf-type" maxLength={80} list="investor-types" value={form.investorContext?.investorType ?? 'individual'} onChange={e => set({ investorContext: { ...form.investorContext, investorType: e.target.value } })} />
                <datalist id="investor-types">{['individual', 'retirement', 'income', 'crypto', 'institutional', 'family_office', 'endowment', 'pension', 'wealth_manager', 'advisor', 'custom'].map(t => <option key={t} value={t} />)}</datalist></div>
            </div>
            <p className="small muted">{tr({ en: 'Jurisdiction does not imply tax or regulatory coverage. Goal amounts use the reporting currency; feasibility is not established.', fr: 'Le pays n’implique aucune couverture fiscale ou réglementaire. Les montants utilisent la devise de présentation; leur faisabilité n’est pas établie.' })}</p>
            {(form.investorContext?.objectives ?? []).map((goal, i) => <div className="form-grid" key={i}>
              <div className="field"><label htmlFor={`goal-name-${i}`}>{tr({ en: 'Goal', fr: 'Objectif' })} {i + 1}</label><input id={`goal-name-${i}`} maxLength={120} value={goal.name} onChange={e => set({ investorContext: { ...form.investorContext, objectives: form.investorContext!.objectives!.map((g, j) => j === i ? { ...g, name: e.target.value } : g) } })} /></div>
              <div className="field"><label htmlFor={`goal-years-${i}`}>{tr({ en: 'Years', fr: 'Années' })}</label><input id={`goal-years-${i}`} type="number" min={0.01} max={150} step="any" value={goal.horizonYears} onChange={e => set({ investorContext: { ...form.investorContext, objectives: form.investorContext!.objectives!.map((g, j) => j === i ? { ...g, horizonYears: Number(e.target.value) } : g) } })} /></div>
              {([
                ['targetAmount', { en: 'Target amount', fr: 'Montant cible' }],
                ['allocatedValue', { en: 'Capital allocated to this goal', fr: 'Capital affecté à cet objectif' }],
                ['annualContribution', { en: 'Assumed yearly contribution', fr: 'Contribution annuelle supposée' }],
                ['assumedReturnPct', { en: 'Assumed yearly return (%) — not a forecast', fr: 'Rendement annuel supposé (%) — aucune prévision' }],
              ] as const).map(([key, text]) => <div className="field" key={key}>
                <label htmlFor={`goal-${key}-${i}`}>{tr(text)}</label><input id={`goal-${key}-${i}`} type="number" step="any" min={key === 'assumedReturnPct' ? -99.99 : 0} value={goal[key] ?? ''} onChange={e => setGoal(i, { [key]: e.target.value === '' ? null : Number(e.target.value) })} />
              </div>)}
              <div className="field"><label htmlFor={`goal-priority-${i}`}>{tr({ en: 'Priority (1 = highest)', fr: 'Priorité (1 = plus élevée)' })}</label><input id={`goal-priority-${i}`} type="number" min={1} max={100} value={goal.priority} onChange={e => setGoal(i, { priority: Number(e.target.value) })} /></div>
              {(['startDate', 'endDate', 'deadline'] as const).map(key => <div className="field" key={key}><label htmlFor={`goal-${key}-${i}`}>{key}</label><input id={`goal-${key}-${i}`} type="date" value={goal[key] ?? ''} onChange={e => setGoal(i, { [key]: e.target.value || null })} /></div>)}
              <div className="field"><label htmlFor={`goal-origin-${i}`}>{tr({ en: 'Goal input origin', fr: 'Origine de l’objectif' })}</label><select id={`goal-origin-${i}`} value={goal.origin ?? 'user'} onChange={e => setGoal(i, { origin: e.target.value as NonNullable<InvestmentGoal['origin']> })}>{['user', 'imported', 'system_default', 'assumption'].map(o => <option key={o} value={o}>{o}</option>)}</select></div>
              <div className="field"><label htmlFor={`goal-source-${i}`}>{tr({ en: 'Source URL (optional)', fr: 'URL source (facultative)' })}</label><input id={`goal-source-${i}`} type="url" value={goal.sourceUrl ?? ''} onChange={e => setGoal(i, { sourceUrl: e.target.value || null })} /></div>
              <button type="button" className="btn ghost" onClick={() => set({ investorContext: { ...form.investorContext, objectives: form.investorContext!.objectives!.filter((_, j) => j !== i) } })}>{tr({ en: 'Remove goal', fr: 'Retirer l’objectif' })}</button>
            </div>)}
            <button type="button" className="btn ghost" disabled={(form.investorContext?.objectives?.length ?? 0) >= 20} onClick={() => set({ investorContext: { ...form.investorContext, objectives: [...(form.investorContext?.objectives ?? []), { name: '', horizonYears: 1, priority: (form.investorContext?.objectives?.length ?? 0) + 1, origin: 'user' }] } })}>{tr({ en: 'Add objective', fr: 'Ajouter un objectif' })}</button>
          </fieldset>

          <AllocationInputs value={form.investorContext} onChange={investorContext => set({ investorContext })} />
          <InvestorInputs value={form.investorContext} onChange={investorContext => set({ investorContext })} />

          <fieldset style={{ marginTop: 16 }}>
            <legend>{tr({ en: 'Preferences', fr: 'Préférences' })}</legend>
            <div className="checks">
              {PREFERENCE_TOGGLES.map(([key, text]) => (
                <label key={key}><input type="checkbox" checked={form[key]} onChange={e => set({ [key]: e.target.checked })} /> {tr(text)}</label>
              ))}
            </div>
            <div className="form-grid" style={{ marginTop: 8 }}>
              <div className="field">
                <label htmlFor="pf-crypto">{tr({ en: 'Crypto interest', fr: 'Intérêt pour la crypto' })}</label>
                <select id="pf-crypto" value={form.cryptoInterest} onChange={e => set({ cryptoInterest: e.target.value as ProfileForm['cryptoInterest'] })}>
                  <option value="none">{tr({ en: 'None', fr: 'Aucun' })}</option>
                  <option value="low">{tr({ en: 'Low', fr: 'Faible' })}</option>
                  <option value="open">{tr({ en: 'Open', fr: 'Ouvert' })}</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="pf-sectors">{tr({ en: 'Excluded sectors, separated by commas', fr: 'Secteurs exclus, séparés par des virgules' })}</label>
                <input id="pf-sectors" type="text" value={form.excludedSectors} onChange={e => set({ excludedSectors: e.target.value })} />
              </div>
            </div>
            <details style={{ marginTop: 8 }}>
              <summary className="small">{tr({ en: 'Themes of interest and excluded asset classes', fr: 'Thèmes d’intérêt et catégories exclues' })}</summary>
              <div className="checks">
                {THEME_TAGS.map(theme => (
                  <label key={theme}><input type="checkbox" checked={form.themesOfInterest.includes(theme)}
                    onChange={e => set({ themesOfInterest: e.target.checked ? [...form.themesOfInterest, theme] : form.themesOfInterest.filter(t => t !== theme) })} /> {labelOf(THEME_TAG, theme, lang)}</label>
                ))}
              </div>
              <div className="checks" style={{ marginTop: 8 }}>
                {ASSET_CLASSES.map(c => (
                  <label key={c}><input type="checkbox" checked={form.excludedAssetClasses.includes(c)}
                    onChange={e => set({ excludedAssetClasses: e.target.checked ? [...form.excludedAssetClasses, c] : form.excludedAssetClasses.filter(x => x !== c) })} /> {tr({ en: 'Exclude', fr: 'Exclure' })} {labelOf(ASSET_CLASS, c, lang)}</label>
                ))}
              </div>
            </details>
            <div className="field" style={{ marginTop: 8 }}>
              <label htmlFor="pf-notes">{tr({ en: 'Notes', fr: 'Notes' })}</label>
              <textarea id="pf-notes" value={form.notes} onChange={e => set({ notes: e.target.value })} />
            </div>
          </fieldset>

          <fieldset style={{ marginTop: 16 }}>
            <legend>{tr({ en: 'Fictional portfolio', fr: 'Portefeuille fictif' })}</legend>
            <div className="checks">
              <label><input type="radio" name="pf-holdings" checked={!form.ownHoldings} onChange={() => set({ ownHoldings: false })} /> {tr({ en: 'Let Aplomb propose a starting mix (labelled as an assumption)', fr: 'Laisser Aplomb proposer une composition de départ (identifiée comme hypothèse)' })}</label>
              <label><input type="radio" name="pf-holdings" checked={form.ownHoldings} onChange={() => set({ ownHoldings: true })} /> {tr({ en: 'Enter holdings', fr: 'Saisir les positions' })}</label>
            </div>
            {form.ownHoldings && (
              <>
                <Field id="pf-capital" text={`${label('capital', tr)} (${form.reportingCurrency || '—'})`} issues={fieldIssues('capital')}>
                  <input id="pf-capital" type="number" min={0} value={form.capital} onChange={e => set({ capital: e.target.value })} />
                </Field>
                <div className="table-scroll" style={{ marginTop: 8 }} role="region" aria-label={label('positions', tr)} tabIndex={0}>
                  <table className="data-table">
                    <thead><tr><th scope="col">{tr({ en: 'Ticker', fr: 'Symbole' })}</th><th scope="col">{tr({ en: 'Weight (%)', fr: 'Poids (%)' })}</th><th scope="col"><span className="sr-only">{tr({ en: 'Remove', fr: 'Retirer' })}</span></th></tr></thead>
                    <tbody>
                      {form.positions.map((p, i) => (
                        <tr key={i}>
                          <td><input aria-label={`${tr({ en: 'Ticker', fr: 'Symbole' })} ${i + 1}`} type="text" value={p.ticker} onChange={e => updatePosition(i, { ticker: e.target.value.toUpperCase() })} /></td>
                          <td><input aria-label={`${tr({ en: 'Weight', fr: 'Poids' })} ${i + 1}`} type="number" min={0} step={0.01} value={p.weightPct} onChange={e => updatePosition(i, { weightPct: e.target.value })} /></td>
                          <td><button type="button" className="btn ghost btn-sm" onClick={() => set({ positions: form.positions.filter((_, j) => j !== i) })}>{tr({ en: 'Remove', fr: 'Retirer' })}</button></td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot><tr><th scope="row">{tr({ en: 'Total', fr: 'Total' })}</th><td className="num" aria-live="polite">{sum.toFixed(2)} %</td><td /></tr></tfoot>
                  </table>
                </div>
                <div className="row-actions">
                  <button type="button" className="btn ghost btn-sm" disabled={form.positions.length >= MAX_POSITIONS} onClick={() => set({ positions: [...form.positions, { ticker: '', weightPct: '' }] })}>{tr({ en: 'Add holding', fr: 'Ajouter une position' })}</button>
                </div>
                {fieldIssues('positions').map((issue, i) => <p key={i} className="field-error">{issueText(issue, tr)}</p>)}
              </>
            )}
          </fieldset>

          <p className="small muted" style={{ marginTop: 12 }}>{tr({ en: 'Rules are derived by code from these fields (editable assumptions, not regulatory limits).', fr: 'Les règles sont dérivées par le code à partir de ces champs (hypothèses modifiables, pas des limites réglementaires).' })}</p>

          {unresolved.length > 0 && (
            <div className="state" style={{ marginTop: 12 }}>
              <p className="state-title">{tr({ en: 'Questions the draft could not resolve', fr: 'Questions que le brouillon n’a pas pu résoudre' })}</p>
              <ul className="bullets small">{unresolved.map(u => <li key={u.field}>{FIELD_LABEL[u.field] ? `${tr(FIELD_LABEL[u.field]!)}: ` : ''}{tr(u.question)}</li>)}</ul>
            </div>
          )}
          {needsConfirmation && (
            <label className="checks" style={{ marginTop: 12 }}>
              <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
              {tr({ en: 'I reviewed the provisional fields and answered the open questions above.', fr: 'J’ai vérifié les champs provisoires et répondu aux questions ouvertes ci-dessus.' })}
            </label>
          )}
          {submitted && needsConfirmation && !confirmed && <p className="field-error">{tr({ en: 'Confirm the drafted fields before saving.', fr: 'Confirmez les champs du brouillon avant d’enregistrer.' })}</p>}

          <div className="row-actions">
            <button type="submit" className="btn" disabled={saving}>{editing.mode === 'update' ? tr({ en: 'Save changes', fr: 'Enregistrer les modifications' }) : tr({ en: 'Save profile', fr: 'Enregistrer le profil' })}</button>
            <button type="button" className="btn ghost" onClick={() => load(EMPTY_PROFILE_FORM, { mode: 'create', fromDraftRunId: null })}>{tr({ en: 'Clear', fr: 'Effacer' })}</button>
          </div>
          {saveError && (
            <ErrorState error={saveError} {...(saveError.code === 'conflict' ? { title: tr({ en: 'This profile changed since you opened it, or is read-only. Your unsaved form is kept.', fr: 'Ce profil a changé depuis son ouverture, ou est en lecture seule. Votre formulaire non enregistré est conservé.' }) } : {})}>
              {saveError.code === 'conflict' && <button type="button" className="btn ghost btn-sm" onClick={reloadProfiles}>{tr({ en: 'Reload profiles', fr: 'Recharger les profils' })}</button>}
            </ErrorState>
          )}
        </form>
      </Card>
    </>
  );
}

function Field({ id, text, issues, children }: { id: string; text: string; issues: ProfileFormIssue[]; children: ReactNode }) {
  const { tr } = useApp();
  return (
    <div className="field">
      <label htmlFor={id}>{text}</label>
      {children}
      {issues.map((issue, i) => <span key={i} className="field-error">{issueText(issue, tr)}</span>)}
    </div>
  );
}

function DraftFromText({ onApply }: { onApply: (run: Run, draft: ProfileDraftResult) => void }) {
  const { tr, lang } = useApp();
  const [text, setText] = useState('');
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const polled = useRun(runId);
  const run = polled.run;
  const draft = run?.result?.kind === 'profile_draft' ? run.result.draft : null;
  const start = async () => {
    setError(null);
    try {
      const created = await getApiClient().createRun({ kind: 'profile_draft', lang, text: text.trim() });
      setRunId(created.runId);
    } catch (e) { setError(asApiError(e)); }
  };
  const busy = run !== null && (run.status === 'queued' || run.status === 'running');
  return (
    <Card title={tr({ en: 'Or describe the fictional investor in words', fr: 'Ou décrivez l’investisseur fictif en mots' })}>
      <div className="field">
        <label htmlFor="draft-text">{tr({ en: 'Description', fr: 'Description' })}</label>
        <textarea id="draft-text" value={text} maxLength={2000} onChange={e => setText(e.target.value)} />
        <span className="hint">{tr({ en: 'Fields are proposed for review; nothing is saved until you confirm.', fr: 'Les champs sont proposés pour révision ; rien n’est enregistré sans confirmation.' })}</span>
      </div>
      <div className="row-actions"><button type="button" className="btn ghost" disabled={!text.trim() || busy} onClick={() => void start()}>{tr({ en: 'Draft a profile', fr: 'Rédiger un brouillon' })}</button></div>
      {error && <ErrorState error={error} />}
      {polled.error && <ErrorState error={polled.error} />}
      {runId && !run && !polled.error && <Loading />}
      {run && !draft && (
        <div>
          <RunStatusBadge status={run.status} />
          <details><summary className="small">{tr({ en: 'Execution trace', fr: 'Trace d’exécution' })}</summary><RunTimeline run={run} /></details>
        </div>
      )}
      {run && draft && (
        <div className="state">
          <p className="state-title">{tr({ en: 'Draft ready — review before applying', fr: 'Brouillon prêt — vérifiez avant de l’appliquer' })}</p>
          <ul className="bullets small">{draft.explanations.map(e => <li key={e.field}>{FIELD_LABEL[e.field] ? `${tr(FIELD_LABEL[e.field]!)}: ` : ''}{tr(e.text)}</li>)}</ul>
          {draft.unresolved.length > 0 && <p className="small">{tr({ en: `${draft.unresolved.length} question(s) remain open.`, fr: `${draft.unresolved.length} question(s) restent ouvertes.` })}</p>}
          <button type="button" className="btn btn-sm" onClick={() => onApply(run, draft)}>{tr({ en: 'Apply draft to the form (provisional)', fr: 'Appliquer le brouillon au formulaire (provisoire)' })}</button>
        </div>
      )}
    </Card>
  );
}
