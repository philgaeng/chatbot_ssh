// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect } from "vitest";
import { computeTileCounts } from "./queueTiles";
import type { TicketListItem } from "./api";

function makeTicket(overrides: Partial<TicketListItem> = {}): TicketListItem {
  return {
    ticket_id: "t1",
    grievance_id: "g1",
    grievance_summary: null,
    status_code: "OPEN",
    priority: "NORMAL",
    is_seah: false,
    intake_route: null,
    organization_id: "org1",
    location_code: null,
    project_code: null,
    assigned_to_user_id: null,
    sla_breached: false,
    step_started_at: null,
    created_at: "2026-07-01T00:00:00Z",
    sla_deadline_at: null,
    my_earliest_task_due_at: null,
    unseen_event_count: 0,
    ...overrides,
  };
}

describe("computeTileCounts", () => {
  const now = new Date("2026-07-05T12:00:00Z").getTime();
  const iso = (offsetMs: number) => new Date(now + offsetMs).toISOString();
  const HOUR = 60 * 60 * 1000;

  it("buckets tickets by deadline boundary (now / +23h / +25h / past); actionNeeded >= dueToday + overdue", () => {
    const tickets: TicketListItem[] = [
      makeTicket({ ticket_id: "past", sla_deadline_at: iso(-1 * HOUR) }), // 1h ago -> overdue
      makeTicket({ ticket_id: "exactly_now", sla_deadline_at: iso(0) }), // deadline == now -> due today, not overdue
      makeTicket({ ticket_id: "plus23h", sla_deadline_at: iso(23 * HOUR) }), // within 24h window -> due today
      makeTicket({ ticket_id: "plus25h", sla_deadline_at: iso(25 * HOUR) }), // outside 24h window -> neither bucket
      makeTicket({
        ticket_id: "resolved_past_due",
        status_code: "RESOLVED",
        sla_deadline_at: iso(-1 * HOUR),
      }), // resolved -> excluded from actionNeeded entirely
    ];

    const counts = computeTileCounts(tickets, now);

    expect(counts.overdue).toBe(1);
    expect(counts.dueToday).toBe(2);
    expect(counts.actionNeeded).toBe(4);
    expect(counts.actionNeeded).toBeGreaterThanOrEqual(counts.dueToday + counts.overdue);
  });
});
