/**
 * roleEntry.test.ts — T3-05.
 *
 * Pins the role view-model shared by the roles cluster, the workflows cluster and the
 * settings shell. Its defaulting behaviour is load-bearing: the catalog renders these
 * fields directly, so a dropped `??` shows up as a blank cell rather than an error.
 */
import { describe, it, expect } from "vitest";
import type { GrmRole } from "@/lib/api";
import { mapGrmRoleToEntry, owningLevelLabel } from "./roleEntry";

const raw = (over: Partial<GrmRole> = {}): GrmRole =>
  ({ role_id: "r1", role_key: "site_focal", display_name: "Site focal person", ...over }) as GrmRole;

describe("mapGrmRoleToEntry", () => {
  it("renames the wire fields onto the view-model", () => {
    const e = mapGrmRoleToEntry(raw({ role_id: "abc", role_key: "grc_chair", display_name: "GRC chair" }));
    expect(e.role_id).toBe("abc");
    expect(e.key).toBe("grc_chair");
    expect(e.label).toBe("GRC chair");
  });

  it("defaults every optional field when the API omits it", () => {
    const e = mapGrmRoleToEntry(raw());
    expect(e.workflow).toBe("Standard");
    expect(e.jurisdiction).toBe("field");
    expect(e.description).toBe("");
    expect(e.role_origin).toBe("system");
    expect(e.steps_count).toBe(0);
    expect(e.officers_count).toBe(0);
    expect(e.owner_organization_id).toBeNull();
  });

  it("passes through supplied values instead of defaulting", () => {
    const e = mapGrmRoleToEntry(
      raw({
        workflow_scope: "SEAH",
        jurisdiction_mode: "country",
        description: "d",
        role_origin: "custom",
        steps_count: 3,
        officers_count: 7,
        owner_organization_id: "DOR",
      }),
    );
    expect(e).toMatchObject({
      workflow: "SEAH",
      jurisdiction: "country",
      description: "d",
      role_origin: "custom",
      steps_count: 3,
      officers_count: 7,
      owner_organization_id: "DOR",
    });
  });

  it("keeps a legitimate zero count rather than substituting a placeholder", () => {
    const e = mapGrmRoleToEntry(raw({ steps_count: 0, officers_count: 0 }));
    expect(e.steps_count).toBe(0);
    expect(e.officers_count).toBe(0);
  });

  it("only defaults on null/undefined, not on falsy — an empty scope stays empty", () => {
    // The mapper uses `??`, not `||`. This is the input where the two actually differ:
    // `"" ?? "Standard"` is "", whereas `"" || "Standard"` would be "Standard".
    // Pinning current behaviour (T3-05 is a verbatim move, not a fix).
    const e = mapGrmRoleToEntry(raw({ workflow_scope: "", description: "" }));
    expect(e.workflow).toBe("");
    expect(e.description).toBe("");
  });
});

describe("owningLevelLabel", () => {
  it("labels an org-scoped role as that org and below", () => {
    expect(owningLevelLabel("DOR")).toBe("DOR & below");
  });

  it("labels an unscoped role as system-wide", () => {
    expect(owningLevelLabel(null)).toBe("System · everywhere");
    expect(owningLevelLabel(undefined)).toBe("System · everywhere");
  });
});
