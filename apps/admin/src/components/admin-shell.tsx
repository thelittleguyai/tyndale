'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  AlertTriangle,
  Database,
  FolderSearch,
  LayoutDashboard,
  ScrollText,
  ShieldCheck,
  Users,
} from 'lucide-react';

import { useRequireAdmin } from '@/lib/use-admin';

const RUNTIME = process.env.NEXT_PUBLIC_RUNTIME_URL || 'http://localhost:4000';

function NotFound() {
  // Anti-enumeration (DL-60): a non-admin sees a plain 404, never the console.
  return (
    <div className="flex min-h-screen items-center justify-center bg-navy-deep">
      <div className="text-center">
        <p className="text-3xl font-bold text-white/80">404</p>
        <p className="mt-2 text-sm text-white/40">This page could not be found.</p>
      </div>
    </div>
  );
}

const NAV = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/users', label: 'Users', icon: Users },
  { href: '/cases', label: 'Cases', icon: FolderSearch },
  { href: '/knowledge', label: 'Knowledge', icon: Database },
  { href: '/audit', label: 'Audit log', icon: ScrollText },
  { href: '/system', label: 'System', icon: Activity },
  { href: '/gaps', label: 'Knowledge gaps', icon: AlertTriangle },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { checking, allowed } = useRequireAdmin();
  const pathname = usePathname();

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-navy-deep">
        <p className="text-sm text-white/40">Checking access…</p>
      </div>
    );
  }
  if (!allowed) return <NotFound />;

  const signOut = async () => {
    try {
      await fetch(`${RUNTIME}/v1/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch {
      /* ignore */
    }
    window.location.href = 'https://dev.tyndaleapp.net/signin';
  };

  return (
    <div className="flex min-h-screen bg-navy-deep text-white">
      <aside className="flex w-60 flex-col border-r border-white/10 bg-navy-soft p-4">
        <div className="mb-6 flex items-center gap-2">
          <ShieldCheck size={20} className="text-sage" />
          <span className="text-sm font-bold tracking-wide">Tyndale Admin</span>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                  active ? 'bg-teal-deep text-white' : 'text-white/60 hover:bg-white/5'
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={signOut}
          className="mt-auto rounded-lg border border-white/15 px-3 py-2 text-left text-xs text-white/60 hover:bg-white/5"
        >
          Sign out
        </button>
      </aside>
      <main className="flex-1 overflow-x-hidden p-6">{children}</main>
    </div>
  );
}
