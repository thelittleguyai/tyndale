/** Animated "[Subagent] is [doing action]…" pills shown during tool execution. */

import { ActivityIndicator, Text, View } from 'react-native';

import type { ToolCall } from '@tyndale/shared';

const ACTION: Record<string, string> = {
  pg_case_file_get: 'reading your case file',
  qdrant_search_billing_codes: 'checking billing-code data',
  qdrant_search_error_detection_rules: 'checking billing rules',
  qdrant_search_laws_regulations: 'checking the law',
  qdrant_search_payer_policies: 'checking payer policies',
  cost_estimate_medicare_rvu: 'estimating costs',
  log_knowledge_gap: 'noting a data gap',
};

function phrase(tool: string): string {
  return ACTION[tool] || 'working';
}

export function ToolCallIndicator({ tools }: { tools: ToolCall[] }) {
  if (!tools.length) return null;
  return (
    <View className="mb-2 gap-1.5">
      {tools.map((t, i) => (
        <View
          key={`${t.tool_name}-${i}`}
          className="flex-row items-center gap-2 self-start rounded-full bg-inset px-3 py-1.5"
        >
          <ActivityIndicator size="small" color="var(--c-accent)" />
          <Text className="text-xs text-secondary">
            {t.subagent || 'Tyndale'} is {phrase(t.tool_name)}…
          </Text>
        </View>
      ))}
    </View>
  );
}
