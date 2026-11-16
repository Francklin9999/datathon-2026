'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowRight, Check, EyeOff, FlaskConical, History, LockKeyhole, Search, SlidersHorizontal } from 'lucide-react';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { LabDecision, LabSession, LabSituation, LabSetting, Profile } from '../../contracts/types';
import { getApiClient } from '../../api';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { invalidateQueries, useQuery } from '../../state/useQuery';
import { Card, PageHeader } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { EXPERIENCE, OBJECTIVE, RISK_LEVEL, labelOf } from '../../lib/labels';
import { InvestmentPlaybook } from './InvestmentPlaybook';
import { DisclosureComparison } from './DisclosureComparison';
import './investor-lab.css';

type Mode = 'new' | 'quick' | 'full';
const ACTIONS = { hold: 'Hold', buy: 'Buy', sell: 'Sell', rebalance: 'Rebalance' } as const;
const REASONS = {
  cash_need: 'I need access to cash', company_evidence: 'The company evidence',
  portfolio_balance: 'Portfolio concentration', loss_discomfort: 'Discomfort with losses',
  long_term: 'My long-term plan', other: 'Another reason',
} as const;

export function InvestorLabPage() {
  const { meta, feature, tr } = useApp();
  if (!meta) return <Loading />;
  if (!feature('profile_creator')) return <Unavailable title={tr({ en: 'Investor Lab is unavailable in this deployment', fr: 'Investor Lab est indisponible dans ce déploiement' })} />;
  return <LabContent />;
}

