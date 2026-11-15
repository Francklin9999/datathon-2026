/** Pure helpers over Brief / Sentence / Segment (contracts/schemas.md §8). */
import type { Brief, BriefSection, Sentence, Run, RuleCheck, RunResult } from '../contracts/types';

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
