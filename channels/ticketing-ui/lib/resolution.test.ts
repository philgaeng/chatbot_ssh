// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import type { ResolutionOption, WorkflowResolutionPanel } from "@/lib/api";
import { systemEventLabel } from "@/lib/mobile-constants";
import { DEFAULT_ACTOR_CHOICE, resolutionActorState, resolutionFormState, resolutionPanelState } from "@/lib/resolution";

const general: ResolutionOption[] = [
  { code: "CLASSIFIED", label: "Grievance classified", default_wording: "Reviewed and classified." },
  { code: "ACCEPTED_OTHER", label: "Grievance accepted — other remedy", default_wording: "Remedy agreed, details below." },
];
const roadWorks: ResolutionOption[] = [
  { code: "ROAD_REPAIRED", label: "Hazard repaired", default_wording: "The hazard was repaired." },
];

describe("resolutionFormState (GRM-116)", () => {
  it("preselects the pre-catalog default when the workflow offers it, with its wording", () => {
    const s = resolutionFormState(general, null, null);
    expect(s.category).toBe("ACCEPTED_OTHER");
    expect(s.note).toBe("Remedy agreed, details below.");
    expect(s.valid).toBe(true);
  });

  it("otherwise preselects the workflow's first action", () => {
    expect(resolutionFormState(roadWorks, null, null).category).toBe("ROAD_REPAIRED");
  });

  it("the wording follows the chosen action until the officer types", () => {
    expect(resolutionFormState(general, "CLASSIFIED", null).note).toBe("Reviewed and classified.");
    expect(resolutionFormState(general, "CLASSIFIED", "My own words here.").note).toBe("My own words here.");
  });

  it("a choice the reloaded options no longer offer falls back, keeping the officer's text", () => {
    const s = resolutionFormState(roadWorks, "ACCEPTED_OTHER", "Officer text survives the reload.");
    expect(s.category).toBe("ROAD_REPAIRED");
    expect(s.note).toBe("Officer text survives the reload.");
  });

  it("no options is a sensitive workflow: text only, no category, no default wording", () => {
    const s = resolutionFormState([], null, null);
    expect(s.textOnly).toBe(true);
    expect(s.category).toBeNull();
    expect(s.note).toBe("");
    expect(s.valid).toBe(false);
    expect(resolutionFormState([], null, "Referred with consent, case closed.").valid).toBe(true);
  });

  it("short text is not valid", () => {
    expect(resolutionFormState(general, null, "too short").valid).toBe(false);
  });
});

describe("the RESOLVED system pill", () => {
  it("prefers the label snapshotted on the event", () => {
    expect(
      systemEventLabel("RESOLVED", { resolution_category: "ROAD_REPAIRED", resolution_category_label: "Hazard repaired" }),
    ).toBe("Case resolved — Hazard repaired");
  });

  it("reads a pre-catalog event's code through the frozen legacy labels", () => {
    expect(systemEventLabel("RESOLVED", { resolution_category: "DEMAND_REJECTED" })).toBe(
      "Case resolved — Complainant demand rejected",
    );
  });

  it("names no outcome for a case that recorded none", () => {
    expect(systemEventLabel("RESOLVED", {})).toBe("Case resolved");
  });
});

describe("resolutionActorState (GRM-117)", () => {
  const jhapa = { organization_id: "JHA", name: "Jhapa Division Road Office" };
  const ilam = { organization_id: "ILA", name: "Ilam Division Road Office" };
  const police = { key: "police", label: "Police" };
  const offers = { selfOffices: [jhapa], externalActors: [police] };

  it("is hidden when nothing is offered — a sensitive workflow records no actor", () => {
    const s = resolutionActorState({ selfOffices: [], externalActors: [] }, DEFAULT_ACTOR_CHOICE);
    expect(s.hidden).toBe(true);
    expect(s.payload).toBeNull();
  });

  it("defaults to 'I did' with the one derived office, and sends no office id", () => {
    const s = resolutionActorState(offers, DEFAULT_ACTOR_CHOICE);
    expect(s.selfOffice).toEqual(jhapa);
    expect(s.payload).toEqual({ resolution_actor_kind: "self" });
  });

  it("an officer with several offices must choose one of theirs", () => {
    const several = { selfOffices: [jhapa, ilam], externalActors: [police] };
    const none = resolutionActorState(several, DEFAULT_ACTOR_CHOICE);
    expect(none.selfOffice).toBeNull();
    expect(none.payload).toBeNull();
    expect(none.missing).toMatch(/which of your offices/);
    const picked = resolutionActorState(several, { kind: "self", organizationId: "ILA", external: null });
    expect(picked.payload).toEqual({ resolution_actor_kind: "self", resolution_actor_organization_id: "ILA" });
  });

  it("another office needs an office picked", () => {
    expect(resolutionActorState(offers, { kind: "organization", organizationId: null, external: null }).missing)
      .toMatch(/office that took the action/);
    expect(resolutionActorState(offers, { kind: "organization", organizationId: "ADB", external: null }).payload)
      .toEqual({ resolution_actor_kind: "organization", resolution_actor_organization_id: "ADB" });
  });

  it("an outside body must be one of the listed ones — nothing typed gets through", () => {
    expect(resolutionActorState(offers, { kind: "external", organizationId: null, external: "a neighbour" }).payload)
      .toBeNull();
    expect(resolutionActorState(offers, { kind: "external", organizationId: null, external: "police" }).payload)
      .toEqual({ resolution_actor_kind: "external", resolution_actor_external: "police" });
  });
});

describe("resolutionPanelState (GRM-119)", () => {
  const row = (code: string) => ({ code, label: code, default_wording: "", can_edit: false, used_by_count: 1 });
  const panel = (n: number, extra: Partial<WorkflowResolutionPanel> = {}): WorkflowResolutionPanel => ({
    actions: Array.from({ length: n }, (_, i) => row(`A${i}`)), can_change: true, max: 8,
    national_choices: [], can_create_national: false, is_sensitive: false, owner_is_ministry: true, ...extra,
  });

  it("counts against the limit and says so when full", () => {
    const s = resolutionPanelState(panel(8), true);
    expect(s.countLabel).toBe("8 of 8");
    expect(s.full).toBe(true);
    expect(s.hint).toMatch(/at most 8/);
  });

  it("an empty draft blocks publishing and says why", () => {
    const s = resolutionPanelState(panel(0), false);
    expect(s.blocksPublish).toBe(true);
    expect(s.hint).toBe("Add at least one action before publishing.");
  });

  it("the last action of a published workflow cannot be removed", () => {
    expect(resolutionPanelState(panel(1), true).canRemove).toBe(false);
    expect(resolutionPanelState(panel(1), false).canRemove).toBe(true);
    expect(resolutionPanelState(panel(2), true).canRemove).toBe(true);
  });

  it("a sensitive workflow never blocks publishing and has nothing to say", () => {
    const s = resolutionPanelState(panel(0, { is_sensitive: true, can_change: false }), false);
    expect(s.blocksPublish).toBe(false);
    expect(s.hint).toBeNull();
  });

  it("a viewer who may not change the workflow can remove nothing", () => {
    expect(resolutionPanelState(panel(3, { can_change: false }), false).canRemove).toBe(false);
  });
});
