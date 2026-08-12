import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Wordmark } from './brand'

/* Wordmark already renders its own <Link href="/">, so it is not wrapped here. */

export function AppHeader({
  backHref,
  backLabel = 'Back',
  right,
}: {
  backHref?: string
  backLabel?: string
  right?: React.ReactNode
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-2xl items-center gap-2 px-4">
        {backHref ? (
          <Link
            href={backHref}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-foreground/70 transition-colors hover:bg-muted"
            aria-label={backLabel}
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
        ) : (
          <Wordmark tone="dark" />
        )}
        <div className="min-w-0 flex-1" />
        {right}
      </div>
    </header>
  )
}
