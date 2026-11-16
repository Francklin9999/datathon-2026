import type { Metadata } from 'next';
import { Redirect } from '../../components/common/Redirect';
import { MOVED_ROUTES } from '../../lib/redirect';

export const metadata: Metadata = { title: 'Portfolio' };

// Risk moved to the Portfolio risk tab; the expert risk tools live in Labs.
export default function Page() {
  return <Redirect to={MOVED_ROUTES['/risk-intelligence/']} label={{ en: 'Portfolio, Risk', fr: 'Portefeuille, Risque' }} />;
}
