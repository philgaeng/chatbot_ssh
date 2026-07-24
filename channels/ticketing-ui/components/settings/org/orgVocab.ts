/**
 * orgVocab.ts — local vocabulary + forest helpers for the Organisation surface.
 *
 * Scope note: this is a leaf helper owned by the org/ workstream (RB-4, Frames 02/06/12).
 * It intentionally does NOT reach into the in-flight `lib/orgTree.ts` / `lib/labels.ts`
 * additions other workstreams own — it only depends on stable modules. Plain-language
 * labels here honour DESIGN §7.C ("no code identifier ever renders"); every slug maps to
 * a human label, falling back to `humanizeSlug` for values not in the map.
 */

import { humanizeSlug } from "@/lib/labels";
import type { OrganizationItem } from "@/lib/api";

// ── Enums (mirror ticketing/models/organization.py + position_types.py) ─────────

/** ORG_CATEGORIES (organization.py:17). Root-only; children inherit. */
export const ORG_CATEGORIES = ["government", "local_government", "donor", "third_party"] as const;
export type OrgCategory = (typeof ORG_CATEGORIES)[number];

/** government / local_government / donor — a new root of these needs super_admin (§2.5). */
export const INSTITUTIONAL_CATEGORIES: ReadonlySet<string> = new Set([
  "government",
  "local_government",
  "donor",
]);

const ORG_CATEGORY_LABELS: Record<string, string> = {
  government: "Government",
  local_government: "Local government",
  donor: "Development partner",
  third_party: "Company / contractor",
};

export function orgCategoryLabel(cat: string | null | undefined): string {
  if (!cat) return "";
  return ORG_CATEGORY_LABELS[cat] ?? humanizeSlug(cat);
}

/** Is this a super-admin-only institutional root category? */
export function isInstitutionalCategory(cat: string | null | undefined): boolean {
  return !!cat && INSTITUTIONAL_CATEGORIES.has(cat);
}

/** UNIT_TYPES (organization.py:18) — the common set; others still humanize cleanly. */
export const UNIT_TYPES = [
  "ministry",
  "department",
  "directorate",
  "provincial_office",
  "division_office",
  "province_assembly",
  "municipality",
  "development_partner",
  "company",
] as const;

const UNIT_TYPE_LABELS: Record<string, string> = {
  ministry: "Ministry",
  department: "Department",
  directorate: "Directorate",
  provincial_office: "Provincial office",
  division_office: "Division office",
  province_assembly: "Province assembly",
  municipality: "Municipality",
  development_partner: "Development partner",
  company: "Company",
};

export function unitTypeLabel(ut: string | null | undefined): string {
  if (!ut) return "";
  return UNIT_TYPE_LABELS[ut] ?? humanizeSlug(ut);
}

/**
 * unit_type → its usual org_category. SOFT hint only: the two are independent columns
 * (organization.py — a company can rarely be donor-adjacent), so this drives prioritisation,
 * never a hard rule. Used to narrow the position-type role picker by "Used at" office types.
 */
export const UNIT_TYPE_ORG_CATEGORY: Record<string, OrgCategory> = {
  ministry: "government",
  department: "government",
  directorate: "government",
  provincial_office: "government",
  division_office: "government",
  province_assembly: "government",
  municipality: "local_government",
  development_partner: "donor",
  company: "third_party",
};

/**
 * Coarse sector for role↔office affinity: public sector (government + local government) vs
 * donor vs company. Both a role's actor_category and an office's org_category fold into this,
 * so a government office and a local-government office both suggest the same public-sector roles.
 */
export function orgCategorySector(
  cat: string | null | undefined,
): "public" | "donor" | "third_party" | null {
  if (cat === "government" || cat === "local_government") return "public";
  if (cat === "donor") return "donor";
  if (cat === "third_party") return "third_party";
  return null;
}

/** visibility_mode (position_types.py) → plain prose (Frame 06 §5). */
export const VISIBILITY_MODES = ["none", "direct_reports", "subtree"] as const;

const VISIBILITY_MODE_LABELS: Record<string, string> = {
  none: "No one extra",
  direct_reports: "Their direct reports' cases",
  subtree: "The whole team below them",
};

export function visibilityModeLabel(vm: string | null | undefined): string {
  if (!vm) return VISIBILITY_MODE_LABELS.none;
  return VISIBILITY_MODE_LABELS[vm] ?? humanizeSlug(vm);
}

