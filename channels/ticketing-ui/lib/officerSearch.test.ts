// SPDX-License-Identifier: Apache-2.0

/**
 * GRM-087 — the officer directory's search matches the columns it renders.
 *
 * ⚠ **Officers are keyed on EMAIL, never display name** (`GRM-081`): a freshly seeded database
 * derives the name from the address, so `l1-officer@grm.local` renders as `L1-Officer` in CI and
 * `Site Officer L1` on a dev box. A test keyed on the name passes locally and fails in CI.
 */
import { describe, it, expect } from "vitest";

import {
  officerSearchHaystack,
  officerMatchesSearch,
  type SearchableOfficer,
  type OfficerSearchLookups,
} from "./officerSearch";
import { prettyLocation } from "./prettyLocation";

const lookups: OfficerSearchLookups = {
  orgById: new Map([
    ["DOR_JHA", { name: "Division Road Office, Jhapa", display_name_ne: "सडक डिभिजन कार्यालय, झापा" }],
    ["ADB", { name: "Asian Development Bank (ADB)", display_name_ne: null }],
  ]),
  projectByCode: new Map([["KL_ROAD", { name: "Kakarbhitta - Laukahi Road Project" }]]),
  locationLabel: prettyLocation,
};

const officer: SearchableOfficer = {
  display_name: "Site Officer L1",
  email: "l1-officer@grm.local",
  positions: ["Senior Divisional Engineer · DOR_JHA"],
  organization_ids: ["DOR_JHA"],
  project_codes: ["KL_ROAD"],
  location_codes: ["NP-P1-D-JHAPA"],
  scopes: [{ location_code: "NP-P1-D-MORANG" }],
};

describe("officerMatchesSearch", () => {
  it("still matches what it always matched", () => {
    for (const term of ["l1-officer@grm.local", "Site Officer", "Divisional Engineer"]) {
      expect(officerMatchesSearch(officer, term, lookups)).toBe(true);
    }
  });

  it("matches the Office column — the regression this exists for", () => {
    // Was FALSE before GRM-087: the office was rendered and unsearchable.
    expect(officerMatchesSearch(officer, "Division Road Office", lookups)).toBe(true);
    expect(officerMatchesSearch(officer, "jhapa", lookups)).toBe(true);
  });

  it("matches the Nepali office name where one exists", () => {
    expect(officerMatchesSearch(officer, "झापा", lookups)).toBe(true);
  });

  it("matches the Project / area column by project name, project code and location", () => {
    expect(officerMatchesSearch(officer, "Kakarbhitta", lookups)).toBe(true);
    expect(officerMatchesSearch(officer, "KL_ROAD", lookups)).toBe(true);
    expect(officerMatchesSearch(officer, "Morang", lookups)).toBe(true);   // from `scopes`
  });

  it("matches a pasted location code, which never appears on screen", () => {
    expect(officerMatchesSearch(officer, "NP-P1-D-JHAPA", lookups)).toBe(true);
  });

  it("is case-insensitive and ignores surrounding whitespace", () => {
    expect(officerMatchesSearch(officer, "  DIVISION ROAD  ", lookups)).toBe(true);
  });

  it("matches everything on an empty term — the box is not a filter until typed in", () => {
    expect(officerMatchesSearch(officer, "", lookups)).toBe(true);
    expect(officerMatchesSearch(officer, "   ", lookups)).toBe(true);
  });

  it("does not match something the officer has nothing to do with", () => {
    expect(officerMatchesSearch(officer, "Kathmandu", lookups)).toBe(false);
    expect(officerMatchesSearch(officer, "Asian Development Bank", lookups)).toBe(false);
  });

  it("survives an officer with no org, project, scope or position", () => {
    const bare: SearchableOfficer = {
      display_name: "Aashma Dor",
      email: "aashma.dor@gmail.com",
      organization_ids: [],
      location_codes: [],
    };
    expect(officerMatchesSearch(bare, "aashma.dor@gmail.com", lookups)).toBe(true);
    expect(officerMatchesSearch(bare, "jhapa", lookups)).toBe(false);
  });

  it("tolerates an organization id the lookup does not hold", () => {
    // The roster and the org list are two fetches; either can be stale for a moment.
    const orphan: SearchableOfficer = { ...officer, organization_ids: ["GONE"] };
    expect(() => officerSearchHaystack(orphan, lookups)).not.toThrow();
    expect(officerMatchesSearch(orphan, "l1-officer@grm.local", lookups)).toBe(true);
  });

  it("de-duplicates a location held both directly and through a scope", () => {
    const dup: SearchableOfficer = {
      ...officer,
      location_codes: ["NP-P1-D-JHAPA"],
      scopes: [{ location_code: "NP-P1-D-JHAPA" }],
    };
    const hay = officerSearchHaystack(dup, lookups);
    expect(hay.split("np-p1-d-jhapa").length - 1).toBe(1);
  });
});
