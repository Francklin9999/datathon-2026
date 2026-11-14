import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import { ContractValidationError, validateContract } from '../src/contracts/validate.js';
import type { AplombContracts } from '../src/contracts/types.js';
import schema from '../../contracts/generated/schema.json' with { type: 'json' };

const root = fileURLToPath(new URL('../../', import.meta.url));
const readJson = (name: string): unknown => JSON.parse(readFileSync(path.join(root, name), 'utf8'));
const cases = readJson('contracts/validation-cases.json') as {
  name: string; contract: keyof AplombContracts; valid: boolean; payload: unknown;
}[];

for (const c of cases) {
  test(c.name, () => {
    if (c.valid) validateContract(c.contract, c.payload);
    else assert.throws(() => validateContract(c.contract, c.payload), ContractValidationError);
  });
}

test('all three fixture response envelopes validate without mutation', () => {
  for (const [name, contract] of [
    ['profiles.json', 'ProfilesResponse'],
    ['run.decision.robert-tsla-25.json', 'Run'],
    ['world.events.sample.json', 'WorldEventsResponse'],
  ] as const) {
    const fixture = readJson(`contracts/fixtures/${name}`);
    const copy = structuredClone(fixture);
    validateContract(contract, fixture);
    assert.deepEqual(fixture, copy);
  }
});

test('validated responses expose useful static types', () => {
  const response = validateContract('ProfilesResponse', readJson('contracts/fixtures/profiles.json'));
  assert.equal(response.items[0]?.profileId, 'robert');
  const run = validateContract('Run', readJson('contracts/fixtures/run.decision.robert-tsla-25.json'));
  assert.equal(run.flags.fixture, true);
  if (run.result?.kind === 'decision') {
    assert.equal(run.result.decision.verdict, 'conflict');
    assert.equal(run.result.decision.counts.conflict, 6);
  } else assert.fail('expected a decision result');
});

test('Python serialization is accepted by the web consumer end to end', () => {
  const python = path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const serialized = execFileSync(python, ['-c', `
import json
from pathlib import Path
from aplomb.contracts.registry import adapter
fixtures = [("ProfilesResponse", "profiles.json"), ("Run", "run.decision.robert-tsla-25.json"),
            ("WorldEventsResponse", "world.events.sample.json")]
print(json.dumps({name: adapter(name).validate_json(Path("contracts/fixtures", file).read_text()).to_wire()
                  for name, file in fixtures}))
`], { cwd: root, encoding: 'utf8' });
  const responses = JSON.parse(serialized) as Record<string, unknown>;
  for (const name of ['ProfilesResponse', 'Run', 'WorldEventsResponse'] as const) {
    validateContract(name, responses[name]);
  }
});

test('meta example contains every feature flag', () => {
  const text = readFileSync(path.join(root, 'contracts/api.md'), 'utf8');
  const examples = [...text.matchAll(/```json\n([\s\S]*?)```/g)].map(m => JSON.parse(m[1]!));
  const meta = examples.find(example => 'contractVersion' in example);
  validateContract('Meta', meta);
  delete meta.features.guardrails;
  assert.throws(() => validateContract('Meta', meta), ContractValidationError);
});

test('non-finite numbers and oversized batches are rejected', () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    assert.throws(() => validateContract('ProposedMove', {
      ticker: 'TSLA', sizePct: value, funding: { mode: 'new_money' },
    }), ContractValidationError);
  }
  assert.throws(() => validateContract('BatchCheckRequest', {
    items: Array(6).fill({ profileId: 'robert', move: null }),
  }), ContractValidationError);
});

test('generated types remain assignable to every documented schema', () => {
  const text = readFileSync(path.join(root, 'contracts/schemas.md'), 'utf8');
  const source = [...text.matchAll(/```ts\n([\s\S]*?)```/g)].map(m => m[1]).join('\n')
    .replace(/^(\s*)(type|interface) /gm, '$1export $2 ');
  const names = [...source.matchAll(/(?:type|interface) (\w+)/g)].map(m => m[1]!);
  const aliases = Object.keys(schema.$defs).filter(name => !names.includes(name))
    .map(name => `type ${name} = Generated.${name};`).join('\n');
  const checks = names.map(name =>
    `type Check_${name} = Assert<Generated.${name} extends Documented.${name} ? true : false>;`,
  ).join('\n');
  const filename = path.join(root, 'web/tests/documented-contracts.virtual.ts');
  const content = `import type * as Generated from '../src/contracts/types.js';
    namespace Documented { ${aliases}\n${source} }
    type Assert<T extends true> = T;\n${checks}`;
  const config = ts.readConfigFile(path.join(root, 'web/tsconfig.json'), ts.sys.readFile);
  const options = ts.parseJsonConfigFileContent(config.config, ts.sys, path.join(root, 'web')).options;
  // The virtual declaration check never emits or shares the Next.js build cache.
  options.incremental = false;
  const host = ts.createCompilerHost(options);
  const read = host.readFile.bind(host);
  host.readFile = file => file === filename ? content : read(file);
  const exists = host.fileExists.bind(host);
  host.fileExists = file => file === filename || exists(file);
  const program = ts.createProgram([filename], options, host);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.equal(diagnostics.length, 0, ts.formatDiagnosticsWithColorAndContext(diagnostics, {
    getCanonicalFileName: f => f, getCurrentDirectory: () => root, getNewLine: () => '\n',
  }));
});
