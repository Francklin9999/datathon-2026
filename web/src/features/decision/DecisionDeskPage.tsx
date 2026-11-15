'use client';
/**
 * Decision Desk (T14, web/page-specs/decision-desk.md). Free text → /requests/parse → user confirms a
 * structured form; deterministic /check previews (250 ms debounce, latest-response-wins); "Analyze
 * evidence" creates a decision run kept in ?runId=; compare uses /check/batch with identical inputs.
 */
import Link from 'next/link';
import { RebalancePanel } from './RebalancePanel';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  ApiError, BatchCheckResponse, CheckResult, DecisionRequest, FetchAssetResponse, FundingMode,
  ParsedRequest, Profile, Run,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, isAbort, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { assetsChanged, useAssetUniverse } from '../../state/useAssetUniverse';
import { useRun } from '../../state/useRun';
import { WindowControl } from '../../components/shell/TopBar';
import { SuggestInput } from '../../components/ui/SuggestInput';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge } from '../../components/common/Badges';
import { RuleTable } from '../../components/run/RuleTable';
import { BriefView } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import {
  BoundaryNote, FundingOptions, ScenarioCards, SnapshotCompare, VerdictHeader, fundingLabel,
} from '../../components/run/Results';
import { ERROR_CODE, FUNDING_MODE, RUN_STATUS, labelOf } from '../../lib/labels';
import { fmtDateTime, fmtPct, fmtPts } from '../../lib/format';
import {
  buildCheckRequest, createLatestGate, describeRequest, moveOf, roundSize, sameDecisionRequest,
  validateMoveForm, type MoveForm, type MoveFormIssue,
} from '../../lib/move';
import { isTerminal } from '../../lib/runs';
import { tickerSuggestions } from '../../lib/suggest';
import { investigationOriginalText, readInvestigationContext, validInvestigationContext } from '../../lib/world';

const FUNDING_MODES: readonly FundingMode[] = ['auto', 'pro_rata', 'from_cash', 'from_holdings', 'new_money'];
const DEBOUNCE_MS = 250;
const EMPTY_FORM: MoveForm = { ticker: '', sizePct: 0, fundingMode: 'auto', fromTickers: [] };

function isApiErrorBody(value: CheckResult | ApiError): value is ApiError {
  return 'error' in value;
}

