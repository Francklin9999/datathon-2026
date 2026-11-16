import type { Metadata } from 'next';
import { Suspense } from 'react';
import { TimeMachinePage } from '../../features/timemachine/TimeMachinePage';

export const metadata: Metadata = { title: 'Replay' };

// ?runId= is read on the client; the static shell renders without it (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <TimeMachinePage />
    </Suspense>
  );
}
