/**
 * friendlyError.test.ts — T3-05.
 *
 * `friendlyError` is the settings clusters' single error-rendering path (34 call sites
 * at extraction time), so this pins the contract it delegates: whatever
 * formatUserFacingError unwraps, callers get the plain `.message` string.
 */
import { describe, it, expect } from "vitest";
import { friendlyError } from "./friendlyError";

describe("friendlyError", () => {
  it("returns the message from an Error", () => {
    expect(friendlyError(new Error("boom"))).toBe("boom");
  });

  it("always returns a string, never throws, for odd inputs", () => {
    for (const input of [null, undefined, 42, {}, "plain string"]) {
      expect(typeof friendlyError(input)).toBe("string");
    }
  });

  it("never returns an empty string (callers render it directly)", () => {
    for (const input of [null, undefined, new Error("")]) {
      expect(friendlyError(input).length).toBeGreaterThan(0);
    }
  });
});
