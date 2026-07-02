import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });

export const metadata: Metadata = {
  title: 'Tyndale Admin',
  description: 'Internal case-review console. Not a public surface.',
  robots: { index: false, follow: false },
};

const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
const plausibleScript =
  process.env.NEXT_PUBLIC_PLAUSIBLE_SCRIPT ?? 'https://plausible.io/js/script.js';
const loadPlausible = process.env.NODE_ENV === 'production' && Boolean(plausibleDomain);

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="bg-navy-deep font-sans text-white antialiased">
        {children}
        {loadPlausible && (
          <Script
            defer
            data-domain={plausibleDomain}
            src={plausibleScript}
            strategy="afterInteractive"
          />
        )}
      </body>
    </html>
  );
}
