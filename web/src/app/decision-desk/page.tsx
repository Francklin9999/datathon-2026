import { Suspense } from 'react';
import { DecisionDeskPage } from '../../features/decision/DecisionDeskPage';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Decide' };

// ?runId= is read on the client; the static shell renders without it (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <DecisionDeskPage />
    </Suspense>
  );
}
