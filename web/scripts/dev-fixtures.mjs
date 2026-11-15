// `npm run dev:fixtures`: next dev with NEXT_PUBLIC_APLOMB_FIXTURES=true, on Windows, macOS and Linux
// (POSIX inline variables do not work in cmd.exe). Extra arguments are passed to next dev.
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const next = require.resolve('next/dist/bin/next');
const child = spawn(process.execPath, [next, 'dev', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: { ...process.env, NEXT_PUBLIC_APLOMB_FIXTURES: 'true' },
});
child.on('exit', code => process.exit(code ?? 1));
