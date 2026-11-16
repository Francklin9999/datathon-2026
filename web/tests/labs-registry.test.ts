import assert from 'node:assert/strict';
import test from 'node:test';
import { readTabParam } from '../src/components/ui/Tabs';
import { DEFAULT_LAB_TOOL, LAB_CATEGORIES, LAB_TOOLS, LAB_TOOL_IDS, toolsOf } from '../src/features/labs/registry';

const bilingual = (text: { en: string; fr: string }) => text.en.trim() !== '' && text.fr.trim() !== '';

test('labs tools have unique ids that are safe in ?tool=', () => {
  assert.equal(new Set(LAB_TOOL_IDS).size, LAB_TOOLS.length);
  for (const id of LAB_TOOL_IDS) assert.match(id, /^[a-z0-9-]+$/, id);
});

test('labs tools carry bilingual labels and purposes in sentence case, without trailing periods', () => {
  for (const tool of LAB_TOOLS) {
    assert.ok(bilingual(tool.label), `${tool.id} label`);
    assert.ok(bilingual(tool.purpose), `${tool.id} purpose`);
    for (const text of [tool.label.en, tool.label.fr, tool.purpose.en, tool.purpose.fr]) {
      assert.doesNotMatch(text, /[.!]$/, `${tool.id}: ${text}`);
      assert.doesNotMatch(text, /_/, `${tool.id}: ${text}`);
    }
    assert.equal(typeof tool.loader, 'function', tool.id);
    assert.ok(tool.icon, tool.id);
  }
});

test('every labs category is bilingual and holds at least one tool, and every tool has a known category', () => {
  const categories = new Set(LAB_CATEGORIES.map(c => c.id));
  assert.equal(categories.size, LAB_CATEGORIES.length);
  for (const category of LAB_CATEGORIES) {
    assert.ok(bilingual(category.label), category.id);
    assert.ok(LAB_TOOLS.some(tool => tool.category === category.id), `${category.id} is empty`);
  }
  for (const tool of LAB_TOOLS) assert.ok(categories.has(tool.category), tool.id);
});

test('labs keeps six tools in three categories, each listed under its own category', () => {
  assert.deepEqual(LAB_CATEGORIES.map(c => c.id), ['instruments', 'planning', 'comparison']);
  assert.deepEqual(LAB_TOOL_IDS, ['instruments', 'target-drift', 'joint-plan', 'goal-funding', 'requirements', 'profile-compare']);
  assert.deepEqual(LAB_CATEGORIES.flatMap(c => toolsOf(c.id).map(t => t.id)), LAB_TOOL_IDS);
  assert.deepEqual(toolsOf('planning').map(t => t.id), ['target-drift', 'joint-plan', 'goal-funding', 'requirements']);
});

test('the default tool needs no profile, and an old link to a tool that left Labs opens it', () => {
  const fallback = LAB_TOOLS.find(tool => tool.id === DEFAULT_LAB_TOOL);
  assert.ok(fallback);
  assert.equal(fallback.needsProfile, false);
  // Removed with their API routes (release 8e560ef), or moved to Portfolio's Risk tab (focus-candidates).
  for (const gone of ['covariance', 'source-availability', 'connected-markets', 'instrument-master', 'sensitivity', 'focus-candidates']) {
    assert.ok(!LAB_TOOL_IDS.includes(gone), gone);
    assert.equal(readTabParam(`?tool=${gone}`, 'tool', LAB_TOOL_IDS, DEFAULT_LAB_TOOL), DEFAULT_LAB_TOOL, gone);
  }
  assert.equal(readTabParam('?tool=joint-plan', 'tool', LAB_TOOL_IDS, DEFAULT_LAB_TOOL), 'joint-plan');
  assert.equal(readTabParam('', 'tool', LAB_TOOL_IDS, DEFAULT_LAB_TOOL), DEFAULT_LAB_TOOL);
});
