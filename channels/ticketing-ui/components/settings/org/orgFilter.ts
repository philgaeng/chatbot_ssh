// SPDX-License-Identifier: Apache-2.0

/**
 * Filtering the organization forest without flattening it (`GRM-086`).
 *
 * **The rule this file exists for: a match keeps its ancestors.** A hit deep in the forest is not
 * an answer on its own — "Division Office" means nothing; "DOR → Provincial Office 1 → Division
 * Office" is the answer. So the filter returns a *pruned forest*, not a list: every matching node,
 * plus the chain above it, with the chain marked as **context** so the UI can render it as such
 * and the count can exclude it.
 *
 * ⚠ **This is also why the filtering is client-side, and why the server's existing `q` cannot be
 * used.** `GET /api/v1/organizations?q=` returns a **flat filtered set** — an organization whose
 * parent does not match comes back *without* its parent, so the forest cannot be rebuilt. That is
 * a structural limit, not a missing feature. `OrgTree` already fetches the whole forest in one
 * call with every filter field on each node, so matching here is both less work and the only
 * correct option. See `DESIGN-settings-findability.md` §6.
 *
 * Pure, per `05_frontend` rule 2.2.
 */
import type { OrganizationItem } from "@/lib/api";

import type { OrgForestNode } from "./orgVocab";

export interface OrgFilterCriteria {
  /** Free text over name, Nepali name and id. */
  q: string;
  /** `unit_type`, or "" for any. */
  unitType: string;
  /** `territory_location_code`, or "" for any. */
  territory: string;
}

export const EMPTY_ORG_FILTER: OrgFilterCriteria = { q: "", unitType: "", territory: "" };

export function isOrgFilterActive(c: OrgFilterCriteria): boolean {
  return c.q.trim() !== "" || c.unitType !== "" || c.territory !== "";
}

/** A forest node plus whether it earned its place or is only here to locate a descendant. */
export interface FilteredOrgNode {
  org: OrganizationItem;
  children: FilteredOrgNode[];
  depth: number;
  /** False = an ancestor shown for context. Render it de-emphasised; do not count it. */
  isMatch: boolean;
}

/**
 * Does one organization match, ignoring the tree entirely?
 *
 * ⚠ `unit_type` is the Type filter, not `org_category`, and that is deliberate: `org_category` is
 * **root-only and inherited by children** (`orgVocab.ts`), so filtering on it silently drops every
 * child whose column is null. The two visible groups already express category.
 */
export function orgMatches(org: OrganizationItem, c: OrgFilterCriteria): boolean {
  if (c.unitType && (org.unit_type ?? "") !== c.unitType) return false;
  if (c.territory && (org.territory_location_code ?? "") !== c.territory) return false;
  const needle = c.q.trim().toLowerCase();
  if (!needle) return true;
  return [org.name, org.display_name_ne ?? "", org.organization_id]
    .join(" ")
    .toLowerCase()
    .includes(needle);
}

/**
 * Prune the forest to matches and the chains that locate them.
 *
 * A node is kept when it matches, **or** when any descendant does. `isMatch` records which of the
 * two it was, so five rows on screen can honestly be reported as "2 organizations match, 3 more
 * shown to place them".
 *
 * With no criteria this returns the forest unchanged, every node a match — so a caller can render
 * one code path whether or not anything is typed.
 */
export function filterForest(
  roots: OrgForestNode[],
  c: OrgFilterCriteria,
): FilteredOrgNode[] {
  const visit = (node: OrgForestNode): FilteredOrgNode | null => {
    const children = node.children
      .map(visit)
      .filter((n): n is FilteredOrgNode => n !== null);
    const selfMatches = orgMatches(node.org, c);
    // Kept for a descendant's sake, not its own — that is what makes it context.
    if (!selfMatches && children.length === 0) return null;
    return { org: node.org, children, depth: node.depth, isMatch: selfMatches };
  };
  return roots.map(visit).filter((n): n is FilteredOrgNode => n !== null);
}

/** How many nodes actually matched — ancestors shown for context are not results. */
export function countMatches(nodes: FilteredOrgNode[]): number {
  let n = 0;
  const walk = (list: FilteredOrgNode[]) => {
    for (const node of list) {
      if (node.isMatch) n += 1;
      walk(node.children);
    }
  };
  walk(nodes);
  return n;
}

/** Every id in the pruned forest — the set the tree must expand so matches are reachable. */
export function idsInForest(nodes: FilteredOrgNode[]): Set<string> {
  const out = new Set<string>();
  const walk = (list: FilteredOrgNode[]) => {
    for (const node of list) {
      out.add(node.org.organization_id);
      walk(node.children);
    }
  };
  walk(nodes);
  return out;
}

/**
 * The distinct values the filters can offer, taken from the forest itself.
 *
 * ⭐ Derived from the data, never hardcoded — a filter offering "Division office" on a deployment
 * that has none is a dead end, and one that cannot offer a type this country uses is worse. Same
 * reason the area list is codes present on real organizations rather than a location hierarchy:
 * it stays correct outside Nepal. (A level-grouped area picker needs `location_level_defs`; that
 * is a larger change and is not this item.)
 */
export function availableFilterValues(items: OrganizationItem[]): {
  unitTypes: string[];
  territories: string[];
} {
  const unitTypes = new Set<string>();
  const territories = new Set<string>();
  for (const o of items) {
    if (o.unit_type) unitTypes.add(o.unit_type);
    if (o.territory_location_code) territories.add(o.territory_location_code);
  }
  return {
    unitTypes: [...unitTypes].sort(),
    territories: [...territories].sort(),
  };
}
