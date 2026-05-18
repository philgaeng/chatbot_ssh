"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listOfficerRoster,
  type OfficerRosterEntry,
  type OrganizationItem,
  type PackageItem,
  type ProjectItem,
  type ProjectOrgItem,
} from "@/lib/api";
import { EditOfficerModal } from "@/components/settings/OfficerModals";
import { ProjectOfficerModal } from "@/components/settings/ProjectOfficerModal";

type RoleChoice = { key: string; label: string };

function officerOnProject(
  o: OfficerRosterEntry,
  project: ProjectItem,
  packageIds: Set<string>,
): boolean {
  if (o.project_codes?.includes(project.short_code)) return true;
  return (o.package_ids ?? []).some((id) => packageIds.has(id));
}

function officersForOrgOnProject(
  roster: OfficerRosterEntry[],
  project: ProjectItem,
  packageIds: Set<string>,
  organizationId: string,
): OfficerRosterEntry[] {
  return roster.filter(
    (o) =>
      o.organization_ids.includes(organizationId) &&
      officerOnProject(o, project, packageIds),
  );
}

function coverageLine(o: OfficerRosterEntry, pkgById: Record<string, PackageItem>): string {
  const parts: string[] = [];
  if (o.project_codes?.length) parts.push(...o.project_codes);
  (o.package_ids ?? []).forEach((id) => {
    const code = pkgById[id]?.package_code;
    if (code) parts.push(code);
  });
  if (o.location_codes.length) parts.push(...o.location_codes.slice(0, 2));
  return parts.length ? parts.join(", ") : "—";
}

export function ProjectStaffingSection({
  project,
  projectActors,
  orgs,
  grmRoleChoices,
  packages,
}: {
  project: ProjectItem;
  projectActors: ProjectOrgItem[];
  orgs: OrganizationItem[];
  grmRoleChoices: RoleChoice[];
  packages: PackageItem[];
}) {
  const [roster, setRoster] = useState<OfficerRosterEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editOfficer, setEditOfficer] = useState<OfficerRosterEntry | null>(null);
  const [addOfficerOrg, setAddOfficerOrg] = useState<{ id: string; name: string } | null>(null);

  const packageIds = useMemo(() => new Set(packages.map((p) => p.package_id)), [packages]);
  const pkgById = useMemo(
    () => Object.fromEntries(packages.map((p) => [p.package_id, p])),
    [packages],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRoster(await listOfficerRoster());
    } catch {
      setRoster([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onProject = useMemo(
    () => roster.filter((o) => officerOnProject(o, project, packageIds)),
    [roster, project, packageIds],
  );

  const actorWarnings = useMemo(() => {
    const warnings: string[] = [];
    const seen = new Set<string>();
    for (const po of projectActors) {
      if (!po.organization_id || seen.has(po.organization_id)) continue;
      seen.add(po.organization_id);
      const covered = officersForOrgOnProject(roster, project, packageIds, po.organization_id);
      if (covered.length === 0) {
        const name = orgs.find((x) => x.organization_id === po.organization_id)?.name ?? po.organization_id;
        warnings.push(`No officer scoped for ${name} on this project.`);
      }
    }
    return warnings;
  }, [projectActors, roster, project, packageIds, orgs]);

  return (
    <div className="mb-6 border-t border-gray-100 pt-6">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Staffing</h3>
          <p className="text-xs text-gray-500 mt-0.5 max-w-2xl">
            Officers whose jurisdiction includes this project or its packages. Add or edit scopes here;
            GRM roles come from the Workflows tab.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            const first = projectActors[0];
            const name = first
              ? orgs.find((o) => o.organization_id === first.organization_id)?.name
              : undefined;
            if (first) {
              setAddOfficerOrg({ id: first.organization_id, name: name ?? first.organization_id });
            }
          }}
          disabled={projectActors.length === 0}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 shrink-0"
        >
          + Add officer
        </button>
      </div>

      {actorWarnings.length > 0 && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 space-y-1">
          {actorWarnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-xs text-gray-400 animate-pulse">Loading officers…</p>
      ) : onProject.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No officers scoped to this project yet.</p>
      ) : (
        <div className="border border-gray-200 rounded-lg overflow-hidden max-w-2xl">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left border-b border-gray-200">
                <th className="px-3 py-2 text-xs font-medium text-gray-500">Officer</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-500">Organization</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-500">GRM roles</th>
                <th className="px-3 py-2 text-xs font-medium text-gray-500">Coverage</th>
                <th className="px-3 py-2 w-24" />
              </tr>
            </thead>
            <tbody>
              {onProject.map((o) => (
                <tr key={o.user_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2.5 font-medium text-gray-800">{o.display_name}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-600">
                    {o.organization_ids.map((id) => orgs.find((x) => x.organization_id === id)?.name ?? id).join(", ")}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-gray-600">
                    {o.role_keys.map((k) => grmRoleChoices.find((r) => r.key === k)?.label ?? k).join(", ")}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-gray-500 font-mono">{coverageLine(o, pkgById)}</td>
                  <td className="px-3 py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => setEditOfficer(o)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Manage
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editOfficer && (
        <EditOfficerModal
          officer={editOfficer}
          roleChoices={grmRoleChoices}
          onClose={() => setEditOfficer(null)}
          onSaved={load}
        />
      )}

      {addOfficerOrg && (
        <ProjectOfficerModal
          project={project}
          organizationId={addOfficerOrg.id}
          organizationName={addOfficerOrg.name}
          roleChoices={grmRoleChoices}
          onClose={() => setAddOfficerOrg(null)}
          onSuccess={load}
        />
      )}
    </div>
  );
}
