"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/app/providers/AuthProvider";
import { getBadge } from "@/lib/api";

const NAV = [
  { href: "/queue",   label: "My Queue",   icon: "🎫", badge: "action"   },
  { href: "/tickets", label: "All Tickets", icon: "📋", badge: null       },
  { href: "/escalated", label: "Escalated", icon: "🔺", badge: "escalated" },
  null, // divider
  { href: "/reports", label: "Reports",    icon: "📊", badge: null       },
  null,
  { href: "/settings", label: "Settings",  icon: "⚙️",  badge: null, adminOnly: true },
  { href: "/help",    label: "Help",       icon: "❓", badge: null       },
] as const;

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isAuthenticated, signOut, canSeeSeah } = useAuth();
  const [unseenCount, setUnseenCount] = useState(0);

  // Poll badge count on each navigation
  useEffect(() => {
    if (!isAuthenticated) return;
    getBadge().then((b) => setUnseenCount(b.unseen_count)).catch(() => {});
  }, [pathname, isAuthenticated]);

  if (!isAuthenticated) return <>{children}</>;

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      {/* ── Sidebar ── */}
      <aside className="hidden md:flex flex-col w-56 bg-slate-800 text-slate-100 shrink-0">
        {/* Logo */}
        <div className="px-5 pt-6 pb-4 border-b border-slate-700">
          <div className="text-lg font-bold tracking-tight">GRM Ticketing</div>
          <div className="text-xs text-slate-400 mt-0.5 truncate">{user?.email ?? "Officer"}</div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV.map((item, i) => {
            if (item === null) return <div key={i} className="my-2 border-t border-slate-700" />;
            if ("adminOnly" in item && item.adminOnly) {
              // Only show settings if admin — for proto we always show it
            }
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const badgeCount =
              item.badge === "action" ? unseenCount :
              item.badge === "escalated" ? 0 : 0;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-slate-600 text-white font-medium"
                    : "text-slate-300 hover:bg-slate-700 hover:text-white"
                }`}
              >
                <span className="text-base leading-none">{item.icon}</span>
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

        {/* Sign out */}
        <div className="p-3 border-t border-slate-700">
          <button
            onClick={signOut}
            className="w-full text-left text-sm text-slate-400 hover:text-red-400 transition-colors px-3 py-2 rounded"
          >
            ↪ Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
          <div className="text-sm text-gray-500">
            {canSeeSeah && (
              <span className="mr-3 text-red-600 font-medium text-xs">🔒 SEAH access</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* Notification bell */}
            <button className="relative text-gray-400 hover:text-gray-600">
              🔔
              {unseenCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                  {unseenCount > 9 ? "9+" : unseenCount}
                </span>
              )}
            </button>
            <span className="text-sm text-gray-600">{user?.name ?? user?.email}</span>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
