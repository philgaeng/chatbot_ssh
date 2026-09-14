// SPDX-License-Identifier: Apache-2.0

/**
 * GRM-086 — filtering the organization forest without flattening it.
 *
 * The forest under test mirrors the seeded shape: one government line four deep, plus an
 * independent root.
 *
 *   Ministry of Infrastructure Development      (ministry)
 *     └ Department of Roads                     (department)
 *         └ Provincial Office 1                 (provincial_office,  NP-P1)
 *             ├ Division Road Office, Jhapa     (division_office,    NP-P1-D-JHAPA)
 *             └ Division Bridge Office, Morang  (division_office,    NP-P1-D-MORANG)
 *   Asian Development Bank (ADB)                (development_partner)
 */
import { describe, it, expect } from "vitest";

import { buildForest } from "./orgVocab";
import {
  orgMatches,
  filterForest,
  countMatches,
  idsInForest,
  availableFilterValues,
  isOrgFilterActive,
  EMPTY_ORG_FILTER,
} from "./orgFilter";
import type { OrganizationItem } from "@/lib/api";

function org(
  id: string,
  name: string,
  parent: string | null,
  unit_type: string,
  territory: string | null = null,
  display_name_ne: string | null = null,
): OrganizationItem {
  return {
    organization_id: id,
    name,
    country_code: "NP",
    is_active: true,
    created_at: "",
    updated_at: "",
    parent_organization_id: parent,
    unit_type,
    territory_location_code: territory,
    display_name_ne,
  };
}

const ITEMS: OrganizationItem[] = [
  org("MOID", "Ministry of Infrastructure Development", null, "ministry"),
  org("DOR", "Department of Roads", "MOID", "department"),
  org("PO1", "Provincial Office 1", "DOR", "provincial_office", "NP-P1"),
  org("DOR_JHA", "Division Road Office, Jhapa", "PO1", "division_office", "NP-P1-D-JHAPA", "सडक डिभिजन, झापा"),
  org("DBO_MOR", "Division Bridge Office, Morang", "PO1", "division_office", "NP-P1-D-MORANG"),
  org("ADB", "Asian Development Bank (ADB)", null, "development_partner"),
];

const ROOTS = buildForest(ITEMS);

describe("orgMatches", () => {
  it("matches name, Nepali name and id", () => {
    const jha = ITEMS.find((o) => o.organization_id === "DOR_JHA")!;
    expect(orgMatches(jha, { ...EMPTY_ORG_FILTER, q: "jhapa" })).toBe(true);
    expect(orgMatches(jha, { ...EMPTY_ORG_FILTER, q: "झापा" })).toBe(true);
    expect(orgMatches(jha, { ...EMPTY_ORG_FILTER, q: "DOR_JHA" })).toBe(true);
  });

  it("ANDs the filters rather than ORing them", () => {
    const jha = ITEMS.find((o) => o.organization_id === "DOR_JHA")!;
    expect(orgMatches(jha, { q: "jhapa", unitType: "division_office", territory: "" })).toBe(true);
    expect(orgMatches(jha, { q: "jhapa", unitType: "ministry", territory: "" })).toBe(false);
  });
});

describe("filterForest", () => {
  it("keeps a deep match's whole ancestor chain, marked as context", () => {
    // The behaviour the whole item exists for: "Division Office" alone is not an answer.
    const out = filterForest(ROOTS, { ...EMPTY_ORG_FILTER, q: "jhapa" });
    expect(out).toHaveLength(1);                       // ADB pruned entirely
    const moid = out[0];
    expect(moid.org.organization_id).toBe("MOID");
    expect(moid.isMatch).toBe(false);                  // context, not a result
    const dor = moid.children[0];
    const po1 = dor.children[0];
    expect(dor.isMatch).toBe(false);
    expect(po1.isMatch).toBe(false);
    expect(po1.children).toHaveLength(1);
    expect(po1.children[0].org.organization_id).toBe("DOR_JHA");
    expect(po1.children[0].isMatch).toBe(true);
  });

  it("counts matches, not the rows on screen", () => {
    const out = filterForest(ROOTS, { ...EMPTY_ORG_FILTER, unitType: "division_office" });
    expect(countMatches(out)).toBe(2);                 // the two division offices
    expect(idsInForest(out).size).toBe(5);             // + 3 ancestors shown to place them
  });

  it("keeps a matching ancestor AND its matching descendant", () => {
    const out = filterForest(ROOTS, { ...EMPTY_ORG_FILTER, q: "office" });
    // "Provincial Office 1" and both division offices match on their own.
    expect(countMatches(out)).toBe(3);
  });

  it("prunes a branch with no match anywhere in it", () => {
    const out = filterForest(ROOTS, { ...EMPTY_ORG_FILTER, q: "asian" });
    expect(out).toHaveLength(1);
    expect(out[0].org.organization_id).toBe("ADB");
    expect(out[0].isMatch).toBe(true);
  });

  it("returns everything, all matching, when nothing is filtered", () => {
    const out = filterForest(ROOTS, EMPTY_ORG_FILTER);
    expect(countMatches(out)).toBe(ITEMS.length);
    expect(idsInForest(out).size).toBe(ITEMS.length);
  });

  it("returns an empty forest when nothing matches — not the unfiltered one", () => {
    // The failure that would make the filter look broken-but-harmless: falling back to everything.
    expect(filterForest(ROOTS, { ...EMPTY_ORG_FILTER, q: "kathmandu" })).toHaveLength(0);
  });

  it("filters by area", () => {
    const out = filterForest(ROOTS, { ...EMPTY_ORG_FILTER, territory: "NP-P1-D-MORANG" });
    expect(countMatches(out)).toBe(1);
    expect(idsInForest(out).has("DBO_MOR")).toBe(true);
    expect(idsInForest(out).has("DOR_JHA")).toBe(false);
  });
});

describe("availableFilterValues", () => {
  it("offers only values the data actually holds", () => {
    // Never hardcoded: a filter offering "Division office" where none exists is a dead end.
    const { unitTypes, territories } = availableFilterValues(ITEMS);
    expect(unitTypes).toEqual([
      "department",
      "development_partner",
      "division_office",
      "ministry",
      "provincial_office",
    ]);
    expect(territories).toEqual(["NP-P1", "NP-P1-D-JHAPA", "NP-P1-D-MORANG"]);
  });

  it("copes with a forest that has no types or territories at all", () => {
    expect(availableFilterValues([])).toEqual({ unitTypes: [], territories: [] });
  });
});

describe("isOrgFilterActive", () => {
  it("treats whitespace as nothing typed", () => {
    expect(isOrgFilterActive(EMPTY_ORG_FILTER)).toBe(false);
    expect(isOrgFilterActive({ ...EMPTY_ORG_FILTER, q: "   " })).toBe(false);
    expect(isOrgFilterActive({ ...EMPTY_ORG_FILTER, q: "a" })).toBe(true);
    expect(isOrgFilterActive({ ...EMPTY_ORG_FILTER, unitType: "ministry" })).toBe(true);
  });
});
