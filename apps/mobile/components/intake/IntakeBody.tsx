/**
 * One renderer per screen KIND (doc 40). The server's Intake Planner decides which screen comes
 * next and hands over every string; this file decides only how a kind is drawn. It holds no
 * sequence and no product copy — a slot the server did not send simply does not render.
 *
 * Floor (§C11): body text 16px (`text-body`), every target ≥ 44px, semantic tokens only.
 */
import { useState } from 'react';
import { ActivityIndicator, Text, TextInput, View } from 'react-native';

import type { IntakeScreen } from '@tyndale/shared';

import { ChatMarkdown } from '../chat/Markdown';
import { Button, Card, Disclosure, TextLink } from '../ui';
import { PressableScale } from '../ui/PressableScale';
import { useThemeColors } from '../../theme/useThemeColors';

export type IntakeAct = (action: string, values?: Record<string, unknown>) => void;

export interface IntakeBodyProps {
  screen: IntakeScreen;
  busy: boolean;
  act: IntakeAct;
  /** capture screens: open the existing upload/camera flow for this document type */
  onCapture: (expect: string | null) => void;
  onEdit: (screenId: string) => void;
  onAttest: (relationship: string) => void;
  onAttestDecline: () => void;
  onPlanConfirm: (accept: boolean) => void;
  onRun: () => void;
  onExit: () => void;
  onHandoff: () => void;
}

const c = (screen: IntakeScreen, slot: string): string | undefined => screen.copy[slot];

/** `markdown`: the line is Brock's THREAD copy (the attest intro carries **bold**) — draw it with
 *  the thread's own renderer rather than showing the asterisks. */
function Body({ text, markdown }: { text?: string | null; markdown?: boolean }) {
  if (!text) return null;
  const cls = 'text-body leading-6 text-secondary';
  if (markdown) {
    return (
      <View className="mt-3">
        <ChatMarkdown text={text} className={cls} />
      </View>
    );
  }
  return <Text className={`mt-3 ${cls}`}>{text}</Text>;
}

/** Every `gloss_*` slot the screen carries — the term is explained where it is first used. */
function Glosses({ screen }: { screen: IntakeScreen }) {
  const glosses = Object.entries(screen.copy).filter(([k]) => k.startsWith('gloss_'));
  if (!glosses.length) return null;
  return (
    <View className="mt-3 gap-2 rounded-2xl bg-inset p-4" testID="intake-glosses">
      {glosses.map(([k, v]) => (
        <Text key={k} className="text-body leading-6 text-secondary">
          {v}
        </Text>
      ))}
    </View>
  );
}

function Option({ label, selected, onPress, testID }: { label: string; selected?: boolean; onPress: () => void; testID?: string }) {
  return (
    <PressableScale
      accessibilityRole="radio"
      accessibilityState={{ checked: !!selected }}
      onPress={onPress}
      testID={testID}
      className={`min-h-[48px] justify-center rounded-2xl border px-4 py-3 ${
        selected ? 'border-accent bg-accent-tint' : 'border-hairline bg-surface'
      }`}
    >
      <Text className={`text-body font-semibold ${selected ? 'text-accent' : 'text-primary'}`}>{label}</Text>
    </PressableScale>
  );
}

function Capture({ screen, busy, act, onCapture }: IntakeBodyProps) {
  const data = screen.data as { expect?: string | null; have?: number; note?: string | null };
  const skip = c(screen, 'skip') ?? c(screen, 'no_bill') ?? c(screen, 'secondary');
  const consequence = c(screen, 'skip_consequence') ?? c(screen, 'no_bill_note') ?? c(screen, 'secondary_consequence');
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Body text={c(screen, 'other_name')} />
      <Glosses screen={screen} />
      {data.note ? (
        // §C12 — a wrong document is said plainly, and the way on is right below it
        <View className="mt-3 rounded-2xl border border-warning bg-warning-tint p-4" testID="intake-note">
          <Text className="text-body leading-6 text-primary">{data.note}</Text>
        </View>
      ) : null}
      <Button
        label={c(screen, 'primary') ?? ''}
        onPress={() => onCapture(data.expect ?? null)}
        disabled={busy}
        fullWidth
        className="mt-6"
        testID="intake-capture"
      />
      {/* trust microcopy AT the moment of capture (§C10) */}
      {c(screen, 'trust') ? <Text className="mt-2 text-center text-body text-faint">{c(screen, 'trust')}</Text> : null}
      {screen.skippable && skip ? (
        <View className="mt-4">
          <Button label={skip} variant="secondary" onPress={() => act('skip')} disabled={busy} fullWidth testID="intake-skip" />
          {/* a skip always says what it costs */}
          <Body text={consequence} />
        </View>
      ) : null}
    </View>
  );
}

