'use client';
/**
 * Decision Desk (T14, web/page-specs/decision-desk.md). Free text → /requests/parse → user confirms a
 * structured form; deterministic /check previews (250 ms debounce, latest-response-wins); "Analyze
 * evidence" creates a decision run kept in ?runId=; compare uses /check/batch with identical inputs.
 */
import Link from 'next/link';
import { CompareDifferences } from './CompareDifferences';
import { AssetPanel } from './AssetPanel';
import { TargetAllocation } from './TargetAllocation';
import './decision.css';
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
import { ResearchOutcomeNote } from '../../components/run/ResearchOutcomeNote';
import {
  BoundaryNote, FundingOptions, ScenarioCards, SnapshotCompare, VerdictHeader, fundingLabel,
} from '../../components/run/Results';
import { ERROR_CODE, FUNDING_MODE, RUN_STATUS, labelOf } from '../../lib/labels';
import { fmtDateTime, fmtNumber, fmtPct, fmtPts } from '../../lib/format';
import {
  buildCheckRequest, createLatestGate, describeRequest, moveOf, previewRefusal, roundSize, sameDecisionRequest,
  unlistedMoveTicker, validateMoveForm, type MoveForm, type MoveFormIssue, type MoveUniverse, type PreviewRefusal,
} from '../../lib/move';
import { isTerminal, pastRunTarget, runElapsedMs } from '../../lib/runs';
import { RUN_LIMITS } from '../../lib/system';
import { describeFailure, bilingualReason, shouldOfferRetry } from '../../lib/failure';
import { INTERPRET_TIMEOUT_MS, startInterpret, type InterpretHandle } from '../../lib/interpret';
import { useNow } from '../../state/useNow';
import { SupportedUniverse } from '../../components/common/SupportedUniverse';
import { onDemandTickerHint } from '../../lib/universe';
import { tickerSuggestions } from '../../lib/suggest';
import { investigationOriginalText, readInvestigationContext, validInvestigationContext } from '../../lib/world';
import { deskContext, prefillTicker } from '../../lib/deskContext';

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
  const { tr, lang, windowSpec, windowCode, announce, profiles, selectProfile, feature } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get('runId');
  const urlEvent = params.get('eventId');
  const contextProfile = params.get('profileId');
  const contextMatches = !contextProfile || contextProfile === profile.profileId;
  const urlSourceRun = params.get('sourceRunId');
  const ticker = params.get('ticker') ?? '';
  // ?ticker= (World investigations, old Markets links) pre-fills the move form for this persona.
  const prefill = contextMatches ? prefillTicker(ticker) : '';
  // Text typed in the top bar ("Ask Aplomb") arrives as ?q= and is interpreted once.
  const askedText = params.get('q');

  const [form, setForm] = useState<MoveForm>(() => prefill ? { ...EMPTY_FORM, ticker: prefill } : EMPTY_FORM);
  const [originalText, setOriginalText] = useState<string | null>(null);
  const [goal, setGoal] = useState<DecisionRequest | null>(null);
  const touched = useRef(false);
  const update = useCallback((patch: Partial<MoveForm>) => {
    touched.current = true;
    setGoal(null);
    setForm(f => ({ ...f, ...patch }));
  }, []);
  // A later link to this page with another ?ticker= (the page stays mounted) switches the asset.
  const prefilled = useRef(prefill);
  useEffect(() => {
    if (!prefill || prefilled.current === prefill) return;
    prefilled.current = prefill;
    update({ ticker: prefill });
  }, [prefill, update]);

  // ----- run restored from the URL -----
  const polled = useRun(runId, finished => announce(`${tr({ en: 'Evidence analysis', fr: 'Analyse des preuves' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;
  const savedContext = run?.profileId === profile.profileId && run.input.kind === 'decision' ? readInvestigationContext(run.input.originalText) : null;
  const { context, shown: shownContext, foreign: foreignContext } = deskContext(
    validInvestigationContext(urlEvent, ticker, urlSourceRun), contextProfile, profile.profileId, savedContext);
  const contextEvent = shownContext?.eventId ?? null;
  const sourceRun = shownContext?.sourceRunId ?? null;
  const contextProfileName = foreignContext && contextProfile ? profiles.find(p => p.profileId === contextProfile)?.name ?? null : null;
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
  // The supported universe is checked only once its read completed; with on-demand fetching on, an
  // unlisted ticker is not blocked here (the instant check offers the fetch).
  const universe = useAssetUniverse();
  const onDemand = feature('on_demand_tickers');
  const moveUniverse = useMemo<MoveUniverse | null>(() => (universe.ready && universe.dataVersion
    ? { assets: universe.assets, total: universe.total, dataVersion: universe.dataVersion, onDemand }
    : null), [universe.ready, universe.assets, universe.total, universe.dataVersion, onDemand]);
  const issues = validateMoveForm(form, currentWeight, { positions: profile.portfolio.positions, universe: moveUniverse });
  const shownIssues = form.sizePct > 0 || form.ticker.trim() ? issues.filter(i => !(i.field === 'sizePct' && form.sizePct === 0)) : [];
  const blocking = shownIssues.length > 0;
  const [preview, setPreview] = useState<PreviewState>({ result: null, error: null, loading: false });
  // Bumped after an on-demand fetch is accepted, so the same move is checked again.
  const [previewNonce, setPreviewNonce] = useState(0);
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
  }, [checkKey, blocking, goal, gate, previewNonce]);

  const previewScope = useMemo<FactScope | null>(() => (preview.result
    ? { kind: 'local', label: { en: 'Instant rule check, computed by code. Not part of an analysis.', fr: 'Vérification instantanée, calculée par le code. Hors de toute analyse.' }, facts: preview.result.facts }
    : null), [preview.result]);

  // ----- run creation -----
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  const move = moveOf(form);
  const confirmedRequest: DecisionRequest | null = goal ?? (move ? { type: 'move', move } : null);
  // A refusal RECEIVED from the instant check (never one still loading): POST /runs runs the same
  // preparation, so the analysis would be refused for the same reason.
  const refusal = !goal && !preview.loading ? previewRefusal(preview.error) : null;
  const canAnalyze = Boolean(confirmedRequest) && (goal !== null || (issues.length === 0 && refusal === null)) && !creating;
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

      {feature('profile_creator') && <Card title={tr({ en: 'Your investment playbook', fr: 'Votre guide d’investissement' })}>
        {profile.investorContext?.playbook ? <>
          <p className="small"><strong>{tr({ en: 'Principle', fr: 'Principe' })}:</strong> {profile.investorContext.playbook.principle}</p>
          <p className="small"><strong>{tr({ en: 'Revisit when', fr: 'Réexaminer lorsque' })}:</strong> {profile.investorContext.playbook.revisitTrigger}</p>
          <Link href="/portfolio/?tab=rules#playbook">{tr({ en: 'Review your playbook and rules', fr: 'Examiner votre guide et vos règles' })}</Link>
        </> : <p className="small">{tr({ en: 'Explore your decisions and create a playbook in Investor Lab.', fr: 'Explorez vos décisions et créez un guide dans Investor Lab.' })}{' '}
          <Link href={`/investor-lab/?mode=quick&profileId=${encodeURIComponent(profile.profileId)}`}>{tr({ en: 'Test my profile', fr: 'Tester mon profil' })}</Link></p>}
      </Card>}

      {contextEvent && <Card title={tr({ en: 'Investigation context', fr: 'Contexte de recherche' })}>
        <p className="small">{tr({ en: 'Event relevance does not establish financial impact. Review its sources before testing a hypothetical move.', fr: 'La pertinence de l’événement ne prouve pas une incidence financière. Examinez ses sources avant de tester un mouvement hypothétique.' })}</p>
        {foreignContext && <p className="stale-note">{tr({ en: 'This event was selected for another investor. Switch to that investor to restore its holding context.', fr: 'Cet événement a été sélectionné pour un autre investisseur. Basculez vers cet investisseur pour retrouver le contexte de la position.' })}
          {contextProfile && contextProfileName && <>{' '}<button type="button" className="linklike" onClick={() => selectProfile(contextProfile)}>
            {tr({ en: 'Switch to', fr: 'Basculer vers' })} {contextProfileName}
          </button></>}</p>}
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
          <MoveFormCard profile={profile} form={form} update={update} maxSize={maxSize} currentWeight={currentWeight} issues={shownIssues} goal={goal}
            refusal={refusal} onDemandHint />
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
                {preview.error && !preview.loading && <PreviewError error={preview.error} ticker={form.ticker} onAccepted={() => setPreviewNonce(n => n + 1)} />}
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
              <button type="button" className="btn" disabled={!canAnalyze} onClick={() => void analyze()} data-tour="analyze"
                aria-describedby={refusal ? 'analyze-hint analyze-refused' : 'analyze-hint'}>
                {tr({ en: 'Analyze evidence', fr: 'Analyser les preuves' })}
              </button>
              <span id="analyze-hint" className="small muted">{tr({ en: 'An AI writes the explanation from the checked figures, then an auditor verifies every sentence.', fr: 'Une IA rédige l’explication à partir des chiffres vérifiés, puis un auditeur contrôle chaque phrase.' })}</span>
            </div>
            {refusal && (
              <p id="analyze-refused" className="field-error">{tr({ en: 'Fix the problem shown in the instant rule check first: the analysis would be refused for the same reason.', fr: 'Corrigez d’abord le problème signalé par la vérification instantanée : l’analyse serait refusée pour la même raison.' })}</p>
            )}
            {createError && <ErrorState error={createError} />}
          </Card>
        </div>
      </div>

      {preview.result && previewScope && !goal && !preview.loading && run?.status !== 'succeeded' && (
        <FactScopeProvider scope={previewScope}>
          <Card title={tr({ en: 'Instant check details', fr: 'Détails de la vérification instantanée' })}>
            <SnapshotCompare before={preview.result.portfolioBefore} after={move ? preview.result.portfolioAfter : null} />
            <h3 className="h4">{tr({ en: 'Rule checks', fr: 'Vérifications des règles' })}</h3>
            <RuleTable checks={preview.result.ruleChecks} rules={profile.rules} caption={tr({ en: 'Preview rule checks', fr: 'Vérifications en aperçu' })} />
            <FundingOptions options={preview.result.fundingOptions} />
          </Card>
        </FactScopeProvider>
      )}

      <AssetPanel ticker={goal ? '' : form.ticker} profile={profile} />

      <ComparePanel profile={profile} form={form} />

      <TargetAllocation key={`${profile.profileId}|${profile.version}`} profile={profile} />

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
          {feature('profile_creator') && run?.status === 'succeeded' && !otherProfileId && profile.investorContext?.playbook && <p className="small">
            {tr({ en: 'Has this evidence changed what would make you revisit your plan?', fr: 'Ces preuves ont-elles changé ce qui vous amènerait à réexaminer votre plan ?' })}{' '}
            <Link href="/portfolio/?tab=rules#playbook">{tr({ en: 'Review or edit your playbook', fr: 'Examiner ou modifier votre guide' })}</Link>
          </p>}
        </Card>
      )}
    </>
  );
}

function PreviewError({ error, ticker, onAccepted }: { error: ApiRequestError; ticker: string; onAccepted: () => void }) {
  const { tr, lang, feature } = useApp();
  const [fetching, setFetching] = useState(false);
  const [result, setResult] = useState<FetchAssetResponse | null>(null);
  const [fetchError, setFetchError] = useState<ApiRequestError | null>(null);
  const symbol = ticker.trim().toUpperCase();
  const canFetch = error.code === 'not_found' && feature('on_demand_tickers') && symbol !== '';
  // The server's bilingual reason (e.g. a funding refusal) replaces its English-only message.
  const reason = bilingualReason(error.details?.reason);
  const fetchTicker = async () => {
    setFetching(true); setFetchError(null);
    try {
      const fetched = await getApiClient().fetchAsset(symbol);
      setResult(fetched);
      if (fetched.accepted) {
        // The new asset joins the suggestions everywhere, and the same move is checked again.
        assetsChanged();
        onAccepted();
      }
    }
    catch (e) { setFetchError(asApiError(e)); }
    finally { setFetching(false); }
  };
  const extra = (
    <>
      {canFetch && !result && (
        <button type="button" className="btn ghost btn-sm" disabled={fetching} onClick={() => void fetchTicker()}>
          {tr({ en: `Fetch ${symbol} on demand`, fr: `Récupérer ${symbol} à la demande` })}
        </button>
      )}
      {fetching && <Loading label={tr({ en: 'Fetching (may take up to 20 s)…', fr: 'Récupération (jusqu’à 20 s)…' })} />}
      {result && (result.accepted
        ? <p className="small">{tr({ en: 'Accepted as an on-demand asset. The move is checked again.', fr: 'Accepté comme actif à la demande. Le mouvement est vérifié de nouveau.' })}</p>
        : <p className="small">{tr({ en: 'Rejected', fr: 'Rejeté' })}: {result.rejectedReason ? tr(result.rejectedReason) : '—'}</p>)}
      {fetchError && <p className="field-error">{fetchError.message}</p>}
    </>
  );
  if (!reason) return <ErrorState error={error}>{extra}</ErrorState>;
  return (
    <div className="state state-error" role="alert">
      <p className="state-title">{labelOf(ERROR_CODE, error.code, lang)}</p>
      <p className="small">{tr(reason)}</p>
      {error.requestId && (
        <details className="tech-details">
          <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
          <p className="mono break">{tr({ en: 'Request', fr: 'Requête' })} {error.requestId}</p>
        </details>
      )}
      {extra}
    </div>
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
  const [startedAt, setStartedAt] = useState(0);
  const [ended, setEnded] = useState<'cancelled' | 'timeout' | null>(null);
  // Failed attempts of the same text (first try included); a bare Retry stops at MAX_FAILED_ATTEMPTS.
  const [failed, setFailed] = useState<{ text: string; count: number; retryAt: number }>({ text: '', count: 0, retryAt: 0 });
  const [lastText, setLastText] = useState('');
  const handleRef = useRef<InterpretHandle<ParsedRequest> | null>(null);
  const trimmed = text.trim();
  const valid = trimmed.length >= 1 && trimmed.length <= 600;
  const interpret = useCallback(async (value: string) => {
    // One interpretation at a time: a new one abandons the previous one.
    handleRef.current?.cancel();
    const handle = startInterpret(signal => getApiClient().parse({ profileId: profile.profileId, text: value, lang }, signal));
    handleRef.current = handle;
    setBusy(true); setStartedAt(Date.now()); setEnded(null); setError(null); setParsed(null); setLastText(value);
    const outcome = await handle.promise;
    // Superseded by a newer interpretation, or the page was left.
    if (handleRef.current !== handle) return;
    handleRef.current = null;
    setBusy(false);
    const countFailure = (retryAfterMs: number | null) => setFailed(f => ({
      text: value, count: f.text === value ? f.count + 1 : 1, retryAt: retryAfterMs ? Date.now() + retryAfterMs : 0,
    }));
    if (outcome.status === 'ok') { setParsed(outcome.value); setFailed({ text: '', count: 0, retryAt: 0 }); }
    else if (outcome.status === 'cancelled') setEnded('cancelled');
    else if (outcome.status === 'timeout') { setEnded('timeout'); countFailure(null); }
    else { setError(outcome.error); countFailure(outcome.error.retryAfterMs); }
  }, [profile.profileId, lang]);
  const cancel = () => handleRef.current?.cancel();
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
  // Leaving the page abandons the request (React's development double mount asks again).
  useEffect(() => () => {
    const handle = handleRef.current;
    handleRef.current = null;
    if (handle) { handle.cancel(); asked.current = null; }
  }, []);
  const now = useNow(busy || failed.retryAt > Date.now());
  const elapsedS = busy ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0;
  const failures = failed.text === lastText ? failed.count : 0;
  const waitS = failed.retryAt > now ? Math.ceil((failed.retryAt - now) / 1000) : 0;
  const failure = error ? describeFailure(error, { failures }) : null;
  // Retry repeats the same text; once the text is edited, Interpret is the action.
  const canRetry = !busy && lastText !== '' && trimmed === lastText && shouldOfferRetry(failures)
    && (ended === 'timeout' || failure?.kind === 'retryable');
  const retryButton = canRetry && (
    <button type="button" className="btn ghost" disabled={waitS > 0} onClick={() => void interpret(lastText)}>
      {waitS > 0 ? tr({ en: `Retry in ${waitS} s`, fr: `Réessayer dans ${waitS} s` }) : tr({ en: 'Retry', fr: 'Réessayer' })}
    </button>
  );
  const timeoutS = Math.round(INTERPRET_TIMEOUT_MS / 1000);
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
      {busy && (
        <div className="state">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="spinner" aria-hidden="true" />
            {/* Announced once; the ticking seconds stay out of the live region. */}
            <span role="status">{tr({ en: 'Interpreting…', fr: 'Interprétation…' })}</span>
            <span className="muted">{fmtNumber(elapsedS, lang, 0)} s</span>
          </div>
          <p className="small muted">{tr({ en: 'The AI is reading your text and this profile. Nothing runs until you confirm.', fr: 'L’IA lit votre texte et ce profil. Rien ne s’exécute avant votre confirmation.' })}</p>
          <div className="row-actions">
            <button type="button" className="btn ghost btn-sm" onClick={cancel}>{tr({ en: 'Cancel interpretation', fr: 'Annuler l’interprétation' })}</button>
          </div>
        </div>
      )}
      {ended === 'cancelled' && (
        <p className="small muted" role="status">{tr({ en: 'Interpretation cancelled. The form below still works without AI.', fr: 'Interprétation annulée. Le formulaire ci-dessous fonctionne toujours sans IA.' })}</p>
      )}
      {ended === 'timeout' && (
        <div className="state state-error" role="alert">
          <p className="state-title">{tr({ en: `No interpretation after ${timeoutS} seconds, so this page stopped waiting.`, fr: `Aucune interprétation après ${timeoutS} secondes : cette page a cessé d’attendre.` })}</p>
          {!shouldOfferRetry(failures) && (
            <p className="small">{tr({ en: 'Still no answer after several tries. Try again later.', fr: 'Toujours pas de réponse après plusieurs essais. Réessayez plus tard.' })}</p>
          )}
          <p className="small">{tr({ en: 'Fill in the form below instead: it works without AI.', fr: 'Remplissez plutôt le formulaire ci-dessous : il fonctionne sans IA.' })}</p>
          {retryButton}
        </div>
      )}
      {error && failure && (
        <ErrorState error={error} {...(error.code === 'upstream_unavailable'
          ? { title: tr({ en: 'AI interpretation is not available on this server right now.', fr: 'L’interprétation par l’IA n’est pas disponible sur ce serveur pour l’instant.' }) } : {})}>
          <p className="small">{tr(failure.message)}</p>
          <p className="small">{tr({ en: 'Fill in the form below instead: it works without AI.', fr: 'Remplissez plutôt le formulaire ci-dessous : il fonctionne sans IA.' })}</p>
          {retryButton}
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
export function MoveFormCard({ profile, form, update, maxSize, currentWeight, issues, goal, refusal = null, onDemandHint = false }: {
  profile: Profile; form: MoveForm; update: (patch: Partial<MoveForm>) => void; maxSize: number; currentWeight: number;
  issues: MoveFormIssue[]; goal: DecisionRequest | null;
  /** A refusal received from the instant check (Decision Desk), shown next to the field it names. */
  refusal?: PreviewRefusal | null | undefined;
  /** The page's instant check offers on-demand fetching (Decision Desk), so an unlisted ticker gets a hint. */
  onDemandHint?: boolean | undefined;
}) {
  const { tr, lang, feature } = useApp();
  // One read of the universe, searched locally on each keystroke; holdings first, offered even if the read fails.
  const universe = useAssetUniverse();
  const { assets } = universe;
  const positions = profile.portfolio.positions;
  const suggestions = useMemo(() => tickerSuggestions(assets, positions.map(p => p.ticker), tr({ en: 'Held', fr: 'Détenu' })),
    [assets, positions, tr]);
  const refusedField = refusal?.field ?? null;
  const issueFor = (field: keyof MoveForm) => issues.some(i => i.field === field) || refusedField === field;
  // With on-demand fetching on, an unlisted ticker is a hint, not an error.
  const unlisted = onDemandHint && universe.ready && universe.dataVersion && feature('on_demand_tickers')
    ? unlistedMoveTicker(form, { positions, universe: { assets, total: universe.total, dataVersion: universe.dataVersion, onDemand: true } })
    : null;
  /** Messages under one field: its form issues, then the instant check's refusal when it names that field. */
  const notesFor = (field: keyof MoveForm): string[] => {
    const notes = issues.filter(i => i.field === field).map(i => tr(i.message));
    if (refusedField === field) {
      notes.push(refusal?.reason
        ? tr(refusal.reason)
        : tr({ en: 'The instant rule check refused this value: see its message.', fr: 'La vérification instantanée a refusé cette valeur : voyez son message.' }));
    }
    return notes;
  };
  const tickerNotes = notesFor('ticker');
  const fundingNotes = notesFor('fundingMode');
  const donorNotes = notesFor('fromTickers');
  const sizeNotes = notesFor('sizePct');
  const describedBy = (...ids: (string | false | null | undefined)[]) => ids.filter(Boolean).join(' ') || undefined;
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
            aria-invalid={issueFor('ticker')}
            aria-describedby={describedBy(tickerNotes.length > 0 && 'move-ticker-error', unlisted && !tickerNotes.length && 'move-ticker-ondemand', 'move-ticker-weight', 'move-ticker-universe')} />
          {tickerNotes.length > 0 && <span id="move-ticker-error" className="field-error">{tickerNotes.join(' ')}</span>}
          {unlisted && !tickerNotes.length && universe.dataVersion && (
            <span id="move-ticker-ondemand" className="hint">{tr(onDemandTickerHint(unlisted, universe.dataVersion))}</span>
          )}
          <span id="move-ticker-weight" className="hint">{tr({ en: 'Current weight', fr: 'Poids actuel' })}: {fmtPct(currentWeight, lang)}</span>
          <SupportedUniverse id="move-ticker-universe" />
        </div>
        <div className="field">
          <label htmlFor="move-funding">{tr({ en: 'Funding', fr: 'Financement' })}</label>
          <select id="move-funding" value={form.fundingMode} onChange={e => update({ fundingMode: e.target.value as FundingMode })}
            aria-invalid={issueFor('fundingMode')}
            aria-describedby={describedBy(fundingNotes.length > 0 && 'move-funding-error', 'move-funding-hint')}>
            {FUNDING_MODES.map(mode => <option key={mode} value={mode}>{labelOf(FUNDING_MODE, mode, lang)}</option>)}
          </select>
          {fundingNotes.length > 0 && <span id="move-funding-error" className="field-error">{fundingNotes.join(' ')}</span>}
          <span id="move-funding-hint" className="hint">{form.fundingMode === 'new_money'
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
            onChange={e => update({ sizePct: Number(e.target.value) || 0 })} aria-invalid={issueFor('sizePct')}
            aria-describedby={describedBy(sizeNotes.length > 0 && 'move-size-error', 'move-size-hint')} />
        </div>
        {sizeNotes.length > 0 && <span id="move-size-error" className="field-error">{sizeNotes.join(' ')}</span>}
        <span id="move-size-hint" className="hint">{tr({ en: 'Added amount, not a target weight. 0 shows the current portfolio.', fr: 'Montant ajouté, pas un poids cible. 0 montre le portefeuille actuel.' })}</span>
      </div>
      {form.fundingMode === 'from_holdings' && (
        <fieldset style={{ marginTop: 16 }} aria-describedby={donorNotes.length > 0 ? 'move-donors-error' : undefined}>
          <legend>{tr({ en: 'Holdings that fund the move', fr: 'Positions qui financent le mouvement' })}</legend>
          {donorNotes.length > 0 && <p id="move-donors-error" className="field-error">{donorNotes.join(' ')}</p>}
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
    <Card id="compare" section={tr({ en: 'Compare', fr: 'Comparer' })} tour="compare" title={tr({ en: 'Compare with another investor', fr: 'Comparer avec un autre investisseur' })}
      info={tr({ en: 'The same verdict can hide different rules: read the checks, not only the headline.', fr: 'Un même verdict peut cacher des règles différentes : lisez les vérifications, pas seulement le titre.' })}>
      <p className="small muted">{tr({ en: 'See how another investor’s plan answers the same move.', fr: 'Voyez comment le plan d’un autre investisseur répond au même mouvement.' })}</p>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="compare-with">{tr({ en: 'Other investor', fr: 'Autre investisseur' })}</label>
          <select id="compare-with" value={effectiveOther} onChange={e => setOtherId(e.target.value)}>
            {others.map(p => <option key={p.profileId} value={p.profileId}>{p.name}</option>)}
          </select>
        </div>
      </div>
      <p className="small muted">{move
        ? tr({ en: `Same request for both: ${describeRequest({ type: 'move', move }, 'en')}, ${fundingLabel(move.funding, 'en')}, same period.`, fr: `Même requête pour les deux : ${describeRequest({ type: 'move', move }, 'fr')}, ${fundingLabel(move.funding, 'fr')}, même période.` })
        : tr({ en: 'No move set: compares both current portfolios.', fr: 'Aucun mouvement : compare les deux portefeuilles actuels.' })}</p>
      <div className="row-actions"><button type="button" className="btn ghost" onClick={() => void compare()} disabled={state.loading}>{tr({ en: 'Compare the answers', fr: 'Comparer les réponses' })}</button></div>
      {state.loading && <Loading />}
      {state.error && <ErrorState error={state.error} />}
      {state.data && (
        <CompareDifferences data={state.data} names={[0, 1].map(i => {
          const id = state.ids[i] ?? '';
          return profiles.find(x => x.profileId === id)?.name ?? id;
        }) as [string, string]} />
      )}
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
    </Card>
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
  const active = !isTerminal(run.status) && run.status !== 'waiting_input';
  const now = useNow(active);
  const elapsed = active ? runElapsedMs(run, now) : null;
  // Contract defaults (run-events.md §4); the target is not enforced, the limit is the server's hard budget.
  const target = `${fmtNumber(RUN_LIMITS.wallClockTargetMs / 1000, lang, 0)} s`;
  const limit = `${fmtNumber(RUN_LIMITS.wallClockHardMs / 1000, lang, 0)} s`;
  return (
    <FactScopeProvider scope={scope}>
      {stale && original && (
        <p className="stale-note" role="status">
          {tr({ en: `Written for ${describeRequest(original, 'en')} (${fmtDateTime(run.createdAt, 'en')}); analyze again to update the explanation.`, fr: `Rédigé pour ${describeRequest(original, 'fr')} (${fmtDateTime(run.createdAt, 'fr')}) ; analysez de nouveau pour mettre l’explication à jour.` })}
        </p>
      )}
      {active && (
        <p className="small">
          <RunStatusBadge status={run.status} />
          {elapsed !== null && <span className="muted">{' '}{tr({
            en: `${fmtNumber(Math.floor(elapsed / 1000), lang, 0)} s elapsed · target ${target}, server limit ${limit}`,
            fr: `${fmtNumber(Math.floor(elapsed / 1000), lang, 0)} s écoulées · objectif ${target}, limite du serveur ${limit}`,
          })}</span>}
        </p>
      )}
      {active && pastRunTarget(run, now, RUN_LIMITS.wallClockTargetMs) && (
        <p className="stale-note" role="status">{tr({
          en: `This analysis is taking longer than the ${target} target. The server stops it after ${limit} at most; you can also cancel it.`,
          fr: `Cette analyse dépasse l’objectif de ${target}. Le serveur l’arrête au plus tard après ${limit} ; vous pouvez aussi l’annuler.`,
        })}</p>
      )}
      {run.status === 'waiting_input' && run.question && <QuestionForm run={run} />}
      {decision && (
        <>
          <VerdictHeader verdict={decision.verdict} counts={decision.counts} />
          <ResearchOutcomeNote run={run} />
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
