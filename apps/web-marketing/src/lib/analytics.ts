/**
 * Thin wrapper over the Plausible browser API.
 *
 * The Plausible script is only injected in production builds with a configured
 * domain (see app/layout.tsx), so in dev `window.plausible` is absent and events
 * are logged to the console instead of sent — this avoids skewing analytics with
 * dev traffic while keeping the call sites identical.
 */
type EventProps = Record<string, string | number | boolean>;

type PlausibleFn = (event: string, options?: { props?: EventProps }) => void;

export function track(event: string, props?: EventProps): void {
  if (typeof window === 'undefined') return;
  const plausible = (window as unknown as { plausible?: PlausibleFn }).plausible;
  if (typeof plausible === 'function') {
    plausible(event, props ? { props } : undefined);
  } else if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.debug('[analytics] (dev — not sent)', event, props ?? {});
  }
}
