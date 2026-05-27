import { Logo, Wordmark } from '@/components/logo';

export const metadata = { title: 'Sign In — Tyndale' };

export default function SignInPage() {
  return (
    <main className="flex min-h-[70vh] flex-col items-center justify-center bg-cream px-6 text-center">
      <div className="flex items-center gap-2.5 text-ink">
        <Logo size={36} />
        <Wordmark />
      </div>
      <h1 className="mt-8 text-2xl font-bold tracking-tight text-ink">Sign in coming online in Phase 2</h1>
      <p className="mt-3 max-w-md text-ink/70">
        Authentication (Google + Email) is scaffolded but not yet wired. It activates once the
        runtime is up in Phase 2.
      </p>
      <a
        href="/"
        className="mt-8 rounded-md bg-teal px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-teal"
      >
        ← Back home
      </a>
    </main>
  );
}
