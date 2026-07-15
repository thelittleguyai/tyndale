/**
 * The Tyndale Record list (D5, DL-91) — the user-level sub-case list, shown on the dashboard when
 * ENABLE_RECORD_VIEW is on. Redesigned to Direction A (§3): a single "Your record" Card of
 * divider-separated rows (provider · outcome/need · status chip); the Record-level aggregates now
 * live in the four MetricCards at the top of the dashboard, so they're not repeated here. Each row
 * routes to its sub-case summary (results-bearing) or thread (in-flight).
 */
import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { RecordPayload, SubCaseRow } from '@tyndale/shared';

import { CaseRemoveButton, isCaseRemovable } from './CaseRemoveButton';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-04-02" → "Apr 2" (no Date/timezone parsing). Null-safe for best-effort service dates. */
function shortDate(iso: string | null): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const month = MONTHS[parseInt(m[2], 10) - 1];
  return month ? `${month} ${parseInt(m[3], 10)}` : null;
}

const STATUS_CHIP: Record<string, { label: string; bg: string; fg: string }> = {
  audit_complete: { label: 'Results ready', bg: 'bg-accent-tint', fg: 'text-accent' },
  resolved: { label: 'Resolved', bg: 'bg-accent-tint', fg: 'text-accent' },
  audit_running: { label: 'Auditing', bg: 'bg-warning-tint', fg: 'text-warning-on-tint' },
  encounter_verified: { label: 'Auditing', bg: 'bg-warning-tint', fg: 'text-warning-on-tint' },
  audit_incomplete: { label: 'Needs documents', bg: 'bg-warning-tint', fg: 'text-warning-on-tint' },
  awaiting_eob_confirmation: { label: 'Needs documents', bg: 'bg-warning-tint', fg: 'text-warning-on-tint' },
  extraction_failed: { label: "Couldn't read", bg: 'bg-danger-tint', fg: 'text-danger-on-tint' },
  not_a_bill: { label: 'Not a bill', bg: 'bg-danger-tint', fg: 'text-danger-on-tint' },
  encounter_verification_pending: { label: 'Verify visit', bg: 'bg-inset', fg: 'text-secondary' },
};

function Chip({ status }: { status: string }) {
  const c = STATUS_CHIP[status] ?? { label: status, bg: 'bg-inset', fg: 'text-secondary' };
  return (
    <View className={`self-start rounded-full px-2.5 py-1 ${c.bg}`}>
      <Text className={`text-caption font-medium ${c.fg}`}>{c.label}</Text>
    </View>
  );
}

function Subtitle({ row }: { row: SubCaseRow }) {
  const date = shortDate(row.service_date);
  if (row.three_number) {
    return (
      <Text className="mt-0.5 text-caption text-faint" numberOfLines={2}>
        {date ? `${date} visit · ` : ''}you should owe{' '}
        <Text className="font-medium text-accent">{money(row.three_number.tyndale_computed)}</Text> of{' '}
        {money(row.three_number.provider_billed)} billed
      </Text>
    );
  }
  const parts: string[] = [];
  if (date) parts.push(`${date} visit`);
  if (row.open_item_count > 0) {
    parts.push(`${row.open_item_count} document${row.open_item_count === 1 ? '' : 's'} needed`);
  }
  if (row.next_deadline?.due_date) parts.push(`${row.next_deadline.label} closes ${row.next_deadline.due_date}`);
  return (
    <Text className="mt-0.5 text-caption text-faint" numberOfLines={2}>
      {parts.join(' · ') || 'In progress'}
    </Text>
  );
}

function RecordRow({
  row,
  last,
  onPress,
  onRemoved,
}: {
  row: SubCaseRow;
  last: boolean;
  onPress: () => void;
  onRemoved?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className={`min-h-[44px] flex-row items-center justify-between gap-3 p-4 active:bg-inset ${
        last ? '' : 'border-b border-hairline'
      }`}
    >
      <View className="flex-1">
        {/* Title = provider (fallback chain), never the status — the status is the trailing chip. */}
        <Text className="text-body font-medium text-primary" numberOfLines={1}>
          {row.provider || 'Bill review'}
        </Text>
        <Subtitle row={row} />
      </View>
      <View className="flex-row items-center gap-1">
        <Chip status={row.status} />
        {onRemoved && isCaseRemovable(row.status) ? (
          <CaseRemoveButton caseId={row.case_file_id} label={row.provider || 'Bill review'} onDone={onRemoved} />
        ) : null}
      </View>
    </Pressable>
  );
}

export function RecordSection({
  record,
  onChanged,
}: {
  record: RecordPayload;
  onChanged?: () => void;
}) {
  const router = useRouter();
  const go = (c: SubCaseRow) =>
    router.push(
      (c.resume === 'summary' ? `/case/${c.case_file_id}` : `/audit/${c.case_file_id}/thread`) as never,
    );
  return (
    <View>
      <Text className="mb-2 mt-6 text-caption font-medium text-secondary">Your record</Text>
      {record.sub_cases.length === 0 ? (
        <View className="rounded-card border border-hairline bg-surface p-4">
          <Text className="text-body text-faint">
            No bills in your record yet — upload one to get started.
          </Text>
        </View>
      ) : (
        <View className="overflow-hidden rounded-card border border-hairline bg-surface">
          {record.sub_cases.map((c, i) => (
            <RecordRow
              key={c.case_file_id}
              row={c}
              last={i === record.sub_cases.length - 1}
              onPress={() => go(c)}
              onRemoved={onChanged}
            />
          ))}
        </View>
      )}
      {record.has_older ? (
        <Text className="mt-2 text-caption text-faint">Older cases are kept in your full history.</Text>
      ) : null}
    </View>
  );
}
