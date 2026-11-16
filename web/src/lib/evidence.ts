/**
 * Readings of a run's evidence and research outcome for the Evidence page and the decision answer.
 * Everything is derived from the run payload (GET /v1/runs/{id}); nothing here needs /trace.
 *
 * - A08 ("quoted passages found in the cached source document") is evaluated by the auditor only on
 *   cited `{{evidence:…}}` segments and on quotations in the prose (backend ledger/audit.py
 *   parse_draft). A prose quotation without a cited evidence segment always fails A08, so a passing
 *   A08 on a brief that cites no evidence means nothing was compared: shown as "No external quotes to
 *   verify", not "Passed" (QA T3).
 * - Research counts mirror the research step summary (backend agents/workflow.py _research_summary):
 *   kept = distinct evidence IDs, failed = tool calls with ok=false. No date-gate count exists for
 *   research sources, so none is shown.
 */
import type { AuditCheckResult, Brief, I18NText, Run, ToolCall } from '../contracts/types';

// ----- A08 with nothing to evaluate -----

/** Distinct evidence IDs cited by the brief, struck sentences included (the auditor evaluated them). */
export function evidenceCitations(brief: Pick<Brief, 'sections'>): string[] {
  const ids = new Set<string>();
  for (const section of brief.sections) {
    for (const sentence of section.sentences) {
      for (const segment of sentence.segments) if (segment.t === 'evidence') ids.add(segment.evidenceId);
    }
  }
  return [...ids];
}

/** True for a passing A08 on a brief that cites no evidence: the check had nothing to compare. */
export function quoteCheckHadNothingToVerify(check: Pick<AuditCheckResult, 'code' | 'ok'>, brief: Pick<Brief, 'sections'>): boolean {
  return check.code === 'A08' && check.ok && evidenceCitations(brief).length === 0;
}

export const NO_QUOTES_TO_VERIFY: I18NText = { en: 'No external quotes to verify', fr: 'Aucune citation externe à vérifier' };
export const NO_QUOTES_DETAIL: I18NText = {
  en: 'This brief cites no source document, so there was nothing to compare.',
  fr: 'Cette note ne cite aucun document source : il n’y avait rien à comparer.',
};

// ----- Research outcome -----

/** Read-only lookups the researcher may also call; they are not external sources. */
const LOOKUP_TOOLS = new Set(['universe.search', 'universe.get', 'profile.get', 'data.describe', 'macro.series']);

export interface ResearchOutcome {
  /** Tool calls of the research step(s), lookups included, as in the step summary. */
  calls: number;
  /** Calls with ok=false. */
  failed: number;
  /** Distinct evidence IDs the research step(s) saved. */
  saved: number;
}

function researchCalls(run: Pick<Run, 'steps'>): ToolCall[] | null {
  const steps = run.steps.filter(step => step.type === 'research');
  return steps.length ? steps.flatMap(step => step.toolCalls) : null;
}

/** Null when the run has no research step (research was not run). */
export function researchOutcome(run: Pick<Run, 'steps'>): ResearchOutcome | null {
  const steps = run.steps.filter(step => step.type === 'research');
  if (!steps.length) return null;
  const saved = new Set<string>();
  for (const step of steps) {
    for (const id of step.evidenceIds) saved.add(id);
    for (const call of step.toolCalls) for (const id of call.evidenceIds) saved.add(id);
  }
  const calls = steps.flatMap(step => step.toolCalls);
  return { calls: calls.length, failed: calls.filter(call => !call.ok).length, saved: saved.size };
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);
/** French: 0 and 1 take the singular. */
const pluralFr = (n: number, one: string, many: string) => (n > 1 ? many : one);

