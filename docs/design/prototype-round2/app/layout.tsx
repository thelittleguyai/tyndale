import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Figtree, Public_Sans } from 'next/font/google'
import { CaseProvider } from '@/components/tyndale/case-provider'
import { ChatBubble } from '@/components/tyndale/chat-bubble'
import './globals.css'

// Sans-serif everywhere to meet the accessibility floor (§2): Figtree for
// display/headings, Public Sans for body — two sans families, high legibility.
const figtree = Figtree({
  subsets: ['latin'],
  variable: '--font-figtree',
  display: 'swap',
})

const publicSans = Public_Sans({
  subsets: ['latin'],
  variable: '--font-public-sans',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Tyndale — Find what medical bills hide',
  description:
    'Tyndale is an AI medical-bill auditor and advocate. Upload your bill and we independently compute what you should actually owe, name the errors with sources, and coach you through fixing it.',
  generator: 'v0.app',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#1d2a38',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${figtree.variable} ${publicSans.variable} bg-background`}>
      <body className="font-sans antialiased">
        <CaseProvider>
          {children}
          <ChatBubble />
        </CaseProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
