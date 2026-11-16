/** Pure helpers over Brief / Sentence / Segment (contracts/schemas.md §8). */
import type {
  Brief, BriefSection, BriefSectionId, CachedBriefResponse, I18NText, Lang, LimitationCode, RuleStatus, Sentence, Run, RuleCheck, RunResult,
  StepType, WindowCode,
} from '../contracts/types';
import { LIMITATION, RULE_STATUS, WINDOW, labelOf, pick } from './labels';
import { isTerminal } from './runs';

export type BriefMode = 'normal' | 'audit';

/** Normal views never show struck text; the audit view shows everything with markings. */
export function visibleSentences(section: BriefSection, mode: BriefMode): Sentence[] {
  return mode === 'audit' ? section.sentences : section.sentences.filter(s => s.audit.status !== 'struck');
}

function allSentences(brief: Brief): Sentence[] {
  return brief.sections.flatMap(section => section.sentences);
}

/** Sentence IDs whose segments reference the fact. Mirrors the API's documented `usedBy` projection. */
function sentencesUsingFact(briefs: readonly Brief[], factId: string): string[] {
  const ids = new Set<string>();
  for (const brief of briefs) {
    for (const sentence of allSentences(brief)) {
      if (sentence.segments.some(seg => seg.t === 'fact' && seg.factId === factId)) ids.add(sentence.id);
    }
  }
  return [...ids];
}

function rulesUsingFact(checks: readonly RuleCheck[], factId: string): string[] {
  const ids = new Set<string>();
  for (const check of checks) {
    if (check.valueFactId === factId || check.thresholdFactId === factId) ids.add(check.ruleId);
  }
  return [...ids];
}

/** All briefs carried by a result, in display order. */
export function briefsOf(result: RunResult | null): Brief[] {
  if (!result) return [];
  switch (result.kind) {
    case 'decision': return [result.decision.brief];
    case 'rebalance': return [result.rebalance.brief];
    case 'portfolio_brief': return [result.portfolioBrief.brief];
    case 'event_brief': return [result.eventBrief.brief];
    case 'replay': return [result.replay.decision.brief];
    case 'sabotage': return [result.sabotage.briefAfterAudit];
    default: return [];
  }
}

/** Rule checks carried by a result (all scenarios for decisions). */
function ruleChecksOf(result: RunResult | null): RuleCheck[] {
  if (!result) return [];
  switch (result.kind) {
    case 'decision': return result.decision.scenarios.flatMap(s => s.ruleChecks);
    case 'rebalance': return [...result.rebalance.ruleChecksBefore, ...result.rebalance.ruleChecksAfter];
    case 'replay': return result.replay.decision.scenarios.flatMap(s => s.ruleChecks);
    case 'portfolio_brief': return result.portfolioBrief.ruleChecks;
    default: return [];
  }
}

export function factUsage(run: Run, factId: string): { sentenceIds: string[]; ruleIds: string[] } {
  return {
    sentenceIds: sentencesUsingFact(briefsOf(run.result), factId),
    ruleIds: rulesUsingFact(ruleChecksOf(run.result), factId),
  };
}

/** References in a run's briefs that do not resolve inside the same run (AT-07 / AUDUI-01). */
export function danglingReferences(run: Run): string[] {
  const missing: string[] = [];
  for (const brief of briefsOf(run.result)) {
    for (const sentence of allSentences(brief)) {
      for (const seg of sentence.segments) {
        if (seg.t === 'fact' && !run.facts[seg.factId]) missing.push(`${sentence.id}:${seg.factId}`);
        if (seg.t === 'evidence' && !run.evidence[seg.evidenceId]) missing.push(`${sentence.id}:${seg.evidenceId}`);
      }
    }
  }
  return missing;
}

// ----- Display of code-owned brief content (web/DESIGN.md: never show raw enum identifiers) -----

/** Section headings by section id (contracts/schemas.md §8: BriefSectionId). */
const BRIEF_SECTION:Record<BriefSectionId, I18NText> = {
  summary: { en: 'Summary', fr: 'Résumé' },
  facts: { en: 'Facts', fr: 'Faits' },
  assumptions: { en: 'Assumptions', fr: 'Hypothèses' },
  limits: { en: 'Limits', fr: 'Limites' },
  scenarios: { en: 'Scenarios', fr: 'Scénarios' },
  next_checks: { en: 'Next checks', fr: 'Prochaines vérifications' },
};

