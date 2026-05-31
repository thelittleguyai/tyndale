type EventProps = Record<string, string | number | boolean>;
type PlausibleFn = (event: string, options?: { props?: EventProps }) => void;

/** Fire a Plausible custom event (admin engagement: case_viewed, verdict_submitted, …). */
export function track(event: string, props?: EventProps): void {
  if (typeof window === 'undefined') return;
  const plausible = (window as unknown as { plausible?: PlausibleFn }).plausible;
  if (typeof plausible === 'function') {
    plausible(event, props ? { props } : undefined);
  } else if (process.env.NODE_ENV !== 'production') {
    console.debug('[analytics] (dev — not sent)', event, props ?? {});
  }
}
