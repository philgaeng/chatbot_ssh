"use client";

/**
 * <PositionTypesPanel> — the position-types catalog (DESIGN §D1/§D3/§4.4, Frame 06).
 *
 * Self-contained: lists position types (`listPositionTypes`), creates/edits them via
 * <PositionTypeEditor>, deletes with the backend 409 in-use guard surfaced friendly, and
 * opens <ReviewHoldersModal> to inspect who holds a type. Each row shows its owning level
 * (System / an org node) since the catalog is org-scoped (§4.4).
 *
 * When an edit changes the default role, the amber "Heads up" drift card appears — the
 * holders keep their current role (no silent re-sync, doc 16 §4); the admin can review them.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  listPositionTypes,
  listOrganizations,
  deletePositionType,
  type PositionTypeItem,
  type OrganizationItem,
} from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { Bilingual } from "@/components/shared/Bilingual";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { ErrorCard } from "@/components/ui/ErrorCard";

import { PositionTypeEditor } from "./PositionTypeEditor";
import { ReviewHoldersModal } from "./ReviewHoldersModal";
import {
  UNIT_TYPES,
  owningLevelLabel,
  unitTypeLabel,
  orgNameMap,
} from "./orgVocab";

type EditorState = { mode: "create" } | { mode: "edit"; pt: PositionTypeItem };

export function PositionTypesPanel({ canEdit }: { canEdit: boolean }) {
  const [items, setItems] = useState<PositionTypeItem[] | null>(null);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  const [editor, setEditor] = useState<EditorState | null>(null);
  const [reviewFor, setReviewFor] = useState<{ pt: PositionTypeItem; newDefault?: string } | null>(
    null,
  );

  const [query, setQuery] = useState("");
  const [unitFilter, setUnitFilter] = useState<string[]>([]);

  const orgNames = useMemo(() => orgNameMap(orgs), [orgs]);

  // Client-side search + office-type filter over the loaded catalog.
  const filtered = useMemo(() => {
    if (!items) return items;
    const q = query.trim().toLowerCase();
    return items.filter((pt) => {
      // Office-type filter: keep positions usable at any of the selected unit types.
      if (unitFilter.length > 0 && !unitFilter.some((u) => pt.allowed_unit_types.includes(u))) {
        return false;
      }
      if (q) {
        const hay =
          `${pt.display_name} ${pt.display_name_ne ?? ""} ${pt.position_key}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [items, query, unitFilter]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [pts, orgList] = await Promise.all([
        listPositionTypes(),
        listOrganizations(undefined, { tree: true }).catch(() => [] as OrganizationItem[]),
      ]);
      setItems(pts);
      setOrgs(orgList);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function handleSaved(_updated: PositionTypeItem, _before: EditorState | null) {
    // Positions no longer carry a role (DESIGN-cast-model §3.2), so an edit can't change a
    // default role — the old "role drift → review holders" prompt retired with the coupling.
    setEditor(null);
    void load();
  }

  async function handleDelete(pt: PositionTypeItem) {
    if (typeof window !== "undefined") {
      const ok = window.confirm(`Delete position type "${pt.display_name}"?`);
      if (!ok) return;
    }
    setActionError(null);
    try {
      await deletePositionType(pt.position_type_id);
      await load();
    } catch (e) {
      // 409 while referenced by another position or held by any officer — friendly stop.
      setActionError(e);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className={`text-lg font-semibold ${textTokens.heading}`}>Position types</h2>
          <p className={`text-sm ${textTokens.secondary}`}>
            The set of job titles officers can hold, each with a default responsibility.
          </p>
        </div>
        {canEdit && (
          <button
            type="button"
            onClick={() => setEditor({ mode: "create" })}
            className="shrink-0 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            + Add position type
          </button>
        )}
      </div>

      <ErrorNotice error={actionError} />

      {loading ? (
        <div className="space-y-2" aria-busy>
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      ) : loadError ? (
        <ErrorCard message="Couldn't load position types." onRetry={() => void load()} />
      ) : items && items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
          <p className={`text-sm ${textTokens.body}`}>No position types yet.</p>
          {canEdit && (
            <button
              type="button"
              onClick={() => setEditor({ mode: "create" })}
              className="mt-3 rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              Add a position type
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by title…"
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 sm:max-w-xs"
            />
            {(query || unitFilter.length > 0) && (
              <div className="flex items-center gap-3">
                <span className={`text-xs ${textTokens.secondary}`}>
                  {filtered?.length ?? 0} of {items?.length ?? 0}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setQuery("");
                    setUnitFilter([]);
                  }}
                  className="rounded px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>

          {/* Office-type filters (same vocabulary as the editor's "Used at"). */}
          <div className="flex flex-wrap gap-2">
            {UNIT_TYPES.map((ut) => {
              const on = unitFilter.includes(ut);
              return (
                <button
                  key={ut}
                  type="button"
                  onClick={() =>
                    setUnitFilter((prev) =>
                      prev.includes(ut) ? prev.filter((x) => x !== ut) : [...prev, ut],
                    )
                  }
                  aria-pressed={on}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                    on
                      ? "border-blue-300 bg-blue-100 text-blue-700"
                      : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {unitTypeLabel(ut)}
                </button>
              );
            })}
          </div>

          {filtered && filtered.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
              <p className={`text-sm ${textTokens.body}`}>
                No position types match your search or office-type filters.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
              {filtered?.map((pt) => (
                <div key={pt.position_type_id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <div className={`text-sm font-medium ${textTokens.heading}`}>
                      <Bilingual en={pt.display_name} ne={pt.display_name_ne} />
                    </div>
                    <div className={`mt-0.5 text-xs ${textTokens.secondary}`}>
                      {pt.allowed_unit_types.length > 0
                        ? pt.allowed_unit_types.map(unitTypeLabel).join(" · ")
                        : "Job title"}
                    </div>
                  </div>
                  <span className="shrink-0 rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] font-medium text-gray-600">
                    {owningLevelLabel(pt.owner_organization_id, orgNames)}
                  </span>
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setReviewFor({ pt })}
                      className="rounded px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
                    >
                      Review holders
                    </button>
                    {canEdit && (
                      <>
                        <button
                          type="button"
                          onClick={() => setEditor({ mode: "edit", pt })}
                          className="rounded px-2 py-0.5 text-xs font-medium text-gray-600 hover:bg-gray-100"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(pt)}
                          className="rounded px-2 py-0.5 text-xs font-medium text-red-700 hover:bg-red-50"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {editor && (
        <PositionTypeEditor
          mode={editor.mode}
          positionType={editor.mode === "edit" ? editor.pt : undefined}
          allPositionTypes={items ?? []}
          onSaved={(updated) => handleSaved(updated, editor)}
          onCancel={() => setEditor(null)}
        />
      )}

      {reviewFor && (
        <ReviewHoldersModal
          positionType={reviewFor.pt}
          orgNames={orgNames}
          newDefaultRoleKey={reviewFor.newDefault}
          onClose={() => setReviewFor(null)}
        />
      )}
    </div>
  );
}

export default PositionTypesPanel;