const spelled = (text: string) => text.replace(/[_s]+/g, ' ').trim().toLowerCase();

/**
 * Heading of a brief section. The auditor derives titles from the section id (en "Facts", fr "facts"),
 * so a title that only spells out the id is replaced by the bilingual heading for that id. A title
 * that says something else (the refusal brief: id "limits", title "Refusal" / "Refus") is deliberate
 * and kept, as is the title of an id this table does not know.
 */
export function sectionTitle(section: Pick<BriefSection, 'id' | 'title'>, lang: Lang): string {
  const derived = spelled(section.title.en) === spelled(section.id);
  if (derived && Object.hasOwn(BRIEF_SECTION, section.id)) return pick(BRIEF_SECTION[section.id], lang);
  return pick(section.title, lang);
}

/**
 * The limitation code a sentence consists of, or null. The auditor appends one sentence per cited
 * limitation whose only segment is the code itself (catalog A13); the web holds the text of each code.
 * Only an exact, known code matches, so a sentence written by the model is never rewritten.
 */
export function limitationCodeOf(sentence: Pick<Sentence, 'segments'>): LimitationCode | null {
  const [only, ...rest] = sentence.segments;
  if (!only || rest.length > 0 || only.t !== 'text') return null;
  const code = only.text.trim();
  return Object.hasOwn(LIMITATION, code) ? (code as LimitationCode) : null;
}

/**
 * Text of a status segment. A display that is a raw status value ("nee", "pass") is written as the
 * status word of the display language, in lower case because it sits inside a sentence; any other
 * display is the writer's own wording and is returned unchanged.
 */
export function statusWord(display: string, lang: Lang): string {
  const key = display.trim().toLowerCase();
  if (!Object.hasOwn(RULE_STATUS, key)) return display;
  return pick(RULE_STATUS[key as RuleStatus], lang).toLocaleLowerCase(lang);
}

/** A rejected summary never hides surviving factual content on Home. */
export function portfolioSummary(brief: Brief): Sentence[] {
  const surviving = (id: BriefSectionId) => brief.sections.filter(s => s.id === id)
    .flatMap(s => s.sentences).filter(s => s.audit.status !== 'struck');
  const summary = surviving('summary');
  return (summary.length ? summary : surviving('facts')).slice(0, 2);
}

/** Struck sentences of a section, i.e. what normal views leave out. */
export function struckSentences(section: Pick<BriefSection, 'sentences'>): Sentence[] {
  return section.sentences.filter(s => s.audit.status === 'struck');
}

/** The note a normal view shows in place of struck sentences (QA 4.5d), correctly pluralised. */
export function removedNote(count: number): { text: I18NText; link: I18NText } {
  const one = count === 1;
  return {
    text: one
      ? { en: 'The auditor removed 1 sentence that failed its checks.', fr: 'L’auditeur a retiré 1 phrase qui ne passait pas ses contrôles.' }
      : { en: `The auditor removed ${count} sentences that failed its checks.`, fr: `L’auditeur a retiré ${count} phrases qui ne passaient pas ses contrôles.` },
    link: one
      ? { en: 'See it in Evidence', fr: 'La voir dans Preuves' }
      : { en: 'See them in Evidence', fr: 'Les voir dans Preuves' },
  };
}

// ----- Home brief: when a run is written automatically, and what is said about the brief shown -----

/**
 * Whether opening Home may write a brief on its own (QA 2a). Only when no brief of the current data
 * version exists: none at all (new session) or one written on older market data. A brief of the same
 * data version, whatever its window, language or staleness (profile or settings edit), is shown
 * with a note and an enabled Refresh instead. The caller also limits this to one automatic run per
 * session, profile and data version (lib/briefAuto.ts), so a language switch never writes one.
 */
export function shouldAutoRunBrief(run: Pick<Run, 'dataVersion'> | null, dataVersion: string): boolean {
  return run === null || run.dataVersion !== dataVersion;
}

