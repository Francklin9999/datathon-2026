import { OwnedElsewhere } from '../../components/common/OwnedElsewhere';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'World Explorer' };

// Skeleton only: T15 owns the World Explorer body (web/page-specs/world-explorer.md).
export default function Page() {
  return <OwnedElsewhere title={{ en: 'World Explorer', fr: 'Explorateur mondial' }} flag="world_explorer" owner="T15" spec="web/page-specs/world-explorer.md" />;
}
