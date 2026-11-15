import { PortfolioPage } from '../../features/portfolio/PortfolioPage';
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Portfolio' };

export default function Page() {
  return <PortfolioPage />;
}
