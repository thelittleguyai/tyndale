'use client';

import { AdminShell } from '@/components/admin-shell';
import { UserList } from '@/components/user-list';

export default function UsersPage() {
  return (
    <AdminShell>
      <h1 className="mb-5 text-2xl font-bold">Users</h1>
      <UserList />
    </AdminShell>
  );
}
