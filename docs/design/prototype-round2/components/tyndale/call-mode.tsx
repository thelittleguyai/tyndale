'use client'

import { useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  Phone,
  ClipboardList,
  MessageSquareWarning,
  Check,
  X,
  Voicemail,
} from 'lucide-react'
import { PLAN_STEPS, money } from '@/lib/tyndale-data'
import { useCase } from './case-provider'
import { Wordmark } from './brand'

type Screen = 'ready' | 'script' | 'pushback' | 'outcome'

export function CallMode() {
  const router = useRouter()
  const params = useSearchParams()
  const { setCallOutcome, setResolved } = useCase()

  const stepId = params.get('step') ?? PLAN_STEPS[0].id
  const step = useMemo(
    () => PLAN_STEPS.find((s) => s.id === stepId) ?? PLAN_STEPS[0],
    [stepId],
  )

  const [screen, setScreen] = useState<Screen>('ready')
  const [scriptIdx, setScriptIdx] = useState(0)

  function exit() {
    router.push('/thread')
  }

  function chooseOutcome(o: 'fixing' | 'pushback' | 'voicemail') {
    if (o === 'fixing') {
      setCallOutcome('fixing')
      setResolved(true)
    } else {
      setCallOutcome(o)
    }
    router.push('/thread')
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-ink text-cream">
      {/* Ambient depth — soft green/teal auras behind the focused surface */}
      <div
        aria-hidden="true"
        className="aura pointer-events-none absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-money/40"
      />
      <div
        aria-hidden="true"
        className="aura pointer-events-none absolute -right-24 bottom-1/4 h-72 w-72 rounded-full bg-primary/50"
      />
      {/* Top bar */}
      <header className="relative z-10 flex items-center justify-between px-5 pt-6 pb-4">
        <button
          onClick={exit}
          className="flex items-center gap-1.5 text-sm text-cream/70 transition-colors hover:text-cream"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Leave call mode
        </button>
        <Wordmark className="text-cream/90" />
        <div className="w-[104px]" aria-hidden="true" />
      </header>

      {/* Live call chip */}
      <div className="relative z-10 flex items-center justify-center pb-4">
        <div className="flex items-center gap-2 rounded-full bg-cream/10 px-4 py-2 text-sm backdrop-blur">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-money opacity-70" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-money" />
          </span>
          <span className="font-medium">On the call</span>
          <span className="text-cream/50">·</span>
          <span className="text-cream/70">{step.phone || 'Escalation'}</span>
        </div>
      </div>

      <div className="relative z-10 mx-auto flex w-full max-w-xl flex-1 flex-col overflow-y-auto px-5 pb-6">
        {screen === 'ready' && (
          <ReadyScreen step={step} onStart={() => setScreen('script')} />
        )}

        {screen === 'script' && (
          <ScriptScreen
            step={step}
            idx={scriptIdx}
            onPrev={() => {
              if (scriptIdx === 0) setScreen('ready')
              else setScriptIdx((i) => i - 1)
            }}
            onNext={() => {
              if (scriptIdx < step.script.length - 1) setScriptIdx((i) => i + 1)
              else setScreen(step.pushback.length ? 'pushback' : 'outcome')
            }}
          />
        )}

        {screen === 'pushback' && (
          <PushbackScreen
            step={step}
            onBack={() => setScreen('script')}
            onDone={() => setScreen('outcome')}
          />
        )}

        {screen === 'outcome' && <OutcomeScreen onChoose={chooseOutcome} />}
      </div>
    </div>
  )
}

function ReadyScreen({
  step,
  onStart,
}: {
  step: (typeof PLAN_STEPS)[number]
  onStart: () => void
}) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 flex-col justify-center">
        <p className="text-sm uppercase tracking-[0.14em] text-cream/50">
          Step {step.order}
        </p>
        <h1 className="mt-2 text-balance font-serif text-3xl leading-tight">
          {step.title}
        </h1>
        <p className="mt-3 text-cream/70">{step.subtitle}</p>

        {step.targets > 0 && (
          <div className="mt-6 rounded-2xl bg-cream/10 p-5">
            <p className="text-sm text-cream/60">What&apos;s on the line here</p>
            <p className="mt-1 font-serif text-2xl text-money-soft">
              {money(step.targets)}
            </p>
          </div>
        )}

        <ul className="mt-6 flex flex-col gap-3 text-sm text-cream/80">
          <li className="flex items-start gap-2.5">
            <ClipboardList className="mt-0.5 h-4 w-4 shrink-0 text-cream/50" aria-hidden="true" />
            I&apos;ll walk you through exactly what to say, one line at a time.
          </li>
          <li className="flex items-start gap-2.5">
            <MessageSquareWarning className="mt-0.5 h-4 w-4 shrink-0 text-cream/50" aria-hidden="true" />
            If they push back, I&apos;ve got your responses ready.
          </li>
        </ul>
      </div>

      <button
        onClick={onStart}
        className="mt-8 flex w-full items-center justify-center gap-2 rounded-full bg-money py-4 text-base font-semibold text-ink transition-transform active:scale-[0.99]"
      >
        <Phone className="h-5 w-5" aria-hidden="true" />
        Start the script
      </button>
    </div>
  )
}

