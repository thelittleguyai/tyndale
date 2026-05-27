/**
 * Global "SCAFFOLD — not for real PHI" banner. Pinned to the very top of every
 * page per the Phase 1B prompt. Rendered once in the root layout.
 */
export function ScaffoldBanner() {
  return (
    <div
      role="alert"
      className="w-full bg-amber px-3 py-1.5 text-center text-xs font-semibold tracking-wide text-ink"
    >
      SCAFFOLD — not for real PHI
    </div>
  );
}
