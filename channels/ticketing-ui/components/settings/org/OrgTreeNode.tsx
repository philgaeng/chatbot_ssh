// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <OrgTreeNode> — one row in the org forest (DESIGN §4.2, Frame 02/12).
 *
 * Renders: bilingual label, an org_category chip, a unit_type chip, a territory hint,
 * an expand/collapse caret (pure CSS — no icon dependency), and a "⋯" actions menu
 * (Edit · Add child · Delete) gated by `canEdit`. Children render recursively.
 */

import { useState } from "react";

import type { OrganizationItem } from "@/lib/api";
import { orgCategoryBadge, text as textTokens } from "@/lib/design-tokens";
import { Bilingual } from "@/components/shared/Bilingual";

import {
  type OrgForestNode,
  orgCategoryLabel,
  unitTypeLabel,
  territoryHint,
} from "./orgVocab";

function Caret({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-label={open ? "Collapse" : "Expand"}
      className="flex h-5 w-5 shrink-0 items-center justify-center rounded hover:bg-gray-100"
    >
      <span
        className={`h-0 w-0 border-y-[4px] border-l-[6px] border-y-transparent border-l-gray-500 transition-transform ${
          open ? "rotate-90" : ""
        }`}
      />
    </button>
  );
}

function CategoryChip({ category }: { category: string | null | undefined }) {
  if (!category) return null;
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[11px] font-medium ${orgCategoryBadge(category)}`}>
      {orgCategoryLabel(category)}
    </span>
  );
}

function UnitTypeChip({ unitType }: { unitType: string | null | undefined }) {
  if (!unitType) return null;
  return (
    <span className="rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-700">
      {unitTypeLabel(unitType)}
    </span>
  );
}

function ActionsMenu({
  org,
  onEdit,
  onAddChild,
  onDelete,
}: {
  org: OrganizationItem;
  onEdit: (org: OrganizationItem) => void;
  onAddChild: (parent: OrganizationItem) => void;
  onDelete: (org: OrganizationItem) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="More actions"
        className="rounded px-2 py-0.5 text-sm font-bold leading-none text-gray-500 hover:bg-gray-100 hover:text-gray-700"
      >
        ⋯
      </button>
      {open && (
        <>
          {/* click-away backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div
            role="menu"
            className="absolute right-0 z-20 mt-1 w-40 overflow-hidden rounded-md border border-gray-200 bg-white py-1 shadow-lg"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onEdit(org);
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-50"
            >
              Edit
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onAddChild(org);
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-50"
            >
              Add child office
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onDelete(org);
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-red-700 hover:bg-red-50"
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function OrgTreeNode({
  node,
  canEdit,
  expanded,
  onToggle,
  onEdit,
  onAddChild,
  onDelete,
  contextIds,
}: {
  node: OrgForestNode;
  canEdit: boolean;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onEdit: (org: OrganizationItem) => void;
  onAddChild: (parent: OrganizationItem) => void;
  onDelete: (org: OrganizationItem) => void;
  /** While a filter is on (GRM-086): ids shown only to locate a match below them. Rendered
   *  de-emphasised — present and readable, visibly not the answer. Absent when unfiltered. */
  contextIds?: Set<string>;
}) {
  const { org, children, depth } = node;
  const hasChildren = children.length > 0;
  const isOpen = expanded.has(org.organization_id);
  const hint = territoryHint(org);
  const isContext = contextIds?.has(org.organization_id) ?? false;

  return (
    <div>
      <div
        className="group flex items-center gap-2 rounded px-1 py-1.5 hover:bg-gray-50"
        style={{ paddingLeft: `${depth * 1.25 + 0.25}rem` }}
      >
        {hasChildren ? (
          <Caret open={isOpen} onClick={() => onToggle(org.organization_id)} />
        ) : (
          <span className="inline-block h-5 w-5 shrink-0" aria-hidden />
        )}

        <span
          className={
            isContext
              ? `text-sm font-normal ${textTokens.muted}`
              : `text-sm font-medium ${textTokens.heading}`
          }
        >
          <Bilingual en={org.name} ne={org.display_name_ne} />
        </span>

        {!org.is_active && (
          <span className="rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-600">
            Inactive
          </span>
        )}
        <CategoryChip category={org.org_category} />
        <UnitTypeChip unitType={org.unit_type} />
        {hint && <span className={`text-xs ${textTokens.secondary}`}>{hint}</span>}

        {canEdit && (
          <div className="ml-auto flex items-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
            <button
              type="button"
              onClick={() => onAddChild(org)}
              className="rounded px-2 py-0.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
            >
              + Child
            </button>
            <button
              type="button"
              onClick={() => onEdit(org)}
              className="rounded px-2 py-0.5 text-xs font-medium text-gray-600 hover:bg-gray-100"
            >
              Edit
            </button>
            <ActionsMenu org={org} onEdit={onEdit} onAddChild={onAddChild} onDelete={onDelete} />
          </div>
        )}
      </div>

      {hasChildren && isOpen && (
        <div>
          {children.map((child) => (
            <OrgTreeNode
              key={child.org.organization_id}
              node={child}
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
      )}
    </div>
  );
}

export default OrgTreeNode;
