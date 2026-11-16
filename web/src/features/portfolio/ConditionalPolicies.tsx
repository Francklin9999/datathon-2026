'use client';
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { parseModelInput } from '../../api/investorModels';
import { useApp } from '../../state/app';
import { DraftRestoredNote, ProfileWriteError } from '../../components/common/States';
import { Note } from '../../components/common/Note';
import { ConfirmButton } from '../../components/ui/ConfirmButton';
import { dropDraft, stashDraft } from '../../lib/draftStore';
import { labelOf } from '../../lib/labels';
import { useRestoredDraft } from '../../state/useDraft';
import { DIMENSION, ORIGIN } from './portfolioLabels';

const dimensions = ['position', 'sector', 'asset_class', 'country', 'currency', 'theme', 'volatility', 'drawdown'] as const;
const origins = ['user', 'imported', 'system_default', 'assumption'] as const;
const operators = [
  ['lt', { en: 'Less than', fr: 'Moins de' }],
  ['lte', { en: 'At most', fr: 'Au plus' }],
  ['eq', { en: 'Equal to', fr: 'Égal à' }],
  ['gte', { en: 'At least', fr: 'Au moins' }],
  ['gt', { en: 'More than', fr: 'Plus de' }],
] as const;
type Clause = { dimension: typeof dimensions[number]; key: string; operator: 'lt' | 'lte' | 'eq' | 'gte' | 'gt'; threshold: string; sourceReference: string };
const blank = (): Clause => ({ dimension: 'position', key: '', operator: 'lte', threshold: '', sourceReference: '' });
const portfolioWide = (dimension: string) => dimension === 'volatility' || dimension === 'drawdown';

function ClauseRows({ prefix, value, onChange }: { prefix: string; value: Clause[]; onChange: (value: Clause[]) => void }) {
  const { tr, lang } = useApp();
  const patch = (i: number, next: Partial<Clause>) => onChange(value.map((c, j) => (i === j ? { ...c, ...next } : c)));
  return <>
    {value.map((clause, i) => <fieldset key={i}>
      <legend>{tr({ en: 'Condition', fr: 'Condition' })} {i + 1}</legend>
      <div className="form-grid">
        <div className="field"><label htmlFor={`${prefix}-dimension-${i}`}>{tr({ en: 'Measure', fr: 'Mesure' })}</label>
          <select id={`${prefix}-dimension-${i}`} value={clause.dimension} onChange={e => patch(i, { dimension: e.target.value as Clause['dimension'], key: '' })}>
            {dimensions.map(d => <option key={d} value={d}>{labelOf(DIMENSION, d, lang)}</option>)}
          </select></div>
        {!portfolioWide(clause.dimension) && <div className="field"><label htmlFor={`${prefix}-key-${i}`}>{tr({ en: 'Which one', fr: 'Lequel' })}</label>
          <input id={`${prefix}-key-${i}`} required maxLength={120} value={clause.key} onChange={e => patch(i, { key: e.target.value })} aria-describedby={`${prefix}-key-${i}-hint`} />
          <span id={`${prefix}-key-${i}-hint`} className="hint">{tr({ en: 'Ticker, sector, class, three-letter code or theme', fr: 'Symbole, secteur, catégorie, code à trois lettres ou thème' })}</span></div>}
        <div className="field"><label htmlFor={`${prefix}-operator-${i}`}>{tr({ en: 'Comparison', fr: 'Comparaison' })}</label>
          <select id={`${prefix}-operator-${i}`} value={clause.operator} onChange={e => patch(i, { operator: e.target.value as Clause['operator'] })}>
            {operators.map(([v, label]) => <option key={v} value={v}>{tr(label)}</option>)}
          </select></div>
        <div className="field"><label htmlFor={`${prefix}-threshold-${i}`}>{tr({ en: 'Threshold (%)', fr: 'Seuil (%)' })}</label>
          <input id={`${prefix}-threshold-${i}`} required type="number" min={0} max={clause.dimension === 'volatility' ? 1000 : 100} step="any" value={clause.threshold} onChange={e => patch(i, { threshold: e.target.value })} /></div>
        <div className="field"><label htmlFor={`${prefix}-source-${i}`}>{tr({ en: 'Source or reason (optional)', fr: 'Source ou raison (facultative)' })}</label>
          <input id={`${prefix}-source-${i}`} maxLength={1000} value={clause.sourceReference} onChange={e => patch(i, { sourceReference: e.target.value })} /></div>
      </div>
      {value.length > 1 && <button className="btn ghost btn-sm" type="button" onClick={() => onChange(value.filter((_, j) => j !== i))}>{tr({ en: 'Remove condition', fr: 'Retirer la condition' })}</button>}
    </fieldset>)}
    <button className="btn ghost btn-sm" type="button" disabled={value.length >= 10} onClick={() => onChange([...value, blank()])}>{tr({ en: 'Add condition', fr: 'Ajouter une condition' })}</button>
  </>;
}

