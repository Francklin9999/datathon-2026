/** Pure helpers over Brief / Sentence / Segment (contracts/schemas.md §8). */
import type {
  Brief, BriefSection, BriefSectionId, I18NText, Lang, LimitationCode, RuleStatus, Sentence, Run, RuleCheck, RunResult,
} from '../contracts/types';
import { LIMITATION, RULE_STATUS, pick } from './labels';

export type BriefMode = 'normal' | 'audit';

/** Normal views never show struck text; the audit view shows everything with markings. */
export function visibleSentences(section: BriefSection, mode: BriefMode): Sentence[] {
  return mode === 'audit' ? section.sentences : section.sentences.filter(s => s.audit.status !== 'struck');
}

export function allSentences(brief: Brief): Sentence[] {
  return brief.sections.flatMap(section => section.sentences);
}

/** Sentence IDs whose segments reference the fact. Mirrors the API's documented `usedBy` projection. */
export function sentencesUsingFact(briefs: readonly Brief[], factId: string): string[] {
  const ids = new Set<string>();
  for (const brief of briefs) {
    for (const sentence of allSentences(brief)) {
      if (sentence.segments.some(seg => seg.t === 'fact' && seg.factId === factId)) ids.add(sentence.id);
    }
  }
  return [...ids];
}

export function rulesUsingFact(checks: readonly RuleCheck[], factId: string): string[] {
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
    case 'portfolio_brief': return [result.portfolioBrief.brief];
    case 'event_brief': return [result.eventBrief.brief];
    case 'replay': return [result.replay.decision.brief];
    case 'sabotage': return [result.sabotage.briefBeforeAudit, result.sabotage.briefAfterAudit];
    default: return [];
  }
}

/** Rule checks carried by a result (all scenarios for decisions). */
export function ruleChecksOf(result: RunResult | null): RuleCheck[] {
  if (!result) return [];
  switch (result.kind) {
    case 'decision': return result.decision.scenarios.flatMap(s => s.ruleChecks);
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
export const BRIEF_SECTION: Record<BriefSectionId, I18NText> = {
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
