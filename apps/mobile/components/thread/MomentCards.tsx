/**
 * Full-width, visually distinct MOMENT cards for the chat-first thread (DL-91, D0) — never
 * ordinary bubbles. The three-number reveal, and the first-case-unlock (gated OFF in Phase A).
 */
import { Text, View } from 'react-native';

import type { ThreeNumberMomentPayload, UnlockMomentPayload } from '@tyndale/shared';
import { MomentCard } from '../ui';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * D0 three-number reveal — the designed moment (redesign §3). A dark MomentCard that pops on the
 * page in both modes: a caption, two hairline-separated numbers, then the third at 30/500 in the
 * emphasis color, and the script-keyed frame (payload.headline) as a one-line verdict strip in an
 * inset well. This is the fix for the "moments aren't moments" critique.
 */
export function ThreeNumberMoment({ payload }: { payload: ThreeNumberMomentPayload }) {
  return (
    <MomentCard className="my-3">
      <Text className="mb-3 text-caption text-moment-text-faint">Your three numbers</Text>
      <MomentRow label="What you were billed" value={money(payload.provider_billed)} />
      <MomentRow label="What your insurer says you owe" value={money(payload.eob_member_responsibility)} />
      <View className="flex-row items-baseline justify-between pb-0.5 pt-2.5">
        <Text className="text-body font-medium text-moment-text">What you should owe</Text>
        <Text className="text-[30px] font-medium leading-9 text-moment-emphasis">
          {money(payload.tyndale_computed)}
        </Text>
      </View>
      {payload.headline ? (
        <View className="mt-3 rounded-control px-3 py-2" style={{ backgroundColor: 'rgba(255,255,255,0.07)' }}>
          <Text className="text-caption leading-5 text-moment-text">{payload.headline}</Text>
        </View>
      ) : null}
    </MomentCard>
  );
}

function MomentRow({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row items-baseline justify-between border-b border-moment-border py-1.5">
      <Text className="text-caption text-moment-text-faint">{label}</Text>
      <Text className="text-[18px] text-moment-text">{value}</Text>
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
    <View className="my-3 w-full rounded-3xl border border-warning bg-warning-tint p-6 shadow-card">
      <Text className="mb-3 text-xl font-bold text-primary">{payload.headline}</Text>
      <View className="mb-4 gap-2">
        {payload.value_points.map((p, i) => (
          <View key={i} className="flex-row items-start gap-2">
            <Text className="text-accent">✓</Text>
            <Text className="flex-1 text-sm leading-6 text-secondary">{p}</Text>
          </View>
        ))}
      </View>
      <Text className="text-center text-sm font-semibold text-primary">{payload.footnote}</Text>
    </View>
  );
}
