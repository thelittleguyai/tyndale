'use client';

import { useEffect, useState } from 'react';

import { AdminShell } from '@/components/admin-shell';
import { CaseList } from '@/components/case-list';
import { adminGetDashboard, type AdminDashboard } from '@/lib/api-client';

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <p className="text-xs uppercase tracking-widest text-white/40">{label}</p>
      <p className="mt-1 text-3xl font-bold text-white">{value}</p>
    </div>
  );
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminDashboard | null>(null);

  useEffect(() => {
    adminGetDashboard()
      .then(setStats)
      .catch(() => undefined);
  }, []);

  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Dashboard</h1>
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Open cases" value={stats?.open_cases_count ?? 0} />
        <Stat label="Pending verdict" value={stats?.pending_verdict_count ?? 0} />
        <Stat label="Recent verdicts" value={stats?.recent_verdicts.length ?? 0} />
        <Stat label="Shadow appeals" value={stats?.shadow_appeals_pending ?? 0} />
      </div>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/50">
        Recent cases
      </h2>
      <CaseList limit={10} />
    </AdminShell>
  );
}
