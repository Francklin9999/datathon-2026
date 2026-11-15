import type { Metadata } from 'next';
import { Suspense } from 'react';
import { WorldExplorerPage } from '../../features/world/WorldExplorerPage';

export const metadata: Metadata = { title: 'World Explorer' };

// ?eventId=, ?country= and ?runId= are read on the client; the static shell renders without them (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <WorldExplorerPage />
    </Suspense>
  );
}
