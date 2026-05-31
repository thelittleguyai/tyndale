'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import { AdminShell } from '@/components/admin-shell';
import { CaseDetail } from '@/components/case-detail';

export default function CaseDetailPage() {
  const params = useParams<{ case_id: string }>();
  const caseId = String(params.case_id);

  return (
    <AdminShell>
      <Link href="/cases" className="mb-4 inline-block text-sm text-white/50 hover:text-white/80">
        ← All cases
      </Link>
      <CaseDetail caseId={caseId} />
    </AdminShell>
  );
}
