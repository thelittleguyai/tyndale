'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ChevronDown, Phone, Target } from 'lucide-react'
import { cn } from '@/lib/utils'
import { money, PLAN_STEPS } from '@/lib/tyndale-data'

type PlanStep = (typeof PLAN_STEPS)[number]

export function ActionCard({ step }: { step: PlanStep }) {
  const [open, setOpen] = useState(false)
  const callable = step.phone !== ''

  return (
    <div className="overflow-hidden rounded-2xl bg-card shadow-sm ring-1 ring-border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-4 text-left"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary font-display text-lg font-bold text-primary-foreground">
          {step.order}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[16px] font-semibold leading-snug text-foreground">
            {step.title}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[14px] text-muted-foreground">
            {step.targets > 0 && (
              <span className="inline-flex items-center gap-1 font-semibold text-money">
                <Target className="h-4 w-4" aria-hidden="true" />
                targets {money(step.targets)}
              </span>
            )}
            <span>{step.subtitle}</span>
          </span>
        </span>
        <ChevronDown
          className={cn(
            'h-5 w-5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="border-t border-border px-4 pb-4 pt-4">
          <ol className="flex flex-col gap-3">
            {step.script.map((s) => (
              <li key={s.heading}>
                <p className="text-[13px] font-semibold uppercase tracking-wide text-primary">
                  {s.heading}
                </p>
                <p className="mt-1 rounded-lg bg-muted px-3 py-2.5 text-[15px] leading-relaxed text-foreground">
                  {s.body}
                </p>
              </li>
            ))}
          </ol>

          {step.pushback.length > 0 && (
            <div className="mt-4">
              <p className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
                What they might say back
              </p>
              <ul className="mt-2 flex flex-col gap-2.5">
                {step.pushback.map((p) => (
                  <li
                    key={p.theyMight}
                    className="rounded-lg border border-border px-3 py-2.5"
                  >
                    <p className="text-[14px] font-medium text-muted-foreground">
                      {p.theyMight}
                    </p>
                    <p className="mt-1 text-[15px] leading-relaxed text-foreground">
                      <span className="font-semibold text-primary">You: </span>
                      {p.youSay}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {callable && (
            <Link
              href="/call"
              className="mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground transition hover:brightness-110"
            >
              <Phone className="h-5 w-5" aria-hidden="true" />
              Open call mode
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
