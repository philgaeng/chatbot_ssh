"use client";

/**
 * <ProjectPartnersSection> — the organizations this project names (doc 13 §5B order 5, ui/04).
 *
 * One block per entry in the **project type's** organization catalog (`actor_roles`), in the
 * author's own words — "Executing Agency", "Ward Office", "Concessionaire" — not words we
 * picked. Filled values live in `project_organizations.org_role`
 * (DECISION-author-defined-slots §3.3); the type says which ones are required (go-live B1) and
 * which one a grievance is recorded against.
 *
 * Replaces the hardcoded implementing agency + donors pair, which could only express the two
 * organizations the platform happened to know about. Officers are still staffed under
 * Project-wide staffing, never here.
 */
import { useCallback, useEffect, useState } from "react";
import {
  addProjectOrg,
  getProjectActorRoles,
  listProjectOrganizations,
  removeProjectOrg,
  type OrgRole,
  type OrganizationItem,
  type ProjectItem,
  type ProjectOrgItem,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

export function ProjectPartnersSection({
  project,
  orgs,
  canEdit,
  onUpdated,
  flash,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  canEdit: boolean;
  onUpdated: (p: ProjectItem) => void;
  flash: (msg: string) => void;
}) {
  const [catalog, setCatalog] = useState<OrgRole[]>([]);
  const [links, setLinks] = useState<ProjectOrgItem[]>(project.organizations ?? []);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [roles, linked] = await Promise.all([
        getProjectActorRoles(project.project_id),
        listProjectOrganizations(project.project_id),
      ]);
      setCatalog(roles);
      setLinks(linked);
    } catch {
      setCatalog([]);
    } finally {
      setLoading(false);
    }
  }, [project.project_id]);

  useEffect(() => {
    void load();
  }, [load]);

  function orgById(id: string) {
    return orgs.find((o) => o.organization_id === id) ?? null;
  }

  function filledFor(roleKey: string) {
    return links.filter((l) => l.org_role === roleKey);
  }

  async function assign(roleKey: string, orgId: string) {
    setWorking(true);
    try {
      await addProjectOrg(project.project_id, orgId, roleKey);
      const linked = await listProjectOrganizations(project.project_id);
      setLinks(linked);
      setAdding(null);
      onUpdated({ ...project, organizations: linked });
      flash("Saved ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setWorking(false);
    }
  }

  async function unassign(orgId: string) {
    setWorking(true);
    try {
      await removeProjectOrg(project.project_id, orgId);
      const linked = await listProjectOrganizations(project.project_id);
      setLinks(linked);
      onUpdated({ ...project, organizations: linked });
      flash("Removed");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setWorking(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-400 animate-pulse">Loading…</p>;

  if (catalog.length === 0) {
    return (
      <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 max-w-xl">
        This project&apos;s type does not name any organizations yet. Add them to the type under
        Settings → Project types.
      </p>
    );
  }

  return (
    <div className="space-y-6 max-w-xl">
      {catalog.map((role) => {
        const filled = filledFor(role.key);
        const available = orgs.filter(
          (o) => o.is_active && !filled.some((f) => f.organization_id === o.organization_id),
        );
        return (
          <div key={role.key}>
            <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">
              {role.label}{" "}
              {role.required ? (
                <span className="normal-case tracking-normal font-semibold text-red-700">
                  — required before go-live
                </span>
              ) : (
                <span className="normal-case tracking-normal font-normal text-gray-400">— optional</span>
              )}
            </div>
            {role.description && <p className="text-xs text-gray-500 mb-2">{role.description}</p>}

            {filled.length === 0 ? (
              <p
                className={`text-xs rounded px-3 py-2 mb-2 ${
                  role.required
                    ? "text-amber-800 bg-amber-50 border border-amber-200"
                    : "text-gray-400 italic"
                }`}
              >
                {role.required ? "Not named yet — the project cannot go live without it." : "None named."}
              </p>
            ) : (
              <ul className="space-y-1.5 mb-2">
                {filled.map((f) => {
                  const org = orgById(f.organization_id);
                  return (
                    <li
                      key={f.organization_id}
                      className="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2.5"
                    >
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-blue-50 text-[11px] font-bold text-blue-700">
                        {initials(org?.name ?? f.organization_id)}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-medium text-gray-900 truncate">
                          {org?.name ?? f.organization_id}
                        </span>
                        {role.is_routing_anchor && (
                          <span className="block text-xs text-gray-500">
                            Grievances on this project are recorded against this organization
                          </span>
                        )}
                      </span>
                      {canEdit && (
                        <button
                          type="button"
                          onClick={() => void unassign(f.organization_id)}
                          disabled={working}
                          className="text-xs font-semibold text-red-600 hover:underline disabled:opacity-40"
                        >
                          Remove
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}

            {canEdit && (
              adding === role.key ? (
                <select
                  value=""
                  autoFocus
                  disabled={working}
                  onChange={(e) => e.target.value && void assign(role.key, e.target.value)}
                  onBlur={() => setAdding(null)}
                  className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
                  aria-label={`Choose the ${role.label}`}
                >
                  <option value="">— choose an organization —</option>
                  {available.map((o) => (
                    <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
                  ))}
                </select>
              ) : (
                <button
                  type="button"
                  onClick={() => setAdding(role.key)}
                  className="text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
                >
                  {filled.length ? "+ Add another" : `+ Name the ${role.label}`}
                </button>
              )
            )}

            {role.required_package && (
              <p className="text-xs text-gray-400 mt-1.5">
                Can also be named for each lot, under Packages.
              </p>
            )}
          </div>
        );
      })}

      <p className="text-xs text-gray-400 border-t border-gray-100 pt-3">
        These organizations come from the project type. Officers are not added here — put people
        on levels under <span className="font-medium text-gray-500">Project-wide staffing</span>.
      </p>
    </div>
  );
}
