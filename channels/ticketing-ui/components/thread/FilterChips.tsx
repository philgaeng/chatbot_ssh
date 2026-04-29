"use client";

import { useMemo } from "react";
import { SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, AUTHORITY_ROLES } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";

export type FilterChip = "all" | "mine" | "owner" | "supervisor" | "observers" | "tasks";

export function FilterChips({
  events,
  currentUserId,
  assignedToUserId,
  viewerIds,
  active,
  pendingTaskCount,
  onChange,
}: {
  events: TicketEvent[];
  currentUserId: string;
  assignedToUserId: string | null;
  viewerIds: Set<string>;
  active: FilterChip;
  pendingTaskCount: number;
  onChange: (chip: FilterChip) => void;
}) {
  const noteEvents = useMemo(
    () => events.filter((e) => !SYSTEM_EVENT_TYPES.has(e.event_type) && !TASK_EVENT_TYPES.has(e.event_type)),
    [events],
  );

  const hasOwner = useMemo(
    () => !!assignedToUserId && assignedToUserId !== currentUserId &&
      noteEvents.some((e) => e.created_by_user_id === assignedToUserId),
    [noteEvents, assignedToUserId, currentUserId],
  );

  const hasSupervisor = useMemo(
    () => noteEvents.some(
      (e) => e.actor_role && AUTHORITY_ROLES.has(e.actor_role) &&
        e.created_by_user_id !== currentUserId &&
        e.created_by_user_id !== assignedToUserId,
    ),
    [noteEvents, currentUserId, assignedToUserId],
  );

  const hasObservers = useMemo(
    () => noteEvents.some(
      (e) => e.created_by_user_id && viewerIds.has(e.created_by_user_id) &&
        e.created_by_user_id !== currentUserId,
    ),
    [noteEvents, viewerIds, currentUserId],
  );

  const hasTasks = pendingTaskCount > 0 || events.some((e) => TASK_EVENT_TYPES.has(e.event_type));

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
      {hasOwner      && chip("owner",      "🔵 Case owner")}
      {hasSupervisor && chip("supervisor", "🟠 Supervisor")}
      {hasObservers  && chip("observers",  "👁 Observers")}
      {hasTasks      && chip("tasks",      "📋 Tasks", pendingTaskCount)}
    </div>
  );
}
