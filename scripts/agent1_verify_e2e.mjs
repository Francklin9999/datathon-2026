/** Run against isolated API 8101, the production static site on 3101 and fresh Chrome on 9321. */
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';

const output = process.env.APLOMB_QA_OUTPUT || 'docs/evidence/parallel/agent-1/reverification';
await fs.mkdir(path.join(output, 'browser'), { recursive: true });
async function run(name, command, args, browser = false) {
  const log = await fs.open(path.join(output, `${name}.log`), 'w');
  try {
    await new Promise((resolve, reject) => {
      const child = spawn(command, args, {
        env: { ...process.env, APLOMB_QA_OUTPUT: browser ? path.join(output, 'browser') : output },
        stdio: ['ignore', log.fd, log.fd],
      });
      child.on('error', reject);
      child.on('exit', code => code === 0 ? resolve() : reject(new Error(`${name} exited ${code}; inspect ${output}/${name}.log`)));
    });
  } finally { await log.close(); }
  console.log(`PASS ${name}`);
}
await run('http-existing', 'uv', ['run', 'python', 'scripts/agent1_http_smoke.py']);
await run('http-expanded', 'uv', ['run', 'python', 'scripts/agent1_completion_http.py']);
await run('browser-existing', 'node', ['scripts/agent1_browser_extended.mjs'], true);
await run('browser-expanded', 'node', ['scripts/agent1_browser_completion.mjs'], true);
await run('browser-tooltip', 'node', ['scripts/agent1_browser_smoke.mjs'], true);

const read = async name => JSON.parse(await fs.readFile(path.join(output, name), 'utf8'));
const oldHttp = await read('http-smoke.json'), expandedHttp = await read('completion-http.json');
const requests = [...oldHttp.checks, ...expandedHttp.checks];
const inventory = JSON.parse(await fs.readFile('docs/evidence/parallel/agent-1/added-http-routes.json', 'utf8'));
const coverage = inventory.routes.map(route => {
  const pattern = new RegExp(`^${route.path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\\{[^}]+\\\}/g, '[^/]+')}$`);
  const matches = requests.filter(r => r.method === route.method && pattern.test(`/v1${r.path.split('?')[0]}`));
  return { ...route, requests: matches.length, statuses: [...new Set(matches.map(r => r.status))],
    positiveResponse: matches.some(r => r.status >= 200 && r.status < 300) };
});
const missing = coverage.filter(route => !route.requests);
if (missing.length) throw new Error(`Routes without real HTTP acceptance: ${JSON.stringify(missing)}`);
const browser = await read('browser/browser-completion.json');
const summary = { createdAt: new Date().toISOString(), syntheticInputs: true, liveModel: false,
  httpRequests: requests.length, addedRoutesExercised: coverage.length, coverage,
  browserChecks: browser.checks.length, mobile: browser.widths, browserErrors: browser.errors,
  browserExistingChecks: (await read('browser/browser-extended.json')).checks.length,
  tooltipChecks: (await read('browser/browser-interactions.json')).checks.length,
  limitations: ['Provider capture/inspection are exercised in their default permission-denied state. Synthetic source-capture success, integrity and isolation are tested separately in the Python suite; live permission-gated acquisition is not claimed.'] };
await fs.writeFile(path.join(output, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log(JSON.stringify({ httpRequests: requests.length, addedRoutesExercised: coverage.length, browserChecks: browser.checks.length }));
