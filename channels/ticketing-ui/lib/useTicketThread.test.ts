// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import { filterThreadEvents, type ThreadFilterContext } from "@/lib/useTicketThread";
import type { FilterChip } from "@/components/thread/FilterChips";
import type { TicketEvent } from "@/lib/api";

// H2-06 — `filterThreadEvents` is the one chip-filter switch both thread pages now
// call (desktop had a `"system"` case the mobile copy was missing; that silent
// divergence is the drift this ticket resolves). These lock the output per chip,
// including `system`, so the two pages can never diverge again.

function ev(partial: Partial<TicketEvent> & Pick<TicketEvent, "event_id">): TicketEvent {
  return {
    event_type: "NOTE_ADDED",
    old_status_code: null,
    new_status_code: null,
    old_assigned_to: null,
    new_assigned_to: null,
    workflow_step_id: null,
    note: null,
    payload: null,
    seen: false,
    created_at: "2026-07-14T00:00:00Z",
    created_by_user_id: null,
    actor_role: null,
    case_sensitivity: "standard",
    summary_regen_required: false,
    ...partial,
  };
}

const ME = "me@grm.local";
const OWNER = "owner@grm.local";
const SUP = "sup@grm.local";
const OBSERVER = "observer@grm.local";

// A representative mixed thread.
const events: TicketEvent[] = [
  ev({ event_id: "e1", event_type: "NOTE_ADDED", created_by_user_id: ME, actor_role: "site_safeguards_focal_person" }),
  ev({ event_id: "e2", event_type: "NOTE_ADDED", created_by_user_id: OWNER, actor_role: "site_safeguards_focal_person" }),
  ev({ event_id: "e3", event_type: "NOTE_ADDED", created_by_user_id: SUP, actor_role: "pd_piu_safeguards_focal" }),
  ev({ event_id: "e4", event_type: "CREATED", created_by_user_id: "system", actor_role: null }),
  ev({ event_id: "e5", event_type: "ESCALATED", created_by_user_id: OWNER, actor_role: null }),
  ev({ event_id: "e6", event_type: "TASK_ASSIGNED", created_by_user_id: OWNER, actor_role: "site_safeguards_focal_person" }),
  ev({ event_id: "e7", event_type: "COMPLAINANT_MESSAGE", created_by_user_id: "complainant", actor_role: null }),
  ev({ event_id: "e8", event_type: "NOTE_ADDED", created_by_user_id: OBSERVER, actor_role: "grc_member" }),
];

const ctx: ThreadFilterContext = {
  currentUserId: ME,
  assignedToUserId: OWNER,
  viewerIds: new Set([OBSERVER]),
};

const ids = (chip: FilterChip) => filterThreadEvents(events, chip, ctx).map((e) => e.event_id);

describe("filterThreadEvents", () => {
  it("all → every event, unfiltered", () => {
    expect(ids("all")).toEqual(["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8"]);
  });

  it("mine → only events created by the current user", () => {
    expect(ids("mine")).toEqual(["e1"]);
  });

  it("owner → only events created by the assignee", () => {
    expect(ids("owner")).toEqual(["e2", "e5", "e6"]);
  });

  it("supervisor → authority-role events not authored by the owner", () => {
    // e3 (pd_piu) and e8 (grc_member) are authority roles; owner's e2 is excluded.
    expect(ids("supervisor")).toEqual(["e3", "e8"]);
  });

  it("observers → events created by a viewer", () => {
    expect(ids("observers")).toEqual(["e8"]);
  });

  it("tasks → only thread task-card events", () => {
    expect(ids("tasks")).toEqual(["e6"]);
  });

  it("complainant → only inbound complainant messages", () => {
    expect(ids("complainant")).toEqual(["e7"]);
  });

  it("system → only system-pill events (the case mobile was silently missing)", () => {
    expect(ids("system")).toEqual(["e4", "e5"]);
  });

  it("returns a stable result — same input ⇒ same output for every chip", () => {
    const chips: FilterChip[] = ["all", "mine", "owner", "supervisor", "observers", "tasks", "complainant", "system"];
    for (const chip of chips) {
      expect(filterThreadEvents(events, chip, ctx)).toEqual(filterThreadEvents(events, chip, ctx));
    }
  });
});
