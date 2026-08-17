import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { Redirect } from 'expo-router';

import type { PlanProposal } from '@tyndale/shared';

import { confirmPlanProposal, rejectPlanProposal } from '../../lib/api-client';
import { WizardLoading, goToStep, useWizard } from '../../lib/intake-ui';

// Plan-proposal confirm/reject (DL-87). The plan is presented as "your plan" for a
// one-tap confirm — never as something we pulled from a shared library or another member.
function formatDesign(design: Record<string, unknown>): string[] {
  const d = design || {};
  const money = (v: unknown) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const rows: string[] = [];
  if (d.deductible_amount != null) rows.push(`Deductible: ${money(d.deductible_amount)}`);
  if (d.oop_max_amount != null) rows.push(`Out-of-pocket max: ${money(d.oop_max_amount)}`);
  if (d.coinsurance_percent != null) rows.push(`Coinsurance: ${Number(d.coinsurance_percent)}%`);
  if (d.copay_specialist != null) rows.push(`Specialist copay: ${money(d.copay_specialist)}`);
  if (d.copay_pcp != null) rows.push(`Primary-care copay: ${money(d.copay_pcp)}`);
  return rows;
}

export default function PlanProposalScreen() {
  const { state, caseId, loading } = useWizard();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (loading) return <WizardLoading />;
  const proposal = (state?.plan_proposal ?? null) as PlanProposal | null;
  // Nothing to confirm → straight to the benefits step.
  if (!proposal || !caseId) return <Redirect href={'/intake/benefits' as never} />;

  const finish = (fn: () => Promise<unknown>) => async () => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      goToStep('benefits');
    } catch {
      setErr("We couldn't save that — please try again.");
      setBusy(false);
    }
  };

  const rows = formatDesign(proposal.benefit_design as Record<string, unknown>);

  return (
    <ScrollView className="flex-1 bg-page" contentContainerStyle={{ padding: 20, paddingTop: 32 }}>
      <View className="w-full max-w-xl self-center">
        <Text className="mb-2 text-2xl font-bold leading-tight text-primary">
          Confirm your plan details
        </Text>
        <Text className="mb-5 text-[15px] leading-6 text-secondary">{proposal.summary}</Text>

        {rows.length ? (
          <View className="mb-6 rounded-2xl border border-hairline bg-surface p-5">
            {rows.map((r) => (
              <Text key={r} className="mb-1.5 text-base text-primary">
                • {r}
              </Text>
            ))}
          </View>
        ) : null}

        {err ? <Text className="mb-3 text-body text-danger">{err}</Text> : null}

        <Pressable
          disabled={busy}
          onPress={finish(() => confirmPlanProposal(proposal.plan_library_id, caseId))}
          className="mb-3 min-h-[48px] items-center justify-center rounded-xl bg-accent px-4 py-3 hover:bg-accent"
        >
          <Text className="text-base font-bold text-on-accent">Yes, that&apos;s my plan</Text>
        </Pressable>
        <Pressable
          disabled={busy}
          onPress={finish(() => rejectPlanProposal(proposal.plan_library_id, caseId))}
          className="min-h-[48px] items-center justify-center rounded-xl border border-hairline px-4 py-3 hover:bg-inset"
        >
          <Text className="text-base font-semibold text-secondary">Something looks off</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
