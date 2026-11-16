/** Home brief (QA 2a-2c, 4.5a, 4.5d, 6.4): automatic-run policy, stale and window notes, refresh display, rule names. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import type { CachedBriefResponse, Run, Step, WindowCode } from '../src/contracts/types';
import { validateContract } from '../src/contracts/validate';
import {
  briefDisplay, briefProgress, briefStaleReason, briefWindowNote, briefWindowOf, removedNote, shouldAutoRunBrief,
  staleNote, struckSentences,
} from '../src/lib/brief';
import { AUTO_BRIEF_KEEP, autoBriefKey, autoBriefUsed, markAutoBrief, rememberKey } from '../src/lib/briefAuto';
import { ruleName, ruleNameText } from '../src/lib/ruleNames';

const fixture = (): Run => validateContract('Run',
  JSON.parse(readFileSync(new URL('../../contracts/fixtures/run.decision.robert-tsla-25.json', import.meta.url), 'utf8')));

function brief(runId: string, opts: { status?: Run['status']; dataVersion?: string; window?: WindowCode; steps?: Step[] } = {}): Run {
  const base = fixture();
  return {
    ...base, runId, kind: 'portfolio_brief', status: opts.status ?? 'succeeded', dataVersion: opts.dataVersion ?? 'snap-new',
    input: { kind: 'portfolio_brief', window: { code: opts.window ?? '1y' } }, steps: opts.steps ?? base.steps,
  } as Run;
}

function step(type: Step['type'], status: Step['status']): Step {
  const base = fixture().steps[0];
  assert.ok(base);
  return { ...base, type, status };
}

class FakeStorage {
  items = new Map<string, string>();
  getItem(key: string): string | null { return this.items.get(key) ?? null; }
  setItem(key: string, value: string): void { this.items.set(key, value); }
}

// ----- 2a: automatic runs -----

test('a brief is written automatically only when none exists for the current data version', () => {
  assert.equal(shouldAutoRunBrief(null, 'snap-new'), true);                                       // new session
  assert.equal(shouldAutoRunBrief(brief('a', { dataVersion: 'snap-old' }), 'snap-new'), true);     // market data updated
  assert.equal(shouldAutoRunBrief(brief('a', { dataVersion: 'snap-new' }), 'snap-new'), false);    // any window, stale profile or not
  assert.equal(shouldAutoRunBrief(brief('a', { dataVersion: 'snap-new', window: '3y' }), 'snap-new'), false);
});

test('the automatic-run cap is remembered per session, profile and data version, newest 20 kept', () => {
  const store = new FakeStorage();
  const key = autoBriefKey('s_1', 'robert', 'snap-new');
  assert.equal(key, 's_1|robert|snap-new');
  assert.equal(autoBriefUsed(key, store), false);
  markAutoBrief(key, store);
  assert.equal(autoBriefUsed(key, store), true);
  assert.deepEqual(JSON.parse(store.getItem('aplomb.brief.auto.v1') ?? '[]'), [key]);
  // Another browser tab or a reload reads storage, not memory.
  const reloaded = new FakeStorage();
  reloaded.items = new Map(store.items);
  assert.equal(autoBriefUsed(key, reloaded), true);
  assert.equal(autoBriefUsed(autoBriefKey('s_1', 'amira', 'snap-new'), reloaded), false);
  const many = Array.from({ length: 25 }, (_, i) => `k${i}`).reduce<string[]>((list, k) => rememberKey(list, k), []);
  assert.equal(many.length, AUTO_BRIEF_KEEP);
  assert.deepEqual(many.slice(0, 2), ['k5', 'k6']);
  assert.deepEqual(rememberKey(['a', 'b'], 'a'), ['b', 'a']);
  // Unreadable storage: the cap still holds for this page load.
  const broken = { getItem: () => '{not json', setItem: () => { throw new Error('blocked'); } };
  const other = autoBriefKey('s_2', 'robert', 'snap-new');
  assert.equal(autoBriefUsed(other, broken), false);
  markAutoBrief(other, broken);
  assert.equal(autoBriefUsed(other, broken), true);
});

/**
 * Ten Home loads as HomePage evaluates them: the cap is consumed by the first loaded lookup of a
 * session+profile+dataVersion, and a run starts only when shouldAutoRunBrief allows it.
 */
function simulate(loads: { lang: string; window: WindowCode; brief: Run | null }[], dataVersion: string, store: FakeStorage): number {
  let runs = 0;
  for (const load of loads) {
    const key = autoBriefKey('s_sim', 'robert', dataVersion);
    if (autoBriefUsed(key, store)) continue;
    markAutoBrief(key, store);
    if (shouldAutoRunBrief(load.brief, dataVersion)) runs += 1;
  }
  return runs;
}

