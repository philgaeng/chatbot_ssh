import { describe, it, expect } from "vitest";
import {
  formatUserFacingError,
  MSG_IMAGE_BEFORE_ESCALATE,
  MSG_IMAGE_BEFORE_RESOLVE,
} from "./user-messages";

describe("formatUserFacingError", () => {
  it("strips the 'API <status> <path>:' noise prefix and surfaces the FastAPI detail", () => {
    const err = new Error(
      'API 422 /api/v1/tickets/abc/actions: {"detail":"Something else went wrong"}',
    );
    const result = formatUserFacingError(err);
    expect(result.message).not.toMatch(/^API \d+/);
    expect(result.message).not.toContain("/api/v1/");
    expect(result.message).toBe("Something else went wrong");
  });

  it("maps the image-gate validation details to the officer-facing image messages", () => {
    const escalateErr = new Error(
      'API 422 /api/v1/tickets/abc/actions: {"detail":"At least one image attachment is required before escalating"}',
    );
    const resolveErr = new Error(
      'API 422 /api/v1/tickets/abc/actions: {"detail":"At least one image attachment is required before resolving"}',
    );

    const escalateResult = formatUserFacingError(escalateErr);
    const resolveResult = formatUserFacingError(resolveErr);

    expect(escalateResult).toEqual({ message: MSG_IMAGE_BEFORE_ESCALATE, kind: "validation" });
    expect(resolveResult).toEqual({ message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" });
  });

  // R5 (BUILD-REVIEW M3a): object-shaped detail must never raw-dump.
  it("unwraps an object detail with message + errors[] (org CSV import 422)", () => {
    const err = new Error(
      'API 422 /api/v1/organizations/import: {"detail":{"message":"Import rejected — nothing written","errors":["country_code \'XX\' not found"]}}',
    );
    const result = formatUserFacingError(err);
    expect(result.message).not.toContain("{");
    expect(result.message).not.toMatch(/^API \d+/);
    expect(result.message).toContain("Import rejected");
    expect(result.message).toContain("country_code 'XX' not found");
  });

  it("unwraps an object detail with a count field (position-type delete 409)", () => {
    const err = new Error(
      'API 409 /api/v1/position-types/abc: {"detail":{"message":"Position type is in use","reports_count":0,"holders_count":3}}',
    );
    const result = formatUserFacingError(err);
    expect(result.message).not.toContain("{");
    expect(result.message).toContain("Position type is in use");
    expect(result.message).toContain("3 holders");
  });
});
