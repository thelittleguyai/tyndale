'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Check, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TyndaleMark } from './brand'

/**
 * "Not a chatbot with opinions" — two synthetic conversations that play out
 * live, message by message, like you're watching both chats happen at once.
 *
 * When a flagged message lands, its flag chip briefly becomes prominent and
 * the corresponding phrase inside the bubble is underlined — a spotlight that
 * fades after a few seconds so the reader connects concept to evidence.
 */

type Flag = { kind: 'fail' | 'win'; label: string }

type Msg = {
  from: 'user' | 'bot'
  /* Static node, or a render function that receives the spotlight state */
  text: React.ReactNode | ((spot: boolean) => React.ReactNode)
  flag?: Flag
}

/* Phrase highlight — underlines while its message is spotlighted */
function Hl({
  spot,
  kind,
  children,
}: {
  spot: boolean
  kind: 'fail' | 'win'
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        'rounded-sm transition-all duration-500',
        spot &&
          (kind === 'win'
            ? 'bg-money/15 underline decoration-money decoration-2 underline-offset-4'
            : 'bg-destructive/10 underline decoration-destructive decoration-2 underline-offset-4'),
      )}
    >
      {children}
    </span>
  )
}

const USER_Q1 = 'Mercy General billed me $2,340 for my MRI. Is that right?'
const USER_Q2 = 'Wait — you told me last week my deductible was already met.'

const GENERIC_CHAT: Msg[] = [
  { from: 'user', text: USER_Q1 },
  {
    from: 'bot',
    text: (spot) => (
      <>
        Great question! MRI costs can vary significantly based on a number of
        factors, including your geographic region, whether the facility is a
        hospital or freestanding imaging center, whether contrast was used,
        and your specific insurance plan. Generally speaking,{' '}
        <Hl spot={spot} kind="fail">
          MRI scans in the United States can range anywhere from $400 to
          $3,500 or more
        </Hl>
        . Here are some steps you could consider: 1) Request an itemized bill
        from the provider, 2) Contact your insurance company to verify how the
        claim was processed, 3) Ask the billing office whether financial
        assistance or a prompt-pay discount is available. It may also be worth
        checking whether the facility was in-network.
      </>
    ),
    flag: {
      kind: 'fail',
      label:
        'A wall of generic advice — never read your bill, never asked a question',
    },
  },
  { from: 'user', text: USER_Q2 },
  {
    from: 'bot',
    text: (spot) => (
      <>
        I apologize for any confusion! I should clarify that{' '}
        <Hl spot={spot} kind="fail">
          I don&apos;t have memory of previous conversations
        </Hl>
        , so I&apos;m unable to recall what we may have discussed.
        Additionally,{' '}
        <Hl spot={spot} kind="fail">
          I don&apos;t have the ability to access your insurance records,
          Explanation of Benefits documents, claims history, or clinical
          encounter data
        </Hl>
        , as I&apos;m not connected to any systems that could retrieve them.
        For accurate information about your deductible status, I&apos;d
        recommend logging into your member portal or calling the number on the
        back of your insurance card.
      </>
    ),
    flag: {
      kind: 'fail',
      label: 'No memory of your case · no API access to EOBs or visit data',
    },
  },
  {
    from: 'bot',
    text: (spot) => (
      <>
        One more thing that might help: under{' '}
        <Hl spot={spot} kind="fail">
          Section 12(b) of the Fair Medical Billing Act
        </Hl>
        , providers are required to honor a 40% self-pay discount when
        requested in writing within 30 days of the date of service.
      </>
    ),
    flag: { kind: 'fail', label: 'Hallucinated — this law does not exist' },
  },
  {
    from: 'bot',
    text: (spot) => (
      <>
        To summarize the possibilities: you may have been billed an
        out-of-network rate, there could be a duplicate charge on the itemized
        bill, the facility might have applied the wrong fee schedule, your
        deductible may not have been credited, or the price could simply be
        correct for your area.{' '}
        <Hl spot={spot} kind="fail">
          Without access to your documents, I can&apos;t determine which of
          these — if any — applies
        </Hl>
        . I hope this helps! Let me know if you have any other questions.
      </>
    ),
    flag: {
      kind: 'fail',
      label: 'Five maybes, zero findings — you end right where you started',
    },
  },
]

