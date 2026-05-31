'use client';

import { AdminShell } from '@/components/admin-shell';
import { CaseList } from '@/components/case-list';

export default function CasesPage() {
  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Cases</h1>
      <CaseList />
    </AdminShell>
  );
}
