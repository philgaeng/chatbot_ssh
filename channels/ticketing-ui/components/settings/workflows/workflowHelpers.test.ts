// SPDX-License-Identifier: Apache-2.0

/**
 * workflowHelpers.test.ts — T3-05.
 *
 * First test coverage for anything under `components/settings/` (before this, portal
 * vitest was 61 tests over lib/* only, and settings had zero — see sprint D-12).
 *
 * Scope note: these pin the pure-logic helpers extracted out of the settings page.
 * Per-tab *render* smoke tests are NOT here — the portal has no DOM test harness
 * (vitest is `environment: "node"`, `*.test.ts` only, no @testing-library/react).
 * Tracked in followups/settings-tab-render-tests.md.
 */
import { describe, it, expect } from "vitest";
import type { WorkflowDefinition, ProjectWorkflowSlot } from "@/lib/api";
import {
  statusBadge,
  topOrganizations,
  typeBadge,
  emptyBinding,
  workflowTrackOf,
  bindingsFromProject,
  publishedWorkflowOptions,
  NOTIFICATION_EVENTS,
  SEAH_EVENTS,
  NOTIF_TIERS,
  NOTIF_CHANNELS,
} from "./workflowHelpers";

const wf = (over: Partial<WorkflowDefinition> = {}): WorkflowDefinition =>
  ({
    workflow_id: "w1",
    workflow_type: "standard",
    status: "published",
    is_template: false,
    ...over,
  }) as WorkflowDefinition;

describe("statusBadge", () => {
  it("maps each known status to its own class", () => {
    expect(statusBadge("published")).toBe("bg-green-100 text-green-700");
    expect(statusBadge("draft")).toBe("bg-amber-100 text-amber-700");
    expect(statusBadge("archived")).toBe("bg-gray-100 text-gray-500");
    expect(statusBadge("template")).toBe("bg-blue-100 text-blue-700");
  });

  it("falls back for an unknown status", () => {
    expect(statusBadge("nonsense")).toBe("bg-gray-100 text-gray-600");
  });
});

describe("typeBadge", () => {
  it("gives seah the red badge and everything else the slate one", () => {
    expect(typeBadge("seah")).toBe("bg-red-100 text-red-700");
    expect(typeBadge("standard")).toBe("bg-slate-100 text-slate-600");
  });
});

describe("workflowTrackOf", () => {
  it("is case-insensitive on workflow_type", () => {
    expect(workflowTrackOf(wf({ workflow_type: "SEAH" }))).toBe("seah");
    expect(workflowTrackOf(wf({ workflow_type: "seah" }))).toBe("seah");
  });

  it("treats anything non-seah — including empty — as standard", () => {
    expect(workflowTrackOf(wf({ workflow_type: "standard" }))).toBe("standard");
    expect(workflowTrackOf(wf({ workflow_type: "" }))).toBe("standard");
  });
});

describe("emptyBinding", () => {
  it("defaults carry a null intake_route; non-defaults get new_grievance", () => {
    expect(emptyBinding(10, true).intake_route).toBeNull();
    expect(emptyBinding(20).intake_route).toBe("new_grievance");
  });

  it("carries sort_order and is_default through", () => {
    const b = emptyBinding(30, true);
    expect(b.sort_order).toBe(30);
    expect(b.is_default).toBe(true);
    expect(b.workflow_id).toBe("");
  });
});

describe("bindingsFromProject", () => {
  it("seeds a single default binding when the project has no slots", () => {
    const out = bindingsFromProject([]);
    expect(out).toHaveLength(1);
    expect(out[0].is_default).toBe(true);
    expect(out[0].sort_order).toBe(10);
  });

  it("maps slots through, defaulting sort_order by position when absent", () => {
    const slots = [
      { project_workflow_id: "a", display_label: "A", workflow_id: "w1", is_default: true, sort_order: 0 },
      { project_workflow_id: "b", display_label: "B", workflow_id: "w2", is_default: false, sort_order: 55 },
    ] as ProjectWorkflowSlot[];
    const out = bindingsFromProject(slots);
    expect(out.map((b) => b.localId)).toEqual(["a", "b"]);
    expect(out[0].sort_order).toBe(10); // 0 is falsy -> (i+1)*10
    expect(out[1].sort_order).toBe(55); // explicit value wins
    expect(out[0].classifications).toEqual([]);
    expect(out[0].intake_route).toBeNull();
  });
});

