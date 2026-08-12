import Image from 'next/image'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Shared building blocks for the calm / immersive aesthetic:
 * frosted-glass surfaces, soft ambient auras, and conversational choice chips.
 */

/* Frosted glass panel. tone="light" floats over imagery; tone="dark" over navy. */
export function GlassCard({
  children,
  className,
  tone = 'light',
  float,
}: {
  children: React.ReactNode
  className?: string
  tone?: 'light' | 'dark'
  float?: boolean | 'slow'
}) {
  return (
    <div
      className={cn(
        'rounded-3xl',
        tone === 'light' ? 'glass' : 'glass-dark',
        float === true && 'animate-float',
        float === 'slow' && 'animate-float-slow',
        className,
      )}
    >
      {children}
    </div>
  )
}

/* Soft blurred color auras — atmospheric depth behind content (not hard blobs). */
export function AmbientAuras({
  className,
  variant = 'calm',
}: {
  className?: string
  variant?: 'calm' | 'money' | 'warm'
}) {
  const palettes = {
    calm: ['bg-primary/25', 'bg-citation/20'],
    money: ['bg-money/25', 'bg-primary/20'],
    warm: ['bg-amber/20', 'bg-primary/20'],
  }[variant]
  return (
    <div
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}
    >
      <div className={cn('aura absolute -left-24 -top-24 h-80 w-80 rounded-full', palettes[0])} />
      <div
        className={cn(
          'aura absolute -bottom-32 -right-16 h-96 w-96 rounded-full',
          palettes[1],
        )}
      />
    </div>
  )
}

/* Fixed, full-page ambient color wash. Sits behind glass tiles so their
   translucency has something soft to reveal. */
export function PageAmbience({
  variant = 'calm',
}: {
  variant?: 'calm' | 'money' | 'warm'
}) {
  const palettes = {
    calm: ['bg-primary/20', 'bg-citation/15', 'bg-money/10'],
    money: ['bg-money/20', 'bg-primary/15', 'bg-citation/10'],
    warm: ['bg-amber/15', 'bg-primary/15', 'bg-money/10'],
  }[variant]
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className={cn('aura absolute -top-32 left-[-10%] h-[26rem] w-[26rem] rounded-full', palettes[0])} />
      <div className={cn('aura absolute right-[-12%] top-1/3 h-[30rem] w-[30rem] rounded-full', palettes[1])} />
      <div className={cn('aura absolute bottom-[-15%] left-1/4 h-[24rem] w-[24rem] rounded-full', palettes[2])} />
    </div>
  )
}

/* Calm, immersive intro band for feature surfaces. Optional atmospheric banner. */
export function FeatureIntro({
  icon,
  eyebrow,
  title,
  subtitle,
  image,
}: {
  icon: React.ReactNode
  eyebrow: string
  title: React.ReactNode
  subtitle: React.ReactNode
  image?: string
}) {
  return (
    <section className="relative isolate mt-2 overflow-hidden rounded-3xl shadow-soft">
      {image ? (
        <div className="relative h-32 w-full sm:h-40">
          <Image
            src={image}
            alt=""
            fill
            priority
            sizes="(max-width: 768px) 100vw, 42rem"
            className="object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-navy/70 to-navy/10" />
        </div>
      ) : null}
      <div className="relative isolate overflow-hidden bg-accent/60 p-6 sm:p-7">
        {image ? null : <AmbientAuras variant="calm" />}
        <div className="relative">
          <div className="flex items-center gap-2 text-primary">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              {icon}
            </span>
            <span className="text-[13px] font-semibold uppercase tracking-wide">
              {eyebrow}
            </span>
          </div>
          <h1 className="mt-3 text-balance font-display text-2xl font-bold text-foreground sm:text-3xl">
            {title}
          </h1>
          <p className="mt-2 max-w-md text-pretty text-[16px] leading-relaxed text-muted-foreground">
            {subtitle}
          </p>
        </div>
      </div>
    </section>
  )
}

/* Conversational choice chip — the Calm-style "What can we help with?" pill. */
export function ChoiceChip({
  href,
  icon,
  label,
  hint,
  tone = 'light',
}: {
  href: string
  icon: React.ReactNode
  label: string
  hint?: string
  tone?: 'light' | 'dark'
}) {
  return (
    <Link
      href={href}
      className={cn(
        'group flex min-h-[60px] items-center gap-3.5 rounded-2xl px-4 py-3 text-left transition duration-300',
        tone === 'light'
          ? 'glass hover:shadow-float hover:-translate-y-0.5'
          : 'glass-dark hover:-translate-y-0.5',
      )}
    >
      <span
        className={cn(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl',
          tone === 'light' ? 'bg-primary/10 text-primary' : 'bg-white/10 text-navy-foreground',
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            'block text-[15px] font-semibold',
            tone === 'light' ? 'text-foreground' : 'text-navy-foreground',
          )}
        >
          {label}
        </span>
        {hint ? (
          <span
            className={cn(
              'mt-0.5 block truncate text-[13px]',
              tone === 'light' ? 'text-muted-foreground' : 'text-navy-foreground/60',
            )}
          >
            {hint}
          </span>
        ) : null}
      </span>
      <ArrowRight
        className={cn(
          'h-4 w-4 shrink-0 translate-x-0 opacity-40 transition group-hover:translate-x-1 group-hover:opacity-100',
          tone === 'light' ? 'text-primary' : 'text-navy-foreground',
        )}
        aria-hidden="true"
      />
    </Link>
  )
}
