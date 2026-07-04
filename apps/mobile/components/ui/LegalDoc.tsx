/**
 * Renders a shared LegalDoc (from @tyndale/shared) as React Native / NativeWind.
 * Used by app/(app)/privacy.tsx and terms.tsx. The legal COPY lives in
 * @tyndale/shared/legal — this file is presentation only.
 *
 * Draft gate: `published` comes from EXPO_PUBLIC_LEGAL_PUBLISHED at the call
 * site. When false, a DRAFT banner is shown at the top and the bracketed
 * fill-in fields ([SUPPORT EMAIL], etc.) render inline (they come pre-baked
 * into the doc via legalField()).
 */

import { Text, View } from 'react-native';
import {
  ADVOCACY_DISCLAIMER,
  DRAFT_BANNER_TEXT,
  legalField,
  type LegalBlock,
  type LegalDoc,
} from '@tyndale/shared';

function Block({ block }: { block: LegalBlock }) {
  if (block.kind === 'p') {
    return <Text className="mt-3 text-base leading-relaxed text-white/75">{block.text}</Text>;
  }
  if (block.kind === 'bullets') {
    return (
      <View className="mt-3">
        {block.items.map((item, i) => (
          <View key={i} className="mb-2 flex-row">
            <Text className="mr-2 text-base leading-relaxed text-white/50">•</Text>
            <Text className="flex-1 text-base leading-relaxed text-white/75">{item}</Text>
          </View>
        ))}
      </View>
    );
  }
  // callout — all-caps disclaimer / plain-language box
  return (
    <View className="mt-4 rounded-token-md border border-white/15 bg-white/5 p-4">
      <Text className="text-sm leading-relaxed text-white/80">{block.text}</Text>
    </View>
  );
}

export function LegalDocView({ doc, published }: { doc: LegalDoc; published: boolean }) {
  return (
    <View>
      {!published && (
        <View className="mb-6 rounded-token-md border border-amber/60 bg-amber/15 p-4">
          <Text className="text-sm font-semibold leading-relaxed text-amber">{DRAFT_BANNER_TEXT}</Text>
        </View>
      )}

      <Text className="text-3xl font-bold text-white">{doc.title}</Text>
      {doc.showsEffectiveDate && (
        <Text className="mt-2 text-sm text-white/50">Effective Date: {legalField('effectiveDate')}</Text>
      )}

      {/* Advocacy-not-advice disclaimer, always shown up top. */}
      <View className="mt-4 rounded-token-md border border-teal-soft/30 bg-teal-soft/10 p-4">
        <Text className="text-sm leading-relaxed text-white/70">{ADVOCACY_DISCLAIMER}</Text>
      </View>

      {doc.intro.map((block, i) => (
        <Block key={`intro-${i}`} block={block} />
      ))}

      {doc.sections.map((section, si) => (
        <View key={si} className="mt-8">
          <Text className="text-xl font-semibold text-white">
            {section.num ? `${section.num}. ` : ''}
            {section.heading}
          </Text>
          {section.blocks.map((block, bi) => (
            <Block key={bi} block={block} />
          ))}
        </View>
      ))}
    </View>
  );
}
