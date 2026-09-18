'use client';

import { AdminShell } from '@/components/admin-shell';
import { ReviewQueue } from '@/components/review-queue';

export default function ReviewQueuePage() {
  return (
    <AdminShell>
      <ReviewQueue />
    </AdminShell>
  );
}
