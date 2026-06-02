'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import type { AdminUserDetail } from '@tyndale/shared';

import {
  adminBlockUser,
  adminForceLogout,
  adminGetUser,
  adminGetUserAudit,
  adminResetOnboarding,
  adminSendMagicLink,
  adminSetRole,
  adminSoftDeleteUser,
  adminUnblockUser,
  type AdminUserAuditEntry,
} from '@/lib/api-client';

type ActionKey = 'block' | 'unblock' | 'reset' | 'logout' | 'magic' | 'delete' | 'role' | null;

const fmt = (s: string | null) => (s ? new Date(s).toLocaleString() : '—');

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-navy-soft p-4">
      <h3 className="mb-2 text-sm font-semibold text-white/85">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="shrink-0 text-white/40">{label}</span>
      <span className="truncate text-white/80">{value}</span>
    </div>
  );
}

export function UserDetail({ userId }: { userId: string }) {
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [audit, setAudit] = useState<AdminUserAuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [action, setAction] = useState<ActionKey>(null);
  const [reason, setReason] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    adminGetUser(userId)
      .then(setUser)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    adminGetUserAudit(userId)
      .then((r) => setAudit(r.entries))
      .catch(() => {});
  }, [userId]);

  useEffect(() => load(), [load]);

  const run = async () => {
    if (!user) return;
    setBusy(true);
    setError(null);
    try {
      if (action === 'block') await adminBlockUser(userId, reason || 'blocked by admin');
      else if (action === 'unblock') await adminUnblockUser(userId);
      else if (action === 'reset') await adminResetOnboarding(userId);
      else if (action === 'logout') await adminForceLogout(userId);
      else if (action === 'magic') await adminSendMagicLink(userId);
      else if (action === 'delete') await adminSoftDeleteUser(userId);
      else if (action === 'role')
        await adminSetRole(userId, user.user_type === 'admin' ? 'user' : 'admin');
      setAction(null);
      setReason('');
      setConfirmText('');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (error && !user) return <p className="text-sm text-rose">{error}</p>;
  if (!user) return <p className="text-sm text-white/40">Loading…</p>;

  const pill =
    user.status === 'active'
      ? 'bg-sage/20 text-sage'
      : user.status === 'blocked'
        ? 'bg-amber/20 text-amber'
        : 'bg-rose/20 text-rose';
  const deleteReady = action === 'delete' && confirmText === `DELETE ${user.email}`;

  const open = (k: ActionKey) => {
    setAction(k);
    setReason('');
    setConfirmText('');
    setError(null);
  };

  const Btn = ({ k, label, danger, primary }: { k: ActionKey; label: string; danger?: boolean; primary?: boolean }) => (
    <button
      onClick={() => open(k)}
      className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
        danger
          ? 'border border-rose/40 text-rose hover:bg-rose/10'
          : primary
            ? 'bg-teal-deep text-white'
            : 'border border-white/15 text-white/70 hover:bg-white/5'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <Link href="/users" className="text-sm text-white/40 hover:text-white/70">
          ← Users
        </Link>
        <h1 className="text-xl font-bold">{user.email}</h1>
        <span className={`rounded-md px-2 py-0.5 text-xs ${pill}`}>{user.status}</span>
        <span className="rounded-md bg-white/10 px-2 py-0.5 text-xs text-white/60">
          {user.user_type}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Section title="Account">
            <Row label="User ID" value={user.user_id} />
            <Row label="Created" value={fmt(user.created_at)} />
            <Row label="Last activity" value={fmt(user.last_activity_at)} />
            <Row label="JWT version" value={String(user.jwt_version)} />
            <Row label="Service consent" value={String(user.service_consent)} />
            {user.blocked_reason ? <Row label="Blocked reason" value={user.blocked_reason} /> : null}
          </Section>

          <Section title={`Case files (${user.case_file_count})`}>
            {user.recent_case_files.length ? (
              user.recent_case_files.map((c) => (
                <div
                  key={c.case_file_id}
                  className="flex justify-between border-b border-white/5 py-1 text-sm last:border-0"
                >
                  <Link href={`/cases/${c.case_file_id}`} className="text-sage hover:underline">
                    {c.case_file_id.slice(0, 8)}…
                  </Link>
                  <span className="text-white/50">{c.status}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-white/30">None</p>
            )}
          </Section>

          <Section title="Admin action history">
            {audit.length ? (
              audit.slice(0, 20).map((a) => (
                <div
                  key={a.event_id}
                  className="flex justify-between border-b border-white/5 py-1 text-xs last:border-0"
                >
                  <span className="text-white/70">{a.action ?? a.event_type}</span>
                  <span className="text-white/40">{fmt(a.timestamp)}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-white/30">No actions yet</p>
            )}
          </Section>
        </div>

        <div className="space-y-2">
          <h3 className="text-xs uppercase tracking-wide text-white/40">Actions</h3>
          {user.status !== 'soft_deleted' ? (
            <>
              {user.is_blocked ? (
                <Btn k="unblock" label="Unblock" primary />
              ) : (
                <Btn k="block" label="Block" />
              )}
              <Btn k="role" label={user.user_type === 'admin' ? 'Revoke admin' : 'Grant admin'} />
              <Btn k="reset" label="Reset onboarding" />
              <Btn k="logout" label="Force logout" />
              <Btn k="magic" label="Send magic link" />
              <Btn k="delete" label="Soft-delete" danger />
            </>
          ) : (
            <p className="text-sm text-white/30">User is soft-deleted.</p>
          )}
        </div>
      </div>

      {action ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setAction(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-white/10 bg-navy-soft p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-3 text-sm font-bold capitalize">{action} {user.email}</h3>
            {action === 'block' ? (
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason (required)"
                rows={3}
                className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
              />
            ) : action === 'delete' ? (
              <>
                <p className="mb-2 text-xs text-white/60">
                  Anonymizes the email + revokes sessions (case files + audit trail are kept). Type{' '}
                  <span className="text-rose">DELETE {user.email}</span> to confirm.
                </p>
                <input
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  className="mb-3 w-full rounded-lg border border-white/15 bg-black/20 px-2 py-2 text-sm text-white"
                />
              </>
            ) : (
              <p className="mb-3 text-sm text-white/60">Confirm this action?</p>
            )}
            {error ? <p className="mb-2 text-xs text-rose">{error}</p> : null}
            <div className="flex gap-2">
              <button
                onClick={() => setAction(null)}
                className="flex-1 rounded-lg border border-white/15 px-3 py-2 text-sm text-white/70"
              >
                Cancel
              </button>
              <button
                disabled={
                  busy ||
                  (action === 'block' && !reason.trim()) ||
                  (action === 'delete' && !deleteReady)
                }
                onClick={run}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-bold disabled:opacity-40 ${
                  action === 'delete' ? 'bg-rose text-white' : 'bg-sage text-ink'
                }`}
              >
                {busy ? '…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
