import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
// Local, OFL-licensed font files (no build-time network). Variable Fraunces with optical size + SOFT axes.
import '@fontsource-variable/fraunces/full.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './globals.css';
import { AppProvider } from '../state/app';
import { FactDrawerProvider } from '../components/common/FactDrawer';
import { AppShell } from '../components/shell/AppShell';
import { AmbientBackground } from '../components/ui/AmbientBackground';
import { UiProviders } from '../components/ui/ThemeProvider';
import { MOTION_BOOT_SCRIPT, THEME_BOOT_SCRIPT } from '../lib/ui/theme';

export const metadata: Metadata = {
  title: { default: 'Aplomb — simulation only', template: '%s · Aplomb' },
  description: 'Fictional-profile portfolio decision audit. Simulation only. Not financial advice.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#E3E9EE' },
    { media: '(prefers-color-scheme: dark)', color: '#050E17' },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // data-theme / data-motion are set by the boot script before hydration, hence the suppressed warning.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT + MOTION_BOOT_SCRIPT }} />
      </head>
      <body>
        <AmbientBackground />
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