/** The counts line next to the audit verdict; `cited` = evidenceCitations(brief).length. */
export function researchCountsLine(outcome: ResearchOutcome | null, cited: number, replay: boolean): I18NText {
  if (!outcome) {
    return replay
      ? { en: 'Research is not run in historical replays, so no external sources.', fr: 'La recherche n’est pas effectuée dans les rejeux historiques, donc aucune source externe.' }
      : { en: 'Research: not run for this analysis, so no external sources.', fr: 'Recherche : non effectuée pour cette analyse, donc aucune source externe.' };
  }
  const { saved: k, failed: f } = outcome;
  return {
    en: `Research: ${k} ${plural(k, 'source', 'sources')} kept, ${f} tool ${plural(f, 'call', 'calls')} failed, ${cited} cited in this brief.`,
    fr: `Recherche : ${k} ${pluralFr(k, 'source retenue', 'sources retenues')}, ${f} ${pluralFr(f, 'appel d’outil en échec', 'appels d’outil en échec')}, ${cited} ${pluralFr(cited, 'citée', 'citées')} dans cette note.`,
  };
}

/**
 * The ticker of a move request, or null (goal requests and non-decision runs). The decision result's
 * request comes first: an answered clarifying question can replace the submitted one.
 */
function requestTicker(run: Pick<Run, 'input' | 'result'>): string | null {
  const request = run.result?.kind === 'decision' ? run.result.decision.request
    : run.input.kind === 'decision' ? run.input.request : null;
  return request?.type === 'move' ? request.move.ticker : null;
}

/**
 * The plain note shown at the top of an answer whose research step ran and kept nothing; null when
 * research was not run or saved at least one source.
 */
export function researchNothingNote(run: Pick<Run, 'steps' | 'input' | 'result'>): { title: I18NText; body: I18NText } | null {
  const outcome = researchOutcome(run);
  if (!outcome || outcome.saved > 0) return null;
  const ticker = requestTicker(run);
  return {
    title: ticker
      ? { en: `No external information was available for ${ticker}.`, fr: `Aucune information externe n’était disponible pour ${ticker}.` }
      : { en: 'No external information was available for this request.', fr: 'Aucune information externe n’était disponible pour cette demande.' },
    body: {
      en: 'The research step saved no source, so this analysis rests only on the snapshot data and your plan rules.',
      fr: 'L’étape de recherche n’a retenu aucune source : cette analyse ne repose que sur les données de l’instantané et les règles de votre plan.',
    },
  };
}

export const SOURCES_TRIED_ID = 'sources-tried';

/**
 * The element id a `#sentence-…` fragment points at (BriefView's removed-sentence link), or null for
 * any other fragment. The brief renders after the run loads, so the page scrolls to it then.
 */
export function sentenceHashTarget(hash: string): string | null {
  if (!hash.startsWith('#sentence-')) return null;
  try {
    return decodeURIComponent(hash.slice(1));
  } catch {
    return null;
  }
}

// ----- Sources tried -----

export type AttemptOutcome = 'saved' | 'nothing' | 'failed';

export interface ResearchAttempt {
  id: string;
  tool: string;
  /** Host for URL arguments (never the full URL), otherwise the ticker, company, filing or query asked for. */
  target: string | null;
  outcome: AttemptOutcome;
  /** Plain reason for a failed call or for a known "nothing saved" summary; null otherwise. */
  reason: I18NText | null;
  /** Raw error or result summary, for a Technical details disclosure. */
  technical: string | null;
}

const MAX_TARGET = 80;

function hostOf(value: string): string | null {
  try { return new URL(value).host || null; } catch { return null; }
}

/** What the call asked for, from its arguments. URLs are reduced to their host. */
export function attemptTarget(args: Record<string, unknown>): string | null {
  for (const key of ['url', 'start_url']) {
    const value = args[key];
    if (typeof value === 'string' && value.trim()) return hostOf(value.trim());
  }
  for (const key of ['ticker', 'name_or_ticker', 'cik', 'accession', 'query', 'q']) {
    const value = args[key];
    if (typeof value === 'string' && value.trim()) {
      const text = value.trim().replace(/\s+/g, ' ');
      return text.length > MAX_TARGET ? `${text.slice(0, MAX_TARGET)}…` : text;
    }
  }
  return null;
}

