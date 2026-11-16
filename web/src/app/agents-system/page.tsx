import type { Metadata } from 'next';
import { Suspense } from 'react';
import { AgentsSystemPage } from '../../features/system/AgentsSystemPage';

export const metadata: Metadata = { title: 'System' };

// ?runId= is read on the client; the static shell renders without it (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <AgentsSystemPage />
    </Suspense>
  );
}
