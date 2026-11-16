/**
 * Pure Agents & System logic (T15, web/page-specs/agents-system.md): the static role map
 * (contracts/tools.md §6, run-events.md §2), the step → role/actor contract used to check that a
 * run's recorded actors match it (SYS-01), argument redaction and the guardrail/budget readings.
 * Nothing here infers a step: every figure shown comes from the run payload.
 */
import type { AgentRole, GuardrailAudit, I18NText, Run, RunStatus, RunSummary, Step, StepType } from '../contracts/types';
import { briefsOf } from './brief';
import { isTerminal } from './runs';

export type Actor = Step['actor'];
export type WorkNature = 'model' | 'code' | 'mixed';

export function workNature(actor: Actor): WorkNature {
  if (actor === 'code') return 'code';
  if (actor === 'code+llm') return 'mixed';
  return 'model';
}

/** run-events.md §2: which role performs each step type and with what kind of actor. */
export const STEP_CONTRACT: Record<StepType, { agent: AgentRole; actor: Actor }> = {
  plan: { agent: 'planner', actor: 'llm' },
  research: { agent: 'researcher', actor: 'llm+tools' },
  quant: { agent: 'quant', actor: 'code' },
  risk_check: { agent: 'risk_officer', actor: 'code' },
  revise: { agent: 'planner', actor: 'llm' },
  write: { agent: 'writer', actor: 'llm' },
  audit: { agent: 'auditor', actor: 'code+llm' },
  sign: { agent: 'auditor', actor: 'code' },
};

export interface StepDeviation { field: 'agent' | 'actor'; recorded: string; contract: string }

/**
 * What the contract expects of one step of a run of this kind. run-events.md §2.1 overrides the §2
 * table for a profile draft (its audit is "code checks on the draft", with no model review) and for
 * a sabotage run (its write step inserts one labelled sentence built by code, with no model).
 */
function stepContract(type: StepType, kind?: Run['kind']): { agent: AgentRole; actor: Actor } | undefined {
  const base = STEP_CONTRACT[type];
  if (base && kind === 'profile_draft' && type === 'audit') return { ...base, actor: 'code' };
  if (base && kind === 'sabotage' && type === 'write') return { ...base, actor: 'code' };
  return base;
}

/**
 * Differences between what a step recorded and the contract for its run kind. The recorded value is
 * what is shown. Pass the run kind: without it only the general §2 table is applied.
 */
export function stepDeviations(step: Pick<Step, 'type' | 'agent' | 'actor'>, kind?: Run['kind']): StepDeviation[] {
  const expected = stepContract(step.type, kind);
  if (!expected) return [];
  const out: StepDeviation[] = [];
  if (step.agent !== expected.agent) out.push({ field: 'agent', recorded: step.agent, contract: expected.agent });
  if (step.actor !== expected.actor) out.push({ field: 'actor', recorded: step.actor, contract: expected.actor });
  return out;
}

export interface RoleCard {
  role: AgentRole;
  nature: WorkNature;
  /** Step types this role performs (run-events.md §2). */
  steps: StepType[];
  purpose: I18NText;
  /** Tool identifiers the role may call (contracts/tools.md §6); empty = none. */
  tools: string[];
  toolsNote: I18NText;
}

const LOOKUP_TOOLS = ['universe.search', 'universe.get', 'profile.get', 'data.describe', 'macro.series'];

