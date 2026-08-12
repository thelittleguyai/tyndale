'use client'

import { Phone, ShieldCheck, Star, Stethoscope } from 'lucide-react'
import { DOCTORS } from '@/lib/tyndale-data'
import { cn } from '@/lib/utils'
import { AppHeader } from './app-header'
import { FeatureIntro, PageAmbience } from './glass'

export function FindDoctor() {
  return (
    <div className="min-h-dvh bg-background">
      <PageAmbience variant="calm" />
      <AppHeader backHref="/home" />
      <main className="mx-auto w-full max-w-2xl px-5 pb-28 pt-6">
        <FeatureIntro
          icon={<Stethoscope className="h-5 w-5" aria-hidden="true" />}
          eyebrow="Find a Doctor"
          title="A doctor who's actually in your network."
          subtitle="Directories are often wrong, so I never just trust them. I'll tell you what to confirm before you book."
          image="/calm-clinic.png"
        />

        {/* Search controls (demo) */}
        <div className="mt-6 grid grid-cols-2 gap-3">
          <label className="col-span-2 flex flex-col gap-1.5">
            <span className="text-[14px] font-semibold text-foreground">Specialty</span>
            <select className="min-h-[52px] rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2">
              <option>Orthopedic surgery</option>
              <option>Sports medicine</option>
              <option>Primary care</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[14px] font-semibold text-foreground">Within</span>
            <select className="min-h-[52px] rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2">
              <option>10 miles</option>
              <option>25 miles</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[14px] font-semibold text-foreground">Plan</span>
            <select className="min-h-[52px] rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2">
              <option>Blue Shield PPO</option>
            </select>
          </label>
        </div>

        <div className="mt-6 flex flex-col gap-3">
          {DOCTORS.map((d) => {
            const confirmed = d.network.startsWith('Listed in-network')
            return (
              <article
                key={d.id}
                className="glass-tile rounded-3xl p-4 transition duration-300 hover:-translate-y-0.5 hover:shadow-float"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-semibold text-foreground">{d.name}</h2>
                    <p className="text-[13px] text-muted-foreground">
                      {d.specialty} · {d.distance}
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-[13px] font-semibold text-secondary-foreground">
                    <Star className="h-3.5 w-3.5 fill-amber text-amber" aria-hidden="true" />
                    {d.rating}
                    <span className="font-normal text-muted-foreground">
                      ({d.reviews})
                    </span>
                  </span>
                </div>

                <div
                  className={cn(
                    'mt-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-[13.5px] font-medium',
                    confirmed
                      ? 'bg-severity-med-bg text-severity-med'
                      : 'bg-severity-neutral-bg text-severity-neutral',
                  )}
                >
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  {d.network}
                </div>

                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className="text-[13px] text-muted-foreground">
                    {d.costSignal}
                  </span>
                  <button className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-primary px-4 text-[14px] font-semibold text-primary-foreground transition hover:brightness-110">
                    <Phone className="h-4 w-4" aria-hidden="true" />
                    Confirmation script
                  </button>
                </div>
              </article>
            )
          })}
        </div>

        <p className="mt-6 rounded-xl bg-muted px-4 py-3 text-[13px] leading-relaxed text-muted-foreground">
          Safety note: I only surface serious, verified sanctions — and none
          apply to these providers. A clean record here isn&apos;t medical
          advice; it just means nothing alarming is on file.
        </p>
      </main>
    </div>
  )
}
