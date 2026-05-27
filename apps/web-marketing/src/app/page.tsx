import {
  Bot,
  LogIn,
  MousePointerClick,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import { GoogleCta } from '@/components/google-cta';
import { Logo, Wordmark } from '@/components/logo';

type Feature = { icon: LucideIcon; title: string; body: string };

const FEATURES: Feature[] = [
  {
    icon: LogIn,
    title: 'Easy Sign-In',
    body: 'Log in with your Google account in one click. No extra passwords to create or remember.',
  },
  {
    icon: MousePointerClick,
    title: 'Simple to Use',
    body: 'A clean, intuitive design that makes managing your health information quick and effortless.',
  },
  {
    icon: ScanLine,
    title: 'Insurance Card Scanner',
    body: 'Snap a photo of your insurance card and we automatically read and save your coverage details.',
  },
  {
    icon: ShieldCheck,
    title: 'Your Data Stays Safe',
    body: 'Your personal and health information is protected with industry-standard security at every step.',
  },
  {
    icon: Bot,
    title: 'AI Health Assistant',
    body: 'Ask questions, review bills, or get guidance — our built-in assistant is here to help anytime.',
  },
  {
    icon: RefreshCw,
    title: 'Always Up to Date',
    body: 'See your coverage details, cost estimates, and account activity in real time.',
  },
];

const BADGES = [
  { title: 'Fast', caption: 'LOADS IN UNDER A SECOND' },
  { title: 'Secure', caption: 'ENCRYPTED & PROTECTED' },
  { title: 'Reliable', caption: 'ALWAYS AVAILABLE' },
];

export default function HomePage() {
  return (
    <>
      {/* ── Top: dark hero ───────────────────────────────────────────── */}
      <header className="bg-ink">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-2.5 text-white">
            <Logo size={34} />
            <Wordmark />
          </div>
          <a
            href="/signin"
            className="rounded-md border border-white/25 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            Sign In
          </a>
        </div>
      </header>

      <main>
        <section className="bg-ink">
          <div className="mx-auto max-w-3xl px-6 pb-24 pt-16 text-center sm:pt-24">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider text-white/80">
              <span className="h-2 w-2 rounded-full bg-sage" />
              AI-Powered Health Platform
            </span>
            <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight text-white sm:text-5xl">
              Tyndale. Welcome to the App.
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-white/70">
              Sign in with your Google account to get started. New users will be asked to
              complete a quick profile setup.
            </p>
            <div className="mt-9 flex flex-col items-center gap-4">
              <GoogleCta />
              <a
                href="#features"
                className="text-sm font-medium text-white/80 transition hover:text-white"
              >
                Learn more →
              </a>
            </div>
          </div>
        </section>

        {/* ── Middle: cream features ─────────────────────────────────── */}
        <section id="features" className="bg-cream">
          <div className="mx-auto max-w-6xl px-6 py-20 sm:py-24">
            <div className="text-center">
              <span className="inline-block rounded-full bg-teal-tint px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider text-teal-deep">
                Features
              </span>
              <h2 className="mt-5 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
                Simple. Fast. Secure.
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-lg text-ink/70">
                Everything you need to manage your health information in one place, designed to
                be easy for everyone.
              </p>
            </div>

            <ul className="mt-14 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ icon: Icon, title, body }) => (
                <li
                  key={title}
                  className="rounded-lg border border-line-card bg-surface p-6 shadow-card"
                >
                  <span className="inline-flex h-12 w-12 items-center justify-center rounded-md bg-sage-tint text-sage-deep">
                    <Icon size={24} strokeWidth={2} aria-hidden="true" />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold text-ink">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink/70">{body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── Bottom: dark "Built for you" ───────────────────────────── */}
        <section className="bg-ink">
          <div className="mx-auto max-w-5xl px-6 py-20 text-center sm:py-24">
            <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Built for you
            </h2>
            <p className="mt-4 text-lg text-white/70">
              Designed to work the way you expect — every time.
            </p>
            <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-3">
              {BADGES.map(({ title, caption }) => (
                <div key={title} className="flex flex-col items-center">
                  <span className="text-2xl font-bold text-sage">{title}</span>
                  <span className="mt-2 text-xs font-semibold uppercase tracking-wider text-white/55">
                    {caption}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="bg-ink-deep">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="flex items-center gap-2.5 text-white">
            <Logo size={28} />
            <Wordmark className="text-base" />
          </div>
          <p className="mt-5 max-w-2xl text-sm text-white/60">
            Tyndale provides medical billing and coverage advocacy, not medical, legal, or
            financial advice.
          </p>
          <nav className="mt-6 flex gap-6 text-sm text-white/75" aria-label="Footer">
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
          <p className="mt-8 text-xs text-white/45">
            © 2026 The Little Guy LLC. d/b/a Tyndale.
          </p>
        </div>
      </footer>
    </>
  );
}
