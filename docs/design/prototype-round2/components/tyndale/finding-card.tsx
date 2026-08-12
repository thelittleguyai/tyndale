import { money, type Finding } from '@/lib/tyndale-data'
import { CitationChip, SeverityTag } from './primitives'

export function FindingCard({ finding }: { finding: Finding }) {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-[17px] font-semibold leading-snug text-foreground">
          {finding.title}
        </h4>
        <span className="shrink-0 font-display text-lg font-bold text-money tabular-nums">
          −{money(finding.impact)}
        </span>
      </div>
      <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
        {finding.detail}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SeverityTag severity={finding.severity} />
        <CitationChip source={finding.source} />
      </div>
    </div>
  )
}
