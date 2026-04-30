"use client";

import { systemEventLabel } from "@/lib/mobile-constants";
import type { TicketEvent } from "@/lib/api";

export function SystemPill({ event }: { event: TicketEvent }) {
  return (
    <div className="flex justify-center my-2 px-4">
      <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1 text-center">
        {systemEventLabel(event.event_type, event.payload)}
      </span>
    </div>
  );
}
