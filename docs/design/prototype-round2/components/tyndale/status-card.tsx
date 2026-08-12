'use client'

import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const STAGES = [
  'Reading your bill',
  'Checking each charge',
  "Comparing your insurer's math",
  'Writing your summary',
]

/*
 * ONE status card that updates in place. Four labeled bars fill sequentially.
 * A bar only completes when its stage is done — no fake percentages.
 * Auto-advances for the prototype, then calls onComplete.
 */
export function StatusCard({ onComplete }: { onComplete?: () => void }) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    if (stage >= STAGES.length) {
      const t = setTimeout(() => onComplete?.(), 700)
      return () => clearTimeout(t)
    }
    const t = setTimeout(() => setStage((s) => s + 1), 1600)
    return () => clearTimeout(t)
  }, [stage, onComplete])

  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        {stage < STAGES.length ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />
        ) : (
          <Check className="h-4 w-4 text-money" aria-hidden="true" />
        )}
        {stage < STAGES.length ? 'Working on your audit' : 'Audit ready'}
      </div>

      <ul className="mt-4 flex flex-col gap-3.5" aria-live="polite">
        {STAGES.map((label, i) => {
          const done = i < stage
          const active = i === stage
          return (
            <li key={label}>
              <div className="mb-1.5 flex items-center gap-2 text-[15px]">
                {done ? (
                  <Check className="h-4 w-4 text-money" aria-hidden="true" />
                ) : active ? (
                  <Loader2
                    className="h-4 w-4 animate-spin text-primary"
                    aria-hidden="true"
                  />
                ) : (
                  <span
                    className="h-4 w-4 rounded-full border border-border"
                    aria-hidden="true"
                  />
                )}
                <span
                  className={cn(
                    done || active ? 'text-foreground' : 'text-muted-foreground',
                    active && 'font-semibold',
                  )}
                >
                  {label}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    'h-full rounded-full bg-primary transition-all duration-500',
                    done && 'w-full',
                    active && 'w-2/3 animate-pulse',
                    !done && !active && 'w-0',
                  )}
                />
              </div>
            </li>
          )
        })}
      </ul>

      <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
        This takes a few minutes — you can leave; I&apos;ll email you the moment
        it&apos;s ready.
      </p>
    </div>
  )
}
