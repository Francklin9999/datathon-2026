import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
// Local, OFL-licensed font files (no build-time network). Instrument Sans with weight and width axes.
import '@fontsource-variable/instrument-sans/wdth.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './globals.css';
import { AppProvider } from '../state/app';
import { FactDrawerProvider } from '../components/common/FactDrawer';
import { AppShell } from '../components/shell/AppShell';
import { UiProviders } from '../components/ui/ThemeProvider';
import { MOTION_BOOT_SCRIPT, SIDEBAR_BOOT_SCRIPT, THEME_BOOT_SCRIPT } from '../lib/ui/theme';

export const metadata: Metadata = {
  title: { default: 'Aplomb — simulation only', template: '%s · Aplomb' },
  description: 'Fictional-profile portfolio decision audit. Simulation only. Not financial advice.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ECEFF5' },
    { media: '(prefers-color-scheme: dark)', color: '#0B0D12' },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // data-theme / data-sidebar / data-motion are set by the boot script before hydration, hence the suppressed warning.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT + SIDEBAR_BOOT_SCRIPT + MOTION_BOOT_SCRIPT }} />
      </head>
      <body>
        <AppProvider>
          <UiProviders>
            <FactDrawerProvider>
              <AppShell>{children}</AppShell>
            </FactDrawerProvider>
          </UiProviders>
        </AppProvider>
      </body>
    </html>
  );
}
