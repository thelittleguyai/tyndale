'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { MessageCircle } from 'lucide-react'

/*
 * Persistent "Chat with Tyndale" bubble, bottom-right on every screen (§4.6).
 * Hidden on focused flows — the call screen, the thread itself, and the upload
 * intake — where a floating shortcut would be redundant or overlap the CTA.
 */
export function ChatBubble() {
  const pathname = usePathname()
  const hidden =
    pathname === '/call' || pathname === '/thread' || pathname === '/upload'
  if (hidden) return null

  return (
    <Link
      href="/thread"
      className="shadow-float fixed bottom-5 right-5 z-40 inline-flex min-h-[48px] items-center gap-2.5 rounded-full bg-primary px-5 py-3 text-[15px] font-semibold text-primary-foreground transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <MessageCircle className="h-5 w-5 animate-pulse" aria-hidden="true" />
      Chat with Tyndale
    </Link>
  )
}
