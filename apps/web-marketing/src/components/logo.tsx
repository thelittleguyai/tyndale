import { logoSvg } from '@tyndale/shared/design-tokens';

/**
 * Tyndale logo lockup. The mark (from the shared design tokens) sits inside a
 * rounded teal tile, matching the app-icon treatment in docs/design/*.png.
 */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center rounded-[10px] bg-gradient-to-br from-[#2D5A56] to-[#173D3A] ring-1 ring-white/10"
      style={{ width: size, height: size }}
    >
      <span
        aria-hidden="true"
        className="block [&>svg]:block [&>svg]:h-full [&>svg]:w-full"
        style={{ width: Math.round(size * 0.62), height: Math.round(size * 0.62), lineHeight: 0 }}
        dangerouslySetInnerHTML={{ __html: logoSvg }}
      />
    </span>
  );
}

// Color-agnostic wordmark (inherits text color from its parent).
export function Wordmark({ className = '' }: { className?: string }) {
  return <span className={`text-lg font-semibold tracking-tight ${className}`}>Tyndale</span>;
}
