/**
 * The sub-case gameplan (D5 §2, DL-91) — the ordered set of phone calls the user makes, biggest
 * dollar first. `Gameplan` lists the steps (each expandable to its four call beats); `CallMode` is
 * the full-screen, presentation-only step-through of a single call. Engineering renders the
 * structure here; every line of connective + finding copy comes from the API (Brock's D1 script
 * and the agents' claims/actions), never hard-coded.
 */
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { ChevronDown, ChevronUp, Phone, X } from 'lucide-react-native';

import type { GameplanStep } from '../../lib/api-client';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

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
          <Text className="mb-1 text-xs uppercase tracking-wider text-amber">If they push back</Text>
          {s.if_they_push_back.map((line, i) => (
            <Text key={i} className="text-sm leading-6 text-white/80">
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
      <Text className="mb-1 text-xs uppercase tracking-wider text-white/40">{label}</Text>
      <Text className={`text-sm leading-6 ${accent ? 'font-semibold text-sage' : 'text-white/85'}`}>
        {body}
      </Text>
    </View>
  );
}

function StepCard({ step, open, onToggle }: { step: GameplanStep; open: boolean; onToggle: () => void }) {
  return (
    <View className="mb-3 overflow-hidden rounded-2xl border border-white/10 bg-navy-soft">
      <Pressable onPress={onToggle} className="min-h-[44px] flex-row items-center gap-3 p-4">
        <View className="h-7 w-7 items-center justify-center rounded-full bg-teal-deep">
          <Text className="text-sm font-bold text-white">{step.index}</Text>
        </View>
        <View className="flex-1">
          <Text className="text-base font-bold text-white">{step.title}</Text>
          <Text className="text-xs text-white/55">
            Call {step.party_label}
            {step.dollar_impact ? ` · up to ${money(step.dollar_impact)}` : ''}
          </Text>
        </View>
        {open ? (
          <ChevronUp size={18} color="rgba(255,255,255,0.5)" />
        ) : (
          <ChevronDown size={18} color="rgba(255,255,255,0.5)" />
        )}
      </Pressable>
      {open ? (
        <View className="border-t border-white/10 p-4">
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
}: {
  steps: GameplanStep[];
  callModeIntro?: string;
  callModeOutro?: string;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [callMode, setCallMode] = useState(false);
  if (steps.length === 0) return null;
  return (
    <View className="mb-6">
      <Text className="mb-1 mt-2 text-xs uppercase tracking-wider text-white/40">Your game plan</Text>
      <Text className="mb-3 text-sm leading-5 text-white/65">
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
        className="mt-1 min-h-[44px] flex-row items-center justify-center gap-2 rounded-xl bg-sage px-4 py-3 hover:bg-sage-deep"
      >
        <Phone size={16} color="#0B1F2A" />
        <Text className="text-base font-bold text-ink">Walk me through the calls</Text>
      </Pressable>
      {callMode ? (
        <CallMode
          steps={steps}
          intro={callModeIntro}
          outro={callModeOutro}
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
}: {
  steps: GameplanStep[];
  intro: string;
  outro: string;
  onClose: () => void;
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

  return (
    <View className="absolute inset-0 z-50 bg-navy-deep" testID="call-mode">
      <View className="flex-row items-center justify-between px-5 pb-3 pt-14">
        <Text className="text-xs uppercase tracking-widest text-white/45">
          {step ? `Call ${step.index} of ${steps.length}` : onOutro ? 'After the call' : 'Get ready'}
        </Text>
        <Pressable onPress={onClose} className="min-h-[44px] min-w-[44px] items-center justify-center" testID="call-mode-close">
          <X size={22} color="rgba(255,255,255,0.7)" />
        </Pressable>
      </View>

      <ScrollView className="flex-1 px-5" contentContainerStyle={{ paddingBottom: 24 }}>
        <View className="w-full max-w-2xl self-center">
          {onIntro ? (
            <Text className="mt-6 text-xl leading-8 text-white/90">{intro}</Text>
          ) : onOutro ? (
            <Text className="mt-6 text-xl leading-8 text-white/90">{outro}</Text>
          ) : step ? (
            <>
              <Text className="mb-1 mt-2 text-2xl font-bold text-white">{step.title}</Text>
              <Text className="mb-6 text-sm text-white/55">
                Call {step.party_label}
                {step.dollar_impact ? ` · up to ${money(step.dollar_impact)}` : ''}
              </Text>
              <CallBeats step={step} />
            </>
          ) : null}
        </View>
      </ScrollView>

      <View className="flex-row gap-3 px-5 pb-10 pt-3">
        {page > firstPage ? (
          <Pressable
            onPress={() => setPage((p) => p - 1)}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl border border-white/15 px-4 py-3 hover:bg-white/5"
            testID="call-mode-back"
          >
            <Text className="text-base font-semibold text-white/80">Back</Text>
          </Pressable>
        ) : null}
        {page < lastPage ? (
          <Pressable
            onPress={() => setPage((p) => p + 1)}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl bg-sage px-4 py-3 hover:bg-sage-deep"
            testID="call-mode-next"
          >
            <Text className="text-base font-bold text-ink">{onIntro ? "I'm ready" : 'Next'}</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={onClose}
            className="min-h-[48px] flex-1 items-center justify-center rounded-xl bg-sage px-4 py-3 hover:bg-sage-deep"
            testID="call-mode-done"
          >
            <Text className="text-base font-bold text-ink">Done</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