function Summary({ screen, busy, act, onCapture }: IntakeBodyProps) {
  const rows = ((screen.data as { rows?: { slot: string; value: string | null }[] }).rows ?? []);
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Card className="mt-4">
        {rows.map((r) => (
          <View key={r.slot} className="flex-row justify-between gap-3 py-2">
            <Text className="text-body text-secondary">{c(screen, r.slot)}</Text>
            <Text className={`flex-1 text-right text-body ${r.value ? 'text-primary' : 'text-faint'}`}>
              {r.value ?? c(screen, 'row_missing')}
            </Text>
          </View>
        ))}
      </Card>
      <Button label={c(screen, 'fix') ?? ''} variant="tertiary" onPress={() => onCapture('itemized_bill')} disabled={busy} className="mt-2 self-start" />
      <Text className="mt-5 text-lg font-semibold text-primary">{c(screen, 'other_bills')}</Text>
      <Body text={c(screen, 'other_bills_why')} />
      <View className="mt-4 gap-3">
        <Button label={c(screen, 'no') ?? ''} onPress={() => act('no')} disabled={busy} fullWidth testID="intake-summary-no" />
        {/* another bill for the SAME visit attaches to the same case (§C1) */}
        <Button label={c(screen, 'yes') ?? ''} variant="secondary" onPress={() => { act('yes'); onCapture('itemized_bill'); }} disabled={busy} fullWidth />
      </View>
    </View>
  );
}

function Choice({ screen, busy, act }: IntakeBodyProps) {
  const options = ((screen.data as { options?: { value: string; slot?: string; label?: string }[] }).options ?? []);
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Glosses screen={screen} />
      <View className="mt-5 gap-2" accessibilityRole="radiogroup">
        {options.map((o) => (
          <Option
            key={o.value}
            label={o.label ?? (o.slot ? c(screen, o.slot) : undefined) ?? o.value}
            onPress={() => !busy && act('continue', { choice: o.value })}
            testID={`intake-option-${o.value}`}
          />
        ))}
      </View>
      {/* "I'm not sure" is always an answer — and it says what it costs */}
      <Body text={c(screen, 'not_sure_consequence')} />
    </View>
  );
}

function Fields({ screen, busy, act }: IntakeBodyProps) {
  const tc = useThemeColors();
  const fields = ((screen.data as { fields?: { name: string; slot: string; value?: unknown; input: string; required?: boolean }[] }).fields ?? []);
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.name, f.value == null ? '' : String(f.value)])),
  );
  const notSure = c(screen, 'not_sure');
  // never offer a save the server will refuse: every field it marks required must be filled
  // (no field marked → any one value is an answer)
  const filled = (name: string) => Boolean((values[name] ?? '').trim());
  const required = fields.filter((f) => f.required);
  const canSave = required.length ? required.every((f) => filled(f.name)) : fields.some((f) => filled(f.name));
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Glosses screen={screen} />
      <View className="mt-5 gap-4">
        {fields.map((f) => (
          <View key={f.name}>
            <Text nativeID={`label-${f.name}`} className="mb-1 text-body text-secondary">{c(screen, f.slot)}</Text>
            <TextInput
              accessibilityLabelledBy={`label-${f.name}`}
              value={values[f.name] ?? ''}
              onChangeText={(t) => setValues((v) => ({ ...v, [f.name]: t }))}
              keyboardType={f.input === 'usd' ? 'decimal-pad' : 'default'}
              placeholderTextColor={tc.text.faint}
              className="min-h-[48px] rounded-xl border border-hairline bg-surface px-4 text-body text-primary"
              testID={`intake-field-${f.name}`}
            />
          </View>
        ))}
      </View>
      <Button
        label={c(screen, 'primary') ?? ''}
        onPress={() => act('continue', values)}
        disabled={busy || !canSave}
        fullWidth
        className="mt-6"
        testID="intake-fields-save"
      />
      {notSure ? (
        <View className="mt-3">
          <Button label={notSure} variant="secondary" onPress={() => act('not_sure')} disabled={busy} fullWidth />
          <Body text={c(screen, 'not_sure_consequence')} />
        </View>
      ) : screen.skippable && c(screen, 'skip') ? (
        <View className="mt-3">
          <Button label={c(screen, 'skip') ?? ''} variant="secondary" onPress={() => act('skip')} disabled={busy} fullWidth testID="intake-skip" />
          {/* a skip always says what it costs */}
          <Body text={c(screen, 'skip_consequence')} />
        </View>
      ) : null}
    </View>
  );
}

