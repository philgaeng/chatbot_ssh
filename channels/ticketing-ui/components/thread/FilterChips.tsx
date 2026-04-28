"use client";

import { useMemo } from "react";
import { SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, getRoleBubbleStyle } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";

export type FilterChip = "all" | "mine" | "tasks" | "system" | string;

export function FilterChips({
  events,
  currentUserId,
  active,
  pendingTaskCount,
  onChange,
}: {
  events: TicketEvent[];
  currentUserId: string;
  active: FilterChip;
  pendingTaskCount: number;
  onChange: (chip: FilterChip) => void;
}) {
  const authors = useMemo(() => {
    const seen = new Set<string>();
    const result: { userId: string; role: string | null }[] = [];
    for (const e of events) {
      if (SYSTEM_EVENT_TYPES.has(e.event_type)) continue;
      if (TASK_EVENT_TYPES.has(e.event_type)) continue;
      const uid = e.created_by_user_id;
      if (!uid || uid === currentUserId || seen.has(uid)) continue;
      seen.add(uid);
      result.push({ userId: uid, role: e.actor_role });
    }
    return result;
  }, [events, currentUserId]);

  const chip = (id: FilterChip, label: string, badge?: number) => (
    <button
      key={id}
      onClick={() => onChange(active === id ? "all" : id)}
      className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
        active === id
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-600 border-gray-300"
      }`}
    >
      {label}
      {badge !== undefined && badge > 0 && (
        <span className={`ml-1 ${active === id ? "text-blue-200" : "text-amber-500"}`}>
          {badge}
        </span>
      )}
    </button>
  );

  return (
    <div className="flex gap-2 overflow-x-auto px-4 py-2 scrollbar-none">
      {chip("all", "All")}
      {chip("mine", "👤 You")}
      {authors.map(({ userId, role }) => {
        const style = getRoleBubbleStyle(role);
        return chip(userId, `${style.emoji || "@"}${style.label || userId.split("-")[0]}`);
      })}
      {chip("tasks", "📋 Tasks", pendingTaskCount)}
      {chip("system", "⚙️ System")}
    </div>
  );
}
