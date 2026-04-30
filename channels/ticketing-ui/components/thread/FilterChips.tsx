"use client";

import { useMemo } from "react";
import { User, UserCheck, UserCog, Eye, ClipboardList } from "lucide-react";
import { SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, AUTHORITY_ROLES } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";

export type FilterChip = "all" | "mine" | "owner" | "supervisor" | "observers" | "tasks" | "system";

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

  const chip = (id: FilterChip, label: string, Icon?: React.ComponentType<{ size?: number; strokeWidth?: number }>, badge?: number) => (
    <button
      key={id}
      onClick={() => onChange(active === id ? "all" : id)}
      className={`flex-shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
        active === id
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-600 border-gray-300"
      }`}
    >
      {Icon && <Icon size={11} strokeWidth={2} />}
      {label}
      {badge !== undefined && badge > 0 && (
        <span className={`ml-0.5 font-bold ${active === id ? "text-blue-200" : "text-amber-500"}`}>
          {badge}
        </span>
      )}
    </button>
  );

  return (
    <div className="flex gap-2 overflow-x-auto px-4 py-2 scrollbar-none">
      {chip("all",  "All")}
      {chip("mine", "You", User)}
      {hasOwner      && chip("owner",      "Case owner",  UserCheck)}
      {hasSupervisor && chip("supervisor", "Supervisor",  UserCog)}
      {hasObservers  && chip("observers",  "Observers",   Eye)}
      {hasTasks      && chip("tasks",      "Tasks",       ClipboardList, pendingTaskCount)}
    </div>
  );
}
