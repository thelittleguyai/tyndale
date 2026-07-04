import { buildPrivacyDoc } from '@tyndale/shared';
import { LegalDocView } from '../../components/legal-doc';

export const metadata = { title: 'Privacy Policy — Tyndale' };

// One-line publication gate: flip NEXT_PUBLIC_LEGAL_PUBLISHED to "true" (and
// fill LEGAL_FIELDS in @tyndale/shared/legal) after counsel signs off. Default
// is unpublished, so the DRAFT banner shows until then.
const LEGAL_PUBLISHED = process.env.NEXT_PUBLIC_LEGAL_PUBLISHED === 'true';

export default function PrivacyPage() {
  const doc = buildPrivacyDoc();
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <LegalDocView doc={doc} published={LEGAL_PUBLISHED} />
      <a href="/" className="mt-12 inline-block text-sm font-medium text-teal hover:text-teal-deep">
        ← Back home
      </a>
    </main>
  );
}
