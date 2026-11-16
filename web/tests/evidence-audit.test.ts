/** Evidence page readings: A08 with nothing to verify, research counts and note, sources tried, run list scope. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { Brief, DecisionRequest, Run, Step, ToolCall } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import {
  ATTEMPT_OUTCOME, allAttemptsFailed, attemptTarget, evidenceCitations, quoteCheckHadNothingToVerify, researchAttempts,
  researchCountsLine, researchNothingNote, researchOutcome, researchToolLabel, runListKey, runListProfileId, sentenceHashTarget,
  toolFailureReason,
} from '../src/lib/evidence';

test('a #sentence-… fragment names the removed sentence the Evidence page scrolls to', () => {
  // BriefView's removed-sentence link encodes the id; the page decodes it once the brief renders.
  assert.equal(sentenceHashTarget(`#sentence-${encodeURIComponent('S-INJECTED')}`), 'sentence-S-INJECTED');
  assert.equal(sentenceHashTarget('#sentence-a%20b'), 'sentence-a b');
  assert.equal(sentenceHashTarget('#sources-tried'), null);
  assert.equal(sentenceHashTarget(''), null);
  assert.equal(sentenceHashTarget('#sentence-%E0%A4%A'), null, 'a malformed fragment is ignored');
});

const fixtureRun = (): Run => validateContract('Run',
  JSON.parse(readFileSync(new URL('../../contracts/fixtures/run.decision.robert-tsla-25.json', import.meta.url), 'utf8')));

const briefOf = (run: Run): Brief => {
  const result = run.result;
  if (result?.kind !== 'decision') throw new Error('The fixture is a decision run');
  return result.decision.brief;
};

const call = (over: Partial<ToolCall>): ToolCall => ({
  id: 'TC-x', tool: 'web.fetch', args: {}, startedAt: '2026-11-14T21:30:00Z', durationMs: 1, ok: true, resultSummary: '',
  datasetsRead: [], factIds: [], evidenceIds: [], error: null, ...over,
});

const researchStep = (base: Step, toolCalls: ToolCall[]): Step => ({ ...base, type: 'research', agent: 'researcher', actor: 'llm+tools', toolCalls, evidenceIds: [] });

/** The tester's NVDA shape: 7 research calls, 6 failed, 1 answered without saving anything. */
const nvdaCalls = (): ToolCall[] => [
  call({ id: 'TC-1', tool: 'web.fetch', args: { url: 'https://nvidianews.nvidia.com/news?x=1' }, ok: false, error: 'domain_not_allowlisted' }),
  call({ id: 'TC-2', tool: 'web.browse', args: { task: 'NVDA results' }, ok: false, error: 'start_url_required' }),
  call({ id: 'TC-3', tool: 'etf.holdings', args: { ticker: 'SPY' }, ok: false, error: 'issuer_file_not_configured' }),
  call({ id: 'TC-4', tool: 'gdelt.search', args: { query: 'NVIDIA', start: '2026-10-15', end: '2026-11-15' }, ok: false, error: 'invalid_search_window' }),
  call({ id: 'TC-5', tool: 'edgar.find_company', args: { name_or_ticker: 'NVDA' }, ok: false, error: 'source_unavailable' }),
  call({ id: 'TC-6', tool: 'research.save_evidence', args: { url: 'https://investor.nvidia.com/x' }, ok: false, error: 'document_not_fetched_in_run' }),
  call({ id: 'TC-7', tool: 'attention.pageviews', args: { ticker: 'NVDA' }, ok: true, resultSummary: 'unverified_article_mapping' }),
];

test('A08: a passing quote check on a brief that cites no evidence had nothing to verify', () => {
  const run = fixtureRun();
  const brief = briefOf(run);
  const a08 = brief.audit.checks.find(c => c.code === 'A08');
  assert.ok(a08 && a08.ok);
  assert.deepEqual(evidenceCitations(brief), []);
  assert.equal(quoteCheckHadNothingToVerify(a08, brief), true);
  // Another check, or a failed A08, is never relabelled.
  assert.equal(quoteCheckHadNothingToVerify({ code: 'A01', ok: true }, brief), false);
  assert.equal(quoteCheckHadNothingToVerify({ code: 'A08', ok: false }, brief), false);
});

