'use client'

import {
  Camera,
  FileText,
  Receipt,
  ScanLine,
  CheckCircle2,
} from 'lucide-react'

function ActionButton({ children }: { children: React.ReactNode }) {
  return (
    <button
      type="button"
      className="mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-[16px] font-semibold text-primary-foreground transition hover:brightness-110"
    >
      {children}
    </button>
  )
}

/* B2 · Blurry/partial upload — never guesses a number. */
export function BlurryUploadCard() {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        I read most of this, but line 4 is too blurry for me to trust — and I
        won&apos;t guess at a number on your bill. A clearer photo of just that
        part fixes it. Everything else, I&apos;ve got.
      </p>
      <ActionButton>
        <Camera className="h-5 w-5" aria-hidden="true" />
        Retake just line 4
      </ActionButton>
      <p className="mt-3 text-[15px] text-muted-foreground">
        Bring it back and I&apos;ll pick up right where we left off.
      </p>
    </div>
  )
}

/* B3 · Wrong document. */
export function WrongDocumentCard() {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        That looks like a prescription label, not a bill or EOB — to check a
        bill, I need your itemized medical bill or your Explanation of Benefits.
        Here&apos;s what each looks like:
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {[
          { icon: <Receipt className="h-6 w-6" />, label: 'Itemized bill', hint: 'lists each charge' },
          { icon: <FileText className="h-6 w-6" />, label: 'EOB', hint: 'from your insurer' },
        ].map((e) => (
          <div
            key={e.label}
            className="flex flex-col items-center gap-2 rounded-xl border border-border bg-background px-3 py-4 text-center text-primary"
          >
            {e.icon}
            <span className="text-[15px] font-semibold text-foreground">
              {e.label}
            </span>
            <span className="text-[13px] text-muted-foreground">{e.hint}</span>
          </div>
        ))}
      </div>
      <ActionButton>
        <ScanLine className="h-5 w-5" aria-hidden="true" />
        Re-upload the right document
      </ActionButton>
    </div>
  )
}

/* B4 · Summary bill, not itemized. */
export function SummaryBillCard() {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        The itemized bill is where errors actually hide — here&apos;s the script
        to request it. Bring it back and I&apos;ll pick up right where we left
        off.
      </p>
      <div className="mt-3 rounded-lg bg-muted px-3 py-2.5 text-[15px] leading-relaxed text-foreground">
        &ldquo;Hi, I&apos;d like to request a fully itemized bill for my visit on
        June 14th, with CPT codes for each line. Can you email or mail that to
        me?&rdquo;
      </div>
      <ActionButton>
        <Receipt className="h-5 w-5" aria-hidden="true" />
        Add the itemized bill later
      </ActionButton>
    </div>
  )
}

/* B5 · Numbers disagree — Tyndale reconciles and explains first. */
export function NumbersDisagreeCard() {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        These two numbers look like they disagree — but they&apos;re measuring
        different things. One is the total charge before your plan&apos;s
        network discount; the other is what&apos;s left after it. So it&apos;s
        not an error; here&apos;s the real math.
      </p>
      <div className="mt-3 flex items-center gap-2 rounded-lg bg-money-soft px-3 py-2.5 text-[15px] font-medium text-money">
        <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />
        Reconciled — no action needed here.
      </div>
    </div>
  )
}

/* B10 · User asks Tyndale to exaggerate or guarantee — warm decline, no outcome prediction. */
export function HonestOddsCard() {
  return (
    <div className="rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
      <p className="text-[16px] leading-relaxed text-foreground">
        I won&apos;t overstate your case or promise how it&apos;ll turn out —
        that&apos;s exactly the kind of thing everyone else does to you. Here&apos;s
        what actually is off, and it&apos;s a real case: a duplicate charge and a
        coinsurance rate that doesn&apos;t match your plan. Strong facts, cleanly
        sourced. That&apos;s what I&apos;ll help you argue.
      </p>
    </div>
  )
}
