'use client';

import { PreferencesProvider } from '../lib/preferences';

export function Providers({ children }: { children: React.ReactNode }) {
  return <PreferencesProvider>{children}</PreferencesProvider>;
}
