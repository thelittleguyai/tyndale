/**
 * Remove-case affordance (P1 case removal) — the small ✕ on a dashboard/Record row. Shared by the
 * Record list and the classic Open Cases list so both keep the affordance. A case is user-removable
 * unless it carries a real result (in-flight or complete audit); the SERVER is authoritative
 * (soft-delete route: ownership-checked, blocks any case with findings, audited) and 409s otherwise.
 */
import { useState } from 'react';
import { ActivityIndicator, Alert, Platform, Pressable } from 'react-native';
import { X } from 'lucide-react-native';

import { removeCase } from '../../lib/api-client';
import { useThemeColors } from '../../theme/useThemeColors';

const NON_REMOVABLE_STATUSES = new Set(['audit_running', 'audit_complete', 'resolved']);

/** Whether to SHOW the ✕ (the server still has the final say). */
export function isCaseRemovable(status: string): boolean {
  return !NON_REMOVABLE_STATUSES.has(status);
}

function confirmRemoveCase(label: string): Promise<boolean> {
  const msg = `Remove “${label}”? This clears it from your dashboard.`;
  if (Platform.OS === 'web') {
    return Promise.resolve(typeof window !== 'undefined' ? window.confirm(msg) : true);
  }
  return new Promise((resolve) => {
    Alert.alert('Remove case', msg, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: 'Remove', style: 'destructive', onPress: () => resolve(true) },
    ]);
  });
}

export function CaseRemoveButton({
  caseId,
  label,
  onDone,
}: {
  caseId: string;
  label: string;
  onDone: () => void;
}) {
  const tc = useThemeColors();
  const [busy, setBusy] = useState(false);
  const onPress = async (e?: any) => {
    e?.stopPropagation?.(); // don't also open the case (web bubbling; native captures the child)
    if (busy) return;
    if (!(await confirmRemoveCase(label))) return;
    setBusy(true);
    try {
      await removeCase(caseId);
      onDone();
    } catch {
      setBusy(false);
      const m = "We couldn't remove that case — it may have results.";
      if (Platform.OS === 'web' && typeof window !== 'undefined') window.alert(m);
      else Alert.alert('Could not remove', m);
    }
  };
  return (
    <Pressable
      onPress={onPress}
      hitSlop={10}
      accessibilityRole="button"
      accessibilityLabel={`Remove ${label}`}
      className="ml-1 rounded-full p-1.5 hover:bg-inset"
    >
      {busy ? (
        <ActivityIndicator size="small" color={tc.text.secondary} />
      ) : (
        <X size={16} color={tc.text.faint} />
      )}
    </Pressable>
  );
}
