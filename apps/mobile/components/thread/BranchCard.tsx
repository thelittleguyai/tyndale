/**
 * Branch-state card (round-2 N2) — presentation over behaviours the server already ships.
 *
 * The five §5/§10 states (partial-illegible, summary-vs-itemized, wrong document, reconcile,
 * declines) have rendered as plain system lines since they were built; the prototype gives them
 * a card with a small label chip and, where a real next step exists, ONE inline action. The
 * BODY text is Brock's, verbatim from the payload — this component adds chrome only.
 *
 * The action is the prototype's "Retake just that page" idea generalised honestly: it routes to
 * the existing add-a-document path for THIS case (the same re-upload flow the needs-documents
 * checklist uses). It renders only for states where a document actually fixes things —
 * reconcile is information, not an errand, so it gets no button.
 */
import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

export type BranchKind = 'partial_read' | 'summary_bill' | 'wrongdoc' | 'reconcile';

const CHROME: Record<BranchKind, { label: string; action: string | null }> = {
  partial_read: { label: 'Readability', action: 'Add a clearer photo' },
  summary_bill: { label: 'Itemized bill', action: 'Add the itemized bill' },
  wrongdoc: { label: 'Document check', action: 'Add your bill or EOB' },
  reconcile: { label: 'Numbers check', action: null },
};

export function branchKindOf(payload: Record<string, unknown>): BranchKind | null {
  const dq = payload.data_quality as { kind?: string } | undefined;
  if (dq?.kind === 'partial_read') return 'partial_read';
  if (dq?.kind === 'summary_bill') return 'summary_bill';
  if (typeof payload.wrongdoc_branch === 'string') return 'wrongdoc';
  if (payload.branch_state === 'reconcile') return 'reconcile';
  return null;
}

export function BranchCard({
  kind,
  text,
  caseFileId,
}: {
  kind: BranchKind;
  text: string;
  caseFileId: string;
}) {
  const router = useRouter();
  const chrome = CHROME[kind];
  return (
    <View className="my-2 w-full rounded-card border border-accent bg-surface p-4">
      <View className="mb-2 self-start rounded-chip bg-accent-tint px-2.5 py-1">
        <Text className="text-micro font-medium text-accent">{chrome.label}</Text>
      </View>
      <Text className="text-body leading-6 text-primary">{text}</Text>
      {chrome.action ? (
        <Pressable
          onPress={() => router.push({ pathname: '/upload', params: { caseId: caseFileId } })}
          accessibilityRole="button"
          className="mt-3 min-h-[44px] items-center justify-center self-start rounded-control bg-accent px-4 py-2.5"
          testID={`branch-action-${kind}`}
        >
          <Text className="text-body font-medium text-on-accent">{chrome.action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
