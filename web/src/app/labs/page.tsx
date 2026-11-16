import type { Metadata } from 'next';
import { LabsPage } from '../../features/labs/LabsPage';

export const metadata: Metadata = { title: 'Labs' };

// ?tool= is read on the client; the static shell renders the default tool (web/SPEC.md §4).
export default function Page() {
  return <LabsPage />;
}