/** Six roles: four do model work (the Auditor's review half), three are deterministic code (its check half). */
export const ROLE_CARDS: readonly RoleCard[] = [
  {
    role: 'planner', nature: 'model', steps: ['plan', 'revise'],
    purpose: {
      en: 'Reads the request and the profile, then names the scenarios, calculations and research questions to run, or asks one clarifying question. After an objection from the rule check it decides what else to test.',
      fr: 'Lit la requête et le profil, puis nomme les scénarios, calculs et questions de recherche à exécuter, ou pose une question de clarification. Après une objection de la vérification des règles, il décide quoi tester d’autre.',
    },
    tools: LOOKUP_TOOLS,
    toolsNote: {
      en: 'Read-only lookups. It names quant, rule, optimizer and research tasks in its plan; it does not run them and cannot decide whether the controls run.',
      fr: 'Consultations en lecture seule. Il nomme les tâches de calcul, de règles, d’optimisation et de recherche dans son plan ; il ne les exécute pas et ne décide pas si les contrôles s’exécutent.',
    },
  },
  {
    role: 'researcher', nature: 'model', steps: ['research'],
    purpose: {
      en: 'Runs the research questions with the research tools and returns evidence with citations, not conclusions. A page that is not saved as evidence cannot be cited.',
      fr: 'Exécute les questions de recherche avec les outils de recherche et renvoie des preuves citées, pas des conclusions. Une page non enregistrée comme preuve ne peut pas être citée.',
    },
    tools: [
      ...LOOKUP_TOOLS, 'edgar.find_company', 'edgar.list_filings', 'edgar.filing_text', 'edgar.company_facts', 'gdelt.search',
      'web.fetch', 'web.browse', 'attention.pageviews', 'emissions.facilities', 'etf.holdings', 'world.search_events', 'research.save_evidence',
    ],
    toolsNote: {
      en: 'Cannot call quant or rule tools. web.browse and emissions.facilities exist only when their feature flags are on; attention.pageviews and etf.holdings only with reviewed configuration (a ticker-to-article mapping, a dated issuer holdings file). Not executed in a historical replay.',
      fr: 'Ne peut pas appeler les outils de calcul ou de règles. web.browse et emissions.facilities n’existent que si leurs indicateurs sont activés ; attention.pageviews et etf.holdings, seulement avec une configuration vérifiée (une correspondance titre-article, un fichier de positions daté de l’émetteur). Non exécuté dans un rejeu historique.',
    },
  },
  {
    role: 'quant', nature: 'code', steps: ['quant'],
    purpose: {
      en: 'Deterministic code. Computes the mandatory metric set and the calculations the plan asked for. Every number leaves it as a fact with its dataset, method and row counts.',
      fr: 'Code déterministe. Calcule l’ensemble obligatoire de mesures et les calculs demandés par le plan. Chaque nombre en sort sous forme de fait avec son jeu de données, sa méthode et ses nombres de lignes.',
    },
    tools: [
      'quant.asset_metrics', 'quant.calendar_year_return', 'quant.portfolio_snapshot', 'quant.portfolio_metrics', 'quant.apply_move',
      'quant.compare_funding', 'quant.stress_replay', 'quant.correlation', 'quant.exposure', 'quant.price_move_after',
    ],
    toolsNote: {
      en: 'Every data read goes through the date gate; rows after the information cutoff are withheld and counted.',
      fr: 'Chaque lecture passe par le filtre de date ; les lignes postérieures à la date limite sont retenues et comptées.',
    },
  },
  {
    role: 'risk_officer', nature: 'code', steps: ['risk_check'],
    purpose: {
      en: 'Deterministic code. Evaluates every enabled rule for every scenario and computes the verdicts, the funding comparison and the largest size before the first rule conflict. Runs on every decision; the model cannot skip it.',
      fr: 'Code déterministe. Évalue chaque règle activée pour chaque scénario et calcule les verdicts, la comparaison des financements et la taille maximale avant le premier conflit de règle. S’exécute à chaque décision ; le modèle ne peut pas l’ignorer.',
    },
    tools: [
      'rules.check', 'optimizer.max_compatible_size', 'optimizer.goal_candidates', 'optimizer.alternatives', 'optimizer.rebalance',
      'optimizer.derive_thresholds',
    ],
    toolsNote: {
      en: 'Rule and optimizer functions only. Thresholds are rule assumptions, never loosened to make a request fit.',
      fr: 'Fonctions de règles et d’optimisation seulement. Les seuils sont des hypothèses de règles, jamais assouplis pour faire passer une requête.',
    },
  },
  {
    role: 'writer', nature: 'model', steps: ['write'],
    purpose: {
      en: 'Drafts the explanation using tokens that refer to facts, rules and evidence. It receives the ledger and the rule checks; it computes nothing and decides no verdict.',
      fr: 'Rédige l’explication avec des jetons qui renvoient aux faits, aux règles et aux preuves. Il reçoit le registre et les vérifications ; il ne calcule rien et ne décide d’aucun verdict.',
    },
    tools: [],
    toolsNote: { en: 'No tools.', fr: 'Aucun outil.' },
  },
  {
    role: 'auditor', nature: 'mixed', steps: ['audit', 'sign'],
    purpose: {
      en: 'Two parts. Code auditor: runs checks A01–A14 against the ledger, strikes or repairs sentences, then computes the ledger hash and signs. LLM auditor: a model review that receives only the sentences and the facts they cite.',
      fr: 'Deux parties. Auditeur par code : exécute les vérifications A01–A14 sur le registre, raye ou corrige des phrases, puis calcule l’empreinte du registre et signe. Auditeur par modèle : une revue qui ne reçoit que les phrases et les faits qu’elles citent.',
    },
    tools: [],
    toolsNote: {
      en: 'No tools through the model. The code checks read the ledger directly. A guardrail is applied only when one is configured.',
      fr: 'Aucun outil par le modèle. Les vérifications par code lisent directement le registre. Un garde-fou n’est appliqué que s’il est configuré.',
    },
  },
];

