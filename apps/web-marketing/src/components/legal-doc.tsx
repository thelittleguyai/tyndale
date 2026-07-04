/**
 * Renders a shared LegalDoc (from @tyndale/shared) as Next.js / Tailwind.
 * Used by app/privacy/page.tsx and app/terms/page.tsx. The legal COPY lives in
 * @tyndale/shared/legal — this file is presentation only.
 *
 * Draft gate: `published` comes from NEXT_PUBLIC_LEGAL_PUBLISHED at the call
 * site. When false, a DRAFT banner is shown at the top and the bracketed
 * fill-in fields ([SUPPORT EMAIL], etc.) render inline.
 */

import {
  ADVOCACY_DISCLAIMER,
  DRAFT_BANNER_TEXT,
  legalField,
  type LegalBlock,
  type LegalDoc,
} from '@tyndale/shared';

function Block({ block, keyPrefix }: { block: LegalBlock; keyPrefix: string }) {
  if (block.kind === 'p') {
    // Preserve intentional line breaks (contact blocks use \n).
    return (
      <p className="mt-3 whitespace-pre-line leading-relaxed text-ink/75">{block.text}</p>
    );
  }
  if (block.kind === 'bullets') {
    return (
      <ul className="mt-3 list-disc space-y-2 pl-6">
        {block.items.map((item, i) => (
          <li key={`${keyPrefix}-${i}`} className="leading-relaxed text-ink/75">
            {item}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div className="mt-4 rounded-md border border-line bg-cream-soft p-4">
      <p className="text-sm leading-relaxed text-ink/80">{block.text}</p>
    </div>
  );
}

export function LegalDocView({ doc, published }: { doc: LegalDoc; published: boolean }) {
  return (
    <>
      {!published && (
        <div className="mb-6 rounded-md border border-amber bg-amber-soft p-4">
          <p className="text-sm font-semibold leading-relaxed text-amber-deep">{DRAFT_BANNER_TEXT}</p>
        </div>
      )}

      <h1 className="text-3xl font-bold tracking-tight text-ink">{doc.title}</h1>
      {doc.showsEffectiveDate && (
        <p className="mt-2 text-sm text-ink/50">Effective Date: {legalField('effectiveDate')}</p>
      )}

      {/* Advocacy-not-advice disclaimer, always shown up top. */}
      <div className="mt-4 rounded-md border border-teal-soft bg-teal-tint p-4">
        <p className="text-sm leading-relaxed text-ink/70">{ADVOCACY_DISCLAIMER}</p>
      </div>

      {doc.intro.map((block, i) => (
        <Block key={`intro-${i}`} block={block} keyPrefix={`intro-${i}`} />
      ))}

      {doc.sections.map((section, si) => (
        <section key={si} className="mt-8">
          <h2 className="text-xl font-semibold text-ink">
            {section.num ? `${section.num}. ` : ''}
            {section.heading}
          </h2>
          {section.blocks.map((block, bi) => (
            <Block key={bi} block={block} keyPrefix={`s${si}-b${bi}`} />
          ))}
        </section>
      ))}
    </>
  );
}