function PlanConfirm({ screen, busy, onPlanConfirm }: IntakeBodyProps) {
  const rows = ((screen.data as { rows?: { slot: string; value: number | null; unit: string }[] }).rows ?? []);
  const show = (v: number | null, unit: string) =>
    v == null ? '—' : unit === 'fraction' ? `${Math.round(v * 100)}%` : `$${v.toLocaleString()}`;
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Card className="mt-4">
        {rows.map((r) => (
          <View key={r.slot} className="flex-row justify-between py-2">
            <Text className="text-body text-secondary">{c(screen, r.slot)}</Text>
            <Text className="text-body font-semibold text-primary">{show(r.value, r.unit)}</Text>
          </View>
        ))}
      </Card>
      <Glosses screen={screen} />
      <View className="mt-5 gap-3">
        <Button label={c(screen, 'yes') ?? ''} onPress={() => onPlanConfirm(true)} disabled={busy} fullWidth />
        <Button label={c(screen, 'no') ?? ''} variant="secondary" onPress={() => onPlanConfirm(false)} disabled={busy} fullWidth />
      </View>
    </View>
  );
}

interface TimelineData {
  rows?: { document_id: string | null; date: string | null; month_label: string | null; after_visit: boolean; network: string | null }[];
  months?: { label: string; has_eob: boolean; is_visit_month: boolean }[];
  count?: number;
}

function Timeline({ screen, busy, act, onCapture }: IntakeBodyProps) {
  const data = screen.data as TimelineData;
  const gapLines = (c(screen, 'gap_lines') ?? '').split('\n').filter(Boolean);
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Glosses screen={screen} />
      {/* Phase 1 renders ONE row — the patient. Anchored on the plan-year start, never Jan 1. */}
      {data.months?.length ? (
        <View className="mt-5 flex-row flex-wrap gap-2" testID="intake-timeline-months">
          {data.months.map((m) => (
            <View
              key={m.label}
              className={`min-w-[72px] rounded-xl border px-3 py-2 ${
                m.has_eob ? 'border-accent bg-accent-tint' : 'border-hairline bg-surface'
              }`}
            >
              <Text className={`text-body ${m.has_eob ? 'font-semibold text-accent' : 'text-faint'}`}>{m.label}</Text>
              {m.is_visit_month ? <Text className="text-body text-primary">{c(screen, 'visit_marker')}</Text> : null}
            </View>
          ))}
        </View>
      ) : null}
      {(data.rows ?? []).filter((r) => r.after_visit || !r.date).map((r, i) => (
        // collected and shown — and visibly NOT part of this bill's position
        <Text key={r.document_id ?? i} className="mt-3 text-body text-secondary">
          {r.date ? `${r.month_label} — ${c(screen, 'after_visit')}` : c(screen, 'no_date')}
        </Text>
      ))}
      {gapLines.length ? (
        <View className="mt-4 rounded-2xl border border-warning bg-warning-tint p-4" testID="intake-timeline-gaps">
          {gapLines.map((g) => (
            <Text key={g} className="text-body leading-6 text-primary">{g}</Text>
          ))}
          <Text className="mt-1 text-body leading-6 text-primary">{c(screen, 'gap_consequence')}</Text>
        </View>
      ) : null}
      <Button label={c(screen, 'add_more') ?? ''} variant="secondary" onPress={() => onCapture('eob')} disabled={busy} fullWidth className="mt-4" />
      {/* the completeness confirmation — asked EVERY time (locked 5d), as a tap-to-confirm card */}
      {c(screen, 'confirm_text') ? (
        <Card className="mt-5" >
          <Text className="text-body font-semibold leading-6 text-primary" testID="intake-completeness">{c(screen, 'confirm_text')}</Text>
          <View className="mt-4 gap-3">
            <Button label={c(screen, 'confirm_yes') ?? ''} onPress={() => act('yes')} disabled={busy} fullWidth testID="intake-complete-yes" />
            <Button label={c(screen, 'confirm_no') ?? ''} variant="secondary" onPress={() => act('no')} disabled={busy} fullWidth />
          </View>
        </Card>
      ) : null}
    </View>
  );
}

