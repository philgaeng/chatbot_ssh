// SPDX-License-Identifier: Apache-2.0

/** GRM-090 — the staffing-level disclosure predicate. */
import { describe, it, expect } from "vitest";

import {
  blockingSlotCount,
  blockingSummary,
  castScopeKey,
  initiallyOpenSteps,
  staffingSettled,
} from "./castDisclosure";

describe("blockingSlotCount", () => {
  it("counts only slots that are BOTH required and empty", () => {
    const tiers = [
      { required: true, empty: true },    // blocks
      { required: true, empty: false },   // staffed
      { required: false, empty: true },   // optional — an empty observer is not a blocker
      { required: false, empty: false },
    ];
    expect(blockingSlotCount(tiers, false)).toBe(1);
  });

  it("is zero for a fully staffed level", () => {
    expect(blockingSlotCount([{ required: true, empty: false }], false)).toBe(0);
  });

  it("is zero in a package scope, however empty — the package inherits the project", () => {
    // The regression this guards: counting package slots opens every level on every project and
    // undoes the item entirely.
    const allEmpty = [
      { required: true, empty: true },
      { required: true, empty: true },
    ];
    expect(blockingSlotCount(allEmpty, true)).toBe(0);
    expect(blockingSlotCount(allEmpty, false)).toBe(2);
  });

  it("handles a level with no slots at all", () => {
    expect(blockingSlotCount([], false)).toBe(0);
  });
});

describe("blockingSummary", () => {
  it("says it in words, singular and plural", () => {
    expect(blockingSummary(1)).toBe("Needs an officer");
    expect(blockingSummary(2)).toBe("Needs 2 officers");
  });

  it("says nothing when nothing blocks", () => {
    expect(blockingSummary(0)).toBeNull();
    expect(blockingSummary(-1)).toBeNull();
  });
});

describe("initiallyOpenSteps", () => {
  it("opens exactly the levels that block, and no others", () => {
    const open = initiallyOpenSteps([
      { stepId: "L4", blockingCount: 0 },
      { stepId: "L3", blockingCount: 1 },
      { stepId: "L2", blockingCount: 2 },
      { stepId: "L1", blockingCount: 0 },
    ]);
    expect([...open].sort()).toEqual(["L2", "L3"]);
  });

  it("opens nothing when the workflow is fully staffed", () => {
    // Deliberate: a finished workflow collapses to a summary, which is the point.
    const open = initiallyOpenSteps([
      { stepId: "L4", blockingCount: 0 },
      { stepId: "L1", blockingCount: 0 },
    ]);
    expect(open.size).toBe(0);
  });

  it("handles a workflow with no steps", () => {
    expect(initiallyOpenSteps([]).size).toBe(0);
  });
});

describe("staffingSettled (GRM-107)", () => {
  const all = { stepsFor: "wf1", castFor: castScopeKey("wf1", null), rosterSettled: true };

  it("is settled only when steps, cast and roster have all answered for this scope", () => {
    expect(staffingSettled(all, "wf1", null)).toBe(true);
  });

  it("⭐ is NOT settled while the roster is still loading — the window that showed a false blocker", () => {
    // A slot staffed through its named role reads as empty until the roster arrives.
    expect(staffingSettled({ ...all, rosterSettled: false }, "wf1", null)).toBe(false);
  });

  it("is not settled before the cast or the steps arrive", () => {
    expect(staffingSettled({ ...all, castFor: null }, "wf1", null)).toBe(false);
    expect(staffingSettled({ ...all, stepsFor: null }, "wf1", null)).toBe(false);
  });

  it("does not count a load that finished for a different workflow or package", () => {
    expect(staffingSettled(all, "wf2", null)).toBe(false);
    expect(staffingSettled(all, "wf1", "pkg-a")).toBe(false);
    const pkgA = { ...all, castFor: castScopeKey("wf1", "pkg-a") };
    expect(staffingSettled(pkgA, "wf1", "pkg-a")).toBe(true);
    expect(staffingSettled(pkgA, "wf1", "pkg-b")).toBe(false);
  });
});

