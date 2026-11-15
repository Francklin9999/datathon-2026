import { StrategiesPage } from '../../features/strategies/StrategiesPage';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Strategies' };

export default function Page() {
  return <StrategiesPage />;
}
