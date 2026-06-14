"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getNotifications, type NotificationItem } from "@/lib/api";
import { IconBell } from "@/lib/icons";
import { defaultQueuePath, ticketDetailPath } from "@/lib/mobile-routes";

const EVENT_LABELS: Record<string, string> = {
  TICKET_CREATED: "New ticket filed",
  ACKNOWLEDGED: "Ticket acknowledged",
  ESCALATED: "Ticket escalated",
  RESOLVED: "Ticket resolved",
  CLOSED: "Ticket closed",
  NOTE: "Internal note added",
  REPLY_SENT: "Reply sent to complainant",
  COMPLAINANT_MSG: "Complainant sent a message",
  TASK_ASSIGNED: "Task assigned to you",
  TASK_COMPLETED: "Task completed",
  GRC_CONVENED: "GRC hearing convened",
  GRC_DECIDED: "GRC decision recorded",
};

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function NotificationPanel({
  items,
  total,
  onClose,
  mobile = false,
}: {
  items: NotificationItem[];
  total: number;
  onClose: () => void;
  mobile?: boolean;
}) {
  const router = useRouter();

  function go(ticketId: string) {
    onClose();
    router.push(ticketDetailPath(ticketId));
  }

  const panelCls = mobile
    ? "fixed left-3 right-3 top-14 z-50 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden max-h-[min(70vh,28rem)] flex flex-col"
    : "absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden";

  return (
    <div className={panelCls}>
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 bg-gray-50 shrink-0">
        <span className="text-sm font-semibold text-gray-800">Notifications</span>
        <div className="flex items-center gap-2">
          {total > 0 && <span className="text-xs text-gray-500">{total} unread</span>}
          {mobile && (
            <button type="button" onClick={onClose} className="text-xs text-gray-500 px-2 py-1">
              Close
            </button>
          )}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="px-4 py-6 text-center text-sm text-gray-400">No unread notifications</div>
      ) : (
        <ul className={`divide-y divide-gray-50 ${mobile ? "overflow-y-auto flex-1" : "max-h-80 overflow-y-auto"}`}>
          {items.map((n) => (
            <li key={n.event_id}>
              <button
                type="button"
                onClick={() => go(n.ticket_id)}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 active:bg-blue-100 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-blue-700 truncate">{n.grievance_id}</p>
                    <p className="text-sm text-gray-800 mt-0.5">
                      {EVENT_LABELS[n.event_type] ?? n.event_type}
                    </p>
                    {n.note ? (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.note}</p>
                    ) : n.grievance_summary ? (
                      <p className="text-xs text-gray-400 mt-0.5 truncate">{n.grievance_summary}</p>
                    ) : null}
                  </div>
                  <span className="text-[10px] text-gray-400 shrink-0 mt-0.5 whitespace-nowrap">
                    {timeAgo(n.created_at)}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}

      {total > items.length && (
        <div className="border-t border-gray-100 px-4 py-2 text-center shrink-0">
          <button
            type="button"
            onClick={() => {
              onClose();
              router.push(defaultQueuePath());
            }}
            className="text-xs text-blue-600 hover:underline"
          >
            + {total - items.length} more — go to queue
          </button>
        </div>
      )}
    </div>
  );
}

export function NotificationBell({
  unseenCount,
  onCountRefresh,
  mobile = false,
}: {
  unseenCount: number;
  onCountRefresh?: () => void;
  mobile?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notifTotal, setNotifTotal] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    getNotifications(20)
      .then((r) => {
        setNotifications(r.items);
        setNotifTotal(r.total);
      })
      .catch(() => {});
    setOpen(true);
    onCountRefresh?.();
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={toggle}
        className="relative text-gray-500 hover:text-gray-700 p-2 -mr-1 touch-manipulation"
        title="Notifications"
        aria-label="Notifications"
        aria-expanded={open}
      >
        <IconBell size={20} strokeWidth={1.75} />
        {unseenCount > 0 && (
          <span className="absolute top-0.5 right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-0.5">
            {unseenCount > 9 ? "9+" : unseenCount}
          </span>
        )}
      </button>
      {open && (
        <>
          {mobile && (
            <button
              type="button"
              className="fixed inset-0 z-40 bg-black/20"
              aria-label="Close notifications"
              onClick={() => setOpen(false)}
            />
          )}
          <NotificationPanel
            items={notifications}
            total={notifTotal}
            onClose={() => setOpen(false)}
            mobile={mobile}
          />
        </>
      )}
    </div>
  );
}
