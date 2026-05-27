import { Platform } from 'react-native';
import Plausible from 'plausible-tracker';

/**
 * Plausible wrapper for the Expo app. Per the V1-Lite plan, only the web build
 * reports analytics (native traffic is not tracked in V1-Lite), and only in a
 * production build with a configured domain — dev never sends events (keeps dev
 * traffic out of analytics).
 */
type EventProps = Record<string, string | number | boolean>;

const domain = process.env.EXPO_PUBLIC_PLAUSIBLE_DOMAIN;
const apiHost =
  process.env.EXPO_PUBLIC_PLAUSIBLE_SCRIPT?.replace(/\/js\/.*$/, '') ?? 'https://plausible.io';

const enabled = !__DEV__ && Platform.OS === 'web' && Boolean(domain);

const tracker = enabled && domain ? Plausible({ domain, apiHost, trackLocalhost: false }) : null;

export function track(event: string, props?: EventProps): void {
  if (tracker) {
    tracker.trackEvent(event, props ? { props } : undefined);
  } else if (__DEV__) {
    // eslint-disable-next-line no-console
    console.debug('[analytics] (dev — not sent)', event, props ?? {});
  }
}
