'use client'

import { Check, HelpCircle, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Verification } from '@/lib/tyndale-data'
import type { VerifyAnswer } from './case-provider'

const options: {
  value: VerifyAnswer
  label: string
  icon: React.ReactNode
  active: string
}[] = [
  {
    value: 'yes',
    label: 'Yes',
    icon: <Check className="h-5 w-5" aria-hidden="true" />,
    active: 'bg-money text-white ring-money',
  },
  {
    value: 'no',
    label: 'No',
    icon: <X className="h-5 w-5" aria-hidden="true" />,
    active: 'bg-severity-high text-white ring-severity-high',
  },
  {
    value: 'notsure',
    label: 'Not sure',
    icon: <HelpCircle className="h-5 w-5" aria-hidden="true" />,
    active: 'bg-severity-neutral text-white ring-severity-neutral',
  },
]

export function VerificationCard({
  item,
  answer,
  onAnswer,
}: {
  item: Verification
  answer?: VerifyAnswer
  onAnswer: (a: VerifyAnswer) => void
}) {
  return (
    <div className="rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border">
      <p className="text-[16px] font-semibold text-foreground">{item.line}</p>
      <p className="mt-0.5 text-[15px] text-muted-foreground">{item.aside}</p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {options.map((o) => {
          const selected = answer === o.value
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onAnswer(o.value)}
              aria-pressed={selected}
              className={cn(
                'flex min-h-[52px] flex-col items-center justify-center gap-1 rounded-xl px-2 py-2.5 text-sm font-semibold ring-1 transition',
                selected
                  ? o.active
                  : 'bg-background text-foreground ring-border hover:bg-muted',
              )}
            >
              {o.icon}
              {o.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

/* Pre-selected variant: user typed a correction; Tyndale mapped it and asks
 * for one confirming tap (§4.3). */
export function PreSelectedVerificationCard({
  onConfirm,
  confirmed,
}: {
  onConfirm: () => void
  confirmed?: boolean
}) {
  return (
    <div className="rounded-2xl bg-card p-4 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        Sounds like the MRI charge — I&apos;ve marked{' '}
        <span className="font-semibold text-severity-high">
          &ldquo;No, this didn&apos;t happen.&rdquo;
        </span>{' '}
        Tap confirm and I&apos;ll factor it in.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-severity-high-bg px-3 py-1.5 text-[13px] font-semibold text-severity-high">
          <X className="h-4 w-4" aria-hidden="true" />
          No, this didn&apos;t happen
        </span>
      </div>
      <button
        type="button"
        onClick={onConfirm}
        disabled={confirmed}
        className="mt-3 min-h-[48px] w-full rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground transition hover:brightness-110 disabled:opacity-60"
      >
        {confirmed ? 'Confirmed — thank you' : 'Confirm'}
      </button>
    </div>
  )
}
