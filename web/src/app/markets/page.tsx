import type { Metadata } from 'next';
import { Redirect } from '../../components/common/Redirect';
import { MOVED_ROUTES } from '../../lib/redirect';

export const metadata: Metadata = { title: 'Decide' };

// Markets moved: instrument research lives in Decide, connector research in Labs.
export default function Page() {
  return <Redirect to={MOVED_ROUTES['/markets/']} label={{ en: 'Decide', fr: 'Décider' }} />;
}