export function DecisionDeskPage() {
  return <ProfileGate>{profile => <DeskContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

interface PreviewState { result: CheckResult | null; error: ApiRequestError | null; loading: boolean }

function DeskContent({ profile }: { profile: Profile }) {
  const { tr, lang, windowSpec, windowCode, announce, profiles, selectProfile } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get('runId');
  const urlEvent = params.get('eventId');
  const contextProfile = params.get('profileId');
  const urlSourceRun = params.get('sourceRunId');
  const ticker = params.get('ticker') ?? '';
  // Text typed in the top bar ("Ask Aplomb") arrives as ?q= and is interpreted once.
  const askedText = params.get('q');
  const contextMatches = !contextProfile || contextProfile === profile.profileId;


  const [form, setForm] = useState<MoveForm>(() => contextMatches && /^[A-Z0-9.-]{1,20}$/.test(ticker) ? { ...EMPTY_FORM, ticker } : EMPTY_FORM);
  const [originalText, setOriginalText] = useState<string | null>(null);
  const [goal, setGoal] = useState<DecisionRequest | null>(null);
  const touched = useRef(false);
  const update = useCallback((patch: Partial<MoveForm>) => {
    touched.current = true;
    setGoal(null);
    setForm(f => ({ ...f, ...patch }));
  }, []);

  // ----- run restored from the URL -----
  const polled = useRun(runId, finished => announce(`${tr({ en: 'Decision run', fr: 'Exécution de décision' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;
  const savedContext = run?.profileId === profile.profileId && run.input.kind === 'decision' ? readInvestigationContext(run.input.originalText) : null;
  const context = (contextMatches ? validInvestigationContext(urlEvent, ticker, urlSourceRun) : null) ?? savedContext;
  const contextEvent = context?.eventId ?? null;
  const sourceRun = context?.sourceRunId ?? null;
  const runInput = run?.input.kind === 'decision' ? run.input : null;
  useEffect(() => {
    if (!runInput || run?.profileId !== profile.profileId || touched.current) return;
    if (runInput.request.type === 'move') {
      const m = runInput.request.move;
      setForm({ ticker: m.ticker, sizePct: m.sizePct, fundingMode: m.funding.mode, fromTickers: m.funding.fromTickers ?? [] });
      setGoal(null);
    } else {
      setGoal(runInput.request);
    }
    setOriginalText(runInput.originalText);
  }, [runInput, run?.profileId, profile.profileId]);

  // ----- deterministic preview (debounced, latest-wins) -----
  const currentWeight = profile.portfolio.positions.find(p => p.ticker === form.ticker.trim().toUpperCase())?.weightPct ?? 0;
  const maxSize = form.fundingMode === 'new_money' ? 100 : Math.max(0, roundSize(100 - currentWeight));
  const issues = validateMoveForm(form, currentWeight);
  const shownIssues = form.sizePct > 0 || form.ticker.trim() ? issues.filter(i => !(i.field === 'sizePct' && form.sizePct === 0)) : [];
  const blocking = shownIssues.length > 0;
  const [preview, setPreview] = useState<PreviewState>({ result: null, error: null, loading: false });
  const gate = useMemo(() => createLatestGate(), []);
  const checkRequest = useMemo(() => buildCheckRequest(profile.profileId, form, windowSpec), [profile.profileId, form, windowSpec]);
  const checkKey = JSON.stringify(checkRequest);

  useEffect(() => {
    if (blocking || goal) { gate.invalidate(); setPreview({ result: null, error: null, loading: false }); return undefined; }
    const token = gate.issue();
    const controller = new AbortController();
    setPreview(p => ({ ...p, loading: true, error: null }));
    const timer = setTimeout(() => {
      getApiClient().check(checkRequest, controller.signal).then(
        result => { if (gate.isLatest(token)) setPreview({ result, error: null, loading: false }); },
        error => {
          if (isAbort(error) || !gate.isLatest(token)) return;
          setPreview({ result: null, error: asApiError(error), loading: false });
        },
      );
    }, DEBOUNCE_MS);
    return () => { clearTimeout(timer); controller.abort(); };
    // checkKey captures every input of checkRequest.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkKey, blocking, goal, gate]);

  const previewScope = useMemo<FactScope | null>(() => (preview.result
    ? { kind: 'local', label: { en: 'Instant rule check, computed by code. Not part of an analysis.', fr: 'Vérification instantanée, calculée par le code. Hors de toute analyse.' }, facts: preview.result.facts }
    : null), [preview.result]);

  // ----- run creation -----
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const move = moveOf(form);
  const confirmedRequest: DecisionRequest | null = goal ?? (move ? { type: 'move', move } : null);
  const canAnalyze = Boolean(confirmedRequest) && (goal !== null || issues.length === 0) && !creating;
  const analyze = async () => {
    if (!confirmedRequest) return;
    setCreating(true); setCreateError(null);
    try {
      const contextualText = investigationOriginalText(originalText, context);
      const created = await getApiClient().createRun({
        kind: 'decision', profileId: profile.profileId, lang, request: confirmedRequest, window: { code: windowCode },
        ...(contextualText ? { originalText: contextualText } : {}),
      }, `decision-${crypto.randomUUID()}`);
      touched.current = false;
      const next = new URLSearchParams(params.toString());
      next.set('runId', created.runId);
      router.replace(`/decision-desk/?${next.toString()}`);
    } catch (error) {
      setCreateError(asApiError(error));
    } finally { setCreating(false); }
  };

  // AT-20: the signed brief is stale once the request, the window or a rule threshold on screen
  // differs from what the run was computed with. Old sentences are never rewritten, only marked.
  const runChecks = run?.result?.kind === 'decision' ? run.result.decision.scenarios[0]?.ruleChecks ?? [] : [];
  const thresholdChanged = runChecks.some(check => {
    const rule = profile.rules.find(r => r.ruleId === check.ruleId);
    return rule !== undefined && (rule.threshold !== check.threshold || (!rule.enabled && check.status !== 'info'));
  });
  const windowChanged = Boolean(runInput && runInput.window.code !== windowCode);
  const staleRun = Boolean(runInput && run?.profileId === profile.profileId
    && ((confirmedRequest && !sameDecisionRequest(runInput.request, confirmedRequest)) || windowChanged || thresholdChanged));
  const otherProfileId = run?.profileId && run.profileId !== profile.profileId ? run.profileId : null;

  return (
    <>
      <PageHeader actions={<WindowControl />} tour="desk-header"
        title={tr({ en: `Test a move for ${profile.name}`, fr: `Tester un mouvement pour ${profile.name}` })}>
        <p className="page-sub">{tr({ en: 'Describe a move or fill in the form, then analyze the evidence. Nothing is ever executed.', fr: 'Décrivez un mouvement ou remplissez le formulaire, puis analysez les preuves. Rien n’est jamais exécuté.' })}</p>
      </PageHeader>

      <RebalancePanel key={`${profile.profileId}|${profile.version}|${JSON.stringify(windowSpec)}`} profile={profile} />

      {contextEvent && <Card title={tr({ en: 'Investigation context', fr: 'Contexte de recherche' })}>
        <p className="small">{tr({ en: 'Event relevance does not establish financial impact. Review its sources before testing a hypothetical move.', fr: 'La pertinence de l’événement ne prouve pas une incidence financière. Examinez ses sources avant de tester un mouvement hypothétique.' })}</p>
        {!contextMatches && <p className="stale-note">{tr({ en: 'This event was selected for another persona. Select that persona to restore its holding context.', fr: 'Cet événement a été sélectionné pour un autre profil. Sélectionnez ce profil pour retrouver le contexte de la position.' })}</p>}
        <Link href={`/world-explorer/?${new URLSearchParams({ eventId: contextEvent, ...(sourceRun ? { runId: sourceRun } : {}) }).toString()}`}>{tr({ en: 'Review event and original sources', fr: 'Examiner l’événement et ses sources originales' })}</Link>
        {sourceRun && <> · <Link href={`/evidence-audit/?runId=${encodeURIComponent(sourceRun)}`}>{tr({ en: 'Event brief evidence', fr: 'Preuves de la note d’événement' })}</Link></>}
      </Card>}
      <div className="cols">
        <div id="request" data-section={tr({ en: 'Request', fr: 'Demande' })}>
          <FreeText profile={profile} initial={askedText} onConsumed={() => {
            const next = new URLSearchParams(params.toString());
            next.delete('q');
            const rest = next.toString();
            router.replace(rest ? `/decision-desk/?${rest}` : '/decision-desk/');
          }} onUse={(parsed, text) => {
            setOriginalText(text);
            if (!parsed.request) return;
            touched.current = true;
            if (parsed.request.type === 'move') {
              const m = parsed.request.move;
              setGoal(null);
              setForm({ ticker: m.ticker, sizePct: m.sizePct, fundingMode: m.funding.mode, fromTickers: m.funding.fromTickers ?? [] });
            } else {
              setGoal(parsed.request);
            }
          }} />
          <MoveFormCard profile={profile} form={form} update={update} maxSize={maxSize} currentWeight={currentWeight} issues={shownIssues} goal={goal} />
        </div>
        <div>
          <Card id="preview" section={tr({ en: 'Check', fr: 'Vérification' })} tour="preview" title={tr({ en: 'Instant rule check', fr: 'Vérification instantanée des règles' })}
            info={tr({ en: 'Computed by code from the plan’s rules, updated as you change the move. No AI is involved.', fr: 'Calculée par le code à partir des règles du plan, à chaque changement du mouvement. Aucune IA n’intervient.' })}>
            {goal ? (
              <p className="small muted">{tr({ en: 'Goals have no instant check; analyze them instead.', fr: 'Les objectifs n’ont pas de vérification instantanée ; analysez-les directement.' })}</p>
            ) : (
              <>
                <p className="small muted">{move
                  ? `${describeRequest({ type: 'move', move }, lang)}, ${fundingLabel(move.funding, lang)}`
                  : tr({ en: 'Baseline: current portfolio, no move (size 0).', fr: 'Référence : portefeuille actuel, sans mouvement (taille 0).' })}</p>
                {preview.loading && <Loading label={tr({ en: 'Checking rules…', fr: 'Vérification des règles…' })} />}
                {preview.error && !preview.loading && <PreviewError error={preview.error} ticker={form.ticker} />}
                {preview.result && previewScope && !preview.loading && (
                  <FactScopeProvider scope={previewScope}>
                    <VerdictHeader verdict={preview.result.verdict} counts={preview.result.counts} />
                    {move && <BoundaryNote sizePct={preview.result.maxCompatibleSizePct} counts={preview.result.counts} baselineConflict={preview.result.baselineConflict} />}
                    <p className="small muted">{tr({ en: 'Funding used', fr: 'Financement utilisé' })}: {fundingLabel(preview.result.fundingUsed, lang)}</p>
                  </FactScopeProvider>
                )}
              </>
            )}
            <div className="row-actions">
              <button type="button" className="btn" disabled={!canAnalyze} onClick={() => void analyze()} data-tour="analyze">
                {tr({ en: 'Analyze evidence', fr: 'Analyser les preuves' })}
              </button>
              <span className="small muted">{tr({ en: 'Starts the audited AI analysis.', fr: 'Lance l’analyse IA auditée.' })}</span>
            </div>
            {createError && <ErrorState error={createError} />}
          </Card>
        </div>
      </div>

      {preview.result && previewScope && !goal && !preview.loading && run?.status !== 'succeeded' && (
        <FactScopeProvider scope={previewScope}>
          <Card title={tr({ en: 'Preview details', fr: 'Détails de l’aperçu' })}>
            <SnapshotCompare before={preview.result.portfolioBefore} after={move ? preview.result.portfolioAfter : null} />
            <h3 className="h4">{tr({ en: 'Rule checks', fr: 'Vérifications des règles' })}</h3>
            <RuleTable checks={preview.result.ruleChecks} rules={profile.rules} caption={tr({ en: 'Preview rule checks', fr: 'Vérifications en aperçu' })} />
            <FundingOptions options={preview.result.fundingOptions} />
          </Card>
        </FactScopeProvider>
      )}

      <ComparePanel profile={profile} form={form} />

      {runId && (
        <Card id="run" section={tr({ en: 'Analysis', fr: 'Analyse' })} tour="run" title={tr({ en: 'Evidence analysis', fr: 'Analyse des preuves' })}>
          {polled.loading && !run && <Loading />}
          {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
            {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This analysis does not exist or belongs to another session.', fr: 'Cette analyse n’existe pas ou appartient à une autre session.' }) } : {})} />}
          {polled.pollError && (
            <p className="small muted" role="status">{tr({ en: 'Connection lost, retrying…', fr: 'Connexion perdue, nouvel essai…' })}</p>
          )}
          {otherProfileId && (
            <p className="stale-note">
              {tr({ en: 'This analysis belongs to another fictional profile.', fr: 'Cette analyse concerne un autre profil fictif.' })}{' '}
              <button type="button" className="linklike" onClick={() => selectProfile(otherProfileId)}>
                {tr({ en: 'Switch to', fr: 'Basculer vers' })} {profiles.find(p => p.profileId === otherProfileId)?.name ?? otherProfileId}
              </button>
            </p>
          )}
          {run && <DecisionRun run={run} stale={staleRun} />}
        </Card>
      )}
    </>
  );
}

function PreviewError({ error, ticker }: { error: ApiRequestError; ticker: string }) {
  const { tr, feature } = useApp();
  const [fetching, setFetching] = useState(false);
  const [result, setResult] = useState<FetchAssetResponse | null>(null);
  const [fetchError, setFetchError] = useState<ApiRequestError | null>(null);
  const symbol = ticker.trim().toUpperCase();
  const canFetch = error.code === 'not_found' && feature('on_demand_tickers') && symbol !== '';
  const fetchTicker = async () => {
    setFetching(true); setFetchError(null);
    try {
      const fetched = await getApiClient().fetchAsset(symbol);
      setResult(fetched);
      // The new asset joins the suggestions everywhere.
      if (fetched.accepted) assetsChanged();
    }
    catch (e) { setFetchError(asApiError(e)); }
    finally { setFetching(false); }
  };
  return (
    <ErrorState error={error}>
      {canFetch && !result && (
        <button type="button" className="btn ghost btn-sm" disabled={fetching} onClick={() => void fetchTicker()}>
          {tr({ en: `Fetch ${symbol} on demand`, fr: `Récupérer ${symbol} à la demande` })}
        </button>
      )}
      {fetching && <Loading label={tr({ en: 'Fetching (may take up to 20 s)…', fr: 'Récupération (jusqu’à 20 s)…' })} />}
      {result && (result.accepted
        ? <p className="small">{tr({ en: 'Accepted as an on-demand asset. Change the size to re-check.', fr: 'Accepté comme actif à la demande. Modifiez la taille pour revérifier.' })}</p>
        : <p className="small">{tr({ en: 'Rejected', fr: 'Rejeté' })}: {result.rejectedReason ? tr(result.rejectedReason) : '—'}</p>)}
      {fetchError && <p className="field-error">{fetchError.message}</p>}
    </ErrorState>
  );
}

function FreeText({ profile, onUse, initial, onConsumed }: {
  profile: Profile; onUse: (parsed: ParsedRequest, text: string) => void; initial?: string | null; onConsumed?: () => void;
}) {
  const { tr, lang, feature } = useApp();
  const [text, setText] = useState(initial ?? '');
  const [parsed, setParsed] = useState<ParsedRequest | null>(null);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const trimmed = text.trim();
  const valid = trimmed.length >= 1 && trimmed.length <= 600;
  const interpret = useCallback(async (value: string) => {
    setBusy(true); setError(null); setParsed(null);
    try { setParsed(await getApiClient().parse({ profileId: profile.profileId, text: value, lang })); }
    catch (e) { setError(asApiError(e)); }
    finally { setBusy(false); }
  }, [profile.profileId, lang]);
  const submit = async () => { if (valid) await interpret(trimmed); };
  // A request typed in the top bar is interpreted once, then dropped from the address.
  const asked = useRef<string | null>(null);
  useEffect(() => {
    const value = initial?.trim().slice(0, 600) ?? '';
    if (!value || asked.current === value) return;
    asked.current = value;
    setText(value);
    void interpret(value);
    onConsumed?.();
  }, [initial, interpret, onConsumed]);
  const goalBlocked = parsed?.request?.type === 'goal' && !feature('goal_requests');
  return (
    <Card title={tr({ en: 'Describe the move', fr: 'Décrivez le mouvement' })} tour="freetext">
      <form onSubmit={e => { e.preventDefault(); void submit(); }}>
        <div className="field">
          <label htmlFor="request-text">{tr({ en: 'In your own words', fr: 'Dans vos mots' })}</label>
          <textarea id="request-text" value={text} maxLength={600} onChange={e => setText(e.target.value)}
            placeholder={tr({ en: 'e.g. What if this investor added a quarter of the portfolio to Tesla?', fr: 'ex. Et si cet investisseur ajoutait un quart du portefeuille à Tesla ?' })}
            aria-describedby="request-text-hint" />
          <span id="request-text-hint" className="hint">{trimmed.length}/600. {tr({ en: 'Nothing runs until you confirm.', fr: 'Rien ne s’exécute avant votre confirmation.' })}</span>
        </div>
        <div className="row-actions">
          <button type="submit" className="btn ghost" disabled={!valid || busy}>{tr({ en: 'Interpret', fr: 'Interpréter' })}</button>
        </div>
      </form>
      {busy && <Loading label={tr({ en: 'Interpreting…', fr: 'Interprétation…' })} />}
      {error && (
        <ErrorState error={error} {...(error.code === 'upstream_unavailable'
          ? { title: tr({ en: 'AI interpretation is not available on this server right now.', fr: 'L’interprétation par l’IA n’est pas disponible sur ce serveur pour l’instant.' }) } : {})}>
          <p className="small">{tr({ en: 'Fill in the form below instead: it works without AI.', fr: 'Remplissez plutôt le formulaire ci-dessous : il fonctionne sans IA.' })}</p>
        </ErrorState>
      )}
      {parsed && (
        <div className="state" aria-live="polite">
          {parsed.refused ? (
            <>
              <p className="state-title">{tr({ en: 'Not something this simulation does', fr: 'Hors du champ de cette simulation' })}</p>
              <p>{tr(parsed.refused.message)}</p>
              <p className="small muted">{tr({ en: 'Aplomb tests hypothetical moves against fictional plans; no order is placed. The form below still works.', fr: 'Aplomb teste des mouvements hypothétiques contre des plans fictifs ; aucun ordre n’est passé. Le formulaire ci-dessous reste disponible.' })}</p>
            </>
          ) : (
            <>
              <p className="state-title">{tr(parsed.interpretation)}</p>
              {parsed.missing.length > 0 && (
                <ul className="bullets small">{parsed.missing.map(m => <li key={m.field}>{tr(m.question)}</li>)}</ul>
              )}
              {parsed.warnings.length > 0 && <ul className="bullets small">{parsed.warnings.map((w, i) => <li key={i}>{tr(w)}</li>)}</ul>}
              {goalBlocked && <p className="small">{tr({ en: 'Goal requests are turned off; name a specific asset instead.', fr: 'Les objectifs sont désactivés ; nommez plutôt un actif précis.' })}</p>}
              {parsed.request && !goalBlocked && (
                <button type="button" className="btn btn-sm" onClick={() => onUse(parsed, trimmed)}>
                  {tr({ en: 'Use in the form', fr: 'Utiliser dans le formulaire' })}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </Card>
  );
}

/** Structured move form. Also used by the Time Machine (T15) so both pages build the same request. */
export function MoveFormCard({ profile, form, update, maxSize, currentWeight, issues, goal }: {
  profile: Profile; form: MoveForm; update: (patch: Partial<MoveForm>) => void; maxSize: number; currentWeight: number;
  issues: MoveFormIssue[]; goal: DecisionRequest | null;
}) {
  const { tr, lang } = useApp();
  // One read of the universe, searched locally on each keystroke; holdings first, offered even if the read fails.
  const { assets } = useAssetUniverse();
  const positions = profile.portfolio.positions;
  const suggestions = useMemo(() => tickerSuggestions(assets, positions.map(p => p.ticker), tr({ en: 'Held', fr: 'Détenu' })),
    [assets, positions, tr]);
  const issueFor = (field: keyof MoveForm) => issues.some(i => i.field === field);
  return (
    <Card title={tr({ en: 'Move details', fr: 'Détails du mouvement' })} tour="move-form">
      {goal && goal.type === 'goal' && (
        <div className="state">
          <p className="state-title">{tr({ en: 'Goal request confirmed from your text', fr: 'Objectif confirmé à partir de votre texte' })}</p>
          <p className="small">{describeRequest(goal, lang)}{goal.goal.targetExposurePct !== null ? ` · ${tr({ en: 'target', fr: 'cible' })} ${fmtPct(goal.goal.targetExposurePct, lang)}` : ''}</p>
          <p className="small muted">{tr({ en: 'Rules are not loosened for a goal. Editing the form switches back to a single move.', fr: 'Les règles ne sont pas assouplies pour un objectif. Modifier le formulaire revient à un mouvement unique.' })}</p>
        </div>
      )}
      <div className="form-grid">
        <div className="field">
          <label htmlFor="move-ticker">{tr({ en: 'Asset (ticker)', fr: 'Actif (symbole)' })}</label>
          <SuggestInput id="move-ticker" value={form.ticker} onChange={ticker => update({ ticker: ticker.toUpperCase() })}
            suggestions={suggestions} listLabel={tr({ en: 'Matching assets', fr: 'Actifs correspondants' })}
            aria-invalid={issueFor('ticker')} />
          <span className="hint">{tr({ en: 'Current weight', fr: 'Poids actuel' })}: {fmtPct(currentWeight, lang)}</span>
        </div>
        <div className="field">
          <label htmlFor="move-funding">{tr({ en: 'Funding', fr: 'Financement' })}</label>
          <select id="move-funding" value={form.fundingMode} onChange={e => update({ fundingMode: e.target.value as FundingMode })}>
            {FUNDING_MODES.map(mode => <option key={mode} value={mode}>{labelOf(FUNDING_MODE, mode, lang)}</option>)}
          </select>
          <span className="hint">{form.fundingMode === 'new_money'
            ? tr({ en: 'New money enlarges the portfolio, so the denominator changes.', fr: 'Un nouvel apport agrandit le portefeuille ; le dénominateur change.' })
            : tr({ en: 'Funded from the current portfolio value.', fr: 'Financé à partir de la valeur actuelle du portefeuille.' })}</span>
        </div>
      </div>
      <div className="field" style={{ marginTop: 16 }} data-tour="move-size">
        <label htmlFor="move-size">{tr({ en: 'Added size (points of current value)', fr: 'Taille ajoutée (points de la valeur actuelle)' })}</label>
        <div className="slider-row">
          <input type="range" min={0} max={maxSize} step={0.5} value={Math.min(form.sizePct, maxSize)}
            onChange={e => update({ sizePct: Number(e.target.value) })} aria-label={tr({ en: 'Added size slider', fr: 'Curseur de taille ajoutée' })}
            aria-valuetext={fmtPts(form.sizePct, lang)} />
          <input id="move-size" type="number" min={0} max={maxSize} step={0.1} value={form.sizePct}
            onChange={e => update({ sizePct: Number(e.target.value) || 0 })} aria-invalid={issueFor('sizePct')} />
        </div>
        <span className="hint">{tr({ en: 'Added amount, not a target weight. 0 shows the current portfolio.', fr: 'Montant ajouté, pas un poids cible. 0 montre le portefeuille actuel.' })}</span>
      </div>
      {form.fundingMode === 'from_holdings' && (
        <fieldset style={{ marginTop: 16 }}>
          <legend>{tr({ en: 'Holdings that fund the move', fr: 'Positions qui financent le mouvement' })}</legend>
          <div className="checks">
            {profile.portfolio.positions.filter(p => p.ticker !== form.ticker).map(p => (
              <label key={p.ticker}>
                <input type="checkbox" checked={form.fromTickers.includes(p.ticker)}
                  onChange={e => update({ fromTickers: e.target.checked ? [...form.fromTickers, p.ticker] : form.fromTickers.filter(t => t !== p.ticker) })} />
                <span className="ticker">{p.ticker}</span> <span className="small muted">{fmtPct(p.weightPct, lang)}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      {issues.length > 0 && (
        <div className="error-summary" role="alert" style={{ marginTop: 12 }}>
          <ul className="bullets small">{issues.map(issue => <li key={issue.field}>{tr(issue.message)}</li>)}</ul>
        </div>
      )}
    </Card>
  );
}

interface CompareState { loading: boolean; error: ApiRequestError | null; data: BatchCheckResponse | null; ids: string[] }

function ComparePanel({ profile, form }: { profile: Profile; form: MoveForm }) {
  const { tr, profiles, windowSpec, lang } = useApp();
  const others = profiles.filter(p => p.profileId !== profile.profileId);
  const [otherId, setOtherId] = useState('');
  const [state, setState] = useState<CompareState>({ loading: false, error: null, data: null, ids: [] });
  const effectiveOther = others.some(p => p.profileId === otherId) ? otherId : others[0]?.profileId ?? '';
  const move = moveOf(form);
  const compare = async () => {
    if (!effectiveOther) return;
    const ids = [profile.profileId, effectiveOther];
    setState({ loading: true, error: null, data: null, ids });
    try {
      const data = await getApiClient().checkBatch({
        items: [buildCheckRequest(profile.profileId, form, windowSpec), buildCheckRequest(effectiveOther, form, windowSpec)],
      });
      setState({ loading: false, error: null, data, ids });
    } catch (e) { setState({ loading: false, error: asApiError(e), data: null, ids }); }
  };
  if (others.length === 0) return null;
  return (
    <details className="fold compare-fold" id="compare" data-section={tr({ en: 'Compare', fr: 'Comparer' })} data-tour="compare">
      <summary>{tr({ en: 'Compare with another profile', fr: 'Comparer avec un autre profil' })}</summary>
      <div className="fold-body">
      <div className="form-grid">
        <div className="field">
          <label htmlFor="compare-with">{tr({ en: 'Compare with', fr: 'Comparer avec' })}</label>
          <select id="compare-with" value={effectiveOther} onChange={e => setOtherId(e.target.value)}>
            {others.map(p => <option key={p.profileId} value={p.profileId}>{p.name}</option>)}
          </select>
        </div>
      </div>
      <p className="small muted">{move
        ? tr({ en: `Same request for both: ${describeRequest({ type: 'move', move }, 'en')}, ${fundingLabel(move.funding, 'en')}, same window.`, fr: `Même requête pour les deux : ${describeRequest({ type: 'move', move }, 'fr')}, ${fundingLabel(move.funding, 'fr')}, même fenêtre.` })
        : tr({ en: 'No move set: compares both current portfolios.', fr: 'Aucun mouvement : compare les deux portefeuilles actuels.' })}</p>
      <div className="row-actions"><button type="button" className="btn ghost" onClick={() => void compare()} disabled={state.loading}>{tr({ en: 'Compare', fr: 'Comparer' })}</button></div>
      {state.loading && <Loading />}
      {state.error && <ErrorState error={state.error} />}
      {state.data && (
        <div className="compare-panes" style={{ marginTop: 16 }}>
          {state.data.results.map((item, i) => {
            const id = state.ids[i] ?? '';
            const p = profiles.find(x => x.profileId === id);
            return (
              <div className="pane" key={id || i}>
                <h3 className="h4">{p?.name ?? id}</h3>
                {isApiErrorBody(item) ? (
                  <div className="state state-error" role="alert">
                    <p className="state-title">{labelOf(ERROR_CODE, item.error.code, lang)}</p>
                    <p className="small">{item.error.message}</p>
                  </div>
                ) : <ComparePane result={item} profile={p} />}
              </div>
            );
          })}
        </div>
      )}
      <p className="small muted">{tr({ en: 'The same verdict can hide different rules: read the checks, not only the headline.', fr: 'Un même verdict peut cacher des règles différentes : lisez les vérifications, pas seulement le titre.' })}</p>
      </div>
    </details>
  );
}

function ComparePane({ result, profile }: { result: CheckResult; profile: Profile | undefined }) {
  const { tr } = useApp();
  const name = profile?.name ?? '';
  const scope = useMemo<FactScope>(() => ({
    kind: 'local',
    label: { en: `Comparison for ${name}, computed by code.`, fr: `Comparaison pour ${name}, calculée par le code.` },
    facts: result.facts,
  }), [result, name]);
  return (
    <FactScopeProvider scope={scope}>
      <VerdictHeader verdict={result.verdict} counts={result.counts} />
      <BoundaryNote sizePct={result.maxCompatibleSizePct} counts={result.counts} baselineConflict={result.baselineConflict} />
      <RuleTable checks={result.ruleChecks} rules={profile?.rules} caption={tr({ en: 'Compared rule checks', fr: 'Vérifications comparées' })} />
    </FactScopeProvider>
  );
}

function DecisionRun({ run, stale }: { run: Run; stale: boolean }) {
  const { tr, lang } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }), [run]);
  const decision = run.result?.kind === 'decision' ? run.result.decision : null;
  const original = run.input.kind === 'decision' ? run.input.request : null;
  const selected = decision?.scenarios.find(s => s.scenarioId === decision.selectedScenarioId) ?? null;
  return (
    <FactScopeProvider scope={scope}>
      {stale && original && (
        <p className="stale-note" role="status">
          {tr({ en: `Written for ${describeRequest(original, 'en')} (${fmtDateTime(run.createdAt, 'en')}); rerun to update the explanation.`, fr: `Rédigé pour ${describeRequest(original, 'fr')} (${fmtDateTime(run.createdAt, 'fr')}) ; relancez pour mettre l’explication à jour.` })}
        </p>
      )}
      {!isTerminal(run.status) && run.status !== 'waiting_input' && (
        <p className="small"><RunStatusBadge status={run.status} /></p>
      )}
      {run.status === 'waiting_input' && run.question && <QuestionForm run={run} />}
      {decision && (
        <>
          <VerdictHeader verdict={decision.verdict} counts={decision.counts} />
          {decision.request.type === 'move' && (() => {
            const boundary = decision.scenarios.find(s => s.kind === 'max_compatible');
            return boundary
              ? <BoundaryNote sizePct={decision.maxCompatibleSizePct} counts={boundary.counts} countsAt="boundary" />
              : <BoundaryNote sizePct={decision.maxCompatibleSizePct} counts={decision.counts} />;
          })()}
          <h3 className="h4">{tr({ en: 'Hypothetical scenarios', fr: 'Scénarios hypothétiques' })}</h3>
          <ScenarioCards scenarios={decision.scenarios} selectedId={decision.selectedScenarioId} />
          {selected && (
            <>
              <h3 className="h4">{tr({ en: 'Before and after (selected scenario)', fr: 'Avant et après (scénario sélectionné)' })}</h3>
              <SnapshotCompare before={decision.portfolioBefore} after={selected.portfolioAfter} />
            </>
          )}
          <FundingOptions options={decision.fundingOptions} />
          <h3 className="h4">{tr({ en: 'Audited brief', fr: 'Note auditée' })}</h3>
          <BriefView brief={decision.brief} />
          <LimitationList codes={decision.limitations} />
          <p className="row-actions small">
            <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'See the evidence and audit', fr: 'Voir les preuves et l’audit' })}</Link>
          </p>
        </>
      )}
      <details className="fold" open={!decision}>
        <summary>{tr({ en: 'Steps', fr: 'Étapes' })}, {labelOf(RUN_STATUS, run.status, lang).toLowerCase()}</summary>
        <RunTimeline run={run} />
      </details>
      {!isTerminal(run.status) && <CancelButton runId={run.runId} />}
    </FactScopeProvider>
  );
}

export function QuestionForm({ run }: { run: Run }) {
  const { tr } = useApp();
  const question = run.question;
  const [value, setValue] = useState(question?.options?.[0]?.value ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [sent, setSent] = useState(false);
  if (!question) return null;
  const submit = async () => {
    setBusy(true); setError(null);
    try { await getApiClient().answer(run.runId, { questionId: question.questionId, value }); setSent(true); }
    catch (e) { setError(asApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <form className="state" onSubmit={e => { e.preventDefault(); void submit(); }}>
      <p className="state-title">{tr(question.text)}</p>
      {question.options ? (
        <fieldset>
          <legend className="sr-only">{tr(question.text)}</legend>
          <div className="checks">
            {question.options.map(o => (
              <label key={o.value}><input type="radio" name="answer" value={o.value} checked={value === o.value} onChange={() => setValue(o.value)} /> {tr(o.label)}</label>
            ))}
          </div>
        </fieldset>
      ) : (
        <div className="field">
          <label htmlFor="answer-text">{tr({ en: 'Your answer', fr: 'Votre réponse' })}</label>
          <input id="answer-text" type="text" value={value} onChange={e => setValue(e.target.value)} />
        </div>
      )}
      <button type="submit" className="btn btn-sm" disabled={busy || !value || sent}>{tr({ en: 'Send answer', fr: 'Envoyer la réponse' })}</button>
      {sent && <p className="small" role="status">{tr({ en: 'Answer sent; the analysis resumes.', fr: 'Réponse envoyée ; l’analyse reprend.' })}</p>}
      {error && <ErrorState error={error} />}
    </form>
  );
}

export function CancelButton({ runId }: { runId: string }) {
  const { tr } = useApp();
  const [error, setError] = useState<ApiRequestError | null>(null);
  return (
    <div className="row-actions">
      <button type="button" className="btn ghost btn-sm" onClick={() => { getApiClient().cancel(runId).catch(e => setError(asApiError(e))); }}>
        {tr({ en: 'Cancel analysis', fr: 'Annuler l’analyse' })}
      </button>
      {error && <span className="field-error">{error.message}</span>}
    </div>
  );
}