/** External-source calls of the research step(s), in call order; lookups are left out. */
export function researchAttempts(run: Pick<Run, 'steps'>): ResearchAttempt[] {
  const calls = researchCalls(run) ?? [];
  return calls.filter(call => !LOOKUP_TOOLS.has(call.tool)).map(call => {
    const outcome: AttemptOutcome = !call.ok ? 'failed' : call.evidenceIds.length ? 'saved' : 'nothing';
    const technical = (outcome === 'failed' ? call.error : call.resultSummary) || null;
    return {
      id: call.id,
      tool: call.tool,
      target: attemptTarget(call.args),
      outcome,
      reason: outcome === 'failed'
        ? toolFailureReason(call.error ?? '')
        : outcome === 'nothing' ? (knownReason(call.resultSummary) ?? NOTHING_SAVED_REASON) : null,
      technical,
    };
  });
}

/** Open the list by default when every attempt failed. */
export function allAttemptsFailed(attempts: readonly ResearchAttempt[]): boolean {
  return attempts.length > 0 && attempts.every(a => a.outcome === 'failed');
}

export const ATTEMPT_OUTCOME: Record<AttemptOutcome, I18NText> = {
  saved: { en: 'Quote saved', fr: 'Citation retenue' },
  nothing: { en: 'Nothing saved', fr: 'Rien de retenu' },
  failed: { en: 'Failed', fr: 'En échec' },
};

const NOTHING_SAVED_REASON: I18NText = {
  en: 'The tool answered, but no quote from this call was saved.',
  fr: 'L’outil a répondu, mais aucune citation de cet appel n’a été retenue.',
};

const TOOL_LABEL: Record<string, I18NText> = {
  'web.fetch': { en: 'Web page', fr: 'Page web' },
  'web.browse': { en: 'Web browsing', fr: 'Navigation web' },
  'edgar.find_company': { en: 'SEC company search', fr: 'Recherche d’entreprise SEC' },
  'edgar.list_filings': { en: 'SEC filing list', fr: 'Liste des dépôts SEC' },
  'edgar.filing_text': { en: 'SEC filing text', fr: 'Texte d’un dépôt SEC' },
  'edgar.company_facts': { en: 'SEC reported figures', fr: 'Chiffres déclarés à la SEC' },
  'gdelt.search': { en: 'GDELT news search', fr: 'Recherche de nouvelles GDELT' },
  'attention.pageviews': { en: 'Wikipedia page views', fr: 'Consultations Wikipédia' },
  'etf.holdings': { en: 'ETF holdings', fr: 'Positions de FNB' },
  'emissions.facilities': { en: 'Reported facility emissions', fr: 'Émissions déclarées des installations' },
  'world.search_events': { en: 'World events', fr: 'Événements mondiaux' },
  'research.save_evidence': { en: 'Saving a quote', fr: 'Enregistrement d’une citation' },
};

/** Plain name of a research tool; an unknown tool keeps its identifier. */
export function researchToolLabel(tool: string): I18NText {
  return TOOL_LABEL[tool] ?? { en: tool, fr: tool };
}

const r = (en: string, fr: string): I18NText => ({ en, fr });