test('ten reloads, window and language changes write at most one brief, and none when one exists', () => {
  const windows: WindowCode[] = ['1y', '1y', '3y', '1y', '3y', '5y', 'ytd', '1y', '3y', 'full'];
  const fresh = new FakeStorage();
  assert.equal(simulate(windows.map((w, i) => ({ lang: i % 2 ? 'fr' : 'en', window: w, brief: null })), 'snap-a', fresh), 1);
  const existing = new FakeStorage();
  const current = brief('kept', { dataVersion: 'snap-b', window: '1y' });
  assert.equal(simulate(windows.map(w => ({ lang: 'en', window: w, brief: current })), 'snap-b', existing), 0);
  // A new data version allows exactly one more.
  const older = brief('older', { dataVersion: 'snap-b' });
  assert.equal(simulate(windows.map(w => ({ lang: 'en', window: w, brief: older })), 'snap-c', existing), 1);
});

// ----- 2b: stale reason (derived on the client) -----

test('the stale note says whether market data or the profile/settings changed', () => {
  const stale = (run: Run | null, flag = true): CachedBriefResponse => ({ run, stale: flag });
  assert.equal(briefStaleReason(stale(brief('a', { dataVersion: 'snap-old' })), 'snap-new'), 'data');
  assert.equal(briefStaleReason(stale(brief('a', { dataVersion: 'snap-new' })), 'snap-new'), 'profile-or-settings');
  assert.equal(briefStaleReason(stale(brief('a'), false), 'snap-new'), null);
  assert.equal(briefStaleReason(stale(null), 'snap-new'), null);
  assert.equal(briefStaleReason(null, 'snap-new'), null);
  assert.equal(staleNote('data').en, 'This brief was written before the market data was last updated. Refresh to update it.');
  assert.equal(staleNote('data').fr, 'Cette note a été rédigée avant la dernière mise à jour des données de marché. Actualisez pour la mettre à jour.');
  assert.match(staleNote('profile-or-settings').en, /profile or the analysis settings/);
  assert.match(staleNote('profile-or-settings').fr, /de ce profil ou des réglages de l’analyse/);
});

// ----- 2a / 6.4: window notes -----

test('the brief window is labelled when it differs from the window or the custom range on screen', () => {
  assert.equal(briefWindowOf(brief('a', { window: '3y' })), '3y');
  assert.equal(briefWindowOf(fixture()), null);
  assert.equal(briefWindowNote('1y', '1y', null), null);
  assert.equal(briefWindowNote(null, '1y', 'Nov 12, 2023 – Nov 12, 2026'), null);
  const other = briefWindowNote('1y', '3y', null);
  assert.equal(other?.en, 'This brief was written for the 1 year window, not the one selected. Refresh to write one for this window.');
  assert.equal(other?.fr, 'Cette note a été rédigée pour la fenêtre 1 an, pas pour celle qui est choisie. Actualisez pour en rédiger une pour cette fenêtre.');
  const custom = briefWindowNote('1y', '1y', 'Nov 12, 2023 – Nov 12, 2026');
  assert.equal(custom?.en, 'This brief uses the 1 year window, not the custom range Nov 12, 2023 – Nov 12, 2026 set above.');
  assert.equal(custom?.fr, 'Cette note utilise la fenêtre 1 an, pas la plage personnalisée Nov 12, 2023 – Nov 12, 2026 choisie plus haut.');
});

// ----- 2c: refresh keeps the previous brief -----

test('briefProgress names the step being executed', () => {
  assert.equal(briefProgress(null), null);
  assert.equal(briefProgress(brief('a', { status: 'queued', steps: [] })), null);
  assert.equal(briefProgress(brief('a', { status: 'running', steps: [step('plan', 'done'), step('write', 'running')] })), 'write');
  assert.equal(briefProgress(brief('a', { status: 'running', steps: [step('plan', 'done')] })), null);
  assert.equal(briefProgress(brief('a', { status: 'succeeded', steps: [step('write', 'running')] })), null);
});

