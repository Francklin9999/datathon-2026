// `npm run dev:aws`: next dev against the deployed AWS API (infra/deploy/site.json), so AI-written
// briefs, analyses and text interpretation work locally without model IDs or AWS credentials on this
// machine. The API accepts http://localhost:3000 only, so keep the default port. Extra arguments are
// passed to next dev. Runs started here are real runs on the team's AWS account.
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const next = require.resolve('next/dist/bin/next');
const site = JSON.parse(readFileSync(new URL('../../infra/deploy/site.json', import.meta.url), 'utf8'));
console.log(`Aplomb web on http://localhost:3000 using the AWS API ${site.api_base}`);
const child = spawn(process.execPath, [next, 'dev', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: { ...process.env, NEXT_PUBLIC_APLOMB_API_BASE: site.api_base },
});
child.on('exit', code => process.exit(code ?? 1));
