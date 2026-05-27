import { logoSvg } from '@tyndale/shared/design-tokens';

/**
 * Tyndale logo mark, sourced from the shared design tokens (inline SVG string).
 */
export function Logo({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: size, height: size, display: 'inline-block', lineHeight: 0 }}
      className={`[&>svg]:h-full [&>svg]:w-full ${className}`}
      dangerouslySetInnerHTML={{ __html: logoSvg }}
    />
  );
}

export function Wordmark({ className = '' }: { className?: string }) {
  return <span className={`text-lg font-semibold tracking-tight ${className}`}>Tyndale</span>;
}