const TYNDALE_CHAT: Msg[] = [
  { from: 'user', text: USER_Q1 },
  {
    from: 'bot',
    text: (spot) => (
      <>
        Let me check — pulling your Mar 12 EOB from Blue Shield now. One
        question first:{' '}
        <Hl spot={spot} kind="win">
          was this at Mercy General&apos;s main hospital, or their outpatient
          imaging center?
        </Hl>{' '}
        The allowed rate is different.
      </>
    ),
    flag: {
      kind: 'win',
      label: 'Asks the follow-up questions that change the answer',
    },
  },
  { from: 'user', text: 'The outpatient imaging center.' },
  {
    from: 'bot',
    text: (spot) => (
      <>
        Then no — it&apos;s wrong.{' '}
        <Hl spot={spot} kind="win">
          Your Mar 12 EOB
        </Hl>{' '}
        shows the plan rate there is <strong>$980</strong>, and you met your
        deductible on Feb 3. You owe 20%: <strong>$196</strong>.
      </>
    ),
    flag: {
      kind: 'win',
      label: 'Retrieves your EOBs so you don\u2019t have to go find them',
    },
  },
  { from: 'user', text: USER_Q2 },
  {
    from: 'bot',
    text: (spot) => (
      <>
        <Hl spot={spot} kind="win">
          Exactly — I have that claim on file
        </Hl>
        , and the math above already counts it.
      </>
    ),
    flag: { kind: 'win', label: 'Short, plain English — easy to follow' },
  },
  {
    from: 'bot',
    text: (spot) => (
      <>
        Charging above the plan rate violates the{' '}
        <Hl spot={spot} kind="win">
          No Surprises Act (45 CFR §149.410)
        </Hl>
        .
      </>
    ),
    flag: {
      kind: 'win',
      label: 'Cites the real statute — checkable, not invented',
    },
  },
  {
    from: 'bot',
    text: (spot) => (
      <>
        <Hl spot={spot} kind="win">
          Finding: one overcharge of <strong>$2,144</strong>
        </Hl>
        . The plan: I send the dispute letter today, Mercy General has 30 days
        to correct it, and I chase them if they don&apos;t. Nothing for you to
        do — want me to send it?
      </>
    ),
    flag: {
      kind: 'win',
      label: 'One concrete finding, one clear plan — not a pile of maybes',
    },
  },
]

/**
 * Shared timeline: alternates between panels so both conversations feel like
 * they are happening at the same time. Each step reveals one message after a
 * "typing" pause sized to the message length.
 */
type Step = { panel: 'generic' | 'tyndale'; index: number; typing: number }

function buildTimeline(): Step[] {
  const steps: Step[] = []
  const g = GENERIC_CHAT
  const t = TYNDALE_CHAT
  const max = Math.max(g.length, t.length)
  for (let i = 0; i < max; i++) {
    if (i < t.length)
      steps.push({
        panel: 'tyndale',
        index: i,
        typing: t[i].from === 'user' ? 1700 : 3000,
      })
    if (i < g.length)
      steps.push({
        panel: 'generic',
        index: i,
        typing: g[i].from === 'user' ? 1700 : 4400,
      })
  }
  return steps
}

const TIMELINE = buildTimeline()

/* How long a flag note stays on screen before disappearing */
const SPOTLIGHT_MS = 5800

function TypingDots() {
  return (
    <div className="flex w-fit items-center gap-1 rounded-2xl rounded-bl-md bg-muted px-3.5 py-3 ring-1 ring-border">
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
      <span className="sr-only">Typing</span>
    </div>
  )
}

function Bubble({
  msg,
  tone,
  spot,
}: {
  msg: Msg
  tone: 'generic' | 'tyndale'
  spot: boolean
}) {
  const isUser = msg.from === 'user'
  const body = typeof msg.text === 'function' ? msg.text(spot) : msg.text
  return (
    <div
      className={cn(
        'animate-rise flex flex-col gap-1.5',
        isUser ? 'items-end' : 'items-start',
      )}
    >
      <div
        className={cn(
          'max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed',
          isUser
            ? 'rounded-br-md bg-navy text-navy-foreground'
            : tone === 'tyndale'
              ? 'rounded-bl-md bg-primary/10 text-foreground ring-1 ring-primary/20'
              : 'rounded-bl-md bg-muted text-muted-foreground ring-1 ring-border',
        )}
      >
        {body}
      </div>
      {/* Flag note appears with the spotlight, then disappears entirely */}
      {msg.flag && spot && (
        <span
          className={cn(
            'animate-rise inline-flex max-w-[92%] origin-left items-start gap-1.5 rounded-lg px-3 py-2 text-[12.5px] font-medium leading-snug shadow-float ring-1',
            msg.flag.kind === 'fail'
              ? 'bg-destructive/15 text-destructive ring-destructive/30'
              : 'bg-money/15 text-money ring-money/30',
          )}
        >
          {msg.flag.kind === 'fail' ? (
            <X className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          ) : (
            <Check className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          )}
          {msg.flag.label}
        </span>
      )}
    </div>
  )
}

