"use client";

import { getRoleBubbleStyle } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";
import { NoteText } from "./NoteText";

// ── 4 contextual bubble styles ────────────────────────────────────────────────
// Color = relationship to this case (not role title)
// Label = role identity (still shown for traceability)
//
// 1. Assigned officer — the case owner          → strong blue
// 2. Higher authority — supervisors, ADB, GRC   → amber
// 3. Viewer / observer                           → subtle gray
// 4. Other officer (default)                    → neutral gray

const AUTHORITY_ROLES = new Set([
  "pd_piu_safeguards_focal",
  "grc_chair", "grc_member",
  "adb_national_project_director", "adb_hq_safeguards", "adb_hq_project", "adb_hq_exec",
  "seah_hq_officer",
  "super_admin", "local_admin",
]);

interface BubbleStyle {
  bubbleCls: string;
  labelCls:  string;
}

function contextStyle(
  userId:           string | null,
  actorRole:        string | null,
  assignedToUserId: string | null,
  viewerIds:        Set<string>,
): BubbleStyle {
  if (userId && userId === assignedToUserId)
    return { bubbleCls: "bg-blue-50  border-l-4 border-blue-600",  labelCls: "text-blue-700 font-semibold"  };

  if (actorRole && AUTHORITY_ROLES.has(actorRole))
    return { bubbleCls: "bg-amber-50 border-l-4 border-amber-500", labelCls: "text-amber-800 font-semibold" };

  if (userId && viewerIds.has(userId))
    return { bubbleCls: "bg-gray-50  border-l-4 border-gray-300",  labelCls: "text-gray-500"                };

  return   { bubbleCls: "bg-gray-100 border-l-4 border-gray-400",  labelCls: "text-gray-600"                };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function NoteBubble({
  event,
  isMine,
  assignedToUserId = null,
  viewerIds = new Set(),
}: {
  event:            TicketEvent;
  isMine:           boolean;
  assignedToUserId?: string | null;
  viewerIds?:        Set<string>;
}) {
  const time = new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (isMine) {
    return (
      <div className="flex flex-col items-end px-4 my-1">
        <div className="max-w-[80%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
          <NoteText text={event.note ?? ""} />
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5 text-right">You · {time}</div>
      </div>
    );
  }

  const { bubbleCls, labelCls } = contextStyle(
    event.created_by_user_id,
    event.actor_role,
    assignedToUserId,
    viewerIds,
  );
  const roleStyle = getRoleBubbleStyle(event.actor_role);
  const roleLabel = roleStyle.label || event.created_by_user_id || "Officer";

  return (
    <div className="flex flex-col items-start px-4 my-1">
      <div className={`max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-800 ${bubbleCls}`}>
        <NoteText text={event.note ?? ""} />
      </div>
      <div className={`text-xs font-medium mt-1 ${labelCls}`}>{roleLabel} · {time}</div>
    </div>
  );
}