// ----- Architecture (docs/03-ARCHITECTURE.md, approved service diagram) -----

export type ArchNodeId = 'browser' | 'cdn' | 'gateway' | 'api' | 'dynamo' | 'worker' | 's3' | 'bedrock' | 'research';

export interface ArchNode { id: ArchNodeId; title: I18NText; role: I18NText; sendsTo: { to: ArchNodeId; label: I18NText }[] }

export const ARCHITECTURE: readonly ArchNode[] = [
  {
    id: 'browser', title: { en: 'Browser', fr: 'Navigateur' },
    role: { en: 'Static Next.js site; holds only the session capability and display preferences.', fr: 'Site Next.js statique ; ne conserve que la capacité de session et les préférences d’affichage.' },
    sendsTo: [
      { to: 'cdn', label: { en: 'loads the static site', fr: 'charge le site statique' } },
      { to: 'gateway', label: { en: 'calls the HTTP API', fr: 'appelle l’API HTTP' } },
    ],
  },
  {
    id: 'cdn', title: { en: 'CloudFront + private S3 site', fr: 'CloudFront + site S3 privé' },
    role: { en: 'Serves the exported pages. No server-side rendering.', fr: 'Sert les pages exportées. Aucun rendu côté serveur.' },
    sendsTo: [],
  },
  {
    id: 'gateway', title: { en: 'API Gateway', fr: 'API Gateway' },
    role: { en: 'Public HTTP entry point.', fr: 'Point d’entrée HTTP public.' },
    sendsTo: [{ to: 'api', label: { en: 'forwards requests', fr: 'transmet les requêtes' } }],
  },
  {
    id: 'api', title: { en: 'FastAPI Lambda', fr: 'Lambda FastAPI' },
    role: { en: 'Deterministic reads and rule checks; stores a queued run and returns at once.', fr: 'Lectures déterministes et vérifications des règles ; enregistre une exécution en file et répond aussitôt.' },
    sendsTo: [
      { to: 'dynamo', label: { en: 'reads and writes profiles, runs, cache', fr: 'lit et écrit profils, exécutions, cache' } },
      { to: 'worker', label: { en: 'asynchronous invoke with the run ID', fr: 'appel asynchrone avec l’identifiant d’exécution' } },
      { to: 's3', label: { en: 'reads versioned data', fr: 'lit les données versionnées' } },
    ],
  },
  {
    id: 'worker', title: { en: 'Worker Lambda', fr: 'Lambda de traitement' },
    role: { en: 'Executes the run steps and writes each step, fact and evidence item as it finishes.', fr: 'Exécute les étapes et écrit chaque étape, fait et preuve dès qu’ils sont terminés.' },
    sendsTo: [
      { to: 'dynamo', label: { en: 'writes steps, facts, evidence', fr: 'écrit étapes, faits, preuves' } },
      { to: 's3', label: { en: 'reads data through the date gate, stores fetched documents', fr: 'lit les données par le filtre de date, stocke les documents récupérés' } },
      { to: 'bedrock', label: { en: 'model calls (planner, researcher, writer, LLM review)', fr: 'appels de modèle (planificateur, chercheur, rédacteur, revue par modèle)' } },
      { to: 'research', label: { en: 'allow-listed source lookups', fr: 'consultations de sources autorisées' } },
    ],
  },
  {
    id: 'dynamo', title: { en: 'DynamoDB', fr: 'DynamoDB' },
    role: { en: 'Profiles, runs (one record per step, fact and evidence item) and cache indexes.', fr: 'Profils, exécutions (un enregistrement par étape, fait et preuve) et index de cache.' },
    sendsTo: [],
  },
  {
    id: 's3', title: { en: 'Versioned data and evidence (S3)', fr: 'Données et preuves versionnées (S3)' },
    role: { en: 'Immutable data snapshots and the text of fetched documents.', fr: 'Instantanés de données immuables et texte des documents récupérés.' },
    sendsTo: [],
  },
  {
    id: 'bedrock', title: { en: 'Amazon Bedrock (via Strands)', fr: 'Amazon Bedrock (via Strands)' },
    role: { en: 'Language models. They explain; they never compute a figure or a verdict.', fr: 'Modèles de langage. Ils expliquent ; ils ne calculent jamais un chiffre ni un verdict.' },
    sendsTo: [],
  },
  {
    id: 'research', title: { en: 'Public research adapters', fr: 'Adaptateurs de recherche publics' },
    role: { en: 'SEC EDGAR, the cached news index and allow-listed pages. Results enter a run only as saved evidence.', fr: 'SEC EDGAR, l’index de nouvelles en cache et des pages autorisées. Les résultats n’entrent dans une exécution que comme preuves enregistrées.' },
    sendsTo: [],
  },
];

