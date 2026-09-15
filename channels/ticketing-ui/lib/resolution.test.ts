// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from "vitest";
import type { ResolutionOption } from "@/lib/api";
import { systemEventLabel } from "@/lib/mobile-constants";
import { resolutionFormState } from "@/lib/resolution";

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
