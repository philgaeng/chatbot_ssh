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

import { OrgTreeNode } from "./OrgTreeNode";
import { OrgEditor } from "./OrgEditor";
import { OrgCsvImport } from "./OrgCsvImport";
import { buildForest, groupRoots, type OrgForestNode } from "./orgVocab";

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

  const groups = useMemo(() => {
    if (!orgs) return { government: [], independent: [] };
    return groupRoots(buildForest(orgs));
  }, [orgs]);

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

      {loading ? (
        <div className="space-y-2" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      ) : loadError ? (
        <ErrorCard message="Couldn't load the organisation tree." onRetry={() => void load()} />
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
