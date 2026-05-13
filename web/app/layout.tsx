import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'HivisionIDPhotos Precision Studio',
  description: 'Phase 0/1 multi-platform web scaffold for ID photo processing.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
