// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <OrgTree> — the org forest editor (DESIGN §4.2, Frames 02 & 12).
 *
 * Self-contained: fetches the whole forest via `listOrganizations(undefined, {tree:true})`,
 * renders it as two groups — the government reporting line and independent roots
 * (contractors / development partners) — with expand/collapse, and hosts
 * create / edit / reparent / delete through <OrgEditor> and CSV bulk-load through
 * <OrgCsvImport>. Reparent is cycle-guarded in the picker (self + descendants excluded);
 * a server 422/403/409 still surfaces via <ErrorNotice>.
 *
 * Replaces the flat OrganizationsTab list (RB-4).
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { listOrganizations, deleteOrganization, type OrganizationItem } from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { ErrorCard } from "@/components/ui/ErrorCard";
import { prettyLocation } from "@/lib/prettyLocation";
import { Search } from "lucide-react";

import { OrgTreeNode } from "./OrgTreeNode";
import { OrgEditor } from "./OrgEditor";
import { OrgCsvImport } from "./OrgCsvImport";
import { buildForest, groupRoots, unitTypeLabel, type OrgForestNode } from "./orgVocab";
import {
  filterForest,
  countMatches,
  idsInForest,
  availableFilterValues,
  isOrgFilterActive,
  EMPTY_ORG_FILTER,
  type OrgFilterCriteria,
} from "./orgFilter";

type EditorState =
  | { mode: "create"; presetParentId: string | null }
  | { mode: "edit"; org: OrganizationItem };

function collectExpandableIds(roots: OrgForestNode[]): Set<string> {
  const ids = new Set<string>();
  const walk = (n: OrgForestNode) => {
    if (n.children.length > 0) {
      ids.add(n.org.organization_id);
      n.children.forEach(walk);
    }
  };
  roots.forEach(walk);
  return ids;
}

function Group({
  title,
  subtitle,
  roots,
  canEdit,
  expanded,
  onToggle,
  onEdit,
  onAddChild,
  onDelete,
  contextIds,
}: {
  title: string;
  subtitle?: string;
  roots: OrgForestNode[];
  canEdit: boolean;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onEdit: (org: OrganizationItem) => void;
  onAddChild: (parent: OrganizationItem) => void;
  onDelete: (org: OrganizationItem) => void;
  contextIds?: Set<string>;
}) {
  if (roots.length === 0) return null;
  return (
    <section>
      <h3 className={`text-xs font-semibold uppercase tracking-wide ${textTokens.secondary}`}>
        {title}
      </h3>
      {subtitle && <p className={`mb-1 text-xs ${textTokens.muted}`}>{subtitle}</p>}
      <div className="mt-1 rounded-lg border border-gray-200 bg-white p-1">
        {roots.map((r) => (
          <OrgTreeNode
            key={r.org.organization_id}
            node={r}
            canEdit={canEdit}
            expanded={expanded}
            onToggle={onToggle}
            onEdit={onEdit}
            onAddChild={onAddChild}
            onDelete={onDelete}
            contextIds={contextIds}
          />
        ))}
      </div>
    </section>
  );
}

