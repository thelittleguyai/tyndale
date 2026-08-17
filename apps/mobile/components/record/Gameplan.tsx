/**
 * The sub-case gameplan (D5 §2, DL-91) — the ordered set of phone calls the user makes, biggest
 * dollar first. `Gameplan` lists the steps (each expandable to its four call beats); `CallMode` is
 * the full-screen, presentation-only step-through of a single call. Engineering renders the
 * structure here; every line of connective + finding copy comes from the API (Brock's D1 script
 * and the agents' claims/actions), never hard-coded.
 */
import { useState } from 'react';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { ChevronDown, ChevronUp, Phone, X } from 'lucide-react-native';

import type { GameplanStep } from '../../lib/api-client';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

/** H6 — the three outcome routes after a call. `pushed_back` is not a failure state: H7 says a
 *  verified finding stands, so it routes to the steadfast next move rather than closing. */
const CALL_OUTCOMES = [
  { key: 'fixing_it', label: "They're fixing it 🎉" },
  { key: 'pushed_back', label: 'They pushed back' },
  { key: 'left_message', label: 'I left a message' },
] as const;

export type CallOutcome = (typeof CALL_OUTCOMES)[number]['key'];

/** B4 — the words for each typed reference kind. The server sends the discriminator and the
 *  number; the label lives here with the rest of the UI copy. */
const REFERENCE_LABEL: Record<'claim' | 'account', string> = {
  claim: 'Claim #',
  account: 'Account #',
};

