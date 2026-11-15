import { Suspense } from 'react';
import { EvidenceAuditPage } from '../../features/audit/EvidenceAuditPage';

// ?runId=&factId= are read on the client; the static shell renders without them (web/SPEC.md §4).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <EvidenceAuditPage />
    </Suspense>
  );
}