describe("publishedWorkflowOptions", () => {
  const all = () => true;

  it("keeps only published, non-template workflows", () => {
    const out = publishedWorkflowOptions(
      [
        wf({ workflow_id: "ok" }),
        wf({ workflow_id: "draft", status: "draft" }),
        wf({ workflow_id: "tpl", is_template: true }),
      ],
      all,
    );
    expect(out.map((w) => w.workflow_id)).toEqual(["ok"]);
  });

  it("filters by the caller's track permission", () => {
    const out = publishedWorkflowOptions(
      [wf({ workflow_id: "s" }), wf({ workflow_id: "x", workflow_type: "seah" })],
      (t) => t === "standard",
    );
    expect(out.map((w) => w.workflow_id)).toEqual(["s"]);
  });

  it("prepends the current selection when it would otherwise be filtered out", () => {
    // Guards the editor against silently dropping an already-bound archived workflow.
    const out = publishedWorkflowOptions(
      [wf({ workflow_id: "ok" }), wf({ workflow_id: "old", status: "archived" })],
      all,
      "old",
    );
    expect(out.map((w) => w.workflow_id)).toEqual(["old", "ok"]);
  });

  it("does not duplicate the selection when it is already published", () => {
    const out = publishedWorkflowOptions([wf({ workflow_id: "ok" })], all, "ok");
    expect(out.map((w) => w.workflow_id)).toEqual(["ok"]);
  });

  it("ignores an unknown selectedId", () => {
    const out = publishedWorkflowOptions([wf({ workflow_id: "ok" })], all, "ghost");
    expect(out.map((w) => w.workflow_id)).toEqual(["ok"]);
  });
});

describe("notification vocab", () => {
  it("SEAH exposes a strict subset of the standard event set", () => {
    const known = new Set(NOTIFICATION_EVENTS.map((e) => e.key));
    for (const k of SEAH_EVENTS) expect(known.has(k)).toBe(true);
    expect(SEAH_EVENTS.size).toBeLessThan(known.size);
  });

  it("does not offer grc_convened or quarterly_report on the SEAH track", () => {
    expect(SEAH_EVENTS.has("grc_convened")).toBe(false);
    expect(SEAH_EVENTS.has("quarterly_report")).toBe(false);
  });

  it("pins the tier and channel vocabularies", () => {
    expect(NOTIF_TIERS).toEqual(["actor", "supervisor", "informed", "observer"]);
    expect(NOTIF_CHANNELS).toEqual(["app", "email", "sms"]);
  });
});

describe("topOrganizations (GRM-122)", () => {
  const org = (id: string, parent: string | null) =>
    ({ organization_id: id, name: id, parent_organization_id: parent, country_code: "NP",
       is_active: true, created_at: "", updated_at: "" });

  it("an admin scoped at one office gets that office as the only top", () => {
    const reach = [org("PD_ADB", "DOR"), org("LOT1", "PD_ADB"), org("LOT2", "PD_ADB")];
    expect(topOrganizations(reach).map((o) => o.organization_id)).toEqual(["PD_ADB"]);
  });

  it("two separate branches give two tops, so the admin must choose", () => {
    const reach = [org("JHAPA", "DOR"), org("ILAM", "DOR")];
    expect(topOrganizations(reach).map((o) => o.organization_id)).toEqual(["JHAPA", "ILAM"]);
  });

  it("a whole forest (a platform admin's reach) has every root as a top", () => {
    const reach = [org("DOR", null), org("PD_ADB", "DOR"), org("CUSTOMS", null)];
    expect(topOrganizations(reach).map((o) => o.organization_id)).toEqual(["DOR", "CUSTOMS"]);
  });
});