/** The four call beats, in order. Shared by the expanded step and call mode. */
function CallBeats({ step }: { step: GameplanStep }) {
  const s = step.script;
  return (
    <View className="gap-4">
      <Beat label="When they pick up" body={s.when_they_pick_up} />
      <Beat label="The problem" body={s.the_problem} />
      <Beat label="The ask" body={s.the_ask} accent />
      <Beat label="Get it in writing" body={s.get_it_in_writing} />
      {s.if_they_push_back.length ? (
        <View>
          <Text className="mb-1 text-xs text-warning">If they push back</Text>
          {s.if_they_push_back.map((line, i) => (
            <Text key={i} className="text-body leading-6 text-secondary">
              {line}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function Beat({ label, body, accent }: { label: string; body: string; accent?: boolean }) {
  return (
    <View>
      <Text className="mb-1 text-xs text-faint">{label}</Text>
      <Text className={`text-body leading-6 ${accent ? 'font-semibold text-accent' : 'text-primary'}`}>
        {body}
      </Text>
    </View>
  );
}

function StepCard({ step, open, onToggle }: { step: GameplanStep; open: boolean; onToggle: () => void }) {
  return (
    <View className="mb-3 overflow-hidden rounded-2xl border border-hairline bg-surface">
      <Pressable onPress={onToggle} className="min-h-[44px] flex-row items-center gap-3 p-4">
        <View className="h-7 w-7 items-center justify-center rounded-full bg-surface-raised">
          <Text className="text-sm font-bold text-primary">{step.index}</Text>
        </View>
        <View className="flex-1">
          <Text className="text-base font-bold text-primary">{step.title}</Text>
          <Text className="text-xs text-faint">
            Call {step.party_label}
            {step.dollar_impact ? ` · up to ${money(step.dollar_impact)}` : ''}
          </Text>
        </View>
        {open ? (
          <ChevronUp size={18} color="var(--c-text-faint)" />
        ) : (
          <ChevronDown size={18} color="var(--c-text-faint)" />
        )}
      </Pressable>
      {open ? (
        <View className="border-t border-hairline p-4">
          <CallBeats step={step} />
        </View>
      ) : null}
    </View>
  );
}

export function Gameplan({
  steps,
  callModeIntro = '',
  callModeOutro = '',
  onOutcome,
}: {
  steps: GameplanStep[];
  callModeIntro?: string;
  callModeOutro?: string;
  /** Forwarded to call mode's "How did it go?" routes. Without it the routes render and go
   *  nowhere — which is what they did until the 2026-08-13 review caught it. */
  onOutcome?: (findingId: string, outcome: CallOutcome) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [callMode, setCallMode] = useState(false);
  if (steps.length === 0) return null;
  return (
    <View className="mb-6">
      <Text className="mb-1 mt-2 text-xs text-faint">Your game plan</Text>
      <Text className="mb-3 text-body leading-6 text-secondary">
        Work the list top to bottom — the biggest-dollar call is first. Tap any step for exactly
        what to say.
      </Text>
      {steps.map((s) => (
        <StepCard
          key={s.finding_id}
          step={s}
          open={openId === s.finding_id}
          onToggle={() => setOpenId(openId === s.finding_id ? null : s.finding_id)}
        />
      ))}
      <Pressable
        onPress={() => setCallMode(true)}
        className="mt-1 min-h-[44px] flex-row items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 hover:bg-accent"
      >
        <Phone size={16} color="var(--c-on-accent)" />
        <Text className="text-base font-bold text-on-accent">Walk me through the calls</Text>
      </Pressable>
      {callMode ? (
        <CallMode
          steps={steps}
          intro={callModeIntro}
          outro={callModeOutro}
          onOutcome={onOutcome}
          onClose={() => setCallMode(false)}
        />
      ) : null}
    </View>
  );
}

/** Full-screen, presentation-only step-through: intro → one call per screen → outro. It submits
 * nothing (the dashboard's outcome follow-up captures what happened later); closing returns to the
 * summary. `intro`/`outro` are the API's call_mode copy; when empty they're simply skipped. */
export function CallMode({
  steps,
  intro,
  outro,
  onClose,
  onOutcome,
}: {
  steps: GameplanStep[];
  intro: string;
  outro: string;
  onClose: () => void;
  /** Fired when the user picks one of the three routes; the caller records the outcome. */
  onOutcome?: (findingId: string, outcome: CallOutcome) => void;
}) {
  // page 0 = intro (if any); 1..N = each call; N+1 = outro. With no intro we start at the first call.
  const hasIntro = intro.trim().length > 0;
  const hasOutro = outro.trim().length > 0;
  const firstPage = hasIntro ? 0 : 1;
  const lastPage = steps.length + (hasOutro ? 1 : 0);
  const [page, setPage] = useState(firstPage);

  const step = page >= 1 && page <= steps.length ? steps[page - 1] : null;
  const onIntro = page === 0;
  const onOutro = page > steps.length;

  // H6 tap-to-dial (B4). `phone` is the typed number printed on that party's own document —
  // extracted at parse time, never guessed or looked up. Null when the documents didn't carry
  // one, and the control simply doesn't render rather than dialing nothing.
  const phone = step?.phone ?? null;
  const dial = () => {
    if (phone) Linking.openURL(`tel:${phone.replace(/[^0-9+]/g, '')}`);
  };

  return (
    <View className="absolute inset-0 z-50 bg-page" testID="call-mode">
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="text-xs text-faint">
          {step ? `Call ${step.index} of ${steps.length}` : onOutro ? 'After the call' : 'Get ready'}
        </Text>
        <Pressable onPress={onClose} className="min-h-[44px] min-w-[44px] items-center justify-center" testID="call-mode-close">
          <X size={22} color="var(--c-text-secondary)" />
        </Pressable>
      </View>

      {/* H6/L7 — PINNED strip: who you're calling, what to quote, and what the call is worth,
          all on screen while the script scrolls. The reference is the TYPED identifier for
          THIS party (B4) — a claim number for the payer, an account number for the provider —
          and the second row is omitted entirely when the documents didn't carry one. */}
      {step ? (
        <View className="mx-5 mb-3 rounded-control bg-inset px-4 py-2.5">
          <View className="flex-row items-center justify-between">
            <Text className="text-caption text-secondary">{step.party_label}</Text>
            {step.dollar_impact ? (
              <Text className="text-body font-medium text-money">{money(step.dollar_impact)}</Text>
            ) : null}
          </View>
          {step.reference_number ? (
            <Text className="mt-0.5 text-caption text-faint" testID="call-mode-reference">
              {REFERENCE_LABEL[step.reference_kind ?? 'claim']} {step.reference_number}
            </Text>
          ) : null}
        </View>
      ) : null}

      <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 24 }}>
        <View className="w-full max-w-2xl self-center">
          {onIntro ? (
            <Text className="mt-6 text-xl leading-8 text-primary">{intro}</Text>
          ) : onOutro ? (
            <Text className="mt-6 text-xl leading-8 text-primary">{outro}</Text>
          ) : step ? (
            <>
              <Text className="mb-1 mt-2 text-2xl font-bold text-primary">{step.title}</Text>
              <Text className="mb-6 text-sm text-faint">
                Call {step.party_label}
                {step.dollar_impact ? ` · up to ${money(step.dollar_impact)}` : ''}
              </Text>
              {/* H6 tap-to-dial — only when a number exists (see the `phone` note above). */}
              {phone ? (
                <Pressable
                  onPress={dial}
                  className="mb-5 min-h-[44px] flex-row items-center justify-center gap-2 rounded-control bg-accent px-4 py-3"
                  testID="call-mode-dial"
                >
                  <Phone size={17} color="var(--c-on-accent)" />
                  <Text className="text-body font-medium text-on-accent">Call {step.party_label}</Text>
                </Pressable>
              ) : null}
              <CallBeats step={step} />

              {/* H6 — "How did it go?" three routes. H7: the pushback route is STEADFAST — a
                  verified finding doesn't soften because the payer said no. */}
              <View className="mt-7 border-t border-hairline pt-5">
                <Text className="mb-3 text-body font-medium text-primary">How did it go?</Text>
                <View className="gap-2">
                  {CALL_OUTCOMES.map((o) => (
                    <Pressable
                      key={o.key}
                      onPress={() => onOutcome?.(step.finding_id, o.key)}
                      className="min-h-[44px] items-center justify-center rounded-control border border-hairline bg-surface px-4 py-3"
                      testID={`call-outcome-${o.key}`}
                    >
                      <Text className="text-body text-primary">{o.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            </>
          ) : null}
        </View>
      </ScrollView>

      <View className="flex-row gap-3 px-5 pb-10 pt-3">
        {page > firstPage ? (
          <Pressable
            onPress={() => setPage((p) => p - 1)}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl border border-hairline px-4 py-3 hover:bg-inset"
            testID="call-mode-back"
          >
            <Text className="text-base font-semibold text-secondary">Back</Text>
          </Pressable>
        ) : null}
        {page < lastPage ? (
          <Pressable
            onPress={() => setPage((p) => p + 1)}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
            testID="call-mode-next"
          >
            <Text className="text-base font-bold text-on-accent">{onIntro ? "I'm ready" : 'Next'}</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={onClose}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
            testID="call-mode-done"
          >
            <Text className="text-base font-bold text-on-accent">Done</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