function Panel({
  tone,
  messages,
  visibleCount,
  typing,
  spotIndex,
}: {
  tone: 'generic' | 'tyndale'
  messages: Msg[]
  visibleCount: number
  typing: boolean
  spotIndex: number | null
}) {
  const isTyndale = tone === 'tyndale'
  const scrollRef = useRef<HTMLDivElement>(null)

  /* Keep the newest message in view inside the panel */
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [visibleCount, typing])

  return (
    <section
      aria-label={
        isTyndale
          ? 'The same question asked to Tyndale'
          : 'The same question asked to a general AI chatbot'
      }
      className={cn(
        'glass-tile overflow-hidden rounded-3xl',
        isTyndale && 'ring-1 ring-primary/25',
      )}
    >
      <header
        className={cn(
          'flex items-center gap-2.5 border-b px-4 py-3',
          isTyndale ? 'border-primary/15 bg-primary/5' : 'border-border/70',
        )}
      >
        {isTyndale ? (
          <TyndaleMark className="h-8 w-8 shrink-0" />
        ) : (
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </div>
        )}
        <div>
          <p className="text-[14px] font-semibold text-foreground">
            {isTyndale ? 'Tyndale' : 'General AI chatbot'}
          </p>
          <p className="text-[12px] text-muted-foreground">
            {isTyndale
              ? 'Your bills, EOBs, plan & the law — connected'
              : 'No documents, no memory, no data connections'}
          </p>
        </div>
        <span
          className={cn(
            'ml-auto inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold',
            isTyndale
              ? 'bg-money/10 text-money'
              : 'bg-destructive/10 text-destructive',
          )}
        >
          {isTyndale ? (
            <Check className="h-3 w-3" aria-hidden="true" />
          ) : (
            <AlertTriangle className="h-3 w-3" aria-hidden="true" />
          )}
          {isTyndale ? 'Evidence' : 'Opinions'}
        </span>
      </header>
      <div
        ref={scrollRef}
        className="flex h-[420px] flex-col gap-3 overflow-y-auto p-4 md:h-[480px]"
      >
        {messages.slice(0, visibleCount).map((m, i) => (
          <Bubble key={i} msg={m} tone={tone} spot={spotIndex === i} />
        ))}
        {typing && <TypingDots />}
      </div>
    </section>
  )
}

export function ChatCompare() {
  const [stepIdx, setStepIdx] = useState(0) // next TIMELINE step to reveal
  const [typingPanel, setTypingPanel] = useState<'generic' | 'tyndale' | null>(
    null,
  )
  const [genericCount, setGenericCount] = useState(0)
  const [tyndaleCount, setTyndaleCount] = useState(0)
  const [spot, setSpot] = useState<{
    panel: 'generic' | 'tyndale'
    index: number
  } | null>(null)
  const [inView, setInView] = useState(false)
  const [reduced, setReduced] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  /* Start the conversation when scrolled into view; restart on re-entry */
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        setInView((was) => {
          if (entry.isIntersecting && !was) {
            setStepIdx(0)
            setGenericCount(0)
            setTyndaleCount(0)
            setTypingPanel(null)
            setSpot(null)
          }
          return entry.isIntersecting
        })
      },
      { threshold: 0.25 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  /* Play the shared timeline: typing pause, then reveal the message */
  useEffect(() => {
    if (reduced) {
      setGenericCount(GENERIC_CHAT.length)
      setTyndaleCount(TYNDALE_CHAT.length)
      setTypingPanel(null)
      return
    }
    if (!inView || stepIdx >= TIMELINE.length) {
      setTypingPanel(null)
      return
    }
    const step = TIMELINE[stepIdx]
    const msg = (step.panel === 'generic' ? GENERIC_CHAT : TYNDALE_CHAT)[
      step.index
    ]
    /* Users don't get a typing indicator bubble — just a beat */
    setTypingPanel(msg.from === 'user' ? null : step.panel)
    const t = setTimeout(() => {
      if (step.panel === 'generic') setGenericCount(step.index + 1)
      else setTyndaleCount(step.index + 1)
      setTypingPanel(null)
      /* Spotlight the flag + highlighted phrase on flagged messages */
      if (msg.flag) setSpot({ panel: step.panel, index: step.index })
      setStepIdx((i) => i + 1)
    }, step.typing)
    return () => clearTimeout(t)
  }, [stepIdx, inView, reduced])

  /* Spotlight fades on its own after a beat (unless replaced by a newer one) */
  useEffect(() => {
    if (!spot) return
    const t = setTimeout(() => setSpot(null), SPOTLIGHT_MS)
    return () => clearTimeout(t)
  }, [spot])

  return (
    <div ref={rootRef} className="mt-8 grid items-start gap-4 md:grid-cols-2">
      <div className="flex flex-col gap-3">
        <Panel
          tone="generic"
          messages={GENERIC_CHAT}
          visibleCount={genericCount}
          typing={typingPanel === 'generic'}
          spotIndex={spot?.panel === 'generic' ? spot.index : null}
        />
        <p className="px-1 text-[14px] leading-relaxed text-muted-foreground">
          A reenactment of what general chatbots do with medical bills: guess
          at price ranges, forget your history, invent statutes, and leave you
          with a pile of maybes and homework.
        </p>
      </div>
      <div className="flex flex-col gap-3">
        <Panel
          tone="tyndale"
          messages={TYNDALE_CHAT}
          visibleCount={tyndaleCount}
          typing={typingPanel === 'tyndale'}
          spotIndex={spot?.panel === 'tyndale' ? spot.index : null}
        />
        <p className="px-1 text-[14px] leading-relaxed text-muted-foreground">
          Tyndale is connected to your EOBs, your plan, and real regulations —
          so every answer is checkable, and the conversation ends with one
          number and one plan.
        </p>
      </div>
    </div>
  )
}
