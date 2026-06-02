'use client';

import { useParams } from 'next/navigation';

import { AdminShell } from '@/components/admin-shell';
import { UserDetail } from '@/components/user-detail';

export default function UserDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AdminShell>
      <UserDetail userId={String(params.id)} />
    </AdminShell>
  );
}
