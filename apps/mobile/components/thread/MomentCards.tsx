/**
 * Full-width, visually distinct MOMENT cards for the chat-first thread (DL-91, D0) — never
 * ordinary bubbles. The three-number reveal, and the first-case-unlock (gated OFF in Phase A).
 */
import { Text, View } from 'react-native';

import type { ThreeNumberMomentPayload, UnlockMomentPayload } from '@tyndale/shared';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** D0 three-number reveal. Full-width sage-framed moment; the headline is the script-keyed frame. */
export function ThreeNumberMoment({ payload }: { payload: ThreeNumberMomentPayload }) {
  const foundSavings = payload.delta > 0.005;
  return (
    <View className="my-3 w-full rounded-3xl border border-sage/40 bg-sage/10 p-6 shadow-card">
      <Text className="mb-4 text-lg font-bold leading-snug text-white">{payload.headline}</Text>
      <View className="gap-2">
        <Row label="What you were billed" value={money(payload.provider_billed)} dim />
        <Row
          label="What your insurer says you owe"
          value={money(payload.eob_member_responsibility)}
          secondary={foundSavings}
        />
        <Row label="What you should owe" value={money(payload.tyndale_computed)} highlight />
      </View>
    </View>
  );
}

function Row({
  label,
  value,
  highlight,
  secondary,
  dim,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  secondary?: boolean;
  dim?: boolean;
}) {
  return (
    <View className="flex-row items-center justify-between border-t border-white/10 pt-2 first:border-t-0 first:pt-0">
      <Text className={`text-sm ${dim ? 'text-white/45' : 'text-white/70'}`}>{label}</Text>
      <Text
        className={
          highlight
            ? 'text-2xl font-bold text-sage'
            : secondary
              ? 'text-base text-white/80'
              : dim
                ? 'text-base text-white/45'
                : 'text-base text-white'
        }
      >
        {value}
      </Text>
    </View>
  );
}

/**
 * D0 first-case unlock moment. Built to Brock's mocked structure but rendered ONLY behind
 * ENABLE_BILLING && ENABLE_FIRST_CASE_UNLOCK — both false in Phase A, so this never mounts yet
 * (the pricing model is being revised; no payment path here). TODO(pricing-memo): wire the flags +
 * the $4.99 first-case checkout when the pricing memo lands.
 */
export function UnlockMoment({ payload }: { payload: UnlockMomentPayload }) {
  return (
    <View className="my-3 w-full rounded-3xl border border-amber/40 bg-amber/10 p-6 shadow-card">
      <Text className="mb-3 text-xl font-bold text-white">{payload.headline}</Text>
      <View className="mb-4 gap-2">
        {payload.value_points.map((p, i) => (
          <View key={i} className="flex-row items-start gap-2">
            <Text className="text-sage">✓</Text>
            <Text className="flex-1 text-sm leading-6 text-white/80">{p}</Text>
          </View>
        ))}
      </View>
      <Text className="text-center text-sm font-semibold text-white/90">{payload.footnote}</Text>
    </View>
  );
}
