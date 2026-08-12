'use client'

import { useState } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  Check,
  FileText,
  IdCard,
  Lightbulb,
  Lock,
  MousePointerClick,
  RotateCcw,
  Upload,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { PageAmbience } from './glass'
import { useCase } from './case-provider'

type StepId = 'bill' | 'sob' | 'card' | 'about'

const STEPS: { id: StepId; label: string }[] = [
  { id: 'bill', label: 'Your bill' },
  { id: 'sob', label: 'Schedule of Benefits' },
  { id: 'card', label: 'Insurance card' },
  { id: 'about', label: 'About you' },
]

/* Where the Schedule of Benefits hides in a typical member portal */
const PORTAL_CLICKS = [
  'Log in to your insurer\u2019s member portal',
  'Open "Coverage & Benefits" (sometimes "My Plan")',
  'Click "Plan Documents" or "Benefit Documents"',
  'Download the one named "Schedule of Benefits" or "Summary of Benefits and Coverage"',
]

export function UploadFlow() {
  const router = useRouter()
  const { setEmail, reset } = useCase()

  const [stepIndex, setStepIndex] = useState(0)
  const [captured, setCaptured] = useState<Record<StepId, boolean>>({
    bill: false,
    sob: false,
    card: false,
    about: false,
  })
  const [emailValue, setEmailValue] = useState('')
  const [dobValue, setDobValue] = useState('')

  const step = STEPS[stepIndex]
  const isLast = stepIndex === STEPS.length - 1

  const goBack = () => setStepIndex((i) => Math.max(0, i - 1))
  const goNext = () => setStepIndex((i) => Math.min(STEPS.length - 1, i + 1))

  const start = () => {
    reset()
    setEmail(emailValue)
    router.push('/thread')
  }

  /* Footer CTA logic: bill is required; SoB and card can be skipped;
     the last step starts the audit. */
  const canContinue =
    step.id === 'bill'
      ? captured.bill
      : step.id === 'about'
        ? emailValue.trim().length > 3
        : true

  return (
    <main className="mx-auto w-full max-w-md px-4 pb-48 pt-5">
      <PageAmbience variant="calm" />
      {/* Progress */}
      <nav aria-label={`Step ${stepIndex + 1} of ${STEPS.length}`} className="flex items-center gap-3">
        {stepIndex > 0 ? (
          <button
            type="button"
            onClick={goBack}
            aria-label="Back to previous step"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-card text-foreground shadow-soft transition hover:bg-muted"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </button>
        ) : (
          <span className="h-10 w-10 shrink-0" aria-hidden="true" />
        )}
        <div className="flex flex-1 items-center gap-1.5">
          {STEPS.map((s, i) => (
            <span
              key={s.id}
              className={cn(
                'h-1.5 flex-1 rounded-full transition-colors duration-500',
                i <= stepIndex ? 'bg-primary' : 'bg-border',
              )}
            />
          ))}
        </div>
        <span className="w-10 shrink-0 text-right text-[13px] font-semibold text-muted-foreground">
          {stepIndex + 1}/{STEPS.length}
        </span>
      </nav>

      {/* One screen at a time */}
      <div key={step.id} className="animate-rise mt-6">
        {step.id === 'bill' && (
          <BillStep
            captured={captured.bill}
            onCapture={(v) => setCaptured((c) => ({ ...c, bill: v }))}
          />
        )}
        {step.id === 'sob' && (
          <SobStep
            captured={captured.sob}
            onCapture={(v) => setCaptured((c) => ({ ...c, sob: v }))}
          />
        )}
        {step.id === 'card' && (
          <CardStep
            captured={captured.card}
            onCapture={(v) => setCaptured((c) => ({ ...c, card: v }))}
          />
        )}
        {step.id === 'about' && (
          <AboutStep
            emailValue={emailValue}
            setEmailValue={setEmailValue}
            dobValue={dobValue}
            setDobValue={setDobValue}
            cardCaptured={captured.card}
          />
        )}
      </div>

      <p className="mt-4 flex items-center justify-center gap-1.5 text-[13px] font-medium text-muted-foreground">
        <Lock className="h-4 w-4" aria-hidden="true" />
        Encrypted. Never sold. Used only for your audit.
      </p>

      {/* Sticky footer */}
      <div className="fixed inset-x-0 bottom-0 z-20 bg-gradient-to-t from-background via-background/90 to-transparent px-4 pb-4 pt-6">
        <div className="mx-auto flex w-full max-w-md flex-col gap-2">
          <button
            type="button"
            onClick={isLast ? start : goNext}
            disabled={!canContinue}
            className={cn(
              'flex min-h-[54px] w-full items-center justify-center gap-2 rounded-2xl px-4 text-[17px] font-semibold text-white shadow-float transition hover:brightness-110 disabled:opacity-50',
              isLast ? 'bg-money' : 'bg-primary',
            )}
          >
            {isLast
              ? 'Start my audit'
              : step.id === 'bill' && !captured.bill
                ? 'Add your bill to continue'
                : 'Continue'}
            {!isLast && canContinue && (
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
          {(step.id === 'sob' || step.id === 'card') && !captured[step.id] && (
            <button
              type="button"
              onClick={goNext}
              className="min-h-[44px] text-[15px] font-semibold text-muted-foreground transition hover:text-foreground"
            >
              I don&apos;t have this right now — skip
            </button>
          )}
        </div>
      </div>
    </main>
  )
}

/* ── Shared capture surface ───────────────────────────────────────────── */

function CaptureSurface({
  captured,
  onCapture,
  icon,
  prompt,
  hint,
  previewLabel,
}: {
  captured: boolean
  onCapture: (v: boolean) => void
  icon: React.ReactNode
  prompt: string
  hint: string
  previewLabel: string
}) {
  if (captured) {
    return (
      <div className="glass-tile overflow-hidden rounded-3xl">
        <div className="relative aspect-[4/3] bg-navy">
          <div className="absolute inset-5 rounded-lg border-2 border-money/80" />
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-8 text-center text-navy-foreground/85">
            <FileText className="h-10 w-10" aria-hidden="true" />
            <p className="text-[14px] font-medium">{previewLabel}</p>
          </div>
          <span className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-money px-3 py-1.5 text-[13px] font-semibold text-white">
            <Check className="h-4 w-4" aria-hidden="true" />
            Looks readable
          </span>
        </div>
        <div className="flex gap-2 p-3">
          <button
            type="button"
            onClick={() => onCapture(false)}
            className="flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl border border-border bg-background px-4 text-[15px] font-semibold text-foreground hover:bg-muted"
          >
            <RotateCcw className="h-5 w-5" aria-hidden="true" />
            Retake
          </button>
          <span className="flex min-h-[48px] flex-[2] items-center justify-center gap-2 rounded-xl bg-money-soft px-4 text-[15px] font-semibold text-money">
            <Check className="h-5 w-5" aria-hidden="true" />
            Got it
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-tile rounded-3xl border-2 border-dashed border-primary/40 p-6">
      <div className="flex flex-col items-center gap-4 py-4 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-primary">
          {icon}
        </div>
        <p className="text-[16px] font-semibold text-foreground">{prompt}</p>
        <p className="text-[14px] text-muted-foreground">{hint}</p>
        <button
          type="button"
          onClick={() => onCapture(true)}
          className="mt-1 flex min-h-[52px] w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground shadow-soft transition hover:brightness-110"
        >
          <Camera className="h-5 w-5" aria-hidden="true" />
          Take photo
        </button>
        <button
          type="button"
          onClick={() => onCapture(true)}
          className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-2xl border border-border bg-background px-4 text-[16px] font-semibold text-foreground transition hover:bg-muted"
        >
          <Upload className="h-5 w-5" aria-hidden="true" />
          Upload a document or photo
        </button>
      </div>
    </div>
  )
}

/* ── Step 1: Bill ─────────────────────────────────────────────────────── */

function BillStep({
  captured,
  onCapture,
}: {
  captured: boolean
  onCapture: (v: boolean) => void
}) {
  return (
    <section aria-label="Add your bill">
      <h1 className="text-balance font-display text-2xl font-bold text-foreground">
        Let&apos;s start with your bill.
      </h1>
      <p className="mt-2 text-[16px] leading-relaxed text-muted-foreground">
        This is the start of your file. I&apos;ll read it, remember your plan,
        and keep watching what happens next — so you&apos;re not doing this
        alone.
      </p>
      <div className="mt-6">
        <CaptureSurface
          captured={captured}
          onCapture={onCapture}
          icon={<Camera className="h-8 w-8" aria-hidden="true" />}
          prompt="Point your camera at the bill"
          hint="I'll frame the edges for you and check it's readable."
          previewLabel="Riverside Imaging Center — statement"
        />
      </div>
    </section>
  )
}

/* ── Step 2: Schedule of Benefits ─────────────────────────────────────── */

function SobStep({
  captured,
  onCapture,
}: {
  captured: boolean
  onCapture: (v: boolean) => void
}) {
  return (
    <section aria-label="Add your Schedule of Benefits">
      <h1 className="text-balance font-display text-2xl font-bold text-foreground">
        Now, your plan&apos;s rulebook.
      </h1>
      <p className="mt-2 text-[16px] leading-relaxed text-muted-foreground">
        Your <strong className="font-semibold text-foreground">Schedule of Benefits</strong>{' '}
        lists exactly what your plan promised — every copay, deductible, and
        coinsurance rate. It&apos;s what I audit your bill against, line by
        line. Without it I can still estimate; with it, my math is exact.
      </p>

      {/* What it looks like */}
      <figure className="glass-tile mt-5 overflow-hidden rounded-3xl">
        <div className="relative aspect-[4/3] bg-muted">
          <Image
            src="/sob-example.png"
            alt="Example of a Schedule of Benefits document: a one-page table listing your annual deductible, out-of-pocket maximum, and copay or coinsurance amounts for each type of visit"
            fill
            sizes="(max-width: 768px) 100vw, 28rem"
            className="object-cover"
          />
        </div>
        <figcaption className="px-4 py-3 text-[13px] leading-relaxed text-muted-foreground">
          Here&apos;s what one looks like — usually 1&ndash;3 pages with a table
          of costs. Yours may say &quot;Summary of Benefits and Coverage&quot;
          instead.
        </figcaption>
      </figure>

      {/* Where to find it */}
      <div className="glass-tile mt-4 rounded-3xl p-5">
        <div className="flex items-center gap-2 text-primary">
          <MousePointerClick className="h-5 w-5" aria-hidden="true" />
          <p className="text-[14px] font-semibold uppercase tracking-wide">
            Where to find it
          </p>
        </div>
        <ol className="mt-3 flex flex-col gap-3">
          {PORTAL_CLICKS.map((click, i) => (
            <li key={click} className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-bold text-primary">
                {i + 1}
              </span>
              <span className="text-[15px] leading-relaxed text-foreground">
                {click}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {/* Screenshot tip */}
      <div className="mt-4 flex items-start gap-3 rounded-3xl bg-accent p-4 shadow-soft">
        <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-[14px] leading-relaxed text-foreground">
          Can&apos;t find it? Take screenshots of your portal as you click
          around and upload them here — I&apos;ll read them and point you to
          exactly where your Schedule of Benefits lives.
        </p>
      </div>

      <div className="mt-5">
        <CaptureSurface
          captured={captured}
          onCapture={onCapture}
          icon={<FileText className="h-8 w-8" aria-hidden="true" />}
          prompt="Add your Schedule of Benefits"
          hint="A photo, screenshots, or the downloaded document all work."
          previewLabel="Blue Shield PPO — Schedule of Benefits"
        />
      </div>
    </section>
  )
}

/* ── Step 3: Insurance card ───────────────────────────────────────────── */

function CardStep({
  captured,
  onCapture,
}: {
  captured: boolean
  onCapture: (v: boolean) => void
}) {
  return (
    <section aria-label="Add your insurance card">
      <h1 className="text-balance font-display text-2xl font-bold text-foreground">
        Your insurance card.
      </h1>
      <p className="mt-2 text-[16px] leading-relaxed text-muted-foreground">
        The front of your card gives me your member ID and plan network —
        that&apos;s how I confirm your exact rates and connect to your insurer
        on your behalf.
      </p>
      <div className="mt-6">
        <CaptureSurface
          captured={captured}
          onCapture={onCapture}
          icon={<IdCard className="h-8 w-8" aria-hidden="true" />}
          prompt="Snap the front of your card"
          hint="Lay it flat — I'll read the member ID and group number."
          previewLabel="Blue Shield PPO — member card"
        />
      </div>
    </section>
  )
}

/* ── Step 4: About you ────────────────────────────────────────────────── */

function AboutStep({
  emailValue,
  setEmailValue,
  dobValue,
  setDobValue,
  cardCaptured,
}: {
  emailValue: string
  setEmailValue: (v: string) => void
  dobValue: string
  setDobValue: (v: string) => void
  cardCaptured: boolean
}) {
  return (
    <section aria-label="About you">
      <h1 className="text-balance font-display text-2xl font-bold text-foreground">
        Last step — about you.
      </h1>
      <p className="mt-2 text-[16px] leading-relaxed text-muted-foreground">
        I&apos;ve pre-filled what I read off your documents. Just confirm
        it&apos;s right and add the two things I can&apos;t read.
      </p>

      {/* Pre-filled from documents */}
      <div className="glass-tile mt-5 rounded-3xl p-5">
        <p className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
          From your documents
        </p>
        <dl className="mt-3 flex flex-col gap-3">
          <PrefilledRow label="Name" value="Sarah Mitchell" source="your bill" />
          <PrefilledRow label="Insurer & plan" value="Blue Shield PPO" source="your bill" />
          {cardCaptured && (
            <PrefilledRow label="Member ID" value="XQP-4471902" source="your insurance card" />
          )}
        </dl>
      </div>

      {/* The two things Tyndale can't read */}
      <div className="mt-4 flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-[15px] font-semibold text-foreground">
            Date of birth
          </span>
          <span className="text-[13px] text-muted-foreground">
            Your insurer requires it to verify you when I pull your records.
          </span>
          <input
            type="date"
            value={dobValue}
            onChange={(e) => setDobValue(e.target.value)}
            aria-label="Date of birth"
            className="min-h-[52px] w-full rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-[15px] font-semibold text-foreground">
            Email address
          </span>
          <span className="text-[13px] text-muted-foreground">
            So I can email you the moment your audit is ready — and bring you
            right back to your case.
          </span>
          <input
            type="email"
            inputMode="email"
            value={emailValue}
            onChange={(e) => setEmailValue(e.target.value)}
            placeholder="sarah@email.com"
            className="min-h-[52px] w-full rounded-2xl border border-input bg-card px-4 text-[16px] text-foreground shadow-soft outline-none ring-primary/40 focus:ring-2"
          />
        </label>
      </div>

      {/* EOBs: fetched automatically, only requested if that fails */}
      <div className="mt-4 flex items-start gap-3 rounded-3xl bg-accent p-4 shadow-soft">
        <Check className="mt-0.5 h-5 w-5 shrink-0 text-money" aria-hidden="true" />
        <p className="text-[14px] leading-relaxed text-foreground">
          <span className="font-semibold">No EOBs needed.</span> With these
          details I&apos;ll pull your Explanation of Benefits from Blue Shield
          automatically. If their system won&apos;t give them to me, I&apos;ll
          ask you — and that&apos;s the only time I will.
        </p>
      </div>
    </section>
  )
}

function PrefilledRow({
  label,
  value,
  source,
}: {
  label: string
  value: string
  source: string
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <dt className="text-[13px] text-muted-foreground">{label}</dt>
        <dd className="text-[16px] font-semibold text-foreground">{value}</dd>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-money-soft px-2.5 py-1 text-[12px] font-medium text-money">
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
        read from {source}
      </span>
    </div>
  )
}