interface AttestData {
  declined?: boolean;
  intro?: string | null;
  confirm?: string | null;
  decline_ack?: string | null;
  relationships?: { value: string; label: string | null }[];
  edge_prompts?: string[];
}

function Attest({ screen, busy, onAttest, onAttestDecline, onExit }: IntakeBodyProps) {
  const data = screen.data as AttestData;
  const [picked, setPicked] = useState<string | null>(null);
  if (data.declined) {
    return (
      <View>
        <Body text={data.decline_ack} markdown />
        <Button label={c(screen, 'back_home') ?? ''} onPress={onExit} fullWidth className="mt-6" />
      </View>
    );
  }
  return (
    <View>
      <Body text={data.intro} markdown />
      {(data.edge_prompts ?? []).map((p) => <Body key={p} text={p} />)}
      <View className="mt-5 gap-2" accessibilityRole="radiogroup">
        {(data.relationships ?? []).map((r) => (
          <Option key={r.value} label={r.label ?? r.value} selected={picked === r.value} onPress={() => setPicked(r.value)} testID={`intake-attest-${r.value}`} />
        ))}
      </View>
      <Body text={data.confirm} markdown />
      <Button label={c(screen, 'primary') ?? ''} onPress={() => picked && onAttest(picked)} disabled={busy || !picked} fullWidth className="mt-5" testID="intake-attest-confirm" />
      {/* the decline path is always offered — refusing closes the flow honestly (F1) */}
      <Button label={c(screen, 'decline') ?? ''} variant="secondary" onPress={onAttestDecline} disabled={busy} fullWidth className="mt-3" testID="intake-attest-decline" />
    </View>
  );
}

type Answer = 'yes' | 'no' | 'not_sure';

interface FactCard { line_item_id: string; code?: string | null; text: string | null; more?: string | null }

function Confirmations({ screen, busy, act }: IntakeBodyProps) {
  // ONE card per fact the engine emitted — the list is never capped and never padded (§A4-5).
  // Each card: the code and ONE plain sentence; the rest under the disclosure (e2e round 3 R4).
  const items = ((screen.data as { line_items?: FactCard[] }).line_items ?? []);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const all = items.length > 0 && items.every((i) => answers[i.line_item_id]);
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <View className="mt-4 gap-4">
        {items.map((it) => (
          <Card key={it.line_item_id}>
            <Text className="text-body font-semibold leading-6 text-primary" testID={`intake-fact-${it.line_item_id}-text`}>
              {it.code ? `${it.code} · ${it.text ?? ''}` : it.text}
            </Text>
            {it.more ? (
              <Disclosure summary={c(screen, 'more') ?? ''}>
                <Text className="text-body leading-6 text-secondary">{it.more}</Text>
              </Disclosure>
            ) : null}
            <View className="mt-3 flex-row gap-2">
              {(['yes', 'no', 'not_sure'] as Answer[]).map((a) => (
                <View key={a} className="flex-1">
                  <Option label={c(screen, a) ?? a} selected={answers[it.line_item_id] === a} onPress={() => setAnswers((s) => ({ ...s, [it.line_item_id]: a }))} testID={`intake-fact-${it.line_item_id}-${a}`} />
                </View>
              ))}
            </View>
            {answers[it.line_item_id] === 'not_sure' ? <Body text={c(screen, 'not_sure_note')} /> : null}
          </Card>
        ))}
      </View>
      <Button
        label={c(screen, 'primary') ?? ''}
        onPress={() => act('continue', { confirmations: items.map((i) => ({ line_item_id: i.line_item_id, response: answers[i.line_item_id] })) })}
        disabled={busy || !all}
        fullWidth
        className="mt-6"
        testID="intake-facts-done"
      />
    </View>
  );
}