function MatchSelect({ id, value, onChange }: { id: string; value: string; onChange: (value: string) => void }) {
  const { tr } = useApp();
  return <div className="field"><label htmlFor={id}>{tr({ en: 'Match', fr: 'Correspondance' })}</label>
    <select id={id} value={value} onChange={e => onChange(e.target.value)}>
      <option value="all">{tr({ en: 'All conditions', fr: 'Toutes les conditions' })}</option>
      <option value="any">{tr({ en: 'Any condition', fr: 'Au moins une condition' })}</option>
    </select></div>;
}

interface ConditionDraft { name: string; origin: string; guard: boolean; whenMode: string; requireMode: string; when: Clause[]; required: Clause[]; advanced: boolean; json: string }

/** Conditional rule form ("when these match, require these limits"), rendered inside the Add a rule card. */
export function ConditionalPolicies({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, feature } = useApp();
  const draftKey = `conditional-policies|${profile.profileId}`;
  const restored = useRestoredDraft<ConditionDraft>(draftKey, profile.version);
  const [name, setName] = useState(restored?.name ?? '');
  const [origin, setOrigin] = useState(restored?.origin ?? 'user');
  const [guard, setGuard] = useState(restored?.guard ?? false);
  const [whenMode, setWhenMode] = useState(restored?.whenMode ?? 'all');
  const [requireMode, setRequireMode] = useState(restored?.requireMode ?? 'all');
  const [when, setWhen] = useState<Clause[]>(restored?.when ?? [blank()]);
  const [required, setRequired] = useState<Clause[]>(restored?.required ?? [blank()]);
  const [advanced, setAdvanced] = useState(restored?.advanced ?? false);
  const [json, setJson] = useState(restored?.json ?? '');
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setInvalid(false); setError(null);
    let conditional: unknown;
    try {
      const node = (clauses: Clause[], mode: string) => {
        const leaves = clauses.map(c => ({ dimension: c.dimension, key: portfolioWide(c.dimension) ? null : c.key, operator: c.operator, threshold: Number(c.threshold), origin, ...(c.sourceReference.trim() ? { sourceReference: c.sourceReference.trim() } : {}) }));
        return leaves.length === 1 ? leaves[0] : { mode, clauses: leaves };
      };
      conditional = advanced ? parseModelInput(json) : { when: guard ? { mode: whenMode, clauses: when.map(c => node([c], 'all')) } : null, require: node(required, requireMode) };
    } catch { setInvalid(true); return; }
    setBusy(true);
    try { applyProfile(await getApiClient().addConditionRule(profile.profileId, { version: profile.version, name, origin, conditional })); dropDraft(draftKey); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  const keepDraft = () => stashDraft(draftKey, profile.version, { name, origin, guard, whenMode, requireMode, when, required, advanced, json } satisfies ConditionDraft);
  const remove = async (id: string) => {
    setBusy(true); setError(null);
    try { applyProfile(await getApiClient().removeConditionRule(profile.profileId, id, profile.version)); dropDraft(draftKey); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  // Adding and removing are profile_creator writes; with the flag off only saved conditional rules are listed.
  const editable = feature('profile_creator');
  const saved = profile.rules.filter(r => r.conditional);
  if (!editable && !saved.length) return null;
  return <div className="add-rule-form">
    <p className="small muted">{tr({ en: 'Require limits only when a situation applies, for example “when tech is above 30%, keep bonds at least 20%”.', fr: 'Imposez des limites seulement dans une situation donnée, par exemple « si la techno dépasse 30 %, garder au moins 20 % d’obligations ».' })}</p>
    {editable && !profile.isDefault && <form onSubmit={e => { e.preventDefault(); void save(); }}><fieldset disabled={busy}>
      {restored && <DraftRestoredNote />}
      <div className="form-grid">
        <div className="field"><label htmlFor="condition-name">{tr({ en: 'Rule name', fr: 'Nom de la règle' })}</label><input id="condition-name" required maxLength={120} value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="field"><label htmlFor="condition-origin">{tr({ en: 'Where it comes from', fr: 'Provenance' })}</label>
          <select id="condition-origin" value={origin} onChange={e => setOrigin(e.target.value)}>{origins.map(o => <option key={o} value={o}>{labelOf(ORIGIN, o, lang)}</option>)}</select></div>
      </div>
      {!advanced && <>
        <label className="checks"><input type="checkbox" checked={guard} onChange={e => setGuard(e.target.checked)} /> {tr({ en: 'Apply only when some conditions match', fr: 'Appliquer seulement si certaines conditions correspondent' })}</label>
        {guard && <fieldset><legend>{tr({ en: 'When', fr: 'Lorsque' })}</legend>
          <MatchSelect id="condition-when-mode" value={whenMode} onChange={setWhenMode} />
          <ClauseRows prefix="condition-when" value={when} onChange={setWhen} />
        </fieldset>}
        <fieldset><legend>{tr({ en: 'Require', fr: 'Exiger' })}</legend>
          <MatchSelect id="condition-require-mode" value={requireMode} onChange={setRequireMode} />
          <ClauseRows prefix="condition-require" value={required} onChange={setRequired} />
        </fieldset>
      </>}
      <details className="fold" open={advanced ? true : undefined}>
        <summary>{tr({ en: 'Advanced: nested conditions as JSON', fr: 'Avancé : conditions imbriquées en JSON' })}</summary>
        <div className="fold-body">
          <label className="checks"><input type="checkbox" checked={advanced} onChange={e => setAdvanced(e.target.checked)} /> {tr({ en: 'Write the rule as JSON instead', fr: 'Écrire la règle en JSON à la place' })}</label>
          {advanced && <div className="field"><label htmlFor="condition-json">{tr({ en: 'Rule object with “when” and “require”', fr: 'Objet de règle avec « when » et « require »' })}</label>
            <textarea id="condition-json" required rows={8} maxLength={20000} value={json} onChange={e => setJson(e.target.value)} aria-describedby="condition-json-hint" />
            <p id="condition-json-hint" className="small muted">{tr({ en: 'Each node is {dimension, key, operator, threshold, origin, sourceReference?} or {mode: all|any, clauses: [nodes]}. Up to 4 levels and 40 nodes; “when” may be null, “require” is needed.', fr: 'Chaque nœud est {dimension, key, operator, threshold, origin, sourceReference?} ou {mode: all|any, clauses: [nœuds]}. Jusqu’à 4 niveaux et 40 nœuds ; « when » peut être null, « require » est obligatoire.' })}</p></div>}
        </div>
      </details>
      <button type="submit" className="btn">{tr({ en: 'Save and check', fr: 'Enregistrer et vérifier' })}</button>
    </fieldset></form>}
    <Note>{tr({ en: 'Missing evidence stays unknown, and a rule whose “when” part does not match is not applied. Country and currency use listing proxies.', fr: 'Une preuve manquante reste inconnue, et une règle dont la partie « lorsque » ne correspond pas ne s’applique pas. Pays et devise sont des approximations de cotation.' })}</Note>
    {invalid && <p role="alert" className="field-error">{tr({ en: 'Enter a valid JSON rule object', fr: 'Saisissez un objet de règle JSON valide' })}</p>}
    {error && <ProfileWriteError error={error} onReload={keepDraft} />}
    {saved.length > 0 && <>
      <h3 className="h4">{tr({ en: 'Saved conditional rules', fr: 'Règles conditionnelles enregistrées' })}</h3>
      {saved.map(r => <details className="fold" key={r.ruleId}>
        <summary>{tr(r.label)} · {labelOf(ORIGIN, r.origin, lang)}</summary>
        <div className="fold-body">
          <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(r.conditional, null, 2)}</pre>
          {editable && <ConfirmButton label={tr({ en: 'Remove rule', fr: 'Retirer la règle' })} confirmLabel={tr({ en: 'Confirm removal', fr: 'Confirmer le retrait' })}
            ariaLabel={`${tr({ en: 'Remove rule', fr: 'Retirer la règle' })} ${tr(r.label)}`} disabled={busy} onConfirm={() => void remove(r.ruleId)} />}
        </div>
      </details>)}
    </>}
  </div>;
}