/** workflow_track on a position type → "Grievance type" prose (Frame 06 §5). */
export const POSITION_TRACKS = ["standard", "seah", "both"] as const;

const POSITION_TRACK_LABELS: Record<string, string> = {
  standard: "Standard (not SEAH)",
  seah: "SEAH",
  both: "Both",
};

export function positionTrackLabel(t: string | null | undefined): string {
  if (!t) return POSITION_TRACK_LABELS.standard;
  return POSITION_TRACK_LABELS[t] ?? humanizeSlug(t);
}

/** reports_to_locus → "same office" / "parent office". */
export const REPORTS_TO_LOCI = ["same_unit", "parent_unit"] as const;

const REPORTS_TO_LOCUS_LABELS: Record<string, string> = {
  same_unit: "Same office",
  parent_unit: "Parent office",
};

export function reportsToLocusLabel(l: string | null | undefined): string {
  if (!l) return "";
  return REPORTS_TO_LOCUS_LABELS[l] ?? humanizeSlug(l);
}

/** Owning level for an org-scoped catalog item (§4.4). null → "System". */
export function owningLevelLabel(
  ownerOrgId: string | null | undefined,
  orgNames: Map<string, string>,
): string {
  if (!ownerOrgId) return "System";
  return orgNames.get(ownerOrgId) ?? ownerOrgId;
}

// ── Forest helpers (client-side; the API returns a flat / depth-first list) ─────

export interface OrgForestNode {
  org: OrganizationItem;
  children: OrgForestNode[];
  depth: number;
}

/**
 * Build a forest from a flat org list. `parent_organization_id` is nullable; a node
 * whose parent isn't in the set is treated as a root (§2.4 — the tree is a forest).
 * Input order is preserved within each sibling group.
 */
export function buildForest(items: OrganizationItem[]): OrgForestNode[] {
  const byId = new Map<string, OrgForestNode>();
  for (const org of items) {
    byId.set(org.organization_id, { org, children: [], depth: 0 });
  }
  const roots: OrgForestNode[] = [];
  for (const org of items) {
    const node = byId.get(org.organization_id)!;
    const parentId = org.parent_organization_id ?? null;
    const parent = parentId ? byId.get(parentId) : undefined;
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }
  // Assign depth by walking from roots (handles any input ordering).
  const setDepth = (node: OrgForestNode, depth: number) => {
    node.depth = depth;
    for (const child of node.children) setDepth(child, depth + 1);
  };
  for (const r of roots) setDepth(r, 0);
  return roots;
}

/** All organization ids in the subtree rooted at `node` (excluding the node itself). */
export function descendantIds(node: OrgForestNode): Set<string> {
  const out = new Set<string>();
  const walk = (n: OrgForestNode) => {
    for (const c of n.children) {
      out.add(c.org.organization_id);
      walk(c);
    }
  };
  walk(node);
  return out;
}

/** Find a node by id anywhere in the forest. */
export function findNode(roots: OrgForestNode[], id: string): OrgForestNode | null {
  for (const r of roots) {
    if (r.org.organization_id === id) return r;
    const inChild = findNode(r.children, id);
    if (inChild) return inChild;
  }
  return null;
}

/**
 * Split forest roots into the two wireframe groups (Frame 02):
 *  • "Government reporting line" — roots whose category is `government`
 *  • "Independent organisations" — every other root (donor, third_party, local_government)
 * Grouping keys on the ROOT's category (children inherit it). See build-sheet risk #2.
 */
export function groupRoots(roots: OrgForestNode[]): {
  government: OrgForestNode[];
  independent: OrgForestNode[];
} {
  const government: OrgForestNode[] = [];
  const independent: OrgForestNode[] = [];
  for (const r of roots) {
    if (r.org.org_category === "government") government.push(r);
    else independent.push(r);
  }
  return { government, independent };
}

/** Build an id → English name map for owner/parent chips. */
export function orgNameMap(items: OrganizationItem[]): Map<string, string> {
  const m = new Map<string, string>();
  for (const o of items) m.set(o.organization_id, o.name);
  return m;
}

/** Territory hint text for a node ("covers Jhapa" / "covers Jhapa + offices below"). */
export function territoryHint(org: OrganizationItem): string | null {
  if (!org.territory_location_code) return null;
  return org.territory_includes_children
    ? `Covers ${org.territory_location_code} and offices below`
    : `Covers ${org.territory_location_code}`;
}
