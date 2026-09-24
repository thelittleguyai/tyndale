/**
 * "See an example" and "Help me find it" (doc 40 §A3, §A5). Both are rendered ONLY when the
 * server sent something to show: a screen with no example has no example button at all — never
 * an empty sheet, never "coming soon". An example is either the doc 41 illustration bundled with
 * the app (assets/examples — its numbered legend rendered beside it as text, never baked into the
 * image) or, until that image lands, the public federal sample opened in the browser (SBC, MSN).
 */
import { useState } from 'react';
import { Image, Linking, Modal, ScrollView, Text, View } from 'react-native';

import type { IntakeExample, IntakeHelp } from '@tyndale/shared';

import { EXAMPLE_IMAGES } from '../../assets/examples';
import { emailIntakeHelp } from '../../lib/api-client';
import { ChatMarkdown } from '../chat/Markdown';
import { Button } from '../ui';

/** The bundled image for an illustrated example — undefined when this build does not carry it. */
function illustrationOf(example: IntakeExample) {
  return example.illustration ? EXAMPLE_IMAGES[example.illustration.slot] : undefined;
}

/** Whether the sheet has anything to show in THIS build: a bundled illustration, or a sample. */
export function exampleShowable(example: IntakeExample | null | undefined): boolean {
  return !!example && (!!illustrationOf(example) || !!example.asset);
}

function Sheet({
  title,
  onClose,
  closeLabel,
  children,
}: {
  title: string | null;
  onClose: () => void;
  closeLabel: string;
  children: React.ReactNode;
}) {
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/50">
        <View className="max-h-[85%] w-full max-w-2xl self-center rounded-t-3xl bg-surface p-5">
          <Text accessibilityRole="header" className="mb-3 text-xl font-bold text-primary">
            {title}
          </Text>
          <ScrollView>{children}</ScrollView>
          <Button label={closeLabel} variant="secondary" onPress={onClose} fullWidth className="mt-4" />
        </View>
      </View>
    </Modal>
  );
}

function Steps({ steps }: { steps: string[] }) {
  return (
    <View className="gap-3">
      {steps.map((s, i) => (
        <View key={i} className="flex-row gap-3">
          <Text className="w-6 text-body font-semibold text-accent">{i + 1}</Text>
          <Text className="flex-1 text-body leading-6 text-primary">{s}</Text>
        </View>
      ))}
    </View>
  );
}

export function ExampleSheet({
  example,
  chrome,
  onClose,
}: {
  example: IntakeExample;
  chrome: Record<string, string>;
  onClose: () => void;
}) {
  const image = illustrationOf(example);
  const asset = example.asset;
  return (
    <Sheet title={example.title} onClose={onClose} closeLabel={chrome.close ?? 'Close'}>
      {Object.values(example.glosses).map((g) => (
        <Text key={g} className="mb-3 text-body leading-6 text-secondary">
          {g}
        </Text>
      ))}
      {image ? (
        <>
          <Image
            source={image}
            resizeMode="contain"
            accessibilityLabel={example.title ?? undefined}
            style={{ width: '100%', aspectRatio: example.illustration?.aspect === 'landscape' ? 1560 / 975 : 1560 / 1950 }}
            testID="intake-example-image"
          />
          {/* the legend, numbered to match the image's badges — text, so it is read aloud */}
          <View className="mt-4 gap-3" testID="intake-example-legend">
            {(example.legend ?? []).map((line, i) => (
              <View key={i} className="flex-row gap-3">
                <Text className="w-6 text-body font-semibold text-accent">{i + 1}</Text>
                <View className="flex-1">
                  <ChatMarkdown text={line} className="text-body leading-6 text-primary" />
                </View>
              </View>
            ))}
          </View>
        </>
      ) : (
        <Steps steps={example.callouts} />
      )}
      {!image && example.source_line ? (
        <Text className="mt-4 text-body text-secondary">{example.source_line}</Text>
      ) : null}
      {asset ? (
        <Button
          label={chrome.open_sample ?? 'Open the sample'}
          variant={image ? 'secondary' : 'primary'}
          onPress={() => Linking.openURL(asset.url).catch(() => undefined)}
          fullWidth
          className="mt-4"
          testID="intake-example-open"
        />
      ) : null}
    </Sheet>
  );
}

export function HelpSheet({
  help,
  chrome,
  caseId,
  screenId,
  onClose,
}: {
  help: IntakeHelp;
  chrome: Record<string, string>;
  caseId: string | null;
  screenId: string;
  onClose: () => void;
}) {
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const send = async () => {
    setSending(true);
    try {
      const r = await emailIntakeHelp(help.document_type, caseId, screenId);
      setMessage(r.message);
    } catch {
      setMessage(chrome.email_failed ?? null);
    } finally {
      setSending(false);
    }
  };
  return (
    <Sheet title={help.title} onClose={onClose} closeLabel={chrome.close ?? 'Close'}>
      {help.note ? <Text className="mb-3 text-body leading-6 text-secondary">{help.note}</Text> : null}
      <Steps steps={help.steps} />
      {/* People leave the app to go to the portal (locked 5c) — email is the one channel built. */}
      {help.can_email ? (
        <Button
          label={chrome.email_steps ?? 'Email me these steps'}
          variant="secondary"
          onPress={send}
          disabled={sending}
          fullWidth
          className="mt-4"
          testID="intake-help-email"
        />
      ) : null}
      {message ? (
        <Text accessibilityLiveRegion="polite" className="mt-2 text-body text-secondary">
          {message}
        </Text>
      ) : null}
    </Sheet>
  );
}
