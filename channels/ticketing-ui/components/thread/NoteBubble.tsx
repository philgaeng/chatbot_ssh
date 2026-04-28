"use client";

import { getRoleBubbleStyle } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";
import { NoteText } from "./NoteText";

function RoleLabel({ actorRole, userId, isMine }: {
  actorRole: string | null;
  userId: string | null;
  isMine: boolean;
}) {
  const style = getRoleBubbleStyle(actorRole);
  return (
    <div className={`text-[11px] mt-1 ${isMine ? "text-right text-blue-300" : style.labelCls}`}>
      {isMine ? "You" : `${style.emoji ? style.emoji + " " : ""}${style.label || userId || "Officer"}`}
    </div>
  );
}

export function NoteBubble({ event, isMine }: { event: TicketEvent; isMine: boolean }) {
  const style = getRoleBubbleStyle(event.actor_role);
  const time = new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (isMine) {
    return (
      <div className="flex flex-col items-end px-4 my-1">
        <div className="max-w-[80%] bg-blue-500 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
          <NoteText text={event.note ?? ""} />
        </div>
        <div className="text-[11px] text-gray-400 mt-0.5">You · {time}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start px-4 my-1">
      <div className={`max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-800 ${style.bubbleCls || "bg-gray-100"}`}>
        <NoteText text={event.note ?? ""} />
      </div>
      <RoleLabel actorRole={event.actor_role} userId={event.created_by_user_id} isMine={false} />
      <div className="text-[11px] text-gray-400">{time}</div>
    </div>
  );
}
