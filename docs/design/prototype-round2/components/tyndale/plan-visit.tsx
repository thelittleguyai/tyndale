'use client'

import { Check, Circle, MapPin, Phone } from 'lucide-react'
import { VISIT_PLAN, type VisitCheckItem } from '@/lib/tyndale-data'
import { cn } from '@/lib/utils'
import { AppHeader } from './app-header'
import { FeatureIntro, PageAmbience } from './glass'

const STATUS_META: Record<
  VisitCheckItem['status'],
  { ring: string; icon: typeof Check; chip: string; chipCls: string }
> = {
  done: {
    ring: 'bg-money/12 text-money',
    icon: Check,
    chip: 'Confirmed',
    chipCls: 'bg-money-soft text-money',
  },
  action: {
    ring: 'bg-severity-med-bg text-severity-med',
    icon: Circle,
    chip: 'Needs a call',
    chipCls: 'bg-severity-med-bg text-severity-med',
  },
  pending: {
    ring: 'bg-severity-neutral-bg text-severity-neutral',
    icon: Circle,
    chip: 'Good to know',
    chipCls: 'bg-severity-neutral-bg text-severity-neutral',
  },
}

export function PlanVisit() {
  return (
    <div className="min-h-dvh bg-background">
      <PageAmbience variant="warm" />
      <AppHeader backHref="/home" />
      <main className="mx-auto w-full max-w-2xl px-5 pb-28 pt-6">
        <FeatureIntro
          icon={<MapPin className="h-5 w-5" aria-hidden="true" />}
          eyebrow="Plan a Visit"
          title="Walk in knowing what's covered."
          subtitle={
            <>
              For your visit to {VISIT_PLAN.provider} on {VISIT_PLAN.date},
              here&apos;s what to lock down first — so nothing surprises you on
              the bill.
            </>
          }
        />

        <div className="mt-6 flex flex-col gap-3">
          {VISIT_PLAN.items.map((item) => {
            const meta = STATUS_META[item.status]
            const Icon = meta.icon
            return (
              <article
                key={item.id}
                className="glass-tile rounded-3xl p-4"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={cn(
                      'flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
                      meta.ring,
                    )}
                  >
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-semibold text-foreground">
                        {item.label}
                      </h2>
                      <span
                        className={cn(
                          'rounded-full px-2.5 py-0.5 text-[12px] font-semibold',
                          meta.chipCls,
                        )}
                      >
                        {meta.chip}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[14px] leading-relaxed text-muted-foreground">
                      {item.detail}
                    </p>
                    {item.action && (
                      <button className="mt-3 inline-flex min-h-[44px] items-center gap-2 rounded-full bg-primary px-4 text-[14px] font-semibold text-primary-foreground transition hover:brightness-110">
                        <Phone className="h-4 w-4" aria-hidden="true" />
                        {item.action}
                      </button>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>

        <p className="mt-6 rounded-xl bg-accent px-4 py-3 text-[14px] leading-relaxed text-foreground">
          Bring back what you learn — I&apos;ll keep it on file for the visit,
          so if a bill shows up later, we already know what was supposed to
          happen.
        </p>
      </main>
    </div>
  )
}
