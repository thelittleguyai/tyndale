'use client'

import Link from 'next/link'
import { ArrowLeft, Check, FileWarning, Upload } from 'lucide-react'
import { money, type RecordCase } from '@/lib/tyndale-data'
import { AppHeader } from './app-header'
import { AmbientAuras, PageAmbience } from './glass'

export function CaseSummary({ record }: { record: RecordCase }) {
  const resolved = record.status === 'resolved'

  return (
    <div className="min-h-dvh bg-background">
      <PageAmbience variant={resolved ? 'money' : 'calm'} />
      <AppHeader />

      <main className="mx-auto w-full max-w-2xl px-5 pb-24 pt-6">
        <Link
          href="/home"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Your home
        </Link>

        <header className="mt-4">
          <p className="text-sm text-muted-foreground">{record.date}</p>
          <h1 className="mt-1 text-balance font-serif text-2xl text-foreground">
            {record.provider}
          </h1>
          <p className="mt-1 text-muted-foreground">{record.service}</p>
        </header>

        {resolved ? (
          <section className="relative isolate mt-6 overflow-hidden rounded-3xl bg-gradient-to-br from-ink to-primary p-6 text-cream shadow-float">
            <AmbientAuras variant="money" />
            <div className="relative">
              <div className="flex items-center gap-2 text-money-soft">
                <Check className="h-5 w-5" aria-hidden="true" />
                <span className="text-sm font-medium">Resolved</span>
              </div>
              <p className="mt-3 text-sm text-cream/60">You got back</p>
              <p className="mt-1 font-serif text-5xl text-money-soft">
                {money(record.recovered)}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-cream/70">
                We caught a lab panel billed at the out-of-network rate. One call
                and a corrected claim later, the money came back to you.
              </p>
            </div>
          </section>
        ) : (
          <section className="glass-tile mt-6 rounded-3xl p-6">
            <div className="flex items-center gap-2 text-alert">
              <FileWarning className="h-5 w-5" aria-hidden="true" />
              <span className="text-sm font-medium">Needs your EOB</span>
            </div>
            <p className="mt-3 text-balance leading-relaxed text-foreground">
              I tried to pull your Explanation of Benefits from your insurer
              automatically, but their system wouldn&apos;t release it. This is
              the one time I need you to add it — so I can check the bill
              against what your plan should have paid.
            </p>
            <Link
              href="/upload"
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-transform active:scale-[0.99]"
            >
              <Upload className="h-4 w-4" aria-hidden="true" />
              Add the EOB
            </Link>
          </section>
        )}

        {/* Timeline */}
        <section className="mt-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            What happened
          </h2>
          <ol className="mt-4 flex flex-col">
            {(resolved
              ? [
                  'You uploaded the bill and your EOB.',
                  'I found the lab panel billed out-of-network.',
                  'You called Mercy General and asked for a reprocess.',
                  'The corrected claim came back — you were refunded $214.',
                ]
              : [
                  'You uploaded the bill from Valley Urgent Care.',
                  'I tried to pull your EOB from your insurer — their system wouldn\u2019t release it.',
                  'I need you to add the EOB so I can compare it against your plan.',
                ]
            ).map((step, i, arr) => (
              <li key={i} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-money/12 text-[11px] font-semibold text-money">
                    {i + 1}
                  </span>
                  {i < arr.length - 1 && (
                    <span className="my-1 w-px flex-1 bg-line" />
                  )}
                </div>
                <p className="pb-5 text-[15px] leading-relaxed text-foreground">
                  {step}
                </p>
              </li>
            ))}
          </ol>
        </section>

        <p className="mt-4 text-center text-xs leading-relaxed text-muted-foreground">
          Tyndale provides medical billing and coverage advocacy, not medical,
          legal, or financial advice.
        </p>
      </main>
    </div>
  )
}
