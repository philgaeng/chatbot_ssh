// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <OrganisationTab> — the Organisation surface shell (DESIGN §D1, §3, Frames 02/06/12).
 *
 * The single component `app/settings/page.tsx` renders for the Organisation domain. It
 * hosts a small sub-nav — "Org tree" and "Position types" — and mounts the self-contained
 * <OrgTree> and <PositionTypesPanel> behind it. The public surface is intentionally tiny
 * (just the two gating props) so the integration point stays stable.
 */

import { useState } from "react";

import { text as textTokens } from "@/lib/design-tokens";

import { OrgTree } from "./OrgTree";
import { PositionTypesPanel } from "./PositionTypesPanel";

type SubTab = "tree" | "positions";

export function OrganisationTab({
  canEdit,
  canCreateRoot,
}: {
  /** May build org structure / edit position types (org_admin+). */
  canEdit: boolean;
  /** May create a new institutional (government/local-gov/donor) root (super_admin). */
  canCreateRoot?: boolean;
}) {
  const [tab, setTab] = useState<SubTab>("tree");

  const subTabs: { key: SubTab; label: string }[] = [
    { key: "tree", label: "Org tree" },
    { key: "positions", label: "Position types" },
  ];

  return (
    <div className="space-y-5">
      <nav
        className="flex gap-1 border-b border-gray-200"
        role="tablist"
        aria-label="Organisation sections"
      >
        {subTabs.map((t) => {
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.key)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition ${
                active
                  ? "border-blue-600 text-blue-700"
                  : `border-transparent ${textTokens.secondary} hover:text-gray-800`
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </nav>

      {tab === "tree" ? (
        <OrgTree canEdit={canEdit} canCreateRoot={canCreateRoot} />
      ) : (
        <PositionTypesPanel canEdit={canEdit} />
      )}
    </div>
  );
}

export default OrganisationTab;
