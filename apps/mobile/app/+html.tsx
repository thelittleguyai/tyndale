/**
 * Static HTML root for the web export (Expo Router `+html.tsx`).
 *
 * The tab used to show the bare URL with a generic globe: the export emitted an EMPTY
 * managed <title> and no icon link. The <title> itself lives in the root layout's <Head>
 * (expo-router/head) so routes can override it; this file carries the static, route-
 * independent head: favicons (generated from the shared logo SVG into public/), the
 * application name, and the theme colour (brand teal, A1).
 */

import { ScrollViewStyleReset } from 'expo-router/html';
import type { PropsWithChildren } from 'react';

import { brand } from '@tyndale/shared';

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
        <meta name="application-name" content="Tyndale" />
        <meta name="apple-mobile-web-app-title" content="Tyndale" />
        <meta name="theme-color" content={brand.teal} />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
        <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
        {/* Keeps the body from scrolling on web so ScrollViews behave like native. */}
        <ScrollViewStyleReset />
      </head>
      <body>{children}</body>
    </html>
  );
}
