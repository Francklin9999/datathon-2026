// Static export only (D-03, web/SPEC.md §4): no server runtime, rewrites, headers or image optimizer.
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not let `next dev` write AGENTS.md/CLAUDE.md into the repository.
  agentRules: false,
  // Contract JSON (schema + development fixtures) lives in ../contracts.
  turbopack: { root: repoRoot },
  outputFileTracingRoot: repoRoot,
};

export default nextConfig;
