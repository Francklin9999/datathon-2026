import { Suspense } from 'react';
import { SourcesPage } from '../../features/sources/SourcesPage';

// ?datasetId=&dataVersion= are read on the client (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <SourcesPage />
    </Suspense>
  );
}
