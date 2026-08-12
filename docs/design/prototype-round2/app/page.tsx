import Link from 'next/link'
import { Footer, TopNav } from '@/components/tyndale/brand'
import { Landing } from '@/components/tyndale/landing'

export default function Page() {
  return (
    <div className="min-h-dvh bg-background">
      <TopNav
        cta={
          <Link
            href="/home"
            className="inline-flex min-h-[44px] items-center rounded-full border border-white/25 px-5 text-[15px] font-semibold text-navy-foreground transition hover:bg-white/10"
          >
            Sign in
          </Link>
        }
      />
      <Landing />
      <Footer />
    </div>
  )
}
