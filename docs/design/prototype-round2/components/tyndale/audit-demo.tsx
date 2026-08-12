'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Check,
  Handshake,
  Phone,
  Quote,
  ScanLine,
  ShieldAlert,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { TyndaleMark } from './brand'

/**
 * Animated product demo — a looping, three-act visualization of the audit:
 *  Act 1 · Add your documents — realistic bills, schedule of benefits, and an
 *          insurance card funnel into the Tyndale intake node (Ramp-style)
 *  Act 2 · Tyndale audits (progress bars)
 *  Act 3 · Every bill sorted: Pay / Negotiate (with a sample script) /
 *          Overcharged (with a resolution plan)
 */

type Phase = 'add' | 'audit' | 'sort'

const PHASES: { id: Phase; label: string; caption: string }[] = [
  {
    id: 'add',
    label: 'Add your documents',
    caption:
      'Drop in every bill — plus your schedule of benefits and insurance card.',
  },
  {
    id: 'audit',
    label: 'Tyndale audits',
    caption:
      'Every line is recomputed against your plan\u2019s real rules and real rates.',
  },
  {
    id: 'sort',
    label: 'Every bill, sorted',
    caption:
      'Each bill comes back categorized — with the exact next step for every one.',
  },
]

/* Audit worklines shown as progress bars in act 2 */
const AUDIT_BARS = [
  'Reading every billed code',
  'Checking your plan\u2019s rules',
  'Comparing to real prices',
  'Recomputing the math',
]

const PHASE_MS: Record<Phase, number> = { add: 7800, audit: 5600, sort: 10500 }

/* ───────────────────────── Mini document mockups ───────────────────────── */

function MiniBill({
  provider,
  amount,
  className,
  style,
}: {
  provider: string
  amount: string
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      className={cn(
        'w-[124px] rounded-md border border-black/10 bg-white p-2.5 shadow-md',
        className,
      )}
      style={style}
    >
      <div className="flex items-center justify-between">
        <span className="truncate text-[8px] font-bold uppercase tracking-wide text-neutral-700">
          {provider}
        </span>
        <span className="text-[7px] font-semibold text-neutral-400">BILL</span>
      </div>
      <div className="mt-1.5 flex flex-col gap-1">
        <div className="h-1 w-full rounded-full bg-neutral-200" />
        <div className="h-1 w-4/5 rounded-full bg-neutral-200" />
        <div className="h-1 w-3/5 rounded-full bg-neutral-200" />
      </div>
      <div className="mt-1.5 flex items-center justify-between border-t border-neutral-200 pt-1">
        <span className="text-[7px] font-semibold uppercase text-neutral-400">
          Amount due
        </span>
        <span className="text-[10px] font-bold text-neutral-800">{amount}</span>
      </div>
    </div>
  )
}

