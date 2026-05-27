import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { ScaffoldBanner } from '@/components/scaffold-banner';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Tyndale — Welcome to the App',
  description:
    'Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice.',
  metadataBase: new URL('https://tyndaleapp.net'),
};

const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
const plausibleScript =
  process.env.NEXT_PUBLIC_PLAUSIBLE_SCRIPT ?? 'https://plausible.io/js/script.js';
// Privacy-respecting first-party analytics only. Load Plausible in production with
// a configured domain; never in dev (keeps dev traffic out of analytics).
const loadPlausible = process.env.NODE_ENV === 'production' && Boolean(plausibleDomain);

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased">
        <ScaffoldBanner />
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
