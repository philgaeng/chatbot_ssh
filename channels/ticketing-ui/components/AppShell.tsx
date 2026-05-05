"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth, MOCK_OFFICERS, setMockUserCookie, type MockOfficer } from "@/app/providers/AuthProvider";
import { getBadge } from "@/lib/api";
import {
  IconQueue, IconAllTickets, IconEscalated, IconReports, IconSettings, IconHelp,
  IconMobileQueue, IconMobileSearch, IconMobileTasks,
  IconBell, IconSignOut, IconLock,
} from "@/lib/icons";

// ── Desktop sidebar nav ───────────────────────────────────────────────────────

const NAV = [
  { href: "/queue",     label: "My Queue",    Icon: IconQueue,      badge: "action"    },
  { href: "/tickets",   label: "All Tickets", Icon: IconAllTickets, badge: null        },
  { href: "/escalated", label: "Escalated",   Icon: IconEscalated,  badge: "escalated" },
  null, // divider
  { href: "/reports",   label: "Reports",     Icon: IconReports,    badge: null        },
  null,
  { href: "/settings",  label: "Settings",    Icon: IconSettings,   badge: null, adminOnly: true },
  { href: "/help",      label: "Help",        Icon: IconHelp,       badge: null        },
] as const;

// Routes that don't require authentication
const PUBLIC_ROUTES = ["/login", "/auth/callback"];

// ── Mobile bottom tab nav ─────────────────────────────────────────────────────

const MOBILE_TABS = [
  { href: "/m/queue",   label: "Queue", Icon: IconMobileQueue  },
  { href: "/m/tickets", label: "All",   Icon: IconMobileSearch },
  { href: "/m/tasks",   label: "Tasks", Icon: IconMobileTasks  },
] as const;

// ── Demo role switcher (bypass-auth mode only) ────────────────────────────────

