'use client'

import { Check, ShieldCheck } from 'lucide-react'
import { AUDIT, money } from '@/lib/tyndale-data'
import { ThreeNumbers } from './three-numbers'
import { AmbientAuras } from './glass'

/*
 * THE REVEAL (moment #1) — a designed event, not a chat bubble.
 * Full-width, visually distinct. Three numbers, hero in money green.
 */
export function RevealCard() {
  return (
    <section
      aria-label="Your audit results"
      className="animate-pop relative isolate overflow-hidden rounded-3xl bg-gradient-to-br from-navy to-primary p-1.5 shadow-float"
    >
      <AmbientAuras variant="money" />
      <div className="relative rounded-[20px] px-5 pb-2 pt-5">
        <p className="text-sm font-semibold uppercase tracking-wide text-navy-foreground/60">
          Your audit is complete
        </p>
        <h3 className="mt-1 font-display text-2xl font-bold text-navy-foreground">
          Here&apos;s what I found.
        </h3>
      </div>
      <div className="relative p-1.5">
        <ThreeNumbers glass />
      </div>
      <p className="relative px-5 pb-4 pt-2 text-center text-[13px] text-navy-foreground/70">
        Your findings are complete and free — nothing teased, nothing held back.
      </p>
    </section>
  )
}

/*
 * THE UNLOCK (moment #2) — persuades with specificity, never pressure.
 * The paywall gates the plan, never the truth.
 */
export function UnlockCard({
  onUnlock,
  unlocked,
}: {
  onUnlock: () => void
  unlocked: boolean
}) {
  return (
    <section
      aria-label="Unlock your resolution plan"
      className="animate-rise overflow-hidden rounded-3xl bg-card shadow-float ring-1 ring-border"
    >
      <div className="bg-money-soft px-5 py-5">
        <p className="font-display text-xl font-bold leading-snug text-money">
          {money(AUDIT.gap)} of this shouldn&apos;t be yours to pay.
        </p>
      </div>
      <div className="px-5 py-5">
        <p className="text-[16px] leading-relaxed text-foreground">
          Unlock your resolution plan — who to call, exactly what to say, every
          deadline — <span className="font-semibold">$4.99, one time.</span>
        </p>
        <ul className="mt-4 flex flex-col gap-2.5">
          {[
            'Every call script, written for you',
            'Every deadline tracked',
            'Your case stays open until it\u2019s resolved',
          ].map((line) => (
            <li key={line} className="flex items-start gap-2.5 text-[15px] text-foreground">
              <Check className="mt-0.5 h-5 w-5 shrink-0 text-money" aria-hidden="true" />
              <span>{line}</span>
            </li>
          ))}
        </ul>

        <button
          type="button"
          onClick={onUnlock}
          disabled={unlocked}
          className="mt-5 flex min-h-[52px] w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground shadow-soft transition hover:brightness-110 disabled:opacity-70"
        >
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          {unlocked ? 'Unlocked — see your plan below' : 'Unlock my plan · $4.99'}
        </button>

        <p className="mt-3 text-center text-[13px] text-muted-foreground">
          One payment. No timers. Your audit stays free.
        </p>
        <p className="mt-2 text-center text-[13px] text-muted-foreground">
          Fixing bills often? Core is $14.99/mo.
        </p>
      </div>
    </section>
  )
}
