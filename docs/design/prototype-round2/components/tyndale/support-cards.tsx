'use client'

import { useState } from 'react'
import { Clock, FilePlus2, Check, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AUDIT, money } from '@/lib/tyndale-data'

/* Dark deadline banner (navy) — §4.7. Never alarmist. */
export function DeadlineBanner({
  recovered = 0,
}: {
  recovered?: number
}) {
  return (
    <div className="rounded-2xl bg-navy p-5 text-navy-foreground">
      <div className="flex items-center gap-2 text-sm font-semibold text-navy-foreground/70">
        <Clock className="h-4 w-4" aria-hidden="true" />
        Where your case stands
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm text-navy-foreground/60">Insurer response due</p>
          <p className="mt-1 font-display text-2xl font-bold">{AUDIT.responseDeadline}</p>
        </div>
        <div>
          <p className="text-sm text-navy-foreground/60">Recovered so far</p>
          <p className="mt-1 font-display text-2xl font-bold text-money-soft">
            {money(recovered)}
          </p>
        </div>
      </div>
      <div className="mt-4 border-t border-white/10 pt-4">
        <p className="text-sm text-navy-foreground/60">Open items</p>
        <p className="mt-1 text-[15px] leading-relaxed">
          Waiting on Blue Shield to reprocess the duplicate MRI and coinsurance
          rate. Nothing for you to do right now.
        </p>
      </div>
      <p className="mt-4 rounded-lg bg-white/5 px-3 py-2.5 text-[15px] leading-relaxed">
        I&apos;ll nudge you Thursday unless it&apos;s resolved — you don&apos;t
        have to remember any of this.
      </p>
    </div>
  )
}

/* Have / need checklist — §4.3 needs-something state. */
type NeedItem = { id: string; label: string; have: boolean; unlocks: string }

export function ChecklistCard({
  onAddDocument,
}: {
  onAddDocument?: () => void
}) {
  const items: NeedItem[] = [
    { id: 'bill', label: 'Bill', have: true, unlocks: 'Got it — this is where I started.' },
    {
      id: 'eob',
      label: 'EOB',
      have: false,
      unlocks: "here's how to get it in 2 minutes",
    },
    {
      id: 'itemized',
      label: 'Itemized bill',
      have: false,
      unlocks: "here's the script to request it",
    },
  ]
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] font-semibold text-foreground">
        To lock in the numbers I need two things:
      </p>
      <ul className="mt-3 flex flex-col gap-3">
        {items.map((it) => (
          <li key={it.id} className="flex items-start gap-3">
            {it.have ? (
              <Check className="mt-0.5 h-5 w-5 shrink-0 text-money" aria-hidden="true" />
            ) : (
              <Circle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
            <span>
              <span
                className={cn(
                  'text-[15px] font-semibold',
                  it.have ? 'text-foreground' : 'text-foreground',
                )}
              >
                {it.label}
              </span>
              <span className="ml-1.5 text-[15px] text-muted-foreground">
                — {it.unlocks}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onAddDocument}
        className="mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl border border-primary bg-background px-4 text-[16px] font-semibold text-primary transition hover:bg-accent"
      >
        <FilePlus2 className="h-5 w-5" aria-hidden="true" />
        Add document
      </button>
      <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
        Add them here whenever they arrive — I&apos;ll pick up right where we
        left off.
      </p>
    </div>
  )
}

const RELATIONSHIPS = [
  'Spouse/partner',
  'Parent/legal guardian',
  'Adult child or family caregiver',
  'Healthcare power of attorney',
  'Guardian/conservator',
  'Executor/administrator',
  'Other',
]

/* Relationship-menu selector — branch B1 attest flow. */
export function RelationshipMenu() {
  const [selected, setSelected] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [declined, setDeclined] = useState(false)

  if (declined) {
    return (
      <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
        <p className="text-[15px] leading-relaxed text-foreground">
          No problem — I can only audit a bill with the patient&apos;s okay. The
          fastest path is for {AUDIT.patient} to start their own file and add you
          later. I&apos;ll keep this here so you can pick up right where we left
          off.
        </p>
        <button
          type="button"
          onClick={() => setDeclined(false)}
          className="mt-4 min-h-[44px] rounded-xl border border-border px-4 text-[15px] font-semibold text-foreground hover:bg-muted"
        >
          Back
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] font-semibold text-foreground">
        What&apos;s your relationship to {AUDIT.patient}?
      </p>
      <div className="mt-3 flex flex-col gap-2">
        {RELATIONSHIPS.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => {
              setSelected(r)
              setConfirmed(false)
            }}
            aria-pressed={selected === r}
            className={cn(
              'min-h-[48px] rounded-xl px-4 text-left text-[15px] font-medium ring-1 transition',
              selected === r
                ? 'bg-primary text-primary-foreground ring-primary'
                : 'bg-background text-foreground ring-border hover:bg-muted',
            )}
          >
            {r}
          </button>
        ))}
      </div>

      {selected && !confirmed && (
        <button
          type="button"
          onClick={() => setConfirmed(true)}
          className="mt-4 min-h-[48px] w-full rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground transition hover:brightness-110"
        >
          Confirm — I&apos;m the {selected.toLowerCase()} and authorized
        </button>
      )}

      {confirmed && (
        <p className="mt-4 rounded-lg bg-money-soft px-3 py-2.5 text-[15px] font-medium text-money">
          Thank you — that&apos;s all I needed. Digging into {AUDIT.patient}&apos;s
          bill now.
        </p>
      )}

      <button
        type="button"
        onClick={() => setDeclined(true)}
        className="mt-3 text-[14px] font-medium text-muted-foreground underline underline-offset-4"
      >
        I&apos;d rather not attest to this
      </button>
    </div>
  )
}
