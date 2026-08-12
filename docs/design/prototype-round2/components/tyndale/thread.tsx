'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  Layers,
  PartyPopper,
  SendHorizonal,
  X,
} from 'lucide-react'
import { AUDIT, FINDINGS, money, PLAN_STEPS, VERIFICATIONS } from '@/lib/tyndale-data'
import { cn } from '@/lib/utils'
import { AppHeader } from './app-header'
import { AgentAttachment, AgentSays, UserSays } from './chat'
import { StatusCard } from './status-card'
import {
  PreSelectedVerificationCard,
  VerificationCard,
} from './verification-card'
import { FindingCard } from './finding-card'
import { RevealCard, UnlockCard } from './moments'
import { ActionCard } from './action-card'
import { ChecklistCard, DeadlineBanner, RelationshipMenu } from './support-cards'
import {
  BlurryUploadCard,
  HonestOddsCard,
  NumbersDisagreeCard,
  SummaryBillCard,
  WrongDocumentCard,
} from './branch-cards'
import { AnswerPill } from './primitives'
import { useCase, type VerifyAnswer } from './case-provider'

const PHASE_ORDER = ['processing', 'verifying', 'revealed', 'unlocked', 'planned']

export function Thread() {
  const c = useCase()
  const phaseIndex = PHASE_ORDER.indexOf(c.phase)
  const atOrPast = (p: string) => phaseIndex >= PHASE_ORDER.indexOf(p)

  const bottomRef = useRef<HTMLDivElement>(null)
  const [branch, setBranch] = useState<string | null>(null)
  const [scenariosOpen, setScenariosOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [showPreselect, setShowPreselect] = useState(false)
  const [preselectConfirmed, setPreselectConfirmed] = useState(false)
  const [composerNote, setComposerNote] = useState<string | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [c.phase, c.unlocked, c.resolved, c.callOutcome, showPreselect, branch, composerNote])

  const allAnswered = VERIFICATIONS.every((v) => c.verifyAnswers[v.id])

  const submitComposer = (e: React.FormEvent) => {
    e.preventDefault()
    if ((e.nativeEvent as any)?.isComposing) return
    const text = typed.trim()
    if (!text) return
    setTyped('')
    if (c.phase === 'verifying') {
      setShowPreselect(true)
    } else {
      setComposerNote(text)
    }
  }

  if (branch) {
    return (
      <BranchView branch={branch} onBack={() => setBranch(null)} />
    )
  }

  return (
    <div className="relative flex min-h-dvh flex-col bg-gradient-to-b from-accent/50 via-background to-background">
      <AppHeader
        backHref="/home"
        backLabel="Back to home"
        title={AUDIT.provider}
        subtitle={`${AUDIT.payer} · service ${AUDIT.serviceDate}`}
        right={
          <button
            type="button"
            onClick={() => setScenariosOpen(true)}
            className="inline-flex h-11 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold text-navy-foreground/80 hover:bg-white/10"
          >
            <Layers className="h-4 w-4" aria-hidden="true" />
            Scenarios
          </button>
        }
      />

      <main className="mx-auto w-full max-w-md flex-1 px-4 pb-40 pt-6">
        <div className="flex flex-col gap-4">
          {/* Opening acknowledgment */}
          <div className="animate-rise">
            <AgentSays>
              Got your documents. I used your details to connect to{' '}
              {AUDIT.payer} and pulled your EOBs automatically — no need to hunt
              for them. Reading everything now…
            </AgentSays>
          </div>

          {/* Processing */}
          {c.phase === 'processing' && (
            <AgentAttachment className="animate-rise">
              <StatusCard onComplete={() => c.setPhase('verifying')} />
            </AgentAttachment>
          )}

          {/* Verification */}
          {atOrPast('verifying') && (
            <>
              <div className="animate-rise">
                <AgentSays>
                  Before I audit, let&apos;s confirm what happened at your visit
                  — three quick ones:
                </AgentSays>
              </div>

              {c.phase === 'verifying' ? (
                <>
                  <AgentAttachment className="flex flex-col gap-3">
                    {VERIFICATIONS.map((v) => (
                      <VerificationCard
                        key={v.id}
                        item={v}
                        answer={c.verifyAnswers[v.id]}
                        onAnswer={(a) => c.answerVerify(v.id, a)}
                      />
                    ))}
                  </AgentAttachment>

                  {showPreselect && (
                    <>
                      <UserSays>The second one never happened.</UserSays>
                      <AgentAttachment className="animate-rise">
                        <PreSelectedVerificationCard
                          confirmed={preselectConfirmed}
                          onConfirm={() => {
                            setPreselectConfirmed(true)
                            c.answerVerify('second-mri', 'no')
                          }}
                        />
                      </AgentAttachment>
                    </>
                  )}

                  <AgentAttachment>
                    <button
                      type="button"
                      onClick={() => c.setPhase('revealed')}
                      className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-money px-4 text-[16px] font-semibold text-white transition hover:brightness-110"
                    >
                      {allAnswered ? 'That\u2019s everything — run my audit' : 'Run my audit'}
                      <ArrowRight className="h-5 w-5" aria-hidden="true" />
                    </button>
                    {!allAnswered && (
                      <p className="mt-2 text-center text-[13px] text-muted-foreground">
                        &ldquo;Not sure&rdquo; is always fine — I&apos;ll never
                        penalize you for it.
                      </p>
                    )}
                  </AgentAttachment>
                </>
              ) : (
                <VerificationRecap answers={c.verifyAnswers} />
              )}
            </>
          )}

          {/* The reveal + findings + unlock */}
          {atOrPast('revealed') && (
            <>
              <div className="animate-rise">
                <AgentSays>
                  I&apos;ve finished. I checked every charge against your plan and
                  the published rates — here&apos;s where it landed.
                </AgentSays>
              </div>

              <AgentAttachment>
                <RevealCard />
              </AgentAttachment>

              <div className="animate-rise">
                <AgentSays>
                  I found <span className="font-semibold">3 problems</span>. Each
                  one is sourced — tap any citation to see where it came from.
                </AgentSays>
              </div>

              <AgentAttachment className="flex flex-col gap-3">
                {FINDINGS.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))}
              </AgentAttachment>

              <div className="animate-rise">
                <AgentSays>
                  That&apos;s the whole picture — findings are complete and free.
                  Nothing is hidden behind a paywall.
                </AgentSays>
              </div>

              <AgentAttachment>
                <UnlockCard
                  unlocked={c.unlocked}
                  onUnlock={() => {
                    c.setUnlocked(true)
                    c.setPhase('unlocked')
                  }}
                />
              </AgentAttachment>
            </>
          )}

          {/* Resolution plan */}
          {c.unlocked && atOrPast('unlocked') && (
            <>
              <div className="animate-rise">
                <AgentSays>
                  Here&apos;s your plan — biggest wins first. I&apos;ll be right
                  here for each one.
                </AgentSays>
              </div>

              <AgentAttachment className="flex flex-col gap-3">
                {PLAN_STEPS.map((s) => (
                  <ActionCard key={s.id} step={s} />
                ))}
              </AgentAttachment>

              <FollowThrough />
            </>
          )}

          {composerNote && (
            <>
              <UserSays>{composerNote}</UserSays>
              <div className="animate-rise">
                <AgentSays>
                  I&apos;ve got that noted on your case — it stays open right
                  here, and I&apos;ll fold it into the next step. Anything you go
                  get, bring it back and I&apos;ll pick up where we left off.
                </AgentSays>
              </div>
            </>
          )}

          <div ref={bottomRef} />
        </div>
      </main>

      {/* Composer */}
      <div className="fixed inset-x-0 bottom-0 z-20 bg-gradient-to-t from-background via-background/90 to-transparent px-4 pb-4 pt-6">
        <form
          onSubmit={submitComposer}
          className="glass mx-auto flex w-full max-w-md items-center gap-2 rounded-full p-1.5 pl-2"
        >
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="Type to Tyndale — you can correct me anytime"
            aria-label="Message Tyndale"
            className="min-h-[44px] flex-1 rounded-full bg-transparent px-3 text-[16px] text-foreground outline-none placeholder:text-muted-foreground/80"
          />
          <button
            type="submit"
            aria-label="Send"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition hover:brightness-110"
          >
            <SendHorizonal className="h-5 w-5" aria-hidden="true" />
          </button>
        </form>
      </div>

      {scenariosOpen && (
        <ScenariosSheet
          onClose={() => setScenariosOpen(false)}
          onPick={(b) => {
            setBranch(b)
            setScenariosOpen(false)
          }}
        />
      )}
    </div>
  )
}