function MiniSoB({
  className,
  style,
}: {
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      className={cn(
        'w-[134px] rounded-md border border-black/10 bg-white p-2.5 shadow-md',
        className,
      )}
      style={style}
    >
      <p className="text-[8px] font-bold uppercase tracking-wide text-primary">
        Schedule of Benefits
      </p>
      <div className="mt-1.5 flex flex-col gap-[3px]">
        {[
          ['Deductible', '$2,000'],
          ['OOP max', '$5,000'],
          ['Specialist', '$50'],
          ['Imaging', '20%'],
        ].map(([k, v]) => (
          <div key={k} className="flex items-center justify-between">
            <span className="text-[7.5px] text-neutral-500">{k}</span>
            <span className="text-[7.5px] font-bold text-neutral-800">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MiniInsuranceCard({
  className,
  style,
}: {
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      className={cn(
        'w-[134px] overflow-hidden rounded-md border border-black/10 bg-white shadow-md',
        className,
      )}
      style={style}
    >
      <div className="flex items-center justify-between bg-navy px-2 py-1">
        <span className="text-[7.5px] font-bold uppercase tracking-wide text-navy-foreground">
          Blue Shield PPO
        </span>
        <span className="h-2 w-3 rounded-[2px] bg-money-soft/80" />
      </div>
      <div className="p-2">
        <p className="text-[8px] font-bold text-neutral-800">SARAH MITCHELL</p>
        <p className="mt-0.5 text-[7.5px] text-neutral-500">
          ID: XPL-4821-9930
        </p>
        <div className="mt-1 flex gap-2">
          <span className="text-[7px] text-neutral-400">GRP 44120</span>
          <span className="text-[7px] text-neutral-400">RxBIN 610502</span>
        </div>
      </div>
    </div>
  )
}

/* ─────────────── Act 1 · Funnel canvas (fixed-coordinate stage) ─────────── */

/* Canvas is 520 x 300. The intake node sits centered at (260, 234).
   Each doc's (--fx, --fy) is the vector from its own center to the node. */
const FUNNEL_DOCS: {
  id: string
  kind: 'bill' | 'sob' | 'card'
  provider?: string
  amount?: string
  x: number
  y: number
  w: number
  h: number
}[] = [
  { id: 'er', kind: 'bill', provider: 'St. Mary\u2019s ER', amount: '$980.00', x: 2, y: 6, w: 124, h: 82 },
  { id: 'mri', kind: 'bill', provider: 'Radiology Ctr', amount: '$1,240.00', x: 132, y: 0, w: 124, h: 82 },
  { id: 'lab', kind: 'bill', provider: 'Quest Labs', amount: '$86.20', x: 262, y: 8, w: 124, h: 82 },
  { id: 'follow', kind: 'bill', provider: 'Dr. Chen Ortho', amount: '$310.00', x: 392, y: 2, w: 124, h: 82 },
  { id: 'sob', kind: 'sob', x: 82, y: 102, w: 134, h: 86 },
  { id: 'card', kind: 'card', x: 306, y: 104, w: 134, h: 68 },
]

const NODE = { x: 260, y: 234 }

function FunnelStage({ cycle }: { cycle: number }) {
  return (
    <div className="mx-auto h-[300px] w-full max-w-[520px] scale-[0.68] sm:scale-100">
      <div className="relative h-[300px] w-[520px]" key={cycle}>
        {FUNNEL_DOCS.map((d, i) => {
          const fx = NODE.x - (d.x + d.w / 2)
          const fy = NODE.y - (d.y + d.h / 2)
          const style: React.CSSProperties = {
            position: 'absolute',
            left: d.x,
            top: d.y,
            animationDelay: `${300 + i * 440}ms`,
            ['--fx' as string]: `${fx}px`,
            ['--fy' as string]: `${fy}px`,
          }
          if (d.kind === 'bill') {
            return (
              <MiniBill
                key={d.id}
                provider={d.provider!}
                amount={d.amount!}
                className="animate-funnel"
                style={style}
              />
            )
          }
          if (d.kind === 'sob') {
            return <MiniSoB key={d.id} className="animate-funnel" style={style} />
          }
          return (
            <MiniInsuranceCard key={d.id} className="animate-funnel" style={style} />
          )
        })}

        {/* Intake node — the Tyndale mark itself */}
        <div
          className="animate-intake absolute flex h-[72px] w-[72px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-card"
          style={{ left: NODE.x, top: NODE.y }}
        >
          <TyndaleMark className="h-14 w-14" />
        </div>
        <p
          className="absolute -translate-x-1/2 text-[12px] font-semibold uppercase tracking-wide text-primary"
          style={{ left: NODE.x, top: NODE.y + 44 }}
        >
          Tyndale
        </p>
      </div>
    </div>
  )
}

/* ─────────────────── Act 3 · Sorted result mini-bill row ────────────────── */

function SortedBill({
  provider,
  amount,
  note,
  show,
  delay,
}: {
  provider: string
  amount: string
  note?: string
  show: boolean
  delay: number
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-2 rounded-lg border border-black/8 bg-white px-2.5 py-1.5 shadow-sm transition-all duration-500',
        show ? 'translate-y-0 opacity-100' : 'translate-y-3 opacity-0',
      )}
      style={{ transitionDelay: show ? `${delay}ms` : '0ms' }}
    >
      <div className="min-w-0">
        <p className="truncate text-[11px] font-bold text-neutral-800">
          {provider}
        </p>
        {note ? (
          <p className="truncate text-[9.5px] text-neutral-500">{note}</p>
        ) : null}
      </div>
      <span className="shrink-0 text-[11px] font-bold text-neutral-800">
        {amount}
      </span>
    </div>
  )
}

/* ──────────────────────────────── Demo shell ────────────────────────────── */

export function AuditDemo() {
  const [phase, setPhase] = useState<Phase>('add')
  const [cycle, setCycle] = useState(0)
  const [reduced, setReduced] = useState(false)
  const [inView, setInView] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  /* Start (and restart) the loop only while the demo is on screen */
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        setInView((was) => {
          if (entry.isIntersecting && !was) {
            setPhase('add')
            setCycle((c) => c + 1)
          }
          return entry.isIntersecting
        })
      },
      { threshold: 0.35 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    if (reduced) {
      setPhase('sort')
      return
    }
    if (!inView) return
    timer.current = setTimeout(() => {
      setPhase((p) => {
        if (p === 'add') return 'audit'
        if (p === 'audit') return 'sort'
        setCycle((c) => c + 1)
        return 'add'
      })
    }, PHASE_MS[phase])
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [phase, reduced, inView])

  const phaseIndex = PHASES.findIndex((p) => p.id === phase)
  const sort = phase === 'sort'

  return (
    <div ref={rootRef} className="glass-tile overflow-hidden rounded-3xl">
      {/* Phase rail */}
      <div className="flex items-center gap-1.5 border-b border-white/40 px-5 pt-5 pb-4">
        {PHASES.map((p, i) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              if (p.id === 'add') setCycle((c) => c + 1)
              setPhase(p.id)
            }}
            className="group flex min-w-0 flex-1 flex-col gap-1.5 text-left"
            aria-label={`Show step: ${p.label}`}
            aria-current={p.id === phase}
          >
            <span className="h-1.5 w-full overflow-hidden rounded-full bg-border">
              <span
                className={cn(
                  'block h-full rounded-full bg-primary transition-all ease-linear',
                  i < phaseIndex && 'w-full duration-300',
                  i > phaseIndex && 'w-0 duration-300',
                )}
                style={
                  i === phaseIndex
                    ? {
                        width: '100%',
                        transitionDuration: reduced
                          ? '0ms'
                          : `${PHASE_MS[phase]}ms`,
                        transitionProperty: 'width',
                        transitionTimingFunction: 'linear',
                      }
                    : undefined
                }
              />
            </span>
            <span
              className={cn(
                'truncate text-[12px] font-semibold uppercase tracking-wide transition-colors',
                i === phaseIndex ? 'text-primary' : 'text-muted-foreground/70',
              )}
            >
              {p.label}
            </span>
          </button>
        ))}
      </div>

      {/* Stage */}
      <div className="relative min-h-[360px] px-4 py-6 sm:min-h-[400px] sm:px-5">
        {/* ── Act 1 · Documents funnel into Tyndale ── */}
        <div
          aria-hidden={phase !== 'add'}
          className={cn(
            'absolute inset-0 flex flex-col items-center justify-center transition-all duration-500',
            phase === 'add'
              ? 'opacity-100'
              : 'pointer-events-none opacity-0 scale-95',
          )}
        >
          {phase === 'add' && <FunnelStage cycle={cycle} />}
          <p className="px-6 text-center text-[13px] font-medium text-muted-foreground">
            Four bills. Your benefits. Your card. That&apos;s all Tyndale needs.
          </p>
        </div>

        {/* ── Act 2 · Audit progress ── */}
        <div
          aria-hidden={phase !== 'audit'}
          className={cn(
            'absolute inset-0 flex flex-col items-center justify-center px-6 transition-all duration-500',
            phase === 'audit'
              ? 'opacity-100'
              : 'pointer-events-none opacity-0 scale-95',
          )}
        >
          <div className="glass w-full max-w-sm rounded-2xl p-5">
            <div className="flex items-center gap-2 text-primary">
              <ScanLine className="h-5 w-5 animate-pulse" aria-hidden="true" />
              <span className="text-[13px] font-bold uppercase tracking-wide">
                Auditing 4 bills…
              </span>
            </div>
            <div className="mt-4 flex flex-col gap-3.5">
              {AUDIT_BARS.map((line, i) => (
                <div key={line}>
                  <p className="text-[13px] font-medium text-foreground/85">
                    {line}
                  </p>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-border">
                    <div
                      className="h-full rounded-full bg-primary transition-all ease-out"
                      style={{
                        width: phase === 'audit' ? '100%' : '0%',
                        transitionDuration: reduced ? '0ms' : '1400ms',
                        transitionDelay:
                          phase === 'audit' ? `${300 + i * 700}ms` : '0ms',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-4 text-[13px] font-medium text-muted-foreground">
            No guessing — every number is read from your documents.
          </p>
        </div>

        {/* ── Act 3 · Every bill sorted with its next step ── */}
        <div
          aria-hidden={!sort}
          className={cn(
            'absolute inset-0 flex flex-col justify-center gap-2.5 overflow-y-auto px-4 py-5 transition-all duration-500 sm:px-5',
            sort ? 'opacity-100' : 'pointer-events-none opacity-0 scale-95',
          )}
        >
          <div className="grid gap-2.5 md:grid-cols-3">
            {/* PAY */}
            <div
              className={cn(
                'glass flex flex-col rounded-2xl p-3.5 transition-all duration-500',
                sort ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0',
              )}
              style={{ transitionDelay: sort ? '200ms' : '0ms' }}
            >
              <div className="flex items-center gap-2 text-money">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-money/12">
                  <Check className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="text-[13px] font-bold uppercase tracking-wide">
                  Pay
                </span>
              </div>
              <div className="mt-2.5 flex flex-col gap-1.5">
                <SortedBill
                  provider="Quest Labs"
                  amount="$86.20"
                  note="Matches your plan exactly"
                  show={sort}
                  delay={500}
                />
              </div>
              <p className="mt-2.5 text-[12px] leading-snug text-muted-foreground">
                Billed correctly against your deductible. Safe to pay as-is.
              </p>
            </div>

            {/* NEGOTIATE */}
            <div
              className={cn(
                'glass flex flex-col rounded-2xl p-3.5 transition-all duration-500',
                sort ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0',
              )}
              style={{ transitionDelay: sort ? '600ms' : '0ms' }}
            >
              <div className="flex items-center gap-2 text-amber">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber/12">
                  <Handshake className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="text-[13px] font-bold uppercase tracking-wide">
                  Negotiate
                </span>
              </div>
              <div className="mt-2.5 flex flex-col gap-1.5">
                <SortedBill
                  provider={'St. Mary\u2019s ER'}
                  amount="$980.00"
                  note="Fair rate: $410"
                  show={sort}
                  delay={900}
                />
                <SortedBill
                  provider="Dr. Chen Ortho"
                  amount="$310.00"
                  note="Fair rate: $185"
                  show={sort}
                  delay={1050}
                />
              </div>
              <div
                className={cn(
                  'mt-2.5 rounded-lg bg-background/70 p-2.5 transition-all duration-500',
                  sort ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0',
                )}
                style={{ transitionDelay: sort ? '1300ms' : '0ms' }}
              >
                <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-amber">
                  <Quote className="h-3 w-3" aria-hidden="true" />
                  Your script
                </div>
                <p className="mt-1 text-[11.5px] leading-snug text-foreground/80">
                  &ldquo;The fair-market rate for this visit is $410. I can pay
                  that today — can you adjust the balance?&rdquo;
                </p>
              </div>
            </div>

            {/* OVERCHARGED */}
            <div
              className={cn(
                'glass flex flex-col rounded-2xl p-3.5 transition-all duration-500',
                sort ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0',
              )}
              style={{ transitionDelay: sort ? '1000ms' : '0ms' }}
            >
              <div className="flex items-center gap-2 text-destructive">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-destructive/10">
                  <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="text-[13px] font-bold uppercase tracking-wide">
                  Overcharged
                </span>
              </div>
              <div className="mt-2.5 flex flex-col gap-1.5">
                <SortedBill
                  provider="Radiology Ctr — MRI"
                  amount="$1,240.00"
                  note="Charged twice for one scan"
                  show={sort}
                  delay={1400}
                />
              </div>
              <ol
                className={cn(
                  'mt-2.5 flex flex-col gap-1 transition-all duration-500',
                  sort ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0',
                )}
                style={{ transitionDelay: sort ? '1700ms' : '0ms' }}
              >
                {[
                  'Call billing — cite the duplicate charge',
                  'Request a corrected claim',
                  'Tyndale drafts your dispute letter',
                ].map((step, i) => (
                  <li
                    key={step}
                    className="flex items-start gap-1.5 text-[11.5px] leading-snug text-foreground/80"
                  >
                    <span className="mt-px flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-[9px] font-bold text-destructive">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <p className="flex items-center justify-center gap-1.5 text-center text-[13px] font-medium text-muted-foreground">
            <Phone className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            And when a call is needed — Tyndale makes it with you.
          </p>
        </div>
      </div>

      {/* Caption */}
      <div className="border-t border-white/40 px-5 py-4">
        <p
          key={phase}
          className="animate-rise text-pretty text-center text-[14px] font-medium leading-relaxed text-foreground/85"
        >
          {PHASES[phaseIndex].caption}
        </p>
      </div>
    </div>
  )
}
