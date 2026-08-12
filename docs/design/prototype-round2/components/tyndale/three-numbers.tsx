import { cn } from '@/lib/utils'
import { AUDIT, money } from '@/lib/tyndale-data'

/*
 * The product's signature artifact (§8 locked values):
 * billed $2,347.18 · insurer says $1,184.60 · should actually owe $612.40
 * Hero = "should actually owe" in money green.
 */
export function ThreeNumbers({
  className,
  service = true,
  glass = false,
}: {
  className?: string
  service?: boolean
  glass?: boolean
}) {
  return (
    <div
      className={cn(
        'overflow-hidden rounded-3xl',
        glass ? 'glass' : 'bg-card ring-1 ring-border shadow-soft',
        className,
      )}
    >
      {service && (
        <div className="border-b border-border px-5 py-3 text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">
            MRI of the left knee
          </span>{' '}
          · {AUDIT.provider} · {AUDIT.payer}
        </div>
      )}
      <dl className="divide-y divide-border">
        <Row label="The hospital billed" value={money(AUDIT.billed)} muted />
        <Row
          label="Your insurer says you owe"
          value={money(AUDIT.insurerSays)}
          muted
        />
        <div className="bg-money-soft px-5 py-5">
          <dt className="text-sm font-semibold text-money">
            What you should actually owe
          </dt>
          <dd className="mt-1 font-display text-4xl font-bold text-money">
            {money(AUDIT.shouldOwe)}
          </dd>
        </div>
      </dl>
    </div>
  )
}

function Row({
  label,
  value,
  muted,
}: {
  label: string
  value: string
  muted?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between px-5 py-4">
      <dt className={cn('text-[15px]', muted ? 'text-muted-foreground' : 'text-foreground')}>
        {label}
      </dt>
      <dd
        className={cn(
          'font-display text-xl font-semibold tabular-nums',
          muted ? 'text-foreground/70 line-through decoration-border' : 'text-foreground',
        )}
      >
        {value}
      </dd>
    </div>
  )
}
