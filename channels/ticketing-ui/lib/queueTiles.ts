// Queue deadline + tile-bucketing math — pure functions, extracted from app/queue/page.tsx
// (HR-06) so the SLA-critical arithmetic is unit-testable independent of React rendering.
// No behavior change: same logic, same call sites.

import type { TicketListItem } from "@/lib/api";

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Returns the effective deadline for a ticket:
 * - Action owner (assigned to me): ticket SLA deadline
 * - Task holder only: earliest pending task due date
 * - Both apply: earlier of the two
 */
export function effectiveDeadline(t: TicketListItem): Date | null {
  const sla  = t.sla_deadline_at        ? new Date(t.sla_deadline_at)        : null;
  const task = t.my_earliest_task_due_at ? new Date(t.my_earliest_task_due_at) : null;
  if (sla && task) return sla < task ? sla : task;
  return sla ?? task;
}

export type TicketCategory = "overdue" | "due_today" | "high_priority" | "other";

export function ticketCategory(t: TicketListItem, now: number, in24h: number): TicketCategory {
  const d = effectiveDeadline(t);
  if (d && d.getTime() < now)   return "overdue";
  if (d && d.getTime() <= in24h) return "due_today";
  if (t.priority === "HIGH" || t.priority === "CRITICAL") return "high_priority";
  return "other";
}

export const CATEGORY_ORDER: Record<TicketCategory, number> = {
  overdue:       0,
  due_today:     1,
  high_priority: 2,
  other:         3,
};

export function sortTickets(tickets: TicketListItem[]): TicketListItem[] {
  const now   = Date.now();
  const in24h = now + DAY_MS;
  return [...tickets].sort((a, b) => {
    const ca = CATEGORY_ORDER[ticketCategory(a, now, in24h)];
    const cb = CATEGORY_ORDER[ticketCategory(b, now, in24h)];
    if (ca !== cb) return ca - cb;
    // Within same category: closest deadline first
    const da = effectiveDeadline(a)?.getTime() ?? Infinity;
    const db = effectiveDeadline(b)?.getTime() ?? Infinity;
    return da - db;
  });
}

export interface TileCounts {
  actionNeeded: number;
  dueToday: number;
  overdue: number;
}

/**
 * "Actor" tile counts: Action Needed = all active (non-resolved/closed) tickets on my
 * plate; Due Today / Overdue are subsets bucketed by effectiveDeadline relative to `now`.
 * actionNeeded is always >= dueToday + overdue (each ticket contributes to at most one
 * of the two deadline buckets).
 */
export function computeTileCounts(tickets: TicketListItem[], now: number = Date.now()): TileCounts {
  const in24h = now + DAY_MS;
  let actionNeeded = 0, dueToday = 0, overdue = 0;
  for (const t of tickets) {
    // Action Needed = all active actor tickets (not resolved / closed)
    if (!["RESOLVED", "CLOSED"].includes(t.status_code)) {
      actionNeeded++;
      const d = effectiveDeadline(t);
      if (d) {
        if (d.getTime() < now)         overdue++;
        else if (d.getTime() <= in24h) dueToday++;
      }
    }
  }
  return { actionNeeded, dueToday, overdue };
}
