"use client";

import { useEffect, useMemo, useState } from "react";
import {
  listCountries,
  type CountryItem,
  type OrganizationItem,
  type OrgRole,
} from "@/lib/api";
import { OrgCreateModal } from "@/components/settings/OrgCreateModal";

function defaultRoleKey(actorRoles: OrgRole[]): string {
  const preferred = ["implementing_agency", "donor", "main_contractor"];
  for (const k of preferred) {
    if (actorRoles.some((r) => r.key === k)) return k;
  }
  return actorRoles[0]?.key ?? "";
}

export function ProjectActorAddRow({
  actorRoles,
  orgs,
  defaultCountryCode,
  excludeOrganizationIds,
  onOrganizationCreated,
  onAdd,
  working = false,
  roleRequired = true,
  addLabel = "Add to project",
}: {
  actorRoles: OrgRole[];
  orgs: OrganizationItem[];
  defaultCountryCode: string;
  /** Orgs already linked at this level (project: one row per org). */
  excludeOrganizationIds: Set<string>;
  onOrganizationCreated: (org: OrganizationItem) => void;
  onAdd: (organizationId: string, orgRole: string) => Promise<void>;
  working?: boolean;
  roleRequired?: boolean;
  addLabel?: string;
}) {
  const [roleKey, setRoleKey] = useState("");
  const [orgId, setOrgId] = useState("");
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    setRoleKey(defaultRoleKey(actorRoles));
  }, [actorRoles]);

  useEffect(() => {
    listCountries()
      .then(setCountries)
      .catch(() => setCountries([]));
  }, []);

  const selectableOrgs = useMemo(
    () => orgs.filter((o) => !excludeOrganizationIds.has(o.organization_id)),
    [orgs, excludeOrganizationIds],
  );

  const allOrgIds = useMemo(() => new Set(orgs.map((o) => o.organization_id)), [orgs]);

  async function handleAdd() {
    setLocalError("");
    if (!orgId) {
      setLocalError("Select an organization or create a new one.");
      return;
    }
    if (roleRequired && !roleKey) {
      setLocalError("Select a role on the project.");
      return;
    }
    try {
      await onAdd(orgId, roleKey);
      setOrgId("");
      setRoleKey(defaultRoleKey(actorRoles));
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : "Failed to add");
    }
  }

  async function handleOrgCreated(org: OrganizationItem) {
    onOrganizationCreated(org);
    setShowCreateOrg(false);
    const role = roleKey || defaultRoleKey(actorRoles);
    if (role) {
      try {
        await onAdd(org.organization_id, role);
        setOrgId("");
        setRoleKey(defaultRoleKey(actorRoles));
      } catch (e: unknown) {
        setOrgId(org.organization_id);
        setLocalError(e instanceof Error ? e.message : "Organization created but could not link to project");
      }
    } else {
      setOrgId(org.organization_id);
    }
  }

  return (
    <>
      {showCreateOrg && (
        <OrgCreateModal
          countries={countries.length ? countries : [{ country_code: defaultCountryCode, name: defaultCountryCode, level_defs: [] }]}
          existingOrganizationIds={allOrgIds}
          defaultCountry={defaultCountryCode}
          onCreated={(org) => void handleOrgCreated(org)}
          onClose={() => setShowCreateOrg(false)}
        />
      )}

      <div className="space-y-2 max-w-2xl">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={roleKey}
            onChange={(e) => setRoleKey(e.target.value)}
            className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            {roleRequired && <option value="">— role —</option>}
            {actorRoles.map((r) => (
              <option key={r.key} value={r.key}>{r.label}</option>
            ))}
          </select>
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            className="text-sm border border-gray-300 rounded px-2 py-1.5 min-w-[12rem] focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">
              {selectableOrgs.length === 0 ? "— create or pick org —" : "— organization —"}
            </option>
            {selectableOrgs.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void handleAdd()}
            disabled={working || !orgId || (roleRequired && !roleKey)}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {addLabel}
          </button>
          <button
            type="button"
            onClick={() => setShowCreateOrg(true)}
            disabled={working}
            className="text-sm text-blue-600 hover:underline px-1 py-1.5"
          >
            + New organization
          </button>
        </div>
        {localError && <p className="text-xs text-red-600">{localError}</p>}
        <p className="text-xs text-gray-400">
          Add each partner once with its role, then use <span className="font-medium">Add officer</span> on that row.
        </p>
      </div>
    </>
  );
}