function LabContent() {
  const { profiles, profile: selectedProfile, sessionId, applyProfile, selectProfile, tr, announce } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get('lab');
  const [labState, setLab] = useState<LabSession | null>(null);
  const [saved, setSaved] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const restored = useQuery(id && sessionId ? `lab|${sessionId}|${id}` : null, signal => getApiClient().investorLab(id!, signal));
  const recent = useQuery(!id && sessionId ? `labs|${sessionId}` : null, signal => getApiClient().investorLabs(signal));
  const profileId = params.get('profileId');
  const profile = profileId ? profiles.find(p => p.profileId === profileId) ?? null : selectedProfile;
  const requestedMode = params.get('mode');
  const mode: Mode = requestedMode === 'quick' || requestedMode === 'full' ? requestedMode : 'new';
  const focus = useRef<HTMLHeadingElement>(null);
  const labSession = useRef(sessionId);
  const lab = id && labSession.current === sessionId && labState?.labId === id ? labState : null;

  useEffect(() => {
    if (restored.data?.labId !== id) return;
    const sameSession = labSession.current === sessionId;
    labSession.current = sessionId;
    setLab(current => sameSession && current?.labId === id && current.version > restored.data!.version ? current : restored.data);
  }, [id, restored.data, sessionId]);
  useEffect(() => { setSaved(null); setError(null); }, [id, sessionId]);
  useEffect(() => { if (lab) focus.current?.focus(); }, [lab?.stage, lab?.checkpoint]);
  const invalidateLabs = () => invalidateQueries(key => key.startsWith(`lab|${sessionId}|`) || key === `labs|${sessionId}`);
  const act = async (operation: () => Promise<LabSession>) => {
    setBusy(true); setError(null);
    try {
      const result = await operation();
      invalidateLabs();
      setLab(result);
      announce(result.stage === 'review' ? 'Profile proposal ready to review' : `Checkpoint ${result.checkpoint}: ${result.stage}`);
    } catch (e) { setError(asApiError(e)); }
    finally { setBusy(false); }
  };
  const begin = (situation: LabSituation, chosenMode: Mode) => act(async () => {
    const result = await getApiClient().startInvestorLab({
      mode: chosenMode, situation,
      ...(chosenMode === 'new' ? {} : { profileId: profile?.profileId ?? null, profileVersion: profile?.version ?? null }),
    });
    router.replace(`/investor-lab/?lab=${encodeURIComponent(result.labId)}`, { scroll: false });
    return result;
  });
  const confirm = async (accepted: { key: string; value?: number | null }[], principle: string, trigger: string, explanation: string) => {
    if (!lab) return;
    setBusy(true); setError(null);
    try {
      const result = await getApiClient().confirmInvestorLab(lab.labId, {
        version: lab.version, accepted, principle, revisitTrigger: trigger, explanation,
      });
      invalidateLabs();
      applyProfile(result); selectProfile(result.profileId); setSaved(result);
      // Confirmation has already succeeded. Preserve that state even if the follow-up read fails.
      setLab({ ...lab, stage: 'saved', savedProfileId: result.profileId, version: lab.version + 1 });
      announce(tr({ en: 'Profile and playbook saved', fr: 'Profil et guide enregistrés' }));
      getApiClient().investorLab(lab.labId).then(updated => {
        setLab(current => current?.labId === updated.labId && current.version <= updated.version ? updated : current);
      }).catch(() => { /* saved state remains usable */ });
    } catch (e) { setError(asApiError(e)); }
    finally { setBusy(false); }
  };
  const savedProfile = saved ?? profiles.find(p => p.profileId === lab?.savedProfileId);

  return <div className="investor-lab">
    <PageHeader title={tr({ en: 'Investor Lab', fr: 'Investor Lab' })}
      actions={<Link className="btn ghost btn-sm" href="/profiles/">{tr({ en: 'Profiles', fr: 'Profils' })}</Link>}>
      <p className="page-sub">{tr({ en: 'Explore how you decide. Build a plan you can explain.', fr: 'Explorez vos décisions. Construisez un plan que vous pouvez expliquer.' })}</p>
    </PageHeader>
    {error && <ErrorState error={error}>
      {error.code === 'conflict' && <button className="btn ghost" onClick={() => { restored.reload(); setError(null); }}>Reload Lab</button>}
    </ErrorState>}
    {restored.loading && !lab && <Loading label="Restoring your Lab…" />}
    {restored.error && <ErrorState error={restored.error} onRetry={restored.reload} />}
    {!id && profileId && !profile && <p className="lab-profile-notice" role="status">The requested profile is unavailable. Create a new profile or choose another profile first.</p>}
    {!lab && !id && <SituationForm key={`${mode}|${profile?.profileId}`} profile={profile} initialMode={mode} busy={busy} onStart={begin} />}
    {!lab && !id && recent.data && recent.data.items.length > 0 && <Card title={tr({ en: 'Your recent Labs', fr: 'Vos Labs récents' })}>
      <ul className="list-plain">{recent.data.items.slice().reverse().slice(0, 5).map(item => <li key={item.labId} className="lab-recent">
        <span><strong>{item.situation.name}</strong><span className="block muted small">{item.stage === 'saved' ? 'Profile confirmed' : `Checkpoint ${item.checkpoint} of ${item.checkpointCount}`}</span></span>
        <Link className="btn ghost btn-sm" href={`/investor-lab/?lab=${encodeURIComponent(item.labId)}`}>{item.stage === 'saved' ? 'View' : 'Resume'} <ArrowRight size={14} aria-hidden="true" /></Link>
      </li>)}</ul>
    </Card>}
    {recent.error && !id && <ErrorState error={recent.error} onRetry={recent.reload} />}
    {lab && <>
      <ol className="lab-progress" aria-label="Lab progress">
        {['Your situation', 'Market experience', 'Review your profile', 'Your playbook'].map((text, i) => {
          const active = lab.stage === 'saved' ? 3 : lab.stage === 'review' ? 2 : 1;
          return <li key={text} aria-current={active === i ? 'step' : undefined} data-complete={i < active || undefined}><span>{i < active ? <Check size={13} aria-hidden="true" /> : i + 1}</span>{text}</li>;
        })}
      </ol>
      {!['review', 'saved'].includes(lab.stage) && <>
        <div className="lab-checkpoint-heading">
          <div><p className="lab-kicker"><EyeOff size={14} aria-hidden="true" /> Masked market experience · {lab.checkpoint} / {lab.checkpointCount}</p>
            <h2 ref={focus} tabIndex={-1}>{lab.stage === 'contrast' ? 'One thing changes' : lab.title}</h2></div>
          <span className="lab-chip"><LockKeyhole size={13} aria-hidden="true" /> Dates and identities hidden</span>
        </div>
        <p className="lab-prompt">{lab.prompt}</p>
        <div className="lab-experience">
          <div>
            <Card title="Your hypothetical portfolio" info="Current holdings are represented with disclosed market proxies. The values are an indexed USD illustration, not a reconstruction of an actual account.">
              <LabChart points={lab.chart} />
              <div className="lab-allocation" aria-label="Hypothetical allocation">{lab.sleeves.filter(s => s.weightPct > 0.01).map((s, i) =>
                <div key={s.label}><span className={`lab-dot lab-color-${i % 6}`} /><span>{s.label}</span><strong>{s.weightPct.toFixed(1)}%</strong></div>)}</div>
            </Card>
            {lab.stage !== 'initial' && <Research lab={lab} busy={busy} onConsult={(evidenceId, why) => act(() => getApiClient().labConsult(lab.labId, { version: lab.version, evidenceId, why }))} />}
          </div>
          <div>
            <Card title={lab.stage === 'initial' ? 'Your first instinct' : lab.stage === 'contrast' ? 'Test your explanation' : 'Your considered decision'}>
              {lab.stage === 'initial' && <p className="small muted">Record your initial choice before opening the evidence. There is no return leaderboard.</p>}
              {lab.stage === 'research' && lab.observations.at(-1) && <div className="lab-initial">
                <span className="lab-kicker">Initial choice · recorded</span>
                <strong>{ACTIONS[lab.observations.at(-1)!.initial.action]} · {lab.observations.at(-1)!.initial.targetPct.toFixed(1)}% in Company C</strong>
                <p className="small">{lab.observations.at(-1)!.initial.explanation}</p>
              </div>}
              <DecisionForm key={`${lab.checkpoint}|${lab.stage}`} lab={lab} busy={busy} onSave={(decision, revisitTrigger) =>
                act(() => lab.stage === 'initial' ? getApiClient().labInitial(lab.labId, { version: lab.version, decision })
                  : lab.stage === 'contrast' ? getApiClient().labContrast(lab.labId, { version: lab.version, decision })
                    : getApiClient().labFinal(lab.labId, { version: lab.version, decision, revisitTrigger }))} />
            </Card>
            <div className="lab-situation-note"><strong>Your stated situation</strong><p>{lab.situation.objective} · {lab.situation.horizonYears} years · {lab.situation.cashNeedPct}% planned cash need</p>
              <p className="small muted">Capacity: {lab.situation.riskCapacity.replaceAll('_', ' ')} · Willingness: {lab.situation.riskWillingness.replaceAll('_', ' ')}</p></div>
          </div>
        </div>
      </>}
      {lab.stage === 'review' && <Review key={lab.labId} lab={lab} busy={busy} onConfirm={confirm} headingRef={focus} />}
      {lab.stage === 'saved' && <>
        <div className="lab-saved"><Check size={24} aria-hidden="true" /><div><h2 ref={focus} tabIndex={-1}>Your profile and playbook are saved</h2><p>These confirmed settings now travel with your decisions.</p></div></div>
        {savedProfile && <InvestmentPlaybook key={`${savedProfile.profileId}|${savedProfile.version}`} profile={savedProfile} />}
        {!savedProfile && <Link className="btn" href="/profiles/">Open saved profiles</Link>}
        <Card title="Your first investigation">
          <p>Explore {lab.situation.interest} with your confirmed limits in view.</p>
          <Link className="btn" href={`/decision-desk/?q=${encodeURIComponent(`Investigate ${lab.situation.interest} and how it fits my confirmed investment plan`)}`}>Investigate with Aplomb <ArrowRight size={15} aria-hidden="true" /></Link>
          <Link className="btn ghost" href="/portfolio/?tab=rules">View portfolio rules</Link>
        </Card>
        {savedProfile && <DisclosureComparison key={savedProfile.profileId} profile={savedProfile} />}
      </>}
      <details className="fold lab-method"><summary>About this exercise and its sources</summary>
        <ul className="bullets small">{lab.limitations.map(text => <li key={text}>{text}</li>)}</ul>
        {lab.reveal.length > 0 && <ul className="bullets small">{lab.reveal.map(text => <li key={text}>{text.startsWith('https://') ? <a href={text} target="_blank" rel="noreferrer">Original company release</a> : text}</li>)}</ul>}
      </details>
    </>}
  </div>;
}

