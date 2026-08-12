'use client'

import { useState } from 'react'
import { Calculator, Info, Phone } from 'lucide-react'
import { ESTIMATE_EXAMPLE, money } from '@/lib/tyndale-data'
import { AppHeader } from './app-header'
import { CitationChip } from './primitives'
import { FeatureIntro, AmbientAuras, PageAmbience } from './glass'

export function EstimateCosts() {
  const [procedure, setProcedure] = useState(ESTIMATE_EXAMPLE.procedure)
  const [provider, setProvider] = useState(ESTIMATE_EXAMPLE.provider)
  const [showResult, setShowResult] = useState(false)

  return (
    <div className="min-h-dvh bg-background">
      <PageAmbience variant="money" />
      <AppHeader backHref="/home" />
      <main className="mx-auto w-full max-w-2xl px-5 pb-28 pt-6">
        <FeatureIntro
          icon={<Calculator className="h-5 w-5" aria-hidden="true" />}
          eyebrow="Estimate Costs"
          title="What should this actually cost you?"
          subtitle="Tell me the procedure and where. I'll estimate it against your plan status — not a list price."
        />

        <form
          className="mt-6 flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            setShowResult(true)
          }}
        >
          <label className="flex flex-col gap-1.5">
            <span className="text-[14px] font-semibold text-foreground">
              Procedure
            </span>
            <input
              value={procedure}
              onChange={(e) => setProcedure(e.target.value)}
              className="min-h-[52px] rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[14px] font-semibold text-foreground">
              Provider or facility
            </span>
            <input
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="min-h-[52px] rounded-xl border border-input bg-card px-4 text-[16px] text-foreground outline-none ring-primary/40 focus:ring-2"
            />
          </label>
          <button
            type="submit"
            className="min-h-[52px] rounded-2xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground shadow-soft transition hover:brightness-110"
          >
            Estimate my cost
          </button>
        </form>

        {showResult && (
          <section className="animate-rise mt-8">
            <div className="relative isolate overflow-hidden rounded-3xl bg-gradient-to-br from-navy to-primary p-6 text-navy-foreground shadow-float">
              <AmbientAuras variant="money" />
              <div className="relative">
                <p className="text-[13px] text-navy-foreground/70">
                  Your estimated cost
                </p>
                <p className="mt-1 font-display text-5xl font-bold text-money-soft">
                  {money(ESTIMATE_EXAMPLE.expected)}
                </p>
                <p className="mt-2 text-[14px] text-navy-foreground/70">
                  Likely range {money(ESTIMATE_EXAMPLE.low)}–
                  {money(ESTIMATE_EXAMPLE.high)} · list price{' '}
                  <span className="line-through">
                    {money(ESTIMATE_EXAMPLE.listPrice)}
                  </span>
                </p>
                <span className="mt-4 inline-flex rounded-full bg-white/10 px-3 py-1 text-[12px] font-semibold uppercase tracking-wide text-navy-foreground/80">
                  Estimate — not a guarantee
                </span>
              </div>
            </div>

            <div className="glass-tile mt-4 rounded-3xl p-5">
              <p className="text-[15px] leading-relaxed text-foreground">
                {ESTIMATE_EXAMPLE.rationale}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {ESTIMATE_EXAMPLE.sources.map((s) => (
                  <CitationChip key={s} source={s} />
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-start gap-3 rounded-3xl bg-accent p-4 shadow-soft">
              <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
              <div>
                <p className="text-[15px] font-semibold text-foreground">
                  Want a concrete price?
                </p>
                <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
                  Estimates get thin when a facility hasn&apos;t posted its
                  rates. Ask for a written &ldquo;good-faith estimate&rdquo; —
                  you&apos;re entitled to one.
                </p>
                <button className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-full border border-border bg-card px-4 text-[14px] font-semibold text-foreground transition hover:bg-muted">
                  <Phone className="h-4 w-4" aria-hidden="true" />
                  Get the call script
                </button>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
