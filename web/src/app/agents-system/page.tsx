import { OwnedElsewhere } from '../../components/common/OwnedElsewhere';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Agents & System' };

// Skeleton only: T15 owns the Agents & System body (web/page-specs/agents-system.md).
export default function Page() {
  return <OwnedElsewhere title={{ en: 'Agents & System', fr: 'Agents et système' }} owner="T15" spec="web/page-specs/agents-system.md" />;
}