function VerificationRecap({
  answers,
}: {
  answers: Record<string, VerifyAnswer>
}) {
  return (
    <AgentAttachment className="flex flex-col gap-2">
      {VERIFICATIONS.map((v) => (
        <div
          key={v.id}
          className="flex items-center justify-between gap-2 rounded-xl bg-card px-3 py-2.5 text-[14px] ring-1 ring-border"
        >
          <span className="text-foreground">{v.line}</span>
          {answers[v.id] ? (
            <AnswerPill answer={answers[v.id]} />
          ) : (
            <AnswerPill answer="notsure" />
          )}
        </div>
      ))}
    </AgentAttachment>
  )
}

function FollowThrough() {
  const c = useCase()

  return (
    <>
      <div className="animate-rise">
        <AgentSays>
          Once you&apos;ve made a call, I&apos;ll track what happens. Here&apos;s
          where your case stands — you don&apos;t have to remember any of it.
        </AgentSays>
      </div>

      <AgentAttachment>
        <DeadlineBanner recovered={c.resolved ? AUDIT.gap : 0} />
      </AgentAttachment>

      {c.callOutcome === 'pushback' && (
        <div className="animate-rise">
          <AgentSays>
            That&apos;s okay — expected, even. A &ldquo;no&rdquo; on the first
            call doesn&apos;t mean you&apos;re wrong; the finding still holds.
            When their deadline passes I&apos;ll line up the supervisor script
            and, if needed, a written appeal.
          </AgentSays>
        </div>
      )}
      {c.callOutcome === 'voicemail' && (
        <div className="animate-rise">
          <AgentSays>
            Left a message — nice work. I&apos;ll remind you to follow up in a
            few days if they haven&apos;t called back. Nothing for you to
            remember.
          </AgentSays>
        </div>
      )}

      {!c.resolved ? (
        <AgentAttachment>
          <button
            type="button"
            onClick={() => c.setResolved(true)}
            className="w-full rounded-xl border border-dashed border-border bg-card px-4 py-3 text-[14px] font-medium text-muted-foreground hover:bg-muted"
          >
            Prototype: simulate a corrected EOB arriving from {AUDIT.payer}
          </button>
        </AgentAttachment>
      ) : (
        <>
          <section className="animate-pop overflow-hidden rounded-3xl bg-money p-6 text-center text-white shadow-lg">
            <PartyPopper className="mx-auto h-8 w-8" aria-hidden="true" />
            <p className="mt-3 text-[15px] font-medium text-white/85">
              A corrected EOB just arrived. Here&apos;s what changed:
            </p>
            <p className="mt-2 text-[15px] font-semibold uppercase tracking-wide text-white/80">
              Recovered
            </p>
            <p className="font-display text-5xl font-bold">{money(AUDIT.gap)}</p>
          </section>

          <div className="animate-rise">
            <AgentSays>
              Even after today, I&apos;m still on this: I&apos;ll watch your
              deadlines, re-check the numbers if new documents show up, and keep
              your Record current.
            </AgentSays>
          </div>

          <AgentAttachment>
            <Link
              href="/home"
              className="flex min-h-[52px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground transition hover:brightness-110"
            >
              See it on my home
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
          </AgentAttachment>
        </>
      )}
    </>
  )
}

