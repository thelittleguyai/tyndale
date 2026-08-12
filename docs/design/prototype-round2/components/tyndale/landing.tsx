import Image from 'next/image'
import Link from 'next/link'
import {
  ArrowRight,
  BookText,
  Calculator,
  CalendarCheck,
  Check,
  FileText,
  Lock,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from 'lucide-react'
import {
  GROUNDING_CHIPS,
  money,
  REMEMBERED_CASE,
  STATS,
  STATS_SOURCE,
  TIPS,
  TOTAL_MEMBER_SAVINGS,
} from '@/lib/tyndale-data'
import { ThreeNumbers } from './three-numbers'
import { AuditDemo } from './audit-demo'
import { ChatCompare } from './chat-compare'
import { AmbientAuras, ChoiceChip, GlassCard } from './glass'

export function Landing() {
  return (
    <main>
      <Hero />
      <ChoiceBand />
      <FlowBand />
      <ComparisonBand />
      <ProofCards />
      <StatsBand />
      <SavingsBand />
      <CleanBillBand />
      <TipsBand />
      <OurStory />
      <BetaBand />
    </main>
  )
}

/* 2 · Hero — full-bleed atmospheric photo, floating glass audit card */
function Hero() {
  return (
    <section className="relative isolate overflow-hidden">
      {/* Atmospheric photography with a gentle drift */}
      <div className="absolute inset-0 -z-10">
        <Image
          src="/hero-calm.png"
          alt=""
          fill
          priority
          className="animate-kenburns object-cover"
        />
        {/* Navy scrim — darker on the left where the copy lives */}
        <div className="absolute inset-0 bg-gradient-to-r from-navy/95 via-navy/80 to-navy/35" />
        <div className="absolute inset-0 bg-gradient-to-t from-navy/70 via-transparent to-navy/40" />
      </div>

      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-5 py-20 md:min-h-[88vh] md:grid-cols-[1.05fr_0.95fr] md:py-24">
        <div className="text-navy-foreground">
          <p className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[13px] font-semibold uppercase tracking-wide backdrop-blur">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Your medical bill advocate
          </p>
          <h1 className="mt-5 max-w-xl text-balance font-display text-[2.6rem] font-bold leading-[1.05] md:text-6xl">
            Your medical bill is probably wrong.{' '}
            <span className="text-money-soft">Find what&apos;s hiding in it.</span>
          </h1>
          <p className="mt-5 max-w-md text-pretty text-[17px] leading-relaxed text-navy-foreground/85">
            Upload your bill. Tyndale recomputes what you truly owe against your
            real plan and real prices — and shows you the proof.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/upload"
              className="inline-flex min-h-[56px] items-center justify-center gap-2 rounded-full bg-money px-8 text-[17px] font-semibold text-white shadow-float transition hover:brightness-110"
            >
              Check my bill — free
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
          </div>
        </div>

        {/* Floating product visualization */}
        <div className="relative mx-auto w-full max-w-sm md:pl-4">
          <ThreeNumbers glass className="animate-float-slow" />
          {/* Floating glass finding chip drifting off the top-right corner */}
          <GlassCard
            float
            className="absolute -right-3 -top-7 hidden w-56 p-3.5 sm:block lg:-right-8"
          >
            <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-money">
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              Finding
            </div>
            <p className="mt-1 text-[14px] font-medium leading-snug text-foreground">
              Duplicate MRI charge
            </p>
            <p className="mt-0.5 text-[12px] text-muted-foreground">
              cited to your bill · {money(389)}
            </p>
          </GlassCard>
        </div>
      </div>

      {/* Recovered-for-patients counter — anchored bottom right of the hero */}
      <div className="pointer-events-none absolute bottom-24 right-5 z-10 text-right md:bottom-28 md:right-10">
        <p className="font-display text-4xl font-bold text-money-soft md:text-5xl">
          {money(TOTAL_MEMBER_SAVINGS)}
        </p>
        <p className="mt-1 text-[13px] font-semibold uppercase tracking-wide text-navy-foreground/75">
          recovered for patients
        </p>
      </div>
    </section>
  )
}

/* 2b · Calm-style conversational entry — "What brings you in today?" */
function ChoiceBand() {
  return (
    <section className="relative isolate overflow-hidden bg-accent/40">
      <AmbientAuras variant="calm" />
      <div className="relative mx-auto w-full max-w-3xl px-5 py-16 text-center md:py-20">
        <h2 className="text-balance font-display text-3xl font-bold text-foreground">
          What brings you in today?
        </h2>
        <p className="mx-auto mt-3 max-w-md text-[16px] leading-relaxed text-muted-foreground">
          Start wherever you are. Tyndale takes it from there — one calm step at
          a time.
        </p>
        <div className="mx-auto mt-8 grid max-w-xl gap-3 text-left sm:grid-cols-2">
          <ChoiceChip
            href="/upload"
            icon={<ReceiptText className="h-5 w-5" aria-hidden="true" />}
            label="Check a bill I got"
            hint="Find what you shouldn't owe"
          />
          <ChoiceChip
            href="/estimate"
            icon={<Calculator className="h-5 w-5" aria-hidden="true" />}
            label="Estimate a cost first"
            hint="Know before you go"
          />
          <ChoiceChip
            href="/find-doctor"
            icon={<Stethoscope className="h-5 w-5" aria-hidden="true" />}
            label="Find an in-network doctor"
            hint="Avoid a surprise bill"
          />
          <ChoiceChip
            href="/plan-visit"
            icon={<CalendarCheck className="h-5 w-5" aria-hidden="true" />}
            label="Plan an upcoming visit"
            hint="Walk in knowing what's covered"
          />
        </div>
      </div>
    </section>
  )
}

/* 3 · How-it-works — animated product demo: add → audit → sorted */
function FlowBand() {
  return (
    <section className="relative isolate overflow-hidden">
      <AmbientAuras variant="calm" className="opacity-80" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 md:py-24">
        <h2 className="text-balance font-display text-3xl font-bold text-foreground">
          How it works
        </h2>
        <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-muted-foreground">
          Watch a pile of confusing bills become three clear moves — no
          spreadsheets, no hold music, no guessing.
        </p>
        <div className="mx-auto mt-8 max-w-3xl">
          <AuditDemo />
        </div>
        <p className="mt-6 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
          A real audit — read from the source, not guessed. Every number traces
          back to a document you can open.
        </p>
      </div>
    </section>
  )
}

/* 4 · "Not a chatbot with opinions" — same question, two very different answers */
function ComparisonBand() {
  return (
    <section className="relative isolate overflow-hidden bg-secondary/50">
      <AmbientAuras variant="calm" className="opacity-60" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 md:py-24">
        <h2 className="text-balance font-display text-3xl font-bold text-foreground">
          Not a chatbot with opinions.
        </h2>
        <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-muted-foreground">
          Ask the same question about the same bill. One guesses. One reads
          your documents, remembers your case, and cites the law it stands on.
        </p>

        <ChatCompare />
      </div>
    </section>
  )
}

/* 5 · Two proof cards — Built on the real rulebook / Remembers your case */
function ProofCards() {
  return (
    <section className="relative isolate overflow-hidden">
      <AmbientAuras variant="warm" className="opacity-70" />
      <div className="relative mx-auto grid w-full max-w-5xl gap-4 px-5 py-16 md:grid-cols-2 md:py-20">
      <div className="glass-tile rounded-3xl p-6">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-primary">
          <ShieldCheck className="h-5 w-5" aria-hidden="true" />
        </div>
        <h3 className="mt-4 font-display text-xl font-bold text-foreground">
          Built on the real rulebook
        </h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {GROUNDING_CHIPS.map((chip) => (
            <span
              key={chip}
              className="rounded-full bg-secondary px-3 py-1.5 text-[13px] font-medium text-secondary-foreground"
            >
              {chip}
            </span>
          ))}
        </div>
        <p className="mt-4 text-[14px] leading-relaxed text-muted-foreground">
          Not a generalist guessing — a specialist that reads the answer from
          the source.
        </p>
      </div>

      <div className="glass-tile rounded-3xl p-6">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-primary">
          <FileText className="h-5 w-5" aria-hidden="true" />
        </div>
        <h3 className="mt-4 font-display text-xl font-bold text-foreground">
          Remembers your case
        </h3>
        <dl className="mt-4 overflow-hidden rounded-xl border border-border">
          {[
            { k: 'Your plan', v: REMEMBERED_CASE.plan },
            { k: 'Deductible met this year', v: money(REMEMBERED_CASE.deductibleMet) },
            { k: 'Open case', v: REMEMBERED_CASE.openCase },
            {
              k: 'Resolved before',
              v: `${REMEMBERED_CASE.priorBills} bills, ${money(REMEMBERED_CASE.priorRecoveries)} saved`,
            },
          ].map((r) => (
            <div
              key={r.k}
              className="flex items-center justify-between gap-3 border-b border-border px-3.5 py-2.5 last:border-0"
            >
              <dt className="text-[13px] text-muted-foreground">{r.k}</dt>
              <dd className="text-right text-[13px] font-semibold text-foreground">
                {r.v}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-[14px] leading-relaxed text-muted-foreground">
          Your plan, your history, your deadlines — kept in one file, so you
          never start over.
        </p>
      </div>
      </div>
    </section>
  )
}

/* 6 · Stats band — immersive dark with ambient auras */
function StatsBand() {
  return (
    <section className="relative isolate overflow-hidden bg-navy text-navy-foreground">
      <AmbientAuras variant="money" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 md:py-24">
        <h2 className="text-balance font-display text-3xl font-bold">
          You&apos;re probably not checking. Most people aren&apos;t.
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map((s) => (
            <GlassCard key={s.value} tone="dark" className="p-5">
              <p className="font-display text-4xl font-bold text-money-soft">
                {s.value}
              </p>
              <p className="mt-2 text-[14px] leading-relaxed text-navy-foreground/75">
                {s.label}
              </p>
            </GlassCard>
          ))}
        </div>
        <p className="mt-6 text-[13px] text-navy-foreground/55">{STATS_SOURCE}</p>
      </div>
    </section>
  )
}

/* 7 · Total-savings band */
function SavingsBand() {
  return (
    <section className="relative isolate overflow-hidden">
      <AmbientAuras variant="money" className="opacity-70" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 text-center md:py-24">
        <p className="text-[15px] font-semibold uppercase tracking-wide text-money">
          Recovered for members
        </p>
        <p className="mt-3 font-display text-5xl font-bold text-money md:text-6xl">
          {money(TOTAL_MEMBER_SAVINGS)}
        </p>
        <p className="mx-auto mt-3 max-w-md text-[16px] leading-relaxed text-muted-foreground">
          Money that was never theirs to pay, back where it belongs.
        </p>
      </div>
    </section>
  )
}

/* 8 · Clean-bill band — atmospheric relief image + reassurance */
function CleanBillBand() {
  return (
    <section className="relative isolate overflow-hidden bg-navy text-navy-foreground">
      <div className="absolute inset-0 -z-10">
        <Image src="/relief-call.png" alt="" fill className="object-cover object-right" />
        <div className="absolute inset-0 bg-gradient-to-r from-navy via-navy/90 to-navy/40" />
      </div>
      <div className="mx-auto w-full max-w-5xl px-5 py-20 md:py-28">
        <div className="max-w-lg">
          <h2 className="text-balance font-display text-3xl font-bold">
            Bill checks out? You still have moves.
          </h2>
          <p className="mt-4 text-pretty text-[17px] leading-relaxed text-navy-foreground/85">
            Even a correct bill can be negotiated — cash prices, charity care,
            payment plans. Tyndale finds the path either way, and never sends you
            in without a script.
          </p>
        </div>
      </div>
    </section>
  )
}

/* 9 · Tips & tricks band — subscription-gated tease */
function TipsBand() {
  return (
    <section className="relative isolate overflow-hidden">
      <AmbientAuras variant="calm" className="opacity-70" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 md:py-24">
      <h2 className="text-balance font-display text-3xl font-bold text-foreground">
        The playbook the billing office hopes you don&apos;t have.
      </h2>
      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {TIPS.map((tip) => (
          <div
            key={tip}
            className="glass-tile flex items-start gap-3 rounded-2xl p-4"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Lock className="h-4 w-4" aria-hidden="true" />
            </span>
            <p className="text-[15px] font-medium leading-snug text-foreground/80">
              {tip}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-7">
        <Link
          href="/upload"
          className="inline-flex min-h-[48px] items-center gap-2 rounded-full bg-primary px-6 text-[15px] font-semibold text-primary-foreground transition hover:brightness-110"
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Unlock the full playbook
        </Link>
      </div>
      </div>
    </section>
  )
}

/* 10 · Our Story — small, quiet strip */
function OurStory() {
  return (
    <section className="bg-secondary/50">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-5 px-5 py-12 sm:flex-row sm:gap-6">
        <Image
          src="/founders.png"
          alt="Tyndale's two cofounders"
          width={96}
          height={96}
          className="h-20 w-20 shrink-0 rounded-full object-cover ring-2 ring-border sm:h-24 sm:w-24"
        />
        <div>
          <p className="text-[13px] font-semibold uppercase tracking-wide text-primary">
            Our story
          </p>
          <p className="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
            We started Tyndale after watching people we love overpay bills that
            were simply wrong. Insurers automate denials; hospital billing works
            for the hospital. We&apos;re the only party in the room with no
            reason to lie to you.
          </p>
        </div>
      </div>
    </section>
  )
}

/* 11 · Beta / community band */
function BetaBand() {
  return (
    <section className="relative isolate overflow-hidden bg-accent/40">
      <AmbientAuras variant="calm" />
      <div className="relative mx-auto w-full max-w-5xl px-5 py-16 text-center md:py-24">
        <p className="inline-flex items-center gap-2 rounded-full bg-accent px-3 py-1.5 text-[13px] font-semibold text-primary">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Tyndale is just getting started
        </p>
        <h2 className="mx-auto mt-5 max-w-2xl text-balance font-display text-3xl font-bold text-foreground">
          Every bill Tyndale sees makes it sharper.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-[16px] leading-relaxed text-muted-foreground">
          We&apos;re early — and more errors caught means more people helped. Fix
          your bill, and you make the next person&apos;s fight easier too.
        </p>
        <div className="mt-8 flex flex-col items-center gap-3">
          <Link
            href="/upload"
            className="inline-flex min-h-[56px] items-center justify-center gap-2 rounded-full bg-money px-8 text-[17px] font-semibold text-white shadow-float transition hover:brightness-110"
          >
            Check my bill — free
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Link>
          <span className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-citation-soft px-3 py-1 text-[12px] font-medium text-citation">
              <BookText className="h-3.5 w-3.5" aria-hidden="true" />
              Verified &amp; cited
            </span>
            Every stat and rule traces to a source.
          </span>
        </div>
      </div>
    </section>
  )
}