/**
 * Why the cached brief is stale, derived on the client (the API sends one boolean): written on
 * older market data, or else before a profile or analysis-settings change (profile version,
 * snapshot manifest or AI configuration; the client cannot tell these apart).
 */
export type BriefStaleReason = 'data' | 'profile-or-settings';

export function briefStaleReason(cached: CachedBriefResponse | null, dataVersion: string | null): BriefStaleReason | null {
  if (!cached?.run || !cached.stale) return null;
  return dataVersion !== null && cached.run.dataVersion !== dataVersion ? 'data' : 'profile-or-settings';
}

export function staleNote(reason: BriefStaleReason): I18NText {
  return reason === 'data'
    ? { en: 'This brief was written before the market data was last updated. Refresh to update it.',
      fr: 'Cette note a été rédigée avant la dernière mise à jour des données de marché. Actualisez pour la mettre à jour.' }
    : { en: 'This brief was written before this profile or the analysis settings last changed. Refresh to update it.',
      fr: 'Cette note a été rédigée avant la dernière modification de ce profil ou des réglages de l’analyse. Actualisez pour la mettre à jour.' };
}

/** Window a portfolio brief was written for, or null for another run kind. */
export function briefWindowOf(run: Pick<Run, 'input'> | null): WindowCode | null {
  return run?.input.kind === 'portfolio_brief' ? run.input.window.code : null;
}

const windowWords = (code: WindowCode, lang: Lang) => labelOf(WINDOW, code, lang).toLocaleLowerCase(lang);

/**
 * Note when the brief's window is not the period of the figures on screen (QA 2a, 6.4): written for
 * another window than the selected one, or the dashboard shows a custom range (`customRange`, its
 * label) that the brief does not follow. Null when they match.
 */
export function briefWindowNote(briefWindow: WindowCode | null, windowCode: WindowCode, customRange: string | null): I18NText | null {
  if (briefWindow === null) return null;
  if (briefWindow !== windowCode) {
    return {
      en: `This brief was written for the ${windowWords(briefWindow, 'en')} window, not the one selected. Refresh to write one for this window.`,
      fr: `Cette note a été rédigée pour la fenêtre ${windowWords(briefWindow, 'fr')}, pas pour celle qui est choisie. Actualisez pour en rédiger une pour cette fenêtre.`,
    };
  }
  if (customRange) {
    return {
      en: `This brief uses the ${windowWords(briefWindow, 'en')} window, not the custom range ${customRange} set above.`,
      fr: `Cette note utilise la fenêtre ${windowWords(briefWindow, 'fr')}, pas la plage personnalisée ${customRange} choisie plus haut.`,
    };
  }
  return null;
}

/** Type of the step a run is executing, or null (queued, between steps, finished). */
export function briefProgress(run: Pick<Run, 'status' | 'steps'> | null): StepType | null {
  if (!run || isTerminal(run.status)) return null;
  for (let i = run.steps.length - 1; i >= 0; i--) {
    const step = run.steps[i]!;
    if (step.status === 'running') return step.type;
  }
  return null;
}

/**
 * What the brief card shows (QA 2c). While a new run is being written the previous brief stays
 * visible (greyed, `refreshing`); a failed refresh keeps the previous brief (`refreshFailed`); with
 * no previous brief, the run itself is shown (a skeleton while it loads or is in progress).
 * `current` is the polled run of `runId` (null while it loads); `previous` the last succeeded brief.
 */
export interface BriefDisplay { shown: Run | null; refreshing: boolean; refreshFailed: boolean }

export function briefDisplay(runId: string | null, current: Run | null, previous: Run | null): BriefDisplay {
  if (!runId) return { shown: previous, refreshing: false, refreshFailed: false };
  if (current === null || current.runId !== runId || !isTerminal(current.status)) {
    return { shown: previous, refreshing: true, refreshFailed: false };
  }
  if (current.status === 'succeeded') return { shown: current, refreshing: false, refreshFailed: false };
  if (previous && previous.runId !== current.runId) return { shown: previous, refreshing: false, refreshFailed: true };
  return { shown: current, refreshing: false, refreshFailed: false };
}
