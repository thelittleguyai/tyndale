import { useState } from 'react';

import { intakeManualEntry } from '../../lib/api-client';
import { Field, WizardLoading, WizardShell, goToStep, useWizard } from '../../lib/intake-ui';

export default function CoverageDetailsStep() {
  const { caseId, state, loading, error } = useWizard();
  const cov = (state?.captured_data.coverage ?? {}) as Record<string, string>;
  const [payer, setPayer] = useState(cov.payer_name ?? '');
  const [plan, setPlan] = useState(cov.plan_name ?? '');
  const [memberId, setMemberId] = useState(cov.member_id ?? '');
  const [group, setGroup] = useState(cov.group_number ?? '');
  const [busy, setBusy] = useState(false);

  if (loading) return <WizardLoading />;

  const onContinue = async () => {
    if (!caseId) return;
    setBusy(true);
    try {
      await intakeManualEntry(
        'coverage-details',
        { payer, plan_name: plan, member_id: memberId, group_number: group },
        caseId,
      );
      goToStep('benefits');
    } catch {
      setBusy(false);
    }
  };

  return (
    <WizardShell
      step="coverage-details"
      title="Do these plan details look right?"
      subtitle="I pre-filled what I could read from your card. Fix anything that's off — and don't worry if a field is blank."
      why="These let me identify which plan rules apply to your bills."
      onContinue={onContinue}
      busy={busy}
      error={error}
    >
      <Field label="Insurer" value={payer} onChangeText={setPayer} placeholder="e.g. Aetna" />
      <Field label="Plan name" value={plan} onChangeText={setPlan} placeholder="e.g. Choice POS II" />
      <Field label="Member ID" value={memberId} onChangeText={setMemberId} />
      <Field label="Group number" value={group} onChangeText={setGroup} />
    </WizardShell>
  );
}
