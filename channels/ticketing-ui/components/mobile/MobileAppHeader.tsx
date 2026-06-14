"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/app/providers/AuthProvider";
import { getBadge } from "@/lib/api";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { IconLock } from "@/lib/icons";
import { SlidersHorizontal } from "lucide-react";

function BypassRoleSwitcherMobile() {
  const { user, bypassRoster, switchBypassUser } = useAuth();
  const currentId = user?.sub ?? "";
  const current = bypassRoster?.find((o) => o.user_id === currentId);

  if (!bypassRoster?.length) {
    return (
      <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1 truncate max-w-[7rem]">
        demo
      </span>
    );
  }

  return (
    <select
      value={currentId}
      onChange={(e) => {
        const next = bypassRoster.find((o) => o.user_id === e.target.value);
        if (next) switchBypassUser(next);
      }}
      className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1 max-w-[8rem] truncate"
      aria-label="Switch demo officer"
    >
      {bypassRoster.map((o) => (
        <option key={o.user_id} value={o.user_id}>
          {o.display_name}
        </option>
      ))}
    </select>
  );
}

export function MobileAppHeader({
  title,
  onRefresh,
  refreshing = false,
  showFilterButton = false,
  filtersActive = false,
  onOpenFilters,
  trailing,
}: {
  title: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  showFilterButton?: boolean;
  filtersActive?: boolean;
  onOpenFilters?: () => void;
  trailing?: React.ReactNode;
}) {
  const pathname = usePathname();
  const { isAuthenticated, canSeeSeah } = useAuth();
  const [unseenCount, setUnseenCount] = useState(0);
  const bypass = process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";

  useEffect(() => {
    if (!isAuthenticated) return;
    getBadge().then((b) => setUnseenCount(b.unseen_count)).catch(() => {});
  }, [pathname, isAuthenticated]);

  return (
    <div className="flex-shrink-0 bg-white border-b border-gray-200 px-3 pt-safe-top">
      <div className="flex items-center gap-1 py-2 min-h-[3rem]">
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-semibold text-gray-900 truncate leading-tight">{title}</h1>
          {canSeeSeah && (
            <span className="inline-flex items-center gap-0.5 text-[10px] text-red-600 font-medium">
              <IconLock size={10} strokeWidth={2.5} />
              SEAH
            </span>
          )}
        </div>

        {trailing}

        {showFilterButton && onOpenFilters && (
          <button
            type="button"
            onClick={onOpenFilters}
            className={`relative p-2 rounded-lg touch-manipulation ${
              filtersActive ? "text-blue-600 bg-blue-50" : "text-gray-500 hover:bg-gray-100"
            }`}
            aria-label="Filter tickets"
          >
            <SlidersHorizontal size={20} strokeWidth={2} />
            {filtersActive && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-600 rounded-full" />
            )}
          </button>
        )}

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="text-sm text-blue-600 font-medium px-2 py-2 touch-manipulation disabled:opacity-50"
          >
            {refreshing ? "↻" : "Refresh"}
          </button>
        )}

        <NotificationBell
          unseenCount={unseenCount}
          mobile
          onCountRefresh={() => {
            getBadge().then((b) => setUnseenCount(b.unseen_count)).catch(() => {});
          }}
        />

        {bypass ? <BypassRoleSwitcherMobile /> : <UserMenu variant="mobile" />}
      </div>
    </div>
  );
}