export function OrgTree({
  canEdit,
  canCreateRoot,
}: {
  canEdit: boolean;
  /** May create a new institutional (government/local-gov/donor) root. Defaults to canEdit. */
  canCreateRoot?: boolean;
}) {
  const mayCreateRoot = canCreateRoot ?? canEdit;
  const [orgs, setOrgs] = useState<OrganizationItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [csvOpen, setCsvOpen] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  const [filter, setFilter] = useState<OrgFilterCriteria>(EMPTY_ORG_FILTER);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const items = await listOrganizations(undefined, { tree: true });
      setOrgs(items);
      // Default-expand every node with children so the small happy-path forest is visible.
      setExpanded(collectExpandableIds(buildForest(items)));
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filterActive = isOrgFilterActive(filter);

  /**
   * The pruned forest (GRM-086). Matches keep their ancestors, which render as context — a hit
   * without the line above it is not an answer.
   */
  const filtered = useMemo(() => {
    if (!orgs) return [];
    return filterForest(buildForest(orgs), filter);
  }, [orgs, filter]);

  const groups = useMemo(() => groupRoots(filtered), [filtered]);

  const matchCount = useMemo(() => countMatches(filtered), [filtered]);

  /** Ids kept only to place a match below them — de-emphasised, and not counted as results. */
  const contextIds = useMemo(() => {
    if (!filterActive) return undefined;
    const out = new Set<string>();
    const walk = (list: typeof filtered) => {
      for (const n of list) {
        if (!n.isMatch) out.add(n.org.organization_id);
        walk(n.children);
      }
    };
    walk(filtered);
    return out;
  }, [filtered, filterActive]);

  const choices = useMemo(() => availableFilterValues(orgs ?? []), [orgs]);

  /* A filtered tree must be OPEN, or the matches sit behind collapsed parents and the filter
     looks like it found nothing. Expanding every kept node is correct because the pruned forest
     is small by construction.
     ⚠ And CLEARING the filter has to restore the default expansion. Without the else-branch the
     tree keeps whatever the last filtered set expanded, so clearing a search leaves the forest
     half-collapsed with no explanation — the filter appears to have broken the tree. */
  useEffect(() => {
    if (!orgs) return;
    setExpanded(
      filterActive ? idsInForest(filtered) : collectExpandableIds(buildForest(orgs)),
    );
  }, [filterActive, filtered, orgs]);

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  async function handleDelete(org: OrganizationItem) {
    if (typeof window !== "undefined") {
      const ok = window.confirm(`Delete "${org.name}"? This cannot be undone.`);
      if (!ok) return;
    }
    setActionError(null);
    try {
      await deleteOrganization(org.organization_id);
      await load();
    } catch (e) {
      // Delete guards return a plain-language 409; ErrorNotice renders it friendly.
      setActionError(e);
    }
  }

  const onSaved = () => {
    setEditor(null);
    void load();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className={`text-lg font-semibold ${textTokens.heading}`}>Organisation tree</h2>
          <p className={`text-sm ${textTokens.secondary}`}>
            The government reporting line plus independent organisations (contractors, development
            partners).
          </p>
        </div>
        {canEdit && (
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setCsvOpen(true)}
              className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Import CSV
            </button>
            <button
              type="button"
              onClick={() => setEditor({ mode: "create", presetParentId: null })}
              className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              + Add organisation
            </button>
          </div>
        )}
      </div>

      <ErrorNotice error={actionError} />

      {/* Search + filters (GRM-086). Client-side over the whole forest: the server's `q` returns a
          FLAT set, so a match whose parent does not match comes back without it and the tree
          cannot be rebuilt. See orgFilter.ts. Hidden while the forest is empty — a filter bar over
          nothing is furniture. */}
      {!loading && !loadError && orgs && orgs.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex min-w-[180px] flex-1 items-center gap-2 rounded border border-gray-300 bg-white px-2.5 py-1.5">
            <Search size={15} className="shrink-0 text-gray-400" aria-hidden />
            <input
              value={filter.q}
              onChange={(e) => setFilter((f) => ({ ...f, q: e.target.value }))}
              placeholder="Search organisations…"
              aria-label="Search organisations"
              className="w-full text-sm outline-none"
            />
          </div>
          {/* Type is `unit_type`, NOT `org_category`: category is root-only and inherited, so
              filtering on it would silently drop every child whose column is null — and the two
              groups below already express category. */}
          <select
            value={filter.unitType}
            onChange={(e) => setFilter((f) => ({ ...f, unitType: e.target.value }))}
            aria-label="Type of organisation"
            className="rounded border border-gray-300 bg-white px-2 py-1.5 text-sm"
          >
            <option value="">Type — any</option>
            {choices.unitTypes.map((u) => (
              <option key={u} value={u}>{unitTypeLabel(u)}</option>
            ))}
          </select>
          <select
            value={filter.territory}
            onChange={(e) => setFilter((f) => ({ ...f, territory: e.target.value }))}
            aria-label="Search area"
            className="rounded border border-gray-300 bg-white px-2 py-1.5 text-sm"
          >
            <option value="">Area — any</option>
            {choices.territories.map((code) => (
              <option key={code} value={code}>{prettyLocation(code)}</option>
            ))}
          </select>
        </div>
      )}

      {filterActive && matchCount > 0 && (
        <p className={`text-xs ${textTokens.muted}`}>
          {matchCount} {matchCount === 1 ? "organisation matches" : "organisations match"}
          {filter.q.trim() ? ` \u201c${filter.q.trim()}\u201d` : ""}.
          {contextIds && contextIds.size > 0
            ? ` ${contextIds.size} more shown to place ${matchCount === 1 ? "it" : "them"}.`
            : ""}
        </p>
      )}

      {loading ? (
        <div className="space-y-2" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      ) : loadError ? (
        <ErrorCard message="Couldn't load the organisation tree." onRetry={() => void load()} />
      ) : filterActive && matchCount === 0 ? (
        /* "Nothing here" and "nothing matched" look identical and mean opposite things — an admin
           who cannot tell them apart concludes the screen is broken. Same rule as GRM-087. */
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center">
          <p className={`text-sm font-medium ${textTokens.body}`}>
            No organisations match{filter.q.trim() ? ` \u201c${filter.q.trim()}\u201d` : " these filters"}.
          </p>
          <button
            type="button"
            onClick={() => setFilter(EMPTY_ORG_FILTER)}
            className="mt-2 text-sm font-medium text-blue-700 hover:underline"
          >
            Clear the filters
          </button>
        </div>
      ) : orgs && orgs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className={`text-sm ${textTokens.body}`}>No organisation units yet.</p>
          {canEdit && (
            <div className="mt-3 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => setEditor({ mode: "create", presetParentId: null })}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700"
              >
                Add the top ministry
              </button>
              <button
                type="button"
                onClick={() => setCsvOpen(true)}
                className="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
              >
                Import from CSV
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-5">
          <Group
            title="Government reporting line"
            roots={groups.government}
            contextIds={contextIds}
            canEdit={canEdit}
            expanded={expanded}
            onToggle={toggle}
            onEdit={(org) => setEditor({ mode: "edit", org })}
            onAddChild={(parent) => setEditor({ mode: "create", presetParentId: parent.organization_id })}
            onDelete={handleDelete}
          />
          <Group
            title="Independent organisations"
            subtitle="Own roots, own subtrees — development partners and contractors."
            roots={groups.independent}
            contextIds={contextIds}
            canEdit={canEdit}
            expanded={expanded}
            onToggle={toggle}
            onEdit={(org) => setEditor({ mode: "edit", org })}
            onAddChild={(parent) => setEditor({ mode: "create", presetParentId: parent.organization_id })}
            onDelete={handleDelete}
          />
        </div>
      )}

      {editor && orgs && (
        <OrgEditor
          mode={editor.mode}
          org={editor.mode === "edit" ? editor.org : undefined}
          presetParentId={editor.mode === "create" ? editor.presetParentId : null}
          allOrgs={orgs}
          canEdit={canEdit}
          canCreateRoot={mayCreateRoot}
          onSaved={onSaved}
          onCancel={() => setEditor(null)}
        />
      )}

      {csvOpen && (
        <OrgCsvImport
          onImported={() => void load()}
          onClose={() => setCsvOpen(false)}
        />
      )}
    </div>
  );
}

export default OrgTree;