test('A08: one cited evidence segment (struck sentences included) means quotes were compared', () => {
  const brief = structuredClone(briefOf(fixtureRun()));
  const sentence = brief.sections[0]!.sentences[0]!;
  sentence.segments.push({ t: 'evidence', evidenceId: 'E-001', display: 'Filing' });
  sentence.audit = { ...sentence.audit, status: 'struck' };
  assert.deepEqual(evidenceCitations(brief), ['E-001']);
  assert.equal(quoteCheckHadNothingToVerify({ code: 'A08', ok: true }, brief), false);
});

test('research outcome mirrors the step summary: distinct evidence kept, failed calls', () => {
  const run = fixtureRun();
  assert.equal(researchOutcome(run), null);
  const step = researchStep(run.steps[0]!, [
    call({ id: 'a', evidenceIds: ['E-001'] }),
    call({ id: 'b', evidenceIds: ['E-001', 'E-002'] }),
    call({ id: 'c', ok: false, error: 'request_timeout' }),
  ]);
  assert.deepEqual(researchOutcome({ steps: [...run.steps, step] }), { calls: 3, failed: 1, saved: 2 });
  assert.deepEqual(researchOutcome({ steps: [researchStep(run.steps[0]!, nvdaCalls())] }), { calls: 7, failed: 6, saved: 0 });
});

test('research counts line: pluralised in both languages, and the not-run and replay variants', () => {
  assert.deepEqual(researchCountsLine({ calls: 7, failed: 6, saved: 0 }, 0, false), {
    en: 'Research: 0 sources kept, 6 tool calls failed, 0 cited in this brief.',
    fr: 'Recherche : 0 source retenue, 6 appels d’outil en échec, 0 citée dans cette note.',
  });
  assert.deepEqual(researchCountsLine({ calls: 2, failed: 1, saved: 1 }, 1, false), {
    en: 'Research: 1 source kept, 1 tool call failed, 1 cited in this brief.',
    fr: 'Recherche : 1 source retenue, 1 appel d’outil en échec, 1 citée dans cette note.',
  });
  assert.equal(researchCountsLine({ calls: 3, failed: 0, saved: 2 }, 2, false).fr,
    'Recherche : 2 sources retenues, 0 appel d’outil en échec, 2 citées dans cette note.');
  assert.match(researchCountsLine(null, 0, false).en, /not run for this analysis/);
  assert.match(researchCountsLine(null, 0, true).fr, /rejeux historiques/);
});

test('nothing-kept note: names the move ticker, generic for goals, absent without research or with a saved source', () => {
  const run = fixtureRun();
  assert.equal(researchNothingNote(run), null);
  const failed = { ...run, steps: [...run.steps, researchStep(run.steps[0]!, nvdaCalls())] };
  const note = researchNothingNote(failed);
  assert.deepEqual(note?.title, { en: 'No external information was available for TSLA.', fr: 'Aucune information externe n’était disponible pour TSLA.' });
  assert.match(note!.body.en, /saved no source/);
  const goal = structuredClone(failed);
  const request = JSON.parse(JSON.stringify({
    type: 'goal', goal: { themes: [], assetClasses: ['bond'], tickers: [], targetExposurePct: null, maxLossPct: null, maxVolPct: null, notes: '' },
  })) as DecisionRequest;
  if (goal.input.kind === 'decision') goal.input.request = request;
  if (goal.result?.kind === 'decision') goal.result.decision.request = request;
  assert.equal(researchNothingNote(goal)?.title.en, 'No external information was available for this request.');
  const saved = { ...run, steps: [...run.steps, researchStep(run.steps[0]!, [call({ evidenceIds: ['E-001'] })])] };
  assert.equal(researchNothingNote(saved), null);
});

