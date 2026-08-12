import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { Wordmark } from '@/components/tyndale/brand'
import { UploadFlow } from '@/components/tyndale/upload-flow'

export default function UploadPage() {
  return (
    <div className="min-h-dvh bg-background">
      <header className="sticky top-0 z-30 bg-navy text-navy-foreground">
        <div className="mx-auto flex h-16 w-full max-w-md items-center justify-between px-4">
          <Link
            href="/"
            className="inline-flex h-11 w-11 items-center justify-center rounded-full text-navy-foreground/80 hover:bg-white/10"
            aria-label="Back to home"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
          <Wordmark tone="light" />
          <span className="w-11" aria-hidden="true" />
        </div>
      </header>
      <UploadFlow />
    </div>
  )
}
