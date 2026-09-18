'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import { AdminShell } from '@/components/admin-shell';
import { ReviewWorkspace } from '@/components/review-workspace';

export default function ReviewWorkspacePage() {
  const params = useParams<{ case_id: string }>();
  const caseId = String(params.case_id);

  return (
    <AdminShell>
      <Link href="/review" className="mb-4 inline-block text-sm text-white/50 hover:text-white/80">
        ← Review queue
      </Link>
      <ReviewWorkspace caseId={caseId} />
    </AdminShell>
  );
}