function ScriptScreen({
  step,
  idx,
  onPrev,
  onNext,
}: {
  step: (typeof PLAN_STEPS)[number]
  idx: number
  onPrev: () => void
  onNext: () => void
}) {
  const line = step.script[idx]
  const total = step.script.length
  return (
    <div className="flex flex-1 flex-col">
      {/* progress dots */}
      <div className="flex items-center gap-1.5 pb-6">
        {step.script.map((_, i) => (
          <span
            key={i}
            className={
              'h-1.5 flex-1 rounded-full ' +
              (i <= idx ? 'bg-money' : 'bg-cream/15')
            }
          />
        ))}
      </div>

      <div className="flex flex-1 flex-col justify-center">
        <p className="text-sm uppercase tracking-[0.14em] text-cream/50">
          {line.heading}
        </p>
        <p className="mt-4 text-balance font-serif text-[26px] leading-snug">
          &ldquo;{line.body}&rdquo;
        </p>
      </div>

      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={onPrev}
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-cream/25 text-cream/80 transition-colors hover:bg-cream/10"
          aria-label="Previous line"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        </button>
        <button
          onClick={onNext}
          className="flex flex-1 items-center justify-center gap-2 rounded-full bg-cream py-4 text-base font-semibold text-ink transition-transform active:scale-[0.99]"
        >
          {idx < total - 1 ? 'Next line' : 'They responded'}
          <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

function PushbackScreen({
  step,
  onBack,
  onDone,
}: {
  step: (typeof PLAN_STEPS)[number]
  onBack: () => void
  onDone: () => void
}) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1">
        <p className="text-sm uppercase tracking-[0.14em] text-cream/50">
          If they push back
        </p>
        <h2 className="mt-2 font-serif text-2xl">Here&apos;s what to say</h2>

        <div className="mt-6 flex flex-col gap-4">
          {step.pushback.map((p, i) => (
            <div key={i} className="rounded-2xl bg-cream/10 p-5">
              <p className="text-sm text-cream/60">They might say</p>
              <p className="mt-1 text-cream/90">{p.theyMight}</p>
              <p className="mt-4 text-sm text-money-soft">You say</p>
              <p className="mt-1 text-balance leading-relaxed">{p.youSay}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-cream/25 text-cream/80 transition-colors hover:bg-cream/10"
          aria-label="Back to script"
        >
          <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        </button>
        <button
          onClick={onDone}
          className="flex flex-1 items-center justify-center gap-2 rounded-full bg-cream py-4 text-base font-semibold text-ink transition-transform active:scale-[0.99]"
        >
          How did it go?
          <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

function OutcomeScreen({
  onChoose,
}: {
  onChoose: (o: 'fixing' | 'pushback' | 'voicemail') => void
}) {
  const options: {
    id: 'fixing' | 'pushback' | 'voicemail'
    icon: typeof Check
    title: string
    body: string
  }[] = [
    {
      id: 'fixing',
      icon: Check,
      title: 'They&apos;re fixing it',
      body: 'They agreed to reprocess or correct the charge.',
    },
    {
      id: 'pushback',
      icon: X,
      title: 'They pushed back',
      body: 'I&apos;ll prep your written appeal and next steps.',
    },
    {
      id: 'voicemail',
      icon: Voicemail,
      title: 'Left a voicemail',
      body: 'I&apos;ll remind you to try again and track the deadline.',
    },
  ]
  return (
    <div className="flex flex-1 flex-col justify-center">
      <h2 className="text-balance font-serif text-2xl">How did the call go?</h2>
      <p className="mt-2 text-cream/70">
        Tell me what happened and I&apos;ll take it from here.
      </p>
      <div className="mt-6 flex flex-col gap-3">
        {options.map((o) => {
          const Icon = o.icon
          return (
            <button
              key={o.id}
              onClick={() => onChoose(o.id)}
              className="flex items-center gap-4 rounded-2xl bg-cream/10 p-5 text-left transition-colors hover:bg-cream/15"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-cream/15">
                <Icon className="h-5 w-5 text-cream" aria-hidden="true" />
              </span>
              <span>
                <span
                  className="block font-medium"
                  dangerouslySetInnerHTML={{ __html: o.title }}
                />
                <span
                  className="mt-0.5 block text-sm text-cream/65"
                  dangerouslySetInnerHTML={{ __html: o.body }}
                />
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
