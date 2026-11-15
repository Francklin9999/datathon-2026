import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { AppProvider } from '../state/app';
import { FactDrawerProvider } from '../components/common/FactDrawer';
import { AppShell } from '../components/shell/AppShell';

export const metadata: Metadata = {
  title: 'Aplomb — simulation only',
  description: 'Fictional-profile portfolio decision audit. Simulation only. Not financial advice.',
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#0F2233' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppProvider>
          <FactDrawerProvider>
            <AppShell>{children}</AppShell>
          </FactDrawerProvider>
        </AppProvider>
      </body>
    </html>
  );
}
