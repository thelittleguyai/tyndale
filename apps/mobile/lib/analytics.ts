/**
 * First-party analytics shim for the member app.
 *
 * Plausible was removed (Internal Analytics P0, 2026-07-11): the app is an
 * authenticated health surface, and per Brock's HBNR posture its usage must not
 * flow to a third party. There is no self-hosted first-party Plausible instance,
 * so the SaaS integration is gone entirely (it stays only on the unauthenticated
 * marketing site).
 *
 * Funnel truth is now captured SERVER-SIDE (the runtime emits into
 * `analytics_events` wherever the fact is server-known — never trusting the
 * client for funnel truth). This `track()` is retained as a no-op so call sites
 * keep compiling; client-only interaction events will post to the first-party
 * `POST /v1/events` endpoint when that path is wired. Nothing here sends data
 * off-device.
 */
type EventProps = Record<string, string | number | boolean>;

export function track(event: string, props?: EventProps): void {
  if (__DEV__) {
    // eslint-disable-next-line no-console
    console.debug('[analytics] (first-party; not sent)', event, props ?? {});
  }
}