/* ---------- Branch scenarios ---------- */

const BRANCHES: {
  id: string
  code: string
  label: string
}[] = [
  { id: 'b1', code: 'B1', label: 'Name on bill ≠ account holder' },
  { id: 'b6', code: 'B6', label: 'Missing docs limit the audit' },
  { id: 'b2', code: 'B2', label: 'Blurry / partial upload' },
  { id: 'b3', code: 'B3', label: 'Wrong document uploaded' },
  { id: 'b4', code: 'B4', label: 'Summary bill, not itemized' },
  { id: 'b5', code: 'B5', label: 'Documents seem to contradict' },
  { id: 'b10', code: 'B10', label: 'Asked to exaggerate or guarantee' },
]

function ScenariosSheet({
  onClose,
  onPick,
}: {
  onClose: () => void
  onPick: (b: string) => void
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-navy/40" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-t-3xl bg-background p-5 pb-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-foreground">
            Branch states
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-muted"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-1 text-[14px] text-muted-foreground">
          Every branch ends with a next step — no dead ends. Preview each one:
        </p>
        <div className="mt-4 flex flex-col gap-2">
          {BRANCHES.map((b) => (
            <button
              key={b.id}
              type="button"
              onClick={() => onPick(b.id)}
              className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left hover:bg-muted"
            >
              <span className="inline-flex h-7 shrink-0 items-center justify-center rounded-full bg-accent px-2 text-[13px] font-bold text-primary">
                {b.code}
              </span>
              <span className="text-[15px] font-medium text-foreground">
                {b.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function BranchView({ branch, onBack }: { branch: string; onBack: () => void }) {
  const meta = BRANCHES.find((b) => b.id === branch)
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <AppHeader
        backHref="#"
        backLabel="Back to case"
        title={meta?.label ?? 'Scenario'}
        subtitle={`Branch ${meta?.code}`}
        right={
          <button
            type="button"
            onClick={onBack}
            className="inline-flex h-11 items-center rounded-full px-3 text-[13px] font-semibold text-navy-foreground/80 hover:bg-white/10"
          >
            Done
          </button>
        }
      />
      {/* intercept the back arrow */}
      <button
        type="button"
        onClick={onBack}
        aria-hidden="true"
        className="sr-only"
      />
      <main className="mx-auto w-full max-w-md flex-1 px-4 pb-16 pt-6">
        <div className="flex flex-col gap-4">
          <BranchBody branch={branch} />
        </div>
      </main>
      <div className="sticky bottom-0 border-t border-border bg-background px-4 py-3">
        <div className="mx-auto w-full max-w-md">
          <button
            type="button"
            onClick={onBack}
            className="flex min-h-[50px] w-full items-center justify-center rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground hover:brightness-110"
          >
            Back to my case
          </button>
        </div>
      </div>
    </div>
  )
}

function BranchBody({ branch }: { branch: string }) {
  switch (branch) {
    case 'b1':
      return (
        <>
          <AgentSays>
            This bill is for <span className="font-semibold">Sarah Chen</span>,
            and your account is registered to{' '}
            <span className="font-semibold">Alex Chen</span>. Quick check before
            I dig in — what&apos;s your relationship to Sarah Chen?
          </AgentSays>
          <AgentAttachment>
            <RelationshipMenu />
          </AgentAttachment>
        </>
      )
    case 'b6':
      return (
        <>
          <AgentSays>
            Here&apos;s what I found so far. To lock in the numbers I need two
            things:
          </AgentSays>
          <AgentAttachment className="flex flex-col gap-3">
            {FINDINGS.slice(0, 1).map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
            <ChecklistCard />
          </AgentAttachment>
        </>
      )
    case 'b2':
      return (
        <>
          <AgentSays>Here&apos;s where I got to on your bill.</AgentSays>
          <AgentAttachment>
            <BlurryUploadCard />
          </AgentAttachment>
        </>
      )
    case 'b3':
      return (
        <AgentAttachment>
          <WrongDocumentCard />
        </AgentAttachment>
      )
    case 'b4':
      return (
        <>
          <AgentSays>
            This looks like a summary statement rather than an itemized bill.
          </AgentSays>
          <AgentAttachment>
            <SummaryBillCard />
          </AgentAttachment>
        </>
      )
    case 'b5':
      return (
        <AgentAttachment>
          <NumbersDisagreeCard />
        </AgentAttachment>
      )
    case 'b10':
      return (
        <>
          <UserSays>
            Can you guarantee I&apos;ll win? Maybe make it sound worse than it is
            so they take me seriously.
          </UserSays>
          <AgentAttachment>
            <HonestOddsCard />
          </AgentAttachment>
        </>
      )
    default:
      return null
  }
}