test('sources tried: one row per external call, host only, plain reasons, lookups left out', () => {
  const run = fixtureRun();
  const calls = [call({ id: 'L', tool: 'universe.get', args: { ticker: 'NVDA' } }), ...nvdaCalls()];
  const attempts = researchAttempts({ steps: [...run.steps, researchStep(run.steps[0]!, calls)] });
  assert.equal(attempts.length, 7);
  assert.equal(attempts.filter(a => a.outcome === 'failed').length, 6);
  assert.equal(attempts.filter(a => a.outcome === 'nothing').length, 1);
  assert.equal(attempts[0]!.target, 'nvidianews.nvidia.com');
  assert.equal(attempts[1]!.target, null);
  assert.equal(attempts[4]!.target, 'NVDA');
  assert.equal(attempts[0]!.reason?.en, 'This site is not on the list of reviewed official sources.');
  assert.equal(attempts[0]!.technical, 'domain_not_allowlisted');
  assert.equal(attempts[6]!.reason?.fr, 'Aucun article Wikipédia vérifié n’est associé à ce symbole.');
  assert.equal(allAttemptsFailed(attempts), false);
  assert.equal(allAttemptsFailed(attempts.slice(0, 6)), true);
  assert.equal(allAttemptsFailed([]), false);
  // Non-research steps' calls are not sources tried.
  assert.deepEqual(researchAttempts(run), []);
  assert.equal(researchAttempts({ steps: [researchStep(run.steps[0]!, [call({ evidenceIds: ['E-1'] })])] })[0]!.outcome, 'saved');
  assert.deepEqual(ATTEMPT_OUTCOME.failed, { en: 'Failed', fr: 'En échec' });
  assert.deepEqual(researchToolLabel('gdelt.search'), { en: 'GDELT news search', fr: 'Recherche de nouvelles GDELT' });
  assert.deepEqual(researchToolLabel('new.tool'), { en: 'new.tool', fr: 'new.tool' });
});

test('attempt target: URLs reduce to the host, an invalid URL gives nothing, long queries are cut', () => {
  assert.equal(attemptTarget({ start_url: 'https://www.federalreserve.gov/newsevents.htm?a=b' }), 'www.federalreserve.gov');
  assert.equal(attemptTarget({ url: 'not a url' }), null);
  assert.equal(attemptTarget({ query: 'x'.repeat(100) }), `${'x'.repeat(80)}…`);
  assert.equal(attemptTarget({}), null);
});

test('tool failure reasons: every recorded code has bilingual text; unknown codes say so', () => {
  const codes = [
    'domain_not_allowlisted', 'start_url_required', 'issuer_file_not_configured', 'invalid_search_window', 'source_unavailable',
    'rate_limited', 'request_timeout', 'accession_requires_same_run_list_filings', 'document_not_fetched_in_run', 'quote_not_verified',
    'Tool is unavailable for this role', 'research_unavailable_in_replay', 'left_allowlisted_domains',
  ];
  const other = toolFailureReason('something_new');
  assert.equal(other.en, 'Other reason (see technical details).');
  assert.equal(other.fr, 'Autre raison (voir les détails techniques).');
  for (const code of codes) {
    const reason = toolFailureReason(code);
    assert.notDeepEqual(reason, other, code);
    assert.ok(reason.en && reason.fr && reason.en !== reason.fr, code);
  }
  const malformed = 'The request to the tool was malformed.';
  assert.equal(toolFailureReason('validation_error: start: Input should be a valid date').en, malformed);
  assert.equal(toolFailureReason('Invalid tool arguments: start_url').en, malformed);
  assert.equal(toolFailureReason('http_403').fr, 'La source a répondu avec le statut HTTP 403.');
  assert.match(toolFailureReason('research_calls budget exhausted').en, /research budget/);
});

test('run list scope: the active profile by default, every profile on request, keys share the runs| prefix', () => {
  assert.equal(runListProfileId('profile', 'robert'), 'robert');
  assert.equal(runListProfileId('all', 'robert'), undefined);
  assert.equal(runListProfileId('profile', null), undefined);
  assert.equal(runListKey('s_1', 'robert'), 'runs|s_1|robert');
  assert.equal(runListKey('s_1', undefined), 'runs|s_1|all');
});
