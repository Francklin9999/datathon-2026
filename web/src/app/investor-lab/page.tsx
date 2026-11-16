import { Suspense } from 'react';
import type { Metadata } from 'next';
import { InvestorLabPage } from '../../features/investor-lab/InvestorLabPage';

export const metadata: Metadata = { title: 'Investor Lab' };

export default function Page() {
  return <Suspense><InvestorLabPage /></Suspense>;
}
