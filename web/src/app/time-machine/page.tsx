import { OwnedElsewhere } from '../../components/common/OwnedElsewhere';

// Skeleton only: T15 owns the Time Machine body (web/page-specs/time-machine.md).
export default function Page() {
  return <OwnedElsewhere title={{ en: 'Time Machine', fr: 'Machine à remonter le temps' }} flag="time_machine" owner="T15" spec="web/page-specs/time-machine.md" />;
}
