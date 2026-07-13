"use client";

/**
 * <OfficersTabV2> — the single self-contained Officers surface page.tsx renders (RB-3/RB-4,
 * frames 03 + 11). A small sub-nav switches between:
 *   • Invite   — invite-AS-RESULT flow (<InviteOfficer>, DESIGN §4.1)
 *   • Directory — roster + lifecycle (<OfficersDirectory>, DESIGN §7.F)
 *
 * Sending an invite bumps a refresh key so the Directory re-fetches when next shown.
 */

import { useState } from "react";
import { UserPlus, Users } from "lucide-react";

import { primary, text as textTokens } from "@/lib/design-tokens";
import { InviteOfficer } from "./InviteOfficer";
import { OfficersDirectory } from "./OfficersDirectory";

type SubView = "directory" | "invite";

export function OfficersTabV2({
  canInvite,
  canManage,
}: {
  canInvite: boolean;
  canManage: boolean;
}) {
  const [view, setView] = useState<SubView>("directory");
  // Remount the Directory after an invite so it re-loads the roster.
  const [dirKey, setDirKey] = useState(0);

  const tabs: { key: SubView; label: string; icon: typeof Users; show: boolean }[] = [
    { key: "directory", label: "Directory", icon: Users, show: true },
    { key: "invite", label: "Invite", icon: UserPlus, show: canInvite },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 border-b border-gray-200">
        {tabs
          .filter((t) => t.show)
          .map((t) => {
            const Icon = t.icon;
            const active = view === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setView(t.key)}
                aria-current={active ? "page" : undefined}
                className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
                  active
                    ? `${primary.border} ${primary.text}`
                    : `border-transparent ${textTokens.secondary} hover:text-gray-800`
                }`}
              >
                <Icon size={15} aria-hidden />
                {t.label}
              </button>
            );
          })}
      </div>

      {view === "invite" && canInvite ? (
        <InviteOfficer
          canInvite={canInvite}
          onInvited={() => setDirKey((k) => k + 1)}
        />
      ) : (
        <OfficersDirectory key={dirKey} canManage={canManage} />
      )}
    </div>
  );
}

export default OfficersTabV2;
