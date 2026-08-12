import Image from 'next/image';
import {
  BookOpen,
  Check,
  EyeOff,
  FileText,
  Lock,
  Phone,
  Scale,
  ShieldCheck,
  SlidersHorizontal,
  X,
  type LucideIcon,
} from 'lucide-react';
import { Logo, Wordmark } from '@/components/logo';

/* Landing content ported verbatim from docs/design/prototype-round2/lib/tyndale-data.ts.
   Illustrative example data — clearly framed as an example wherever it renders. */
const COMPARISON: { generic: string; tyndale: string }[] = [
  {
    generic: "Takes the insurer's numbers at face value",
    tyndale: "Independently recomputes, then audits your insurer's own math",
  },
  {
    generic: 'Guesses a "usual" price from memory',
    tyndale: 'Checks against real published prices',
  },
  {
    generic: 'Two different answers if you ask twice',
    tyndale: 'Deterministic math, and shows its work',
  },
  {
    generic: 'Can invent a citation',
    tyndale: 'Cites the actual statute or plan clause so you can verify',
  },
];

const GROUNDING_CHIPS = [
  'CPT / NCCI code rules',
  "Your plan's benefits",
  'Your EOBs',
  'Your deductible & out-of-pocket max',
  'Published hospital & insurer prices',
  'Federal & state law',
  "Your insurer's own policies",
];

/** The "remembers your case" proof rows — an ILLUSTRATIVE case, not a real member. */
const REMEMBERED_CASE_ROWS: { k: string; v: string }[] = [
  { k: 'Your plan', v: 'UnitedHealthcare Choice Plus' },
  { k: 'Deductible met this year', v: '$1,750.00' },
  { k: 'Open case', v: 'St. Anne — appeal due Jul 24' },
  { k: 'Resolved before', v: '2 bills, $890.00 saved' },
];

type Feature = { icon: LucideIcon; title: string; body: string };

const FEATURES: Feature[] = [
  {
    icon: FileText,
    title: 'Every line, in plain English',
    body: 'Procedure codes, modifiers, adjustments — each line item on your bill is translated into words you actually use, and verified against the care you received.',
  },
  {
    icon: Scale,
    title: 'Checked against real prices',
    body: 'Each charge is compared to your plan benefits, Medicare rates, and the prices your hospital and insurer publish — not a generic average.',
  },
  {
    icon: BookOpen,
    title: 'Findings you can verify',
    body: 'Every finding cites its source — the plan clause, the rate, the published price — so you can check the work before you pick up the phone.',
  },
  {
    icon: Phone,
    title: 'A plan, not just a report',
    body: 'Phone scripts, dispute guidance, and concrete next steps for each finding, so you know exactly who to call and what to say.',
  },
];

type Step = { title: string; body: string };

const STEPS: Step[] = [
  {
    title: 'Upload your bill and insurance info',
    body: 'Add your medical bill, your EOB, and your insurance details. Photos and PDFs both work.',
  },
  {
    title: 'Tyndale translates and checks every line',
    body: 'Each charge is explained in plain English, verified against the care you received, and checked against your plan, Medicare rates, and published prices.',
  },
  {
    title: 'Get your three-number audit and a plan',
    body: 'What you were billed, what your insurer says you owe, and what you should actually owe — with cited findings and concrete next steps.',
  },
];

type TrustItem = { icon: LucideIcon; title: string; body: string };

const TRUST: TrustItem[] = [
  {
    icon: Lock,
    title: 'Encrypted, always',
    body: 'Your documents are encrypted in transit and at rest.',
  },
  {
    icon: EyeOff,
    title: 'Never sold',
    body: 'We never sell your data — not to insurers, not to advertisers, not to anyone.',
  },
  {
    icon: SlidersHorizontal,
    title: 'You decide',
    body: 'Nothing you upload is used to improve Tyndale unless you say so — a consent toggle in your settings keeps that choice in your hands.',
  },
];

