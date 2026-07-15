/**
 * The Tyndale Record (D5, DL-91) — the user-level master view that replaces the ad-hoc Open Cases
 * list when ENABLE_RECORD_VIEW is on. Record-level aggregates (recovered CONFIRMED vs identified
 * ESTIMATE, shown separately + labeled) then sub-case rows with at-a-glance status chips. Each row
 * routes to its sub-case summary (results-bearing) or thread (in-flight).
 */
import { useRouter } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import type { RecordPayload, SubCaseRow } from '@tyndale/shared';

function money(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

const STATUS_CHIP: Record<string, { label: string; bg: string; fg: string }> = {
  audit_complete: { label: 'Results ready', bg: 'bg-accent-tint', fg: 'text-accent' },
  audit_running: { label: 'Auditing', bg: 'bg-warning-tint', fg: 'text-warning' },
  encounter_verified: { label: 'Auditing', bg: 'bg-warning-tint', fg: 'text-warning' },
  audit_incomplete: { label: 'Needs documents', bg: 'bg-warning-tint', fg: 'text-warning' },
  extraction_failed: { label: "Couldn't read", bg: 'bg-danger-tint', fg: 'text-danger' },
  not_a_bill: { label: 'Not a bill', bg: 'bg-danger-tint', fg: 'text-danger' },
  encounter_verification_pending: { label: 'Verify visit', bg: 'bg-inset', fg: 'text-primary' },
};

function Chip({ status }: { status: string }) {
  const c = STATUS_CHIP[status] ?? { label: status, bg: 'bg-inset', fg: 'text-secondary' };
  return (
    <View className={`rounded-full px-2.5 py-0.5 ${c.bg}`}>
      <Text className={`text-[11px] font-semibold ${c.fg}`}>{c.label}</Text>
    </View>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <View className="flex-1">
      <Text className="text-xs text-secondary">{label}</Text>
      <Text className="mt-0.5 text-xl font-bold text-primary">{value}</Text>
      {hint ? <Text className="text-[10px] uppercase tracking-wide text-faint">{hint}</Text> : null}
    </View>
  );
}

function Row({ row, onPress }: { row: SubCaseRow; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="mb-2 rounded-2xl border border-hairline bg-surface p-4 hover:border-hairline"
    >
      <View className="mb-1 flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-base font-bold text-primary" numberOfLines={1}>
          {row.label}
        </Text>
        <Chip status={row.status} />
      </View>
      {row.three_number ? (
        <Text className="text-sm text-secondary">
          You should owe <Text className="font-bold text-accent">{money(row.three_number.tyndale_computed)}</Text>
          {'  ·  billed '}
          {money(row.three_number.provider_billed)}
        </Text>
      ) : (
        <Text className="text-sm text-faint">More documents needed to finish</Text>
      )}
      <View className="mt-1.5 flex-row flex-wrap items-center gap-x-3 gap-y-1">
        {row.open_item_count > 0 ? (
          <Text className="text-xs text-warning">
            {row.open_item_count} open item{row.open_item_count === 1 ? '' : 's'}
          </Text>
        ) : null}
        {row.recovered_so_far > 0 ? (
          <Text className="text-xs text-accent">Recovered {money(row.recovered_so_far)} so far</Text>
        ) : null}
        {row.next_deadline?.due_date ? (
          <Text className="text-xs text-danger">
            {row.next_deadline.label} due {row.next_deadline.due_date}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

export function RecordSection({ record }: { record: RecordPayload }) {
  const router = useRouter();
  const a = record.aggregates;
  return (
    <View>
      <Text className="mb-3 mt-6 text-xs uppercase tracking-widest text-faint">
        Your Tyndale Record
      </Text>
      <View className="mb-4 rounded-2xl bg-surface-raised p-5">
        <View className="mb-4 flex-row gap-4">
          <Stat label="Recovered so far" value={money(a.total_recovered)} hint="confirmed" />
          <Stat label="Identified" value={money(a.total_identified)} hint="estimated" />
        </View>
        <View className="flex-row gap-4">
          <Stat label="Billed reviewed" value={money(a.total_billed_reviewed)} />
          <Stat
            label="Open items"
            value={String(a.open_items)}
            hint={a.next_check_in_date ? `next check-in ${a.next_check_in_date}` : undefined}
          />
        </View>
      </View>

      {record.sub_cases.length === 0 ? (
        <Text className="mb-2 text-sm text-faint">
          No bills in your record yet — upload one to get started.
        </Text>
      ) : (
        record.sub_cases.map((c) => (
          <Row
            key={c.case_file_id}
            row={c}
            onPress={() =>
              router.push(
                (c.resume === 'summary'
                  ? `/case/${c.case_file_id}`
                  : `/audit/${c.case_file_id}/thread`) as never,
              )
            }
          />
        ))
      )}
      {record.has_older ? (
        <Text className="mt-1 text-sm text-faint">Full history →</Text>
      ) : null}
    </View>
  );
}
