'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ArrowRight,
  Calculator,
  ChevronDown,
  Clock,
  FileText,
  MapPin,
  MessageCircle,
  Plus,
  ReceiptText,
  Stethoscope,
  TrendingUp,
} from 'lucide-react'
import {
  CHECK_IN,
  DISCLAIMER,
  LIFETIME_RECOVERED,
  money,
  RECORD_CASES,
  USER,
  type CaseStatus,
} from '@/lib/tyndale-data'
import { cn } from '@/lib/utils'
import { Wordmark } from './brand'
import { StatusChip } from './primitives'
import { AmbientAuras, PageAmbience } from './glass'
import { useCase } from './case-provider'

export function Dashboard() {
  const router = useRouter()
  const { resolved } = useCase()
  const liveRecovered = resolved ? 572 : 0
  const lifetime = LIFETIME_RECOVERED + liveRecovered
  const openCases = RECORD_CASES.filter((c) => c.status !== 'resolved').length

  return (
    <div className="min-h-dvh bg-background">
      <PageAmbience variant="calm" />
      {/* Header */}
      <header className="sticky top-0 z-30 border-b border-border/70 bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-3xl items-center justify-between px-5">
          <Wordmark tone="dark" />
          <Link
            href="/upload"
            className="inline-flex min-h-[44px] items-center gap-1.5 rounded-full bg-primary px-4 text-[14px] font-semibold text-primary-foreground transition hover:brightness-110"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Check a bill
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl px-5 pb-28 pt-6">
        {/* Greeting — immersive ambient panel */}
        <section className="relative isolate overflow-hidden rounded-3xl bg-gradient-to-br from-navy to-primary p-6 text-navy-foreground shadow-float">
          <AmbientAuras variant="money" />
          <div className="relative">
            <p className="text-[15px] text-navy-foreground/70">Welcome back,</p>
            <h1 className="font-display text-3xl font-bold">{USER.firstName}.</h1>
            <p className="mt-1 max-w-md text-[15px] leading-relaxed text-navy-foreground/80">
              I&apos;m still on your cases — deadlines watched, numbers
              re-checked.
            </p>
          </div>
        </section>

        {/* Quick check-in — surfaces FIRST */}
        {!resolved && <CheckInCard onOpen={() => router.push('/thread')} />}

        {/* Analytics — visually distinct stat cards */}
        <section aria-label="Your numbers" className="mt-6">
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              tone="money"
              icon={<TrendingUp className="h-4 w-4" aria-hidden="true" />}
              label="Recovered to date"
              value={money(lifetime)}
            />
            <StatCard
              tone="plain"
              icon={<FileText className="h-4 w-4" aria-hidden="true" />}
              label="Open cases"
              value={String(openCases)}
              sub="1 needs you"
            />
          </div>
          <div className="glass-tile mt-3 rounded-3xl p-5">
            <div className="flex items-center justify-between">
              <p className="text-[13px] font-semibold text-foreground">
                {USER.plan}
              </p>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-severity-med-bg px-2.5 py-1 text-[12px] font-semibold text-severity-med">
                <Clock className="h-3.5 w-3.5" aria-hidden="true" />
                Next deadline Jul 24
              </span>
            </div>
            <Meter
              label="Deductible met"
              met={USER.deductibleMet}
              total={USER.deductibleTotal}
            />
            <Meter
              label="Out-of-pocket met"
              met={USER.oopMet}
              total={USER.oopTotal}
            />
          </div>
        </section>

        {/* Quick actions — tile grid with tooltips */}
        <section aria-label="Quick actions" className="mt-6">
          <h2 className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
            Quick actions
          </h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <ActionTile
              href="/upload"
              icon={<ReceiptText className="h-5 w-5" aria-hidden="true" />}
              label="Check a bill"
              tip="Upload a new bill and I'll audit it against your plan."
            />
            <ActionTile
              href="/estimate"
              icon={<Calculator className="h-5 w-5" aria-hidden="true" />}
              label="Estimate Costs"
              tip="See what a procedure should cost against your plan status."
            />
            <ActionTile
              href="/find-doctor"
              icon={<Stethoscope className="h-5 w-5" aria-hidden="true" />}
              label="Find a Doctor"
              tip="Search in-network doctors — confirmed, not just listed."
            />
            <ActionTile
              href="/plan-visit"
              icon={<MapPin className="h-5 w-5" aria-hidden="true" />}
              label="Plan a Visit"
              tip="Pre-visit checklist: referral, prior auth, and what's billable."
            />
            <ActionTile
              href="/thread"
              icon={<MessageCircle className="h-5 w-5" aria-hidden="true" />}
              label="Chat with Tyndale"
              tip="Pick up the conversation about any of your cases."
            />
          </div>
        </section>

        {/* Cases */}
        <section aria-label="Your cases" className="mt-8">
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-xl font-bold text-foreground">
              Your cases
            </h2>
            <span className="text-[13px] text-muted-foreground">
              {RECORD_CASES.length} on file this year
            </span>
          </div>
          <div className="mt-3 flex flex-col gap-3">
            {RECORD_CASES.map((c) => {
              const isLive = c.id === 'riverside-0614'
              const label =
                isLive && resolved ? 'Resolved — recovered $572' : c.statusLabel
              const status: CaseStatus =
                isLive && resolved ? 'resolved' : c.status
              return (
                <button
                  key={c.id}
                  onClick={() =>
                    router.push(isLive ? '/thread' : `/record/${c.id}`)
                  }
                  className="glass-tile group flex items-center gap-4 rounded-3xl p-4 text-left transition duration-300 hover:-translate-y-0.5 hover:shadow-float"
                >
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="truncate font-semibold text-foreground">
                        {c.provider}
                      </span>
                      {isLive && !resolved && (
                        <span className="rounded-full bg-money/12 px-2 py-0.5 text-[11px] font-semibold text-money">
                          Active
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block truncate text-[13px] text-muted-foreground">
                      {c.service} · {c.date}
                    </span>
                    <span className="mt-2 block">
                      <StatusChip status={status} label={label} />
                    </span>
                  </span>
                  <ArrowRight
                    className="h-5 w-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </button>
              )
            })}
          </div>
        </section>

        <p className="mt-8 text-center text-xs leading-relaxed text-muted-foreground">
          {DISCLAIMER}
        </p>
      </main>
    </div>
  )
}

/* Quick check-in card — clickable to reveal the full detail, then answer */
function CheckInCard({ onOpen }: { onOpen: () => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <section
      aria-label="Pending check-in"
      className="animate-rise mt-6 overflow-hidden rounded-3xl border-2 border-primary/30 bg-accent shadow-soft"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-start gap-3 p-4 text-left"
      >
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <MessageCircle className="h-5 w-5" aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12px] font-semibold uppercase tracking-wide text-primary">
            A quick check-in
          </span>
          <span className="mt-0.5 block font-semibold text-foreground">
            {CHECK_IN.prompt}
          </span>
          <span className="mt-1 inline-flex items-center gap-1 text-[13px] text-primary">
            {expanded ? 'Hide details' : 'Remind me what this was about'}
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                expanded && 'rotate-180',
              )}
              aria-hidden="true"
            />
          </span>
        </span>
      </button>

      {expanded && (
        <div className="border-t border-primary/15 px-4 py-3 pl-16">
          <p className="text-[14px] leading-relaxed text-foreground/85">
            {CHECK_IN.context}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2 border-t border-primary/15 p-4 pl-16 sm:flex-row">
        <button
          type="button"
          onClick={onOpen}
          className="min-h-[44px] flex-1 rounded-xl bg-money px-4 text-[15px] font-semibold text-white transition hover:brightness-110"
        >
          They&apos;re fixing it
        </button>
        <button
          type="button"
          onClick={onOpen}
          className="min-h-[44px] flex-1 rounded-xl border border-border bg-card px-4 text-[15px] font-semibold text-foreground transition hover:bg-muted"
        >
          They pushed back
        </button>
        <button
          type="button"
          onClick={onOpen}
          className="min-h-[44px] flex-1 rounded-xl border border-border bg-card px-4 text-[15px] font-semibold text-foreground transition hover:bg-muted"
        >
          I left a message
        </button>
      </div>
    </section>
  )
}

function StatCard({
  tone,
  icon,
  label,
  value,
  sub,
}: {
  tone: 'money' | 'plain'
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
}) {
  return (
    <div
      className={cn(
        'rounded-3xl p-5',
        tone === 'money'
          ? 'bg-navy text-navy-foreground shadow-soft'
          : 'glass-tile',
      )}
    >
      <div
        className={cn(
          'flex items-center gap-1.5 text-[13px] font-medium',
          tone === 'money' ? 'text-navy-foreground/70' : 'text-muted-foreground',
        )}
      >
        {icon}
        {label}
      </div>
      <p
        className={cn(
          'mt-2 font-display text-3xl font-bold tabular-nums',
          tone === 'money' ? 'text-money-soft' : 'text-foreground',
        )}
      >
        {value}
      </p>
      {sub && (
        <p
          className={cn(
            'mt-0.5 text-[12px]',
            tone === 'money'
              ? 'text-navy-foreground/55'
              : 'text-muted-foreground',
          )}
        >
          {sub}
        </p>
      )}
    </div>
  )
}

function Meter({ label, met, total }: { label: string; met: number; total: number }) {
  const pct = Math.min(100, Math.round((met / total) * 100))
  return (
    <div className="mt-3">
      <div className="flex items-baseline justify-between text-[13px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold text-foreground tabular-nums">
          {money(met)} <span className="text-muted-foreground">of {money(total)}</span>
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-amber"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/* Action tile with hover/long-press tooltip */
function ActionTile({
  href,
  icon,
  label,
  tip,
}: {
  href: string
  icon: React.ReactNode
  label: string
  tip: string
}) {
  const [show, setShow] = useState(false)
  return (
    <Link
      href={href}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
      className="glass-tile group relative flex min-h-[100px] flex-col justify-between rounded-3xl p-4 transition duration-300 hover:-translate-y-0.5 hover:shadow-float"
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-primary">
        {icon}
      </span>
      <span className="mt-3 text-[14px] font-semibold text-foreground">
        {label}
      </span>
      {show && (
        <span
          role="tooltip"
          className="pointer-events-none absolute -top-2 left-1/2 z-10 w-max max-w-[200px] -translate-x-1/2 -translate-y-full rounded-lg bg-navy px-3 py-2 text-[12px] leading-snug text-navy-foreground shadow-lg"
        >
          {tip}
        </span>
      )}
    </Link>
  )
}
