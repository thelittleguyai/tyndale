'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { cn } from '@/lib/utils'
import { DISCLAIMER } from '@/lib/tyndale-data'

/**
 * Brand mark: a verified document — navy circle ring around a document whose
 * text lines are swept by a green check. Ring and document render in
 * currentColor so the mark works on light (navy) and dark (cream) surfaces;
 * pass a text-* class to set the tone.
 */
export function TyndaleMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center text-navy',
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 48 48" fill="none" className="h-full w-full">
        {/* Circle ring */}
        <circle
          cx="24"
          cy="24"
          r="21"
          stroke="currentColor"
          strokeWidth="3.25"
        />
        {/* Document */}
        <rect
          x="14.5"
          y="11.5"
          width="19"
          height="25"
          rx="3.5"
          fill="currentColor"
        />
        {/* Text lines — top two full, third shortened where the check sweeps */}
        <g
          stroke="#98A2B3"
          strokeWidth="2.6"
          strokeLinecap="round"
          opacity="0.95"
        >
          <path d="M19 18.5h10" />
          <path d="M19 23.5h10" />
          <path d="M19 28.5h4.5" />
        </g>
        {/* Green check sweeping across the document's lower half */}
        <path
          d="M18.5 29.5l5.5 5.5 10-12.5"
          stroke="#34A853"
          strokeWidth="3.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

export function Wordmark({
  className,
  tone = 'light',
}: {
  className?: string
  tone?: 'light' | 'dark'
}) {
  return (
    <Link
      href="/"
      className={cn('inline-flex items-center gap-2.5', className)}
      aria-label="Tyndale home"
    >
      <TyndaleMark
        className={cn(
          'h-8 w-8',
          tone === 'light' ? 'text-navy-foreground' : 'text-navy',
        )}
      />
      <span
        className={cn(
          'font-display text-xl font-semibold tracking-tight',
          tone === 'light' ? 'text-navy-foreground' : 'text-foreground',
        )}
      >
        Tyndale
      </span>
    </Link>
  )
}

export function TopNav({
  cta,
}: {
  cta?: React.ReactNode
}) {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-30 text-navy-foreground transition-all duration-300',
        scrolled ? 'glass-dark' : 'bg-transparent',
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5">
        <Wordmark tone="light" />
        {cta}
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-border bg-navy text-navy-foreground/80">
      <div className="mx-auto w-full max-w-5xl px-5 py-10">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <Wordmark tone="light" />
          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <Link href="/upload" className="underline-offset-4 hover:underline">
              Check my bill
            </Link>
            <Link href="/home" className="underline-offset-4 hover:underline">
              My home
            </Link>
            <Link href="/thread" className="underline-offset-4 hover:underline">
              My case
            </Link>
          </nav>
        </div>
        <p className="mt-8 max-w-xl text-sm leading-relaxed text-navy-foreground/70">
          {DISCLAIMER}
        </p>
        <p className="mt-3 text-xs text-navy-foreground/50">
          © {new Date().getFullYear()} Tyndale. We work only for the patient.
        </p>
      </div>
    </footer>
  )
}