/** Illustrative three-number audit card (clearly labeled as an example). */
function AuditMock() {
  return (
    <div className="w-full max-w-md rounded-lg bg-surface p-6 shadow-elev ring-1 ring-black/5 sm:p-7">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/50">
          Your audit
        </p>
        <span className="rounded-full bg-amber-soft px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
          Example
        </span>
      </div>

      <dl className="mt-5 space-y-3">
        <div className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3">
          <dt className="text-sm text-ink/55">What you were billed</dt>
          <dd className="text-lg font-semibold text-ink/35 line-through decoration-ink/30">
            $2,347.18
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-4 rounded-md border border-line-soft px-4 py-3">
          <dt className="text-sm text-ink/55">What your insurer says you owe</dt>
          <dd className="text-lg font-semibold text-ink/70">$1,184.60</dd>
        </div>
        <div className="flex items-baseline justify-between gap-4 rounded-md bg-sage-soft px-4 py-3.5 ring-1 ring-sage/25">
          <dt className="text-sm font-medium text-teal-deep">What you should actually owe</dt>
          <dd className="text-2xl font-bold text-sage-deep">$612.40</dd>
        </div>
      </dl>

      <p className="mt-4 text-xs leading-relaxed text-ink/45">
        Every difference is a finding, cited to your plan documents and published rates.
      </p>
    </div>
  );
}