function Field({ label, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return <div className="field"><label htmlFor={id}>{label}</label>{children(id)}</div>;
}

function SituationForm({ profile, initialMode, busy, onStart }: { profile: Profile | null; initialMode: Mode; busy: boolean; onStart: (s: LabSituation, mode: Mode) => void }) {
  const { tr, lang } = useApp();
  const [mode, setMode] = useState<Mode>(profile ? initialMode : 'new');
  const existing = mode !== 'new' ? profile : null;
  const previous = existing?.investorContext?.playbook?.reviews?.at(-1)?.situation;
  const [name, setName] = useState(existing?.name ?? '');
  const [objective, setObjective] = useState<LabSituation['objective']>(existing?.objective ?? 'balanced');
  const [years, setYears] = useState(String(existing?.horizonYears.min ?? 10));
  const [cash, setCash] = useState(String(previous?.cashNeedPct ?? 0));
  const [months, setMonths] = useState(String(previous?.cashNeedMonths ?? 12));
  const [capacity, setCapacity] = useState(existing?.investorContext?.riskCapacity ?? '');
  const [willingness, setWillingness] = useState(existing?.riskLevel ?? '');
  const [experience, setExperience] = useState<LabSituation['experience']>(existing?.experience ?? 'beginner');
  const [interest, setInterest] = useState(previous?.interest ?? 'Artificial intelligence');
  const [currency, setCurrency] = useState(existing?.reportingCurrency ?? 'CAD');
  const [capital, setCapital] = useState('100000');
  const [holdings, setHoldings] = useState('');
  const [formError, setFormError] = useState('');
  const submit = () => {
    const parsed = holdings.trim() && !existing ? holdings.split('\n').filter(s => s.trim()).map(line => {
      const parts = line.trim().split(/[\s,]+/);
      const [ticker = '', weight = ''] = parts;
      return { ticker: ticker.toUpperCase(), weightPct: parts.length === 2 && weight ? Number(weight) : NaN };
    }) : [];
    if (!name.trim()) { setFormError('Enter a profile label.'); return; }
    if (parsed.length > 40 || new Set(parsed.map(p => p.ticker)).size !== parsed.length
      || parsed.some(p => !p.ticker || !Number.isFinite(p.weightPct) || p.weightPct < 0 || p.weightPct > 100)
      || (parsed.length && Math.abs(parsed.reduce((n, p) => n + p.weightPct, 0) - 100) > 0.01)) {
      setFormError('Enter up to 40 unique tickers, each with a percentage, totalling 100%.'); return;
    }
    if (!capacity || !willingness) return;
    setFormError('');
    onStart({ name: name.trim(), objective, horizonYears: Number(years), cashNeedPct: Number(cash),
      cashNeedMonths: Number(cash) > 0 ? Number(months) : null, riskCapacity: capacity as LabSituation['riskCapacity'],
      riskWillingness: willingness as LabSituation['riskWillingness'], experience, interest,
      reportingCurrency: currency, capital: Number(capital), holdings: parsed }, mode);
  };
  return <>
    <div className="lab-entry-grid">
      {([
        ['new', 'Create with Investor Lab', 'A few essentials, three situations, and your first playbook.', FlaskConical],
        ['quick', 'Quick check', 'Changed goals or cash needs? Revisit one targeted situation.', SlidersHorizontal],
        ['full', 'Full Investor Lab', 'Review your profile through three contrasting situations.', History],
      ] as const).map(([value, title, description, Icon]) => <button className="lab-entry" type="button" key={value} aria-pressed={mode === value}
        disabled={value !== 'new' && !profile} onClick={() => {
          setMode(value); const p = value !== 'new' ? profile : null;
          setName(p?.name ?? ''); setObjective(p?.objective ?? 'balanced'); setYears(String(p?.horizonYears.min ?? 10));
          setCapacity(p?.investorContext?.riskCapacity ?? ''); setWillingness(p?.riskLevel ?? '');
          setExperience(p?.experience ?? 'beginner'); setCurrency(p?.reportingCurrency ?? 'CAD');
          const prior = p?.investorContext?.playbook?.reviews?.at(-1)?.situation;
          setCash(String(prior?.cashNeedPct ?? 0)); setMonths(String(prior?.cashNeedMonths ?? 12));
          setInterest(prior?.interest ?? 'Artificial intelligence'); setFormError('');
        }}><Icon size={22} aria-hidden="true" /><strong>{title}</strong><span>{description}</span><ArrowRight size={17} aria-hidden="true" /></button>)}
    </div>
    <Card title={existing ? `Test ${existing.name}'s profile` : tr({ en: 'Start with your situation', fr: 'Commencez par votre situation' })}>
      <form onSubmit={event => { event.preventDefault(); submit(); }} className="lab-situation-form">
        <p className="small muted">Use a fictional investor. Your financial capacity and your comfort with risk are two separate inputs.</p>
        <div className="form-grid">
          <Field label="Profile label">{id => <input id={id} type="text" required maxLength={40} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. My long-term plan" />}</Field>
          <Field label="What is the main goal?">{id => <select id={id} value={objective} onChange={e => setObjective(e.target.value as typeof objective)}>{Object.entries(OBJECTIVE).map(([key, text]) => <option key={key} value={key}>{tr(text)}</option>)}</select>}</Field>
          <Field label="How many years until this goal?">{id => <input id={id} required type="number" min={0.25} max={100} step={0.25} value={years} onChange={e => setYears(e.target.value)} />}</Field>
          <Field label="Planned withdrawal (% of portfolio)">{id => <input id={id} required type="number" min={0} max={100} step="any" value={cash} onChange={e => setCash(e.target.value)} />}</Field>
          {Number(cash) > 0 && <Field label="When will that cash be needed? (months)">{id => <input id={id} required type="number" min={1} max={120} value={months} onChange={e => setMonths(e.target.value)} />}</Field>}
          <Field label="Experience with investing">{id => <select id={id} value={experience} onChange={e => setExperience(e.target.value as typeof experience)}>{Object.keys(EXPERIENCE).map(key => <option key={key} value={key}>{labelOf(EXPERIENCE, key as typeof experience, lang)}</option>)}</select>}</Field>
        </div>
        <div className="lab-risk-inputs">
          <Field label="Financial capacity to absorb losses">{id => <><select id={id} required value={capacity} onChange={e => setCapacity(e.target.value)}><option value="">Choose a level</option>{Object.entries(RISK_LEVEL).map(([key, text]) => <option key={key} value={key}>{tr(text)}</option>)}</select><span className="hint">Based on resources, obligations, and the goal's flexibility.</span></>}</Field>
          <Field label="Willingness to experience losses">{id => <><select id={id} required value={willingness} onChange={e => setWillingness(e.target.value)}><option value="">Choose a level</option>{Object.entries(RISK_LEVEL).map(([key, text]) => <option key={key} value={key}>{tr(text)}</option>)}</select><span className="hint">How much uncertainty you intend to accept.</span></>}</Field>
        </div>
        <Field label="Choose a first research interest">{id => <select id={id} value={interest} onChange={e => setInterest(e.target.value)}>
          {['Artificial intelligence', 'Diversified index funds', 'Clean energy', 'Dividend income', 'Healthcare', 'Semiconductors', 'Crypto assets'].map(text => <option key={text}>{text}</option>)}
        </select>}</Field>
        {!existing && <details className="fold"><summary>Optional: add a hypothetical portfolio</summary>
          <div className="form-grid">
            <Field label="Fictional capital">{id => <input id={id} required type="number" min={1} value={capital} onChange={e => setCapital(e.target.value)} />}</Field>
            <Field label="Reporting currency">{id => <select id={id} value={currency} onChange={e => setCurrency(e.target.value)}><option>CAD</option><option>USD</option></select>}</Field>
          </div>
          <Field label="Holdings, one ticker and weight per line">{id => <textarea id={id} value={holdings} onChange={e => setHoldings(e.target.value)} placeholder={'SPY 60\nAGG 30\nMSFT 10'} rows={4} />}</Field>
          <span className="hint">Leave blank to review Aplomb's proposed starting mix at the end.</span>
        </details>}
        {formError && <p role="alert" className="field-error">{formError}</p>}
        {existing?.isDefault && <p className="small muted">Confirming changes will create a personal copy of this example profile.</p>}
        <div className="lab-form-footer"><span className="small muted">Nothing changes in your profile until the final review.</span>
          <button type="submit" className="btn" disabled={busy}>{busy ? 'Preparing your Lab…' : 'Begin with these circumstances'} <ArrowRight size={15} aria-hidden="true" /></button></div>
      </form>
    </Card>
  </>;
}

function LabChart({ points }: { points: LabSession['chart'] }) {
  const id = useId();
  const values = points.map(p => p.value);
  const min = Math.min(...values, 95) * 0.98;
  const max = Math.max(...values, 105) * 1.02;
  const y = (v: number) => 170 - (v - min) / (max - min) * 140;
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${20 + i / Math.max(1, points.length - 1) * 480},${y(p.value)}`).join(' ');
  return <figure className="lab-chart">
    <figcaption><span>Portfolio index · starts at 100</span><strong>{values.at(-1)?.toFixed(1)}</strong></figcaption>
    <svg viewBox="0 0 520 195" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>Hypothetical portfolio through this checkpoint</title><desc id={`${id}-desc`}>Index from 100 to {values.at(-1)?.toFixed(1)}. Only information available at the current checkpoint is shown.</desc>
      {[min, 100, max].map((v, i) => <g key={i}><line x1={20} x2={500} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={v === 100 ? '4 4' : undefined} /><text x={20} y={y(v) - 6} fill="var(--text-3)" fontSize={10}>{v.toFixed(0)}</text></g>)}
      <path d={`${path}L500,180 L20,180 Z`} fill="var(--accent)" opacity={0.07} />
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2.5} strokeLinejoin="round" />
      <circle cx={500} cy={y(values.at(-1) ?? 100)} r={4} fill="var(--accent)" />
    </svg>
    <div className="lab-chart-axis"><span>Earlier observations</span><span>Current checkpoint</span></div>
    <details><summary className="small">Inspect visible observations</summary><div className="lab-chart-data"><table className="data-table"><thead><tr><th>Observation</th><th>Index</th></tr></thead><tbody>{points.map(p => <tr key={p.step}><td>{p.step + 1}</td><td>{p.value.toFixed(2)}</td></tr>)}</tbody></table></div></details>
  </figure>;
}

function DecisionForm({ lab, busy, onSave }: { lab: LabSession; busy: boolean; onSave: (decision: LabDecision, trigger: string) => void }) {
  const original = lab.observations.at(-1);
  const baseline = lab.stage === 'initial' ? lab.focusPct : original?.startingPct ?? lab.focusPct;
  const [action, setAction] = useState<LabDecision['action']>(lab.stage === 'research' ? original?.initial.action ?? 'hold' : 'hold');
  const [target, setTarget] = useState<number | null>(lab.stage === 'research' ? original?.initial.targetPct ?? baseline : baseline);
  const [reason, setReason] = useState<LabDecision['reason']>(lab.stage === 'research' ? original?.initial.reason ?? 'long_term' : 'long_term');
  const [explanation, setExplanation] = useState('');
  const [trigger, setTrigger] = useState('');
  const invalid = target === null || !Number.isFinite(target) || target < 0 || target > 100
    || (action === 'hold' && Math.abs(target - baseline) > 0.011)
    || (action === 'buy' && target <= baseline + 0.001)
    || (action === 'sell' && target >= baseline - 0.001);
  return <form className="lab-decision-form" onSubmit={e => { e.preventDefault(); if (!invalid && target !== null) onSave({ action, targetPct: target, reason, explanation }, trigger); }}>
    <fieldset><legend className="sr-only">Your action</legend><div className="lab-actions">{Object.entries(ACTIONS).map(([key, text]) =>
      <label key={key} data-selected={action === key || undefined}><input type="radio" name={`action-${lab.stage}`} value={key} checked={action === key}
        onChange={() => { setAction(key as typeof action); if (key === 'hold') setTarget(baseline); }} />{text}</label>)}</div></fieldset>
    <Field label="Target allocation to Company C (%)">{id => <><input id={id} type="number" required min={0} max={100} step="any" value={target ?? ''}
      onChange={e => setTarget(e.target.value === '' ? null : Number(e.target.value))} disabled={action === 'hold'} />
      <span className="hint">Starting weight {baseline.toFixed(1)}%. Other sleeves adjust proportionally.</span></>}</Field>
    <Field label="What is driving this choice?">{id => <select id={id} value={reason} onChange={e => setReason(e.target.value as typeof reason)}>{Object.entries(REASONS).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select>}</Field>
    <Field label={lab.stage === 'contrast' ? 'What does this contrast tell you?' : 'Explain your choice in relation to your goal'}>{id => <textarea id={id} required minLength={10} maxLength={2000} rows={4} value={explanation} onChange={e => setExplanation(e.target.value)} placeholder="What matters, and what would change your mind?" />}</Field>
    {lab.stage === 'research' && <Field label="What would make you revisit this decision?">{id => <textarea id={id} required minLength={10} maxLength={2000} rows={3} value={trigger} onChange={e => setTrigger(e.target.value)} placeholder="A changed cash need, a specific company result, an allocation limit…" />}</Field>}
    {invalid && <p className="field-error" role="alert">Buy must increase the allocation; sell must reduce it. Choose rebalance for another target.</p>}
    <button className="btn" type="submit" disabled={busy || invalid || explanation.trim().length < 10 || (lab.stage === 'research' && trigger.trim().length < 10)}>
      {busy ? 'Saving…' : lab.stage === 'initial' ? 'Record choice & investigate' : lab.stage === 'contrast' ? 'Continue' : 'Record final decision'} <ArrowRight size={14} aria-hidden="true" />
    </button>
  </form>;
}

function Research({ lab, busy, onConsult }: { lab: LabSession; busy: boolean; onConsult: (id: string, why: string) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [why, setWhy] = useState('');
  const consulted = lab.observations.at(-1)?.consultations ?? [];
  return <Card title="Investigate with Aplomb" actions={<Search size={17} aria-hidden="true" />}>
    <p className="small muted">Open the evidence that matters. Record why you used it before your final decision.</p>
    <div className="lab-evidence">{lab.evidence.map(item => {
      const used = consulted.find(c => c.evidenceId === item.evidenceId);
      return <div key={item.evidenceId} className="lab-evidence-item">
        <button className="lab-evidence-toggle" type="button" aria-expanded={open === item.evidenceId}
          onClick={() => { setOpen(open === item.evidenceId ? null : item.evidenceId); setWhy(used?.why ?? ''); }}>
          <span><strong>{item.title}</strong><span className="block small muted">{item.available ? item.relativeDate : 'Unavailable at this checkpoint'}</span></span>
          {used ? <Check size={16} aria-label="Consulted" /> : item.available ? <ArrowRight size={16} aria-hidden="true" /> : <LockKeyhole size={15} aria-hidden="true" />}
        </button>
        {open === item.evidenceId && <div className="lab-evidence-body"><p>{item.summary}</p>
          {lab.stage === 'research' && item.available && <form onSubmit={e => { e.preventDefault(); onConsult(item.evidenceId, why); }}>
            <Field label="Why is this useful for your decision?">{id => <textarea id={id} required minLength={5} maxLength={1000} rows={2} value={why} onChange={e => setWhy(e.target.value)} />}</Field>
            <button type="submit" className="btn ghost btn-sm" disabled={busy || why.trim().length < 5}>{used ? 'Update evidence note' : 'Add to my evidence'}</button>
          </form>}
        </div>}
      </div>;
    })}</div>
    {consulted.length > 0 && <p className="small lab-evidence-count">{consulted.length} evidence {consulted.length === 1 ? 'note' : 'notes'} recorded</p>}
  </Card>;
}

function Review({ lab, busy, onConfirm, headingRef }: { lab: LabSession; busy: boolean; onConfirm: (accepted: { key: string; value?: number | null }[], principle: string, trigger: string, explanation: string) => void; headingRef: React.RefObject<HTMLHeadingElement | null> }) {
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, number>>({});
  const [principle, setPrinciple] = useState(lab.proposedPrinciple);
  const [trigger, setTrigger] = useState(lab.proposedRevisitTrigger);
  const [explanation, setExplanation] = useState('');
  const allRequired = lab.settings.every(s => !s.required || accepted[s.key]);
  const validValues = lab.settings.every(s => {
    if (!accepted[s.key] || s.minimum == null || s.maximum == null) return true;
    const value = values[s.key] ?? s.value;
    return value != null && Number.isFinite(value) && value >= s.minimum && value <= s.maximum;
  });
  const confirm = () => onConfirm(lab.settings.filter(s => accepted[s.key]).map(s => {
    const value = values[s.key] ?? s.value;
    return value === undefined ? { key: s.key } : { key: s.key, value };
  }), principle, trigger, explanation);
  return <>
    <h2 ref={headingRef} tabIndex={-1}>A profile you can explain</h2>
    <p className="lab-prompt">Your circumstances, choices, and proposed rules remain distinct. Accept or edit each setting you want to use.</p>
    <Card id="lab-stated" title="1. Stated circumstances">
      <dl className="lab-facts"><div><dt>Goal & horizon</dt><dd>{lab.situation.objective} · {lab.situation.horizonYears} years</dd></div><div><dt>Planned cash need</dt><dd>{lab.situation.cashNeedPct}%{lab.situation.cashNeedPct > 0 ? ` within ${lab.situation.cashNeedMonths} months` : ''}</dd></div><div><dt>Financial capacity</dt><dd>{lab.situation.riskCapacity.replaceAll('_', ' ')}</dd></div><div><dt>Willingness</dt><dd>{lab.situation.riskWillingness.replaceAll('_', ' ')}</dd></div></dl>
    </Card>
    <Card title="2. Observed choices">
      {lab.observations.map(obs => <details className="lab-observation" id={`lab-observation-${obs.checkpoint}`} key={obs.checkpoint}>
        <summary><span>Checkpoint {obs.checkpoint} · {obs.title}</span><strong>{obs.initial.targetPct.toFixed(1)}% → {obs.final?.targetPct.toFixed(1)}%</strong></summary>
        <p className="small"><strong>Initial:</strong> {obs.initial.explanation}</p>
        <ul className="bullets small">{obs.consultations.map(c => <li key={c.evidenceId}><strong>{c.title}:</strong> {c.why}</li>)}</ul>
        {!obs.consultations.length && <p className="small muted">No evidence notes recorded.</p>}
        <p className="small"><strong>Final:</strong> {obs.final?.explanation}</p><p className="small"><strong>Contrast:</strong> {obs.contrastPrompt} {obs.contrast?.explanation}</p>
        <p className="small muted">{obs.interpretation}</p>
      </details>)}
    </Card>
    <Card title="3. Proposed settings" actions={<button className="btn ghost btn-sm" type="button" onClick={() => setAccepted(Object.fromEntries(lab.settings.map(s => [s.key, true])))}>Accept all proposed settings</button>}>
      <p className="small muted">Unchecked settings keep their current values. For a new profile, every setting needs confirmation. Choosing a size in a simulation does not make it your limit.</p>
      <div className="lab-settings">{lab.settings.map(setting => <Setting key={setting.key} setting={setting} accepted={!!accepted[setting.key]} value={values[setting.key] ?? setting.value ?? undefined}
        onAccept={v => setAccepted(a => ({ ...a, [setting.key]: v }))} onValue={v => setValues(a => ({ ...a, [setting.key]: v }))} />)}</div>
    </Card>
    <Card title="Your editable investment playbook">
      <form onSubmit={e => { e.preventDefault(); if (allRequired && validValues) confirm(); }}>
        <Field label="The principle I want to follow">{id => <textarea id={id} required minLength={10} maxLength={2000} rows={3} value={principle} onChange={e => setPrinciple(e.target.value)} />}</Field>
        <Field label="What would make me revisit a decision">{id => <textarea id={id} required minLength={10} maxLength={2000} rows={3} value={trigger} onChange={e => setTrigger(e.target.value)} />}</Field>
        <Field label="Why these settings reflect my intended approach">{id => <textarea id={id} required minLength={10} maxLength={2000} rows={3} value={explanation} onChange={e => setExplanation(e.target.value)} />}</Field>
        {!allRequired && <p className="small muted">Review and accept the required settings above before saving.</p>}
        {!validValues && <p className="field-error" role="alert">Enter a value within the allowed range for each accepted setting.</p>}
        <button type="submit" className="btn" disabled={busy || !allRequired || !validValues || explanation.trim().length < 10 || principle.trim().length < 10 || trigger.trim().length < 10}>{busy ? 'Saving…' : 'Confirm & save profile'} <Check size={15} aria-hidden="true" /></button>
      </form>
    </Card>
  </>;
}

function Setting({ setting: s, accepted, value, onAccept, onValue }: { setting: LabSetting; accepted: boolean; value: number | undefined; onAccept: (v: boolean) => void; onValue: (v: number) => void }) {
  const id = useId();
  return <div className="lab-setting">
    <div className="lab-setting-heading"><label><input type="checkbox" checked={accepted} onChange={e => onAccept(e.target.checked)} /> <strong>{s.label}</strong></label>{s.required && <span className="small muted">Confirm to create</span>}</div>
    <div className="lab-setting-diff"><span>{s.current ?? 'Not set'}</span><ArrowRight size={16} aria-label="proposed change" />
      {s.minimum !== undefined && s.minimum !== null && s.maximum !== undefined && s.maximum !== null
        ? <label htmlFor={id} className="lab-setting-number"><input id={id} aria-label={`Proposed ${s.label} (${s.minimum} to ${s.maximum} percent)`} type="number" min={s.minimum} max={s.maximum} step="any" value={value != null && Number.isFinite(value) ? value : ''} onChange={e => onValue(e.target.value === '' ? NaN : Number(e.target.value))} /> %</label>
        : <strong>{s.proposed}</strong>}
    </div>
    <p className="small">{s.explanation}</p><div className="lab-basis"><span>Based on</span>{s.basis.map((basis, i) => basis.startsWith('Checkpoint ') ? <a key={i} href={`#lab-observation-${basis.split(':')[0]?.split(' ')[1]}`}>{basis}</a> : basis === 'Stated circumstances' ? <a key={i} href="#lab-stated">{basis}</a> : <span key={i}>{basis}</span>)}</div>
  </div>;
}