test('briefDisplay keeps the previous brief while a new one is written and after it fails', () => {
  const previous = brief('old');
  assert.deepEqual(briefDisplay(null, null, previous), { shown: previous, refreshing: false, refreshFailed: false });
  assert.deepEqual(briefDisplay(null, null, null), { shown: null, refreshing: false, refreshFailed: false });
  // Loading, queued and running: previous greyed, or nothing (skeleton) without one.
  assert.deepEqual(briefDisplay('new', null, previous), { shown: previous, refreshing: true, refreshFailed: false });
  for (const status of ['queued', 'running'] as const) {
    assert.deepEqual(briefDisplay('new', brief('new', { status }), previous), { shown: previous, refreshing: true, refreshFailed: false });
    assert.deepEqual(briefDisplay('new', brief('new', { status }), null), { shown: null, refreshing: true, refreshFailed: false });
  }
  const done = brief('new');
  assert.deepEqual(briefDisplay('new', done, previous), { shown: done, refreshing: false, refreshFailed: false });
  const failed = brief('new', { status: 'failed' });
  assert.deepEqual(briefDisplay('new', failed, previous), { shown: previous, refreshing: false, refreshFailed: true });
  assert.deepEqual(briefDisplay('new', failed, null), { shown: failed, refreshing: false, refreshFailed: false });
  // A payload of another run ID is never treated as the new run.
  assert.deepEqual(briefDisplay('new', brief('other'), previous), { shown: previous, refreshing: true, refreshFailed: false });
});

// ----- 4.5d: removed sentences -----

test('the removed-sentence note is pluralised and only counts struck sentences', () => {
  assert.equal(removedNote(1).text.en, 'The auditor removed 1 sentence that failed its checks.');
  assert.equal(removedNote(1).text.fr, 'L’auditeur a retiré 1 phrase qui ne passait pas ses contrôles.');
  assert.equal(removedNote(3).text.en, 'The auditor removed 3 sentences that failed its checks.');
  assert.equal(removedNote(3).text.fr, 'L’auditeur a retiré 3 phrases qui ne passaient pas ses contrôles.');
  assert.deepEqual(removedNote(1).link, { en: 'See it in Evidence', fr: 'La voir dans Preuves' });
  assert.deepEqual(removedNote(2).link, { en: 'See them in Evidence', fr: 'Les voir dans Preuves' });
  const run = fixture();
  const section = run.result?.kind === 'decision' ? run.result.decision.brief.sections[0] : undefined;
  assert.ok(section && section.sentences.length > 0);
  assert.deepEqual(struckSentences(section), []);
  const first = section.sentences[0]!;
  const edited = { sentences: [{ ...first, audit: { ...first.audit, status: 'struck' as const } }, ...section.sentences.slice(1)] };
  assert.deepEqual(struckSentences(edited).map(s => s.id), [first.id]);
});

// ----- 4.5a: rule names -----

test('every rule of the default profiles has an EN and FR name; families and unknown IDs', () => {
  const defaults = JSON.parse(readFileSync(new URL('../../backend/aplomb/profiles/defaults.json', import.meta.url), 'utf8'));
  const fixtures = JSON.parse(readFileSync(new URL('../../contracts/fixtures/profiles.json', import.meta.url), 'utf8'));
  const ids = new Set<string>();
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === 'object') {
      const record = node as Record<string, unknown>;
      if (typeof record.ruleId === 'string') ids.add(record.ruleId);
      Object.values(record).forEach(walk);
    }
  };
  walk(defaults);
  walk(fixtures);
  assert.ok(ids.size >= 15, `found ${ids.size} rule IDs`);
  for (const id of ids) {
    const name = ruleNameText(id);
    assert.ok(name && name.en && name.fr, `no name for ${id}`);
  }
  assert.equal(ruleName('cap.position', 'en'), 'Single-asset limit');
  assert.equal(ruleName('cap.position', 'fr'), 'Limite par actif');
  assert.equal(ruleName('cap.growth_assets', 'en'), 'Growth-asset limit');
  assert.equal(ruleName('cap.asset_class.crypto', 'en'), 'Crypto limit');
  assert.equal(ruleName('cap.asset_class.equity', 'en'), 'Asset-class limit');
  assert.equal(ruleName('exclude.sector.energy', 'fr'), 'Exclusion de secteur');
  assert.equal(ruleName('cap.country.ca', 'en'), 'Country limit');
  assert.equal(ruleName('floor.currency.cad', 'fr'), 'Plancher par devise');
  assert.equal(ruleName('custom.condition.x', 'en'), 'Conditional rule');
  assert.equal(ruleName('exclude.ticker.TSLA', 'en'), 'Excluded holding');
  assert.equal(ruleName('cap.country.', 'en'), null);
  assert.equal(ruleName('unknown.rule', 'en'), null);
});