function MockRoleSwitcher() {
  const { user, switchMockUser } = useAuth();
  const [open, setOpen] = useState(false);

  const currentId = user?.sub ?? "";
  const current = MOCK_OFFICERS.find(o => o.user_id === currentId) ?? MOCK_OFFICERS[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 border border-dashed border-amber-400 rounded-lg px-2.5 py-1 bg-amber-50 hover:bg-amber-100 transition"
        title="Demo: click to switch officer role"
      >
        <span className="text-amber-600 text-[10px] font-bold uppercase tracking-wide">demo</span>
        <span className="font-medium">{current.name}</span>
        <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-xl shadow-lg z-50 py-1 overflow-hidden"
          onBlur={() => setOpen(false)}
        >
          <div className="px-3 py-1.5 text-[10px] text-amber-600 font-semibold uppercase tracking-wide border-b border-gray-100">
            Switch demo officer
          </div>
          {MOCK_OFFICERS.map(o => (
            <button
              key={o.user_id}
              onClick={() => { setOpen(false); switchMockUser(o); }}
              className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition ${
                o.user_id === currentId
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                o.user_id === currentId ? "bg-blue-200 text-blue-700" : "bg-gray-100 text-gray-500"
              }`}>
                {o.name.charAt(0)}
              </div>
              <div>
                <div>{o.name}</div>
                <div className="text-[10px] text-gray-400">{o.role_keys[0]}</div>
              </div>
              {o.user_id === currentId && (
                <span className="ml-auto text-blue-500 text-xs">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Desktop shell ─────────────────────────────────────────────────────────────

function DesktopShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, signOut, canSeeSeah, isAdmin } = useAuth();
  const [unseenCount, setUnseenCount] = useState(0);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated && !PUBLIC_ROUTES.includes(pathname)) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    getBadge().then((b) => setUnseenCount(b.unseen_count)).catch(() => {});
  }, [pathname, isAuthenticated]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <div className="text-sm text-gray-400">Loading…</div>
      </div>
    );
  }

  if (!isAuthenticated) return <>{children}</>;

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      <aside className="hidden md:flex flex-col w-56 bg-slate-800 text-slate-100 shrink-0">
        <div className="px-5 pt-6 pb-4 border-b border-slate-700">
          <div className="text-lg font-bold tracking-tight">GRM Ticketing</div>
          <div className="text-xs text-slate-400 mt-0.5 truncate">{user?.email ?? "Officer"}</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV.map((item, i) => {
            if (item === null) return <div key={i} className="my-2 border-t border-slate-700" />;
            if ("adminOnly" in item && item.adminOnly && !isAdmin) return null;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const badgeCount = item.badge === "action" ? unseenCount : 0;
            const { Icon } = item;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  active ? "bg-slate-600 text-white font-medium" : "text-slate-300 hover:bg-slate-700 hover:text-white"
                }`}
              >
                <Icon size={16} strokeWidth={1.75} className="shrink-0" />
                <span className="flex-1">{item.label}</span>
                {badgeCount > 0 && (
                  <span className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full min-w-[1.25rem] text-center">
                    {badgeCount > 99 ? "99+" : badgeCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="p-3 border-t border-slate-700">
          <button
            onClick={signOut}
            className="w-full flex items-center gap-2 text-sm text-slate-400 hover:text-red-400 transition-colors px-3 py-2 rounded"
          >
            <IconSignOut size={14} strokeWidth={1.75} />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex flex-col flex-1 min-w-0">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
          <div className="text-sm text-gray-500">
            {canSeeSeah && (
              <span className="mr-3 inline-flex items-center gap-1 text-red-600 font-medium text-xs">
                <IconLock size={12} strokeWidth={2.5} />
                SEAH access
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button className="relative text-gray-400 hover:text-gray-600 p-1">
              <IconBell size={18} strokeWidth={1.75} />
              {unseenCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                  {unseenCount > 9 ? "9+" : unseenCount}
                </span>
              )}
            </button>
            {process.env.NEXT_PUBLIC_BYPASS_AUTH === "true" ? (
              <MockRoleSwitcher />
            ) : (
              <span className="text-sm text-gray-600">{user?.name ?? user?.email}</span>
            )}
          </div>
        </header>
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

// ── Mobile shell ──────────────────────────────────────────────────────────────

function MobileShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();
  const [unseenCount, setUnseenCount] = useState(0);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated && !PUBLIC_ROUTES.includes(pathname)) {
      router.replace("/login");
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    getBadge().then((b) => setUnseenCount(b.unseen_count)).catch(() => {});
  }, [pathname, isAuthenticated]);

  if (isLoading) {
    return (
      <div className="min-h-dvh flex items-center justify-center bg-white">
        <div className="text-sm text-gray-400">Loading…</div>
      </div>
    );
  }

  if (!isAuthenticated) return <>{children}</>;

  // Thread screens (/m/tickets/[id]) get full-screen with no bottom bar
  // (the page manages its own header + sticky input bar)
  const isThreadScreen = /^\/m\/tickets\/[^/]+/.test(pathname);

  return (
    <div className="flex flex-col h-dvh bg-white overflow-hidden">
      {/* Scrollable content area */}
      <div className={`flex-1 overflow-hidden ${isThreadScreen ? "" : "overflow-y-auto"}`}>
        {children}
      </div>

      {/* Bottom tab bar — hidden on thread screen (thread has its own footer) */}
      {!isThreadScreen && (
        <nav className="flex-shrink-0 border-t border-gray-200 bg-white safe-area-bottom">
          <div className="flex">
            {MOBILE_TABS.map((tab) => {
              const active = pathname === tab.href || pathname.startsWith(tab.href + "/");
              const isQueue = tab.href === "/m/queue";
              const { Icon } = tab;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex-1 flex flex-col items-center justify-center py-2 text-xs transition-colors relative ${
                    active ? "text-blue-600" : "text-gray-400"
                  }`}
                >
                  <Icon size={22} strokeWidth={1.75} className="mb-0.5" />
                  <span className="font-medium">{tab.label}</span>
                  {isQueue && unseenCount > 0 && (
                    <span className="absolute top-1.5 right-[calc(50%-12px)] bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
                      {unseenCount > 99 ? "99+" : unseenCount}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}

// ── Root shell — routes to mobile or desktop ──────────────────────────────────

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // All /m/* routes use the mobile shell
  if (pathname.startsWith("/m")) {
    return <MobileShell>{children}</MobileShell>;
  }

  return <DesktopShell>{children}</DesktopShell>;
}
