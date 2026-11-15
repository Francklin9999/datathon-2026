import { ProfilesPage } from '../../features/profiles/ProfilesPage';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Profiles' };

export default function Page() {
  return <ProfilesPage />;
}
