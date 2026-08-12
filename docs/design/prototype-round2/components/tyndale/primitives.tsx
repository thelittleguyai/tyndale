'use client'

import { useState } from 'react'
import { BookText, Check, Clock, FileWarning, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Severity, CaseStatus } from '@/lib/tyndale-data'

/* Citation chip — every legal / pricing claim carries one, tappable to source. */
export function CitationChip({ source }: { source: string }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-full bg-citation-soft px-3 py-1.5 text-left text-[13px] font-medium text-citation transition hover:brightness-95"
      >
        <BookText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span>source: {source}</span>
      </button>
      {open && (
        <span className="mt-2 block rounded-lg border border-citation/25 bg-citation-soft/60 px-3 py-2 text-[13px] leading-relaxed text-citation">
          This claim is computed from the document above — not a guess. Tap the
          document in your file to see the exact line it came from.
        </span>
      )}
    </span>
  )
}

const severityStyles: Record<Severity, { bg: string; text: string; label: string }> = {
  high: { bg: 'bg-severity-high-bg', text: 'text-severity-high', label: 'High impact' },
  medium: { bg: 'bg-severity-med-bg', text: 'text-severity-med', label: 'Worth fixing' },
  neutral: {
    bg: 'bg-severity-neutral-bg',
    text: 'text-severity-neutral',
    label: 'Note',
  },
}

export function SeverityTag({ severity }: { severity: Severity }) {
  const s = severityStyles[severity]
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold',
        s.bg,
        s.text,
      )}
    >
      {s.label}
    </span>
  )
}

const statusStyles: Record<
  CaseStatus,
  { bg: string; text: string; icon: React.ReactNode }
> = {
  resolved: {
    bg: 'bg-money-soft',
    text: 'text-money',
    icon: <Check className="h-4 w-4" aria-hidden="true" />,
  },
  waiting: {
    bg: 'bg-amber-soft',
    text: 'text-amber',
    icon: <Clock className="h-4 w-4" aria-hidden="true" />,
  },
  needs: {
    bg: 'bg-severity-neutral-bg',
    text: 'text-severity-neutral',
    icon: <FileWarning className="h-4 w-4" aria-hidden="true" />,
  },
}

export function StatusChip({
  status,
  label,
}: {
  status: CaseStatus
  label: string
}) {
  const s = statusStyles[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold',
        s.bg,
        s.text,
      )}
    >
      {s.icon}
      {label}
    </span>
  )
}

export function AnswerPill({ answer }: { answer: 'yes' | 'no' | 'notsure' }) {
  const map = {
    yes: { label: 'Yes, that happened', cls: 'bg-money-soft text-money', icon: <Check className="h-4 w-4" /> },
    no: { label: "No, this didn't happen", cls: 'bg-severity-high-bg text-severity-high', icon: <X className="h-4 w-4" /> },
    notsure: { label: "I'm not sure", cls: 'bg-severity-neutral-bg text-severity-neutral', icon: null },
  }[answer]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold',
        map.cls,
      )}
    >
      {map.icon}
      {map.label}
    </span>
  )
}
