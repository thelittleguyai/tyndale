/**
 * /intake — the guided front door (doc 40). ONE screen: the server's Intake Planner decides
 * what to show after every capture and answer, and hands over every string. This file holds no
 * sequence and no product copy; it loads the state, draws `screen`, and posts what the user did.
 *
 *   /intake              the welcome — or "pick up where you left off" if a case is unfinished
 *   /intake?case=<id>    that case, at whatever the planner says is next
 *   …&screen=<id>        a specific screen (the readiness "Change" links)
 *
 * Save and resume is structural: every answer is one committed write on the server, so "Save
 * and exit" saves nothing extra — it just leaves.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';

import type { IntakeStateResponse } from '@tyndale/shared';

import {
  answerIntake,
  attestCase,
  confirmPlanProposal,
  declineAttest,
  getIntakeState,
  handoffIntake,
  rejectPlanProposal,
  runIntake,
  startIntake,
} from '../../lib/api-client';
import { IntakeBody } from '../../components/intake/IntakeBody';
import { IntakeProgressBar } from '../../components/intake/IntakeProgressBar';
import { ExampleSheet, HelpSheet } from '../../components/intake/IntakeSheets';
import { Button } from '../../components/ui';
import { PressableScale } from '../../components/ui/PressableScale';
import { Screen } from '../../components/ui/Screen';
import { useThemeColors } from '../../theme/useThemeColors';

// The advocacy-not-advice line is LEGAL text (unchanged from the CO-1A wizard) — it is not
// product copy and is deliberately not a registry key under the grade-5 rule.
const DISCLAIMER =
  'Tyndale provides medical billing and coverage advocacy, not medical, legal, or financial advice.';
const POLL_MS = 4000;

export default function IntakeScreenRoute() {
  const tc = useThemeColors();
  const params = useLocalSearchParams<{ case?: string; screen?: string }>();
  const [state, setState] = useState<IntakeStateResponse | null>(null);
  const [resumeDismissed, setResumeDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<'load' | 'save' | null>(null);
  const [sheet, setSheet] = useState<'example' | 'help' | null>(null);
  const running = useRef(false);
  const caseId = state?.case_file_id ?? params.case ?? null;

  const load = useCallback(
    async (screen?: string) => {
      try {
        const s = await getIntakeState(params.case ?? state?.case_file_id ?? undefined, { screen });
        setState(s);
        setFailed(null);
      } catch {
        setFailed('load');
      }
    },
    [params.case, state?.case_file_id],
  );

  // Reload whenever the screen regains focus: the user comes BACK from the capture flow with a
  // new document on the case, and the planner — not this file — decides what that changes.
  useFocusEffect(
    useCallback(() => {
      void load(params.screen);
      // eslint-disable-next-line react-hooks/exhaustive-deps -- re-run on focus and on the URL's case/screen only; `load` changes with every state and would loop
    }, [params.case, params.screen]),
  );

  // "Reading your bill" — poll until the engine's facts land.
  useEffect(() => {
    if (state?.screen.kind !== 'progress') return;
    const t = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(t);
  }, [state?.screen.kind, load]);

  // READY → run the audit and hand off to the EXISTING results surfaces (§C2). Once.
  useEffect(() => {
    if (state?.current_step !== 'READY' || !state.case_file_id || running.current) return;
    running.current = true;
    runIntake(state.case_file_id)
      .then((r) => router.replace(r.next_route as never))
      .catch(() => {
        running.current = false;
        setFailed('save');
      });
  }, [state?.current_step, state?.case_file_id]);

  const guard = async (fn: () => Promise<IntakeStateResponse | void>) => {
    setBusy(true);
    setFailed(null);
    try {
      const next = await fn();
      if (next) setState(next);
      else await load();
    } catch {
      setFailed('save');
    } finally {
      setBusy(false);
    }
  };

  const act = (action: string, values?: Record<string, unknown>) => {
    if (!state) return;
    void guard(async () => {
      // the welcome is the one screen with no case yet: starting IS the answer
      if (!state.case_file_id) return startIntake();
      return answerIntake(state.case_file_id, state.screen.id, action, values ?? {});
    });
  };

  if (!state) {
    return (
      <View className="flex-1 items-center justify-center bg-page p-6">
        {failed ? (
          <Button label="Try again" onPress={() => void load()} testID="intake-retry" />
        ) : (
          <ActivityIndicator color={tc.accent} />
        )}
      </View>
    );
  }

  const { screen, chrome, progress } = state;
  const resume = !params.case && !resumeDismissed ? state.resume : null;
  const exit = () => router.replace('/' as never);

  return (
    <Screen className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 20, paddingBottom: 48 }}>
      <View className="mb-5 flex-row items-center justify-between gap-3">
        <View className="flex-1">
          <IntakeProgressBar progress={progress} />
        </View>
        <PressableScale onPress={exit} className="min-h-[44px] justify-center px-2" testID="intake-save-exit">
          <Text className="text-body font-semibold text-secondary">{chrome.save_exit}</Text>
        </PressableScale>
      </View>

      {resume ? (
        <View testID="intake-resume">
          <Text accessibilityRole="header" className="text-2xl font-bold text-primary">{resume.title}</Text>
          <Text className="mt-3 text-body leading-6 text-secondary">{resume.body}</Text>
          <Button label={resume.primary ?? ''} onPress={() => setResumeDismissed(true)} fullWidth className="mt-6" testID="intake-resume-continue" />
          <Button label={resume.new ?? ''} variant="secondary" onPress={() => void guard(() => startIntake())} disabled={busy} fullWidth className="mt-3" />
          {/* states the REAL link lifetime — never a promise the auth layer does not keep */}
          <Text className="mt-4 text-body text-faint">{resume.link_expiry}</Text>
        </View>
      ) : (
        <View>
          <Text accessibilityRole="header" className="text-2xl font-bold leading-tight text-primary" testID="intake-title">
            {screen.copy.title}
          </Text>
          <IntakeBody
            key={screen.id}
            screen={screen}
            busy={busy}
            act={act}
            onCapture={(expect) =>
              router.push({
                pathname: '/upload',
                params: { caseId: caseId ?? '', ...(expect ? { expect } : {}), returnTo: `/intake?case=${caseId ?? ''}` },
              } as never)
            }
            onEdit={(id) => void guard(async () => getIntakeState(caseId ?? undefined, { screen: id }))}
            onAttest={(relationship) => void guard(async () => { if (caseId) await attestCase(caseId, relationship); })}
            onAttestDecline={() => void guard(async () => { if (caseId) await declineAttest(caseId); })}
            onPlanConfirm={(accept) =>
              void guard(async () => {
                const id = String((screen.data as { plan_library_id?: string }).plan_library_id ?? '');
                if (!caseId || !id) return;
                return accept ? confirmPlanProposal(id, caseId) : rejectPlanProposal(id, caseId);
              })
            }
            onRun={() => undefined}
            onExit={exit}
            // a population Phase 1 does not carry: the SERVER closes the guided route for this case
            // and says where the chat-first flow picks it up — this file does not choose
            onHandoff={() =>
              void guard(async () => {
                if (!caseId) return;
                const r = await handoffIntake(caseId);
                router.replace(r.next_route as never);
                return state; // leaving — nothing to reload
              })
            }
          />
          <View className="mt-5 flex-row flex-wrap gap-3">
            {/* present ONLY when the server sent something to show — never an empty sheet */}
            {screen.example ? (
              <Button label={chrome.see_example ?? ''} variant="tertiary" onPress={() => setSheet('example')} testID="intake-see-example" />
            ) : null}
            {screen.help ? (
              <Button label={chrome.help_find ?? ''} variant="tertiary" onPress={() => setSheet('help')} testID="intake-help" />
            ) : null}
          </View>
        </View>
      )}

      {failed ? (
        <View className="mt-4" accessibilityLiveRegion="polite">
          <Text className="text-body text-danger">{failed === 'load' ? chrome.load_error : chrome.save_error}</Text>
          <Button label={chrome.retry ?? ''} variant="secondary" onPress={() => void load()} className="mt-2 self-start" />
        </View>
      ) : null}

      <Text className="mt-10 text-center text-body text-faint">{DISCLAIMER}</Text>

      {sheet === 'example' && screen.example ? (
        <ExampleSheet example={screen.example} chrome={chrome} onClose={() => setSheet(null)} />
      ) : null}
      {sheet === 'help' && screen.help ? (
        <HelpSheet help={screen.help} chrome={chrome} caseId={caseId} screenId={screen.id} onClose={() => setSheet(null)} />
      ) : null}
    </Screen>
  );
}