// ----- Run readings -----

const SENSITIVE_KEY = /session|token|secret|passw|authori[sz]ation|api[_-]?key|credential|cookie/i;
const SENSITIVE_VALUE = /(^|[^a-z0-9])s_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\bAKIA[0-9A-Z]{16}\b|\bBearer\s+\S+/i;
export const REDACTED = '[redacted]';
const MAX_STRING = 300;

/**
 * Defensive redaction of tool-call arguments before display. The contract already excludes secrets;
 * this also hides anything keyed or shaped like a session capability, token or cloud credential.
 */
export function redactArgs(value: unknown, depth = 0): unknown {
  if (depth > 6) return '…';
  if (typeof value === 'string') {
    if (SENSITIVE_VALUE.test(value)) return REDACTED;
    return value.length > MAX_STRING ? `${value.slice(0, MAX_STRING)}…` : value;
  }
  if (Array.isArray(value)) return value.map(item => redactArgs(item, depth + 1));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) =>
      [key, SENSITIVE_KEY.test(key) ? REDACTED : redactArgs(item, depth + 1)]));
  }
  return value;
}

export function formatArgs(args: Record<string, unknown>): string {
  return JSON.stringify(redactArgs(args), null, 2);
}

/** What a step recorded as produced: its own IDs plus those of its tool calls, de-duplicated. */
export function stepProduced(step: Pick<Step, 'factIds' | 'evidenceIds' | 'toolCalls'>): { factIds: string[]; evidenceIds: string[] } {
  const factIds = new Set(step.factIds);
  const evidenceIds = new Set(step.evidenceIds);
  for (const call of step.toolCalls) {
    for (const id of call.factIds) factIds.add(id);
    for (const id of call.evidenceIds) evidenceIds.add(id);
  }
  return { factIds: [...factIds], evidenceIds: [...evidenceIds] };
}

export type GuardrailReading = 'no_brief' | 'applied' | 'applied_flag_off' | 'configured_not_applied' | 'not_configured';

/**
 * Configured (the `/meta` `guardrails` flag) versus applied (the signed brief's audit record).
 * A flag is configuration; only the audit record says a guardrail acted on this run.
 */
export function guardrailReading(configured: boolean, audit: GuardrailAudit | null): GuardrailReading {
  if (!audit) return 'no_brief';
  if (audit.applied) return configured ? 'applied' : 'applied_flag_off';
  return configured ? 'configured_not_applied' : 'not_configured';
}

export function runGuardrailAudit(run: Pick<Run, 'result'>): GuardrailAudit | null {
  const briefs = briefsOf(run.result);
  const brief = briefs[briefs.length - 1];
  return brief ? brief.audit.guardrail : null;
}

// ----- Run picker: the list is a snapshot, the selected run is polled -----

export interface LiveRunStatus { runId: string; status: RunStatus }

/**
 * Rows to display: the row of the polled run follows its live status. A terminal status already in
 * the list is final and is never replaced by an older, non-terminal poll.
 */