export default function HomePage() {
  return (
    <>
      {/* ── Top: navy→teal gradient spanning header + hero ── */}
      <div className="relative isolate overflow-hidden bg-gradient-to-b from-navy via-teal-deep to-teal">
        {/* Atmospheric hero photograph (prototype round 2), held behind a navy scrim so the
            A3 navy→teal gradient still reads and every hero string keeps AA contrast. */}
        <Image
          src="/hero-calm.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="-z-10 object-cover opacity-40"
        />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-navy/95 via-navy/75 to-navy/45" />
        <header>
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 text-white">
            <div className="flex items-center gap-2.5">
              <Logo size={34} />
              <Wordmark className="text-white" />
            </div>
            <a
              href="/signin"
              className="inline-flex min-h-[44px] items-center rounded-full bg-white px-4 py-2 text-sm font-medium text-ink transition hover:bg-white/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Sign in
            </a>
          </div>
        </header>

        <section>
          <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-12 px-6 pb-24 pt-12 sm:pt-16 lg:grid-cols-2 lg:gap-16">
            <div className="max-w-2xl">
              <span className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-white/90">
                Your medical bill advocate
              </span>
              <h1 className="mt-6 text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl">
                Medical bills are full of errors.{' '}
                <span className="text-white/80">Find what&rsquo;s hiding in yours.</span>
              </h1>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-white/70">
                Upload your bill and insurance documents, and Tyndale translates every charge
                into plain English, checks it against your plan and published prices, and shows
                you what you should actually owe — with the evidence to back it up.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-5">
                <a
                  href="/signin"
                  className="inline-flex items-center rounded-lg bg-white px-6 py-3 text-base font-semibold text-ink shadow-sm transition hover:bg-cream focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-teal-deep"
                >
                  Check my bill &mdash; free
                </a>
                <a
                  href="#how-it-works"
                  className="inline-flex min-h-[44px] items-center text-sm font-medium text-white/80 transition hover:text-white"
                >
                  How it works ↓
                </a>
              </div>
            </div>

            <div className="flex justify-center lg:justify-end">
              <AuditMock />
            </div>
          </div>
        </section>
      </div>

      <main>
        {/* ── B5 · Not a chatbot with opinions ── */}
        <ComparisonBand />

        {/* ── B6 · The grounding proof cards ── */}
        <GroundingBand />

        {/* ── How it works (cream) ── */}
        <section id="how-it-works" className="bg-cream">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">
                How it works
              </p>
              <h2 className="mt-4 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
                From confusing bill to clear answer
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-ink/60">
                Three steps from the envelope you dread opening to a number you can trust — and
                a plan for closing the gap.
              </p>
            </div>

            <ol className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-3">
              {STEPS.map(({ title, body }, i) => (
                <li
                  key={title}
                  className="rounded-lg bg-surface p-7 shadow-card ring-1 ring-black/[0.04]"
                >
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-teal text-base font-bold text-white">
                    {i + 1}
                  </span>
                  <h3 className="mt-5 text-base font-semibold text-ink">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink/60">{body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── Features (cream-soft) ── */}
        <section id="features" className="bg-cream-soft">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal">
                What Tyndale checks
              </p>
              <h2 className="mt-4 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
                Built to read the fine print for you
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-ink/60">
                Not a chatbot with opinions — an audit of your actual bill against your actual
                coverage, with sources attached.
              </p>
            </div>

            <ul className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <li
                  key={title}
                  className="rounded-lg bg-surface p-7 shadow-card ring-1 ring-black/[0.04]"
                >
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-md bg-teal-tint text-teal">
                    <Icon size={21} strokeWidth={1.75} aria-hidden="true" />
                  </span>
                  <h3 className="mt-5 text-base font-semibold text-ink">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink/60">{body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Trust (navy) ── */}
        <section className="bg-navy">
          <div className="mx-auto max-w-5xl px-6 py-20 text-center sm:py-24">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Your documents. Your rules.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-white/55">
              Medical bills are some of the most personal documents you have. We treat them
              that way.
            </p>

            <div className="mx-auto mt-12 grid max-w-4xl grid-cols-1 gap-6 sm:grid-cols-3">
              {TRUST.map(({ icon: Icon, title, body }) => (
                <div
                  key={title}
                  className="flex flex-col items-center rounded-lg bg-white/[0.04] px-6 py-8 ring-1 ring-white/10"
                >
                  <span className="inline-flex h-11 w-11 items-center justify-center rounded-md bg-white/10 text-white">
                    <Icon size={21} strokeWidth={1.75} aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 text-base font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{body}</p>
                </div>
              ))}
            </div>

            <div className="mt-14">
              <a
                href="/signin"
                className="inline-flex items-center rounded-lg bg-white px-6 py-3 text-base font-semibold text-ink shadow-sm transition hover:bg-cream focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-navy"
              >
                Check my bill &mdash; free
              </a>
            </div>

            <p className="mx-auto mt-10 max-w-2xl text-xs leading-relaxed text-white/40">
              Tyndale is an advocacy tool: it helps you understand and question your medical
              bills. It does not provide medical, legal, or financial advice.
            </p>
          </div>
        </section>

        {/* ── B4 · Recovered for members ── */}
        <SavingsBand />

        {/* ── Clean-bill reassurance (prototype copy; not a checklist item) ── */}
        <CleanBillBand />

        {/* ── B7/B8 · Our Story — the small band, not a cofounder block ── */}
        <OurStoryBand />
      </main>

      {/* ── Footer ── */}
      <footer className="bg-navy-deep">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="flex items-center gap-2.5 text-white">
            <Logo size={28} />
            <Wordmark className="text-base text-white" />
          </div>
          <p className="mt-5 max-w-2xl text-sm text-white/55">
            Tyndale provides medical billing and coverage advocacy, not medical, legal, or
            financial advice.
          </p>
          <nav className="mt-6 flex gap-6 text-sm text-white/70" aria-label="Footer">
            <a href="/privacy" className="transition hover:text-white">
              Privacy
            </a>
            <a href="/terms" className="transition hover:text-white">
              Terms
            </a>
            <a href="mailto:support@tyndaleapp.net" className="transition hover:text-white">
              Contact
            </a>
          </nav>
          <p className="mt-8 text-xs text-white/40">© 2026 The Little Guy LLC. d/b/a Tyndale.</p>
        </div>
      </footer>
    </>
  );
}

/* ────────────────────────────────────────────────────────────────────────────
 * Round-2 landing bands, ported from docs/design/prototype-round2.
 * Copy is VERBATIM from the prototype (no paraphrase); containers are restyled
 * to our Tailwind 3 config + the consolidated shared tokens. `sage` is the
 * money/savings ramp (#2E7D5B, checklist A4) and `citation` is A6 — we do not
 * introduce the prototype's second token vocabulary.
 * ──────────────────────────────────────────────────────────────────────────── */

/** B5 · "Not a chatbot with opinions" — same question, two very different answers. */
function ComparisonBand() {
  return (
    <section className="bg-cream-soft">
      <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
        <h2 className="max-w-3xl text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Not a chatbot with opinions.
        </h2>
        <p className="mt-4 max-w-2xl text-lg leading-relaxed text-ink/70">
          Ask the same question about the same bill. One guesses. One reads your documents,
          remembers your case, and cites the law it stands on.
        </p>

        <div className="mt-10 overflow-hidden rounded-lg ring-1 ring-line">
          <div className="grid grid-cols-1 sm:grid-cols-2">
            <div className="border-b border-line bg-surface px-5 py-3.5 sm:border-b-0 sm:border-r">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">
                A general chatbot
              </p>
            </div>
            <div className="bg-teal-tint px-5 py-3.5">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">
                Tyndale
              </p>
            </div>
          </div>
          {COMPARISON.map((row) => (
            <div key={row.tyndale} className="grid grid-cols-1 border-t border-line sm:grid-cols-2">
              <div className="flex gap-2.5 border-b border-line bg-surface px-5 py-4 sm:border-b-0 sm:border-r">
                <X size={17} className="mt-0.5 shrink-0 text-ink/35" aria-hidden="true" />
                <p className="text-base leading-6 text-ink/60">{row.generic}</p>
              </div>
              <div className="flex gap-2.5 bg-surface px-5 py-4">
                <Check size={17} className="mt-0.5 shrink-0 text-sage" aria-hidden="true" />
                <p className="text-base leading-6 text-ink">{row.tyndale}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/** B6 · The two-card grounding band — every claim traces to a source. */
function GroundingBand() {
  return (
    <section className="bg-cream">
      <div className="mx-auto grid max-w-6xl gap-5 px-6 py-20 sm:py-24 lg:grid-cols-2">
        <div className="rounded-lg bg-surface p-7 shadow-card ring-1 ring-black/[0.04]">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-md bg-teal-tint text-teal">
            <ShieldCheck size={20} aria-hidden="true" />
          </span>
          <h3 className="mt-5 text-xl font-bold tracking-tight text-ink">
            Built on the real rulebook
          </h3>
          <ul className="mt-4 flex flex-wrap gap-2">
            {GROUNDING_CHIPS.map((chip) => (
              <li
                key={chip}
                className="rounded-full bg-cream px-3 py-1.5 text-[13px] font-medium text-ink/75"
              >
                {chip}
              </li>
            ))}
          </ul>
          <p className="mt-5 text-base leading-relaxed text-ink/65">
            Not a generalist guessing — a specialist that reads the answer from the source.
          </p>
        </div>

        <div className="rounded-lg bg-surface p-7 shadow-card ring-1 ring-black/[0.04]">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-md bg-teal-tint text-teal">
            <FileText size={20} aria-hidden="true" />
          </span>
          <h3 className="mt-5 text-xl font-bold tracking-tight text-ink">Remembers your case</h3>
          <dl className="mt-4 overflow-hidden rounded-md ring-1 ring-line">
            {REMEMBERED_CASE_ROWS.map((r) => (
              <div
                key={r.k}
                className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5 last:border-0"
              >
                <dt className="text-[13px] text-ink/60">{r.k}</dt>
                <dd className="text-right text-[13px] font-semibold text-ink">{r.v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-5 text-base leading-relaxed text-ink/65">
            Your plan, your history, your deadlines — kept in one file, so you never start over.
          </p>
        </div>
      </div>
    </section>
  );
}

/** B4 · Total recovered for members. */
function SavingsBand() {
  return (
    <section className="bg-cream-soft">
      <div className="mx-auto max-w-6xl px-6 py-20 text-center sm:py-24">
        <p className="text-base font-semibold uppercase tracking-[0.14em] text-sage-deep">
          Recovered for members
        </p>
        <p className="mt-3 text-5xl font-bold tracking-tight text-sage-deep sm:text-6xl">
          $504,100
        </p>
        <p className="mx-auto mt-4 max-w-md text-base leading-relaxed text-ink/65">
          Money that was never theirs to pay, back where it belongs.
        </p>
      </div>
    </section>
  );
}

/** Clean-bill reassurance — prototype copy the checklist doesn't cover (prototype wins). */
function CleanBillBand() {
  return (
    <section className="relative isolate overflow-hidden bg-navy">
      <Image
        src="/relief-call.jpg"
        alt=""
        fill
        sizes="100vw"
        className="-z-10 object-cover object-right"
      />
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-navy via-navy/92 to-navy/45" />
      <div className="mx-auto max-w-6xl px-6 py-20 sm:py-28">
        <div className="max-w-lg">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Bill checks out? You still have moves.
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-white/80">
            Even a correct bill can be negotiated — cash prices, charity care, payment plans.
            Tyndale finds the path either way, and never sends you in without a script.
          </p>
        </div>
      </div>
    </section>
  );
}

/** B7/B8 · Our Story — a SMALL band across the page (a large cofounder block was rejected). */
function OurStoryBand() {
  return (
    <section className="bg-cream">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-5 px-6 py-14 sm:flex-row sm:gap-7">
        <Image
          src="/founders.jpg"
          alt="Tyndale&rsquo;s two cofounders"
          width={96}
          height={96}
          className="h-20 w-20 shrink-0 rounded-full object-cover ring-2 ring-line sm:h-24 sm:w-24"
        />
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Our story</p>
          <p className="mt-2 max-w-2xl text-base leading-relaxed text-ink/70">
            We started Tyndale after watching people we love overpay bills that were simply
            wrong. Insurers automate denials; hospital billing works for the hospital. We&rsquo;re
            the only party in the room with no reason to lie to you.
          </p>
        </div>
      </div>
    </section>
  );
}