interface ReadinessLine { key: string; label: string | null; resolved: boolean; state: string; limits: string | null; edit_screen: string | null }

function Readiness({ screen, busy, act, onEdit }: IntakeBodyProps) {
  const data = screen.data as { lines?: ReadinessLine[]; can_run?: boolean };
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <View className="mt-4 gap-3">
        {(data.lines ?? []).map((l) => (
          <Card key={l.key}>
            {/* e2e round 3 R2: the label column takes the row and may shrink (min-w-0); "Change"
                is a TextLink — its own width, never stretched (shrink-0). The tertiary Button is
                full-width by default: beside a flex-1 column it squeezed every label to one
                character per line. */}
            <View className="flex-row items-start gap-3" testID={`intake-readiness-row-${l.key}`}>
              <View className="min-w-0 flex-1" testID={`intake-readiness-label-${l.key}`}>
                <Text className="text-body font-semibold text-primary">{l.label}</Text>
                <Text className={`text-body ${l.resolved ? 'text-accent' : 'text-secondary'}`}>
                  {l.resolved ? c(screen, 'resolved') : l.state === 'skipped' ? c(screen, 'skipped') : c(screen, 'unresolved')}
                </Text>
                {/* what leaving it unresolved LIMITS */}
                {l.limits ? <Text className="mt-1 text-body leading-6 text-secondary">{l.limits}</Text> : null}
              </View>
              {l.edit_screen ? (
                <TextLink label={c(screen, 'edit') ?? ''} onPress={() => onEdit(l.edit_screen!)} disabled={busy} testID={`intake-edit-${l.key}`} />
              ) : null}
            </View>
          </Card>
        ))}
      </View>
      {data.can_run ? (
        <Button label={c(screen, 'primary') ?? ''} onPress={() => act('ack')} disabled={busy} fullWidth className="mt-6" testID="intake-ready-continue" />
      ) : (
        <Body text={c(screen, 'cannot_run')} />
      )}
    </View>
  );
}

function Info({ screen, busy, act }: IntakeBodyProps) {
  return (
    <View>
      <Body text={c(screen, 'body')} />
      <Body text={c(screen, 'doctrine')} />
      <Button label={c(screen, 'primary') ?? ''} onPress={() => act('ack')} disabled={busy} fullWidth className="mt-6" testID="intake-primary" />
      {c(screen, 'trust') ? <Text className="mt-2 text-center text-body text-faint">{c(screen, 'trust')}</Text> : null}
    </View>
  );
}

function Waiting({ screen }: IntakeBodyProps) {
  const tc = useThemeColors();
  const steps = Object.entries(screen.copy).filter(([k]) => k.startsWith('step_'));
  return (
    <View>
      <Body text={c(screen, 'body') ?? c(screen, 'leave')} />
      <Glosses screen={screen} />
      <View className="mt-6 items-center"><ActivityIndicator color={tc.accent} /></View>
      {/* real stages only — these are the engine's actual phases, not decoration */}
      <View className="mt-5 gap-2">
        {steps.map(([k, v]) => <Text key={k} className="text-body text-secondary">{v}</Text>)}
      </View>
    </View>
  );
}

export function IntakeBody(props: IntakeBodyProps) {
  const { screen, busy, onHandoff } = props;
  switch (screen.kind) {
    case 'capture':
    case 'coach':
      return <Capture {...props} />;
    case 'summary':
      return <Summary {...props} />;
    case 'choice':
      return <Choice {...props} />;
    case 'fields':
      return <Fields {...props} />;
    case 'plan_confirm':
      return <PlanConfirm {...props} />;
    case 'timeline':
      return <Timeline {...props} />;
    case 'attest':
      return <Attest {...props} />;
    case 'confirmations':
      return <Confirmations {...props} />;
    case 'readiness':
      return <Readiness {...props} />;
    case 'progress':
      return <Waiting {...props} />;
    case 'ready':
      // the controller starts the audit the moment the planner says READY; this is its wait
      return <Waiting {...props} />;
    case 'handoff':
      return (
        <View>
          <Body text={c(screen, 'body')} />
          <Button label={c(screen, 'primary') ?? ''} onPress={onHandoff} disabled={busy} fullWidth className="mt-6" testID="intake-handoff" />
        </View>
      );
    default:
      return <Info {...props} />;
  }
}