/** Exact error codes and messages recorded by the research tools and the tool registry. */
const REASONS: Record<string, I18NText> = {
  domain_not_allowlisted: r('This site is not on the list of reviewed official sources.', 'Ce site ne figure pas sur la liste des sources officielles vérifiées.'),
  left_allowlisted_domains: r('The page led away from the reviewed official sites.', 'La page menait hors des sites officiels vérifiés.'),
  start_url_required: r('No start page was given, so the browser could not open anything.', 'Aucune page de départ n’a été fournie : le navigateur n’a rien pu ouvrir.'),
  no_page_captured: r('The browser could not read any page.', 'Le navigateur n’a pu lire aucune page.'),
  browser_unavailable: r('The web browser is not available in this deployment.', 'Le navigateur web n’est pas disponible dans ce déploiement.'),
  browser_access_denied: r('The web browser is not available in this deployment.', 'Le navigateur web n’est pas disponible dans ce déploiement.'),
  browser_stream_unavailable: r('The web browser is not available in this deployment.', 'Le navigateur web n’est pas disponible dans ce déploiement.'),
  issuer_file_not_configured: r('No holdings file is configured for this fund.', 'Aucun fichier de positions n’est configuré pour ce fonds.'),
  invalid_search_window: r('The requested dates were after the data date or covered more than 90 days.', 'Les dates demandées dépassaient la date des données ou couvraient plus de 90 jours.'),
  source_unavailable: r('The source did not answer or refused the request.', 'La source n’a pas répondu ou a refusé la demande.'),
  source_unavailable_or_invalid: r('The source did not answer or sent an unusable reply.', 'La source n’a pas répondu ou a envoyé une réponse inutilisable.'),
  dns_unavailable: r('The source’s address could not be resolved.', 'L’adresse de la source n’a pas pu être résolue.'),
  dns_timeout: r('The source’s address could not be resolved.', 'L’adresse de la source n’a pas pu être résolue.'),
  rate_limited: r('The source asked for fewer requests.', 'La source a demandé moins de requêtes.'),
  request_timeout: r('The source took too long to answer.', 'La source a mis trop de temps à répondre.'),
  response_too_large: r('The source’s reply was too large to read.', 'La réponse de la source était trop volumineuse pour être lue.'),
  unsupported_content_type: r('The source sent a kind of document that cannot be read.', 'La source a envoyé un type de document illisible.'),
  redirect_or_retry_limit: r('The source redirected too many times.', 'La source a redirigé trop de fois.'),
  unsafe_url: r('The address was refused as unsafe.', 'L’adresse a été refusée comme non sûre.'),
  accession_requires_same_run_list_filings: r('The filing was not listed earlier in this analysis.', 'Le dépôt n’avait pas été listé plus tôt dans cette analyse.'),
  document_not_fetched_in_run: r('The quote came from a page not read in this analysis.', 'La citation provenait d’une page non lue dans cette analyse.'),
  quote_not_verified: r('The quoted text was not found on the page.', 'Le texte cité est introuvable sur la page.'),
  research_unavailable_in_replay: r('Research is not run in historical replays.', 'La recherche n’est pas effectuée dans les rejeux historiques.'),
  'Research is disabled in historical runs': r('Research is not run in historical replays.', 'La recherche n’est pas effectuée dans les rejeux historiques.'),
  'Tool is unavailable for this role': r('This tool is not available in this deployment.', 'Cet outil n’est pas disponible dans ce déploiement.'),
  'Unknown tool argument': r('The request to the tool was malformed.', 'La demande adressée à l’outil était mal formée.'),
  'The requested tool was unavailable or rejected its input.': r('The tool was unavailable or rejected the request.', 'L’outil était indisponible ou a refusé la demande.'),
  'Run wall-clock budget exhausted': r('The analysis ran out of time for research.', 'L’analyse n’avait plus de temps pour la recherche.'),
  unverified_article_mapping: r('No reviewed Wikipedia article is linked to this ticker.', 'Aucun article Wikipédia vérifié n’est associé à ce symbole.'),
};

const MALFORMED = r('The request to the tool was malformed.', 'La demande adressée à l’outil était mal formée.');
const OTHER_REASON = r('Other reason (see technical details).', 'Autre raison (voir les détails techniques).');

function knownReason(code: string): I18NText | null {
  return REASONS[code.trim()] ?? null;
}

/** Plain reason for a failed research call; unknown codes say so and keep the raw code for Technical details. */
export function toolFailureReason(code: string): I18NText {
  const text = code.trim();
  const known = knownReason(text);
  if (known) return known;
  if (text.startsWith('validation_error') || text.startsWith('Invalid tool arguments')) return MALFORMED;
  const status = /^http_(\d{3})$/.exec(text);
  if (status) return r(`The source answered with HTTP status ${status[1]}.`, `La source a répondu avec le statut HTTP ${status[1]}.`);
  if (/ budget exhausted$/.test(text)) return r('The analysis used up its research budget.', 'L’analyse a épuisé son budget de recherche.');
  return OTHER_REASON;
}

// ----- Run list scope (Evidence page) -----

export type RunListScope = 'profile' | 'all';

/** The profile filter sent to GET /v1/runs: the active profile, or none for "All profiles". */
export function runListProfileId(scope: RunListScope, activeProfileId: string | null | undefined): string | undefined {
  return scope === 'profile' && activeProfileId ? activeProfileId : undefined;
}

/** Query key; it starts with `runs|` so a page can invalidate every run list at once. */
export function runListKey(sessionId: string, profileId: string | undefined): string {
  return `runs|${sessionId}|${profileId ?? 'all'}`;
}