export function applyLiveStatus(items: readonly RunSummary[], live: LiveRunStatus | null): RunSummary[] {
  if (!live) return [...items];
  return items.map(item => (
    item.runId === live.runId && item.status !== live.status && !isTerminal(item.status) ? { ...item, status: live.status } : item));
}

/**
 * True when the list's copy of the polled run is still active while the run has reached a terminal
 * status: its verdict and duration belong to GET /runs and must be read again, not derived here.
 */
export function listRowIsBehind(items: readonly RunSummary[], live: LiveRunStatus | null): boolean {
  if (!live || !isTerminal(live.status)) return false;
  const row = items.find(item => item.runId === live.runId);
  return row !== undefined && !isTerminal(row.status);
}

/**
 * Refresh loaded rows from a newer page without clearing the table: a row present in `fresh` is
 * replaced in place; order, rows absent from `fresh` and the number of rows are kept.
 */
export function refreshRunRows(loaded: readonly RunSummary[], fresh: readonly RunSummary[]): RunSummary[] {
  const byId = new Map(fresh.map(item => [item.runId, item]));
  return loaded.map(item => byId.get(item.runId) ?? item);
}

/** Contract defaults from run-events.md §4; a deployment may override them by environment variable. */
export const RUN_LIMITS = { llmCalls: 12, researchToolCalls: 12, reviseLoops: 2, wallClockTargetMs: 90_000, wallClockHardMs: 180_000 } as const;

export interface BudgetLimits {
  /** `trace`: every limit below was reported by GET /runs/{id}/trace; `default`: all are RUN_LIMITS. */
  source: 'trace' | 'default';
  llmCalls: number;
  researchToolCalls: number;
  reviseLoops: number;
  /** The 90 s target is a contract figure (capped at the hard limit); the trace reports the hard limit only. */
  wallClockTargetMs: number;
  wallClockHardMs: number;
}

const TRACE_BUDGET = { llmCalls: 'llm_calls', researchToolCalls: 'research_calls', reviseLoops: 'revisions', wallClockHardMs: 'wall_clock_ms' } as const;

/**
 * The limits to show next to a run's recorded usage. The trace's limits are used only when the
 * trace belongs to `runId` and reports all four configurable budgets (run-events.md §4); otherwise
 * every limit is the contract default, so one column never mixes the two sources.
 */
export function budgetLimits(trace: { runId: string; budgets: readonly { name: string; limit: number }[] } | null | undefined, runId: string): BudgetLimits {
  const fallback: BudgetLimits = { source: 'default', ...RUN_LIMITS };
  if (!trace || trace.runId !== runId) return fallback;
  const limit = (name: string) => trace.budgets.find(item => item.name === name)?.limit;
  const read = Object.fromEntries(Object.entries(TRACE_BUDGET).map(([key, name]) => [key, limit(name)]));
  if (!Object.values(read).every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0)) return fallback;
  const limits = read as Record<keyof typeof TRACE_BUDGET, number>;
  // A deployment may lower the hard limit below the contract's 90 s target; the target never exceeds it.
  return { source: 'trace', ...limits, wallClockTargetMs: Math.min(RUN_LIMITS.wallClockTargetMs, limits.wallClockHardMs) };
}

/** Budget use read from the run payload only: `run.usage` totals and the steps that are present. */
export function runBudget(run: Pick<Run, 'usage' | 'steps'>) {
  return {
    ...run.usage,
    reviseLoops: run.steps.filter(step => step.type === 'revise').length,
    researchToolCalls: run.steps.filter(step => step.type === 'research').reduce((n, step) => n + step.toolCalls.length, 0),
    failedToolCalls: run.steps.reduce((n, step) => n + step.toolCalls.filter(call => !call.ok).length, 0),
    stepsRecorded: run.steps.length,
  };
}

/** Public site manifest, validated before display; it does not identify the API artifact. */
export function siteBuildIdentity(value: unknown): { revision: string; builtAt: string } | null {
  if (!value || typeof value !== 'object') return null;
  const manifest = value as Record<string, unknown>;
  if (typeof manifest.revision !== 'string' || !/^[0-9a-f]{40}$/.test(manifest.revision)
      || typeof manifest.built_at !== 'string' || !Number.isFinite(Date.parse(manifest.built_at))) return null;
  return { revision: manifest.revision, builtAt: manifest.built_at };
}
