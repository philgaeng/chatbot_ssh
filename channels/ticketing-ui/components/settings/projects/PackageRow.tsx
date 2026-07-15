"use client";

/**
 * <PackageRow> — one package row inside <ProjectEditor>: contractor/consultant org
 * bindings and package locations.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import {
  addPackageOrg,
  removePackageOrg,
  type PackageItem,
  type OrganizationItem,
  type OrgRole,
} from "@/lib/api";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { LocationSearch } from "@/components/LocationSearch";

export function PackageRow({
  projectId,
  pkg,
  orgs,
  actorRoles,
  expanded,
  onToggle,
  onUpdate,
  onActorsChange,
  onAddLoc,
  onRemoveLoc,
}: {
  projectId:    string;
  pkg:          PackageItem;
  orgs:         OrganizationItem[];
  actorRoles:   OrgRole[];
  expanded:     boolean;
  onToggle:     () => void;
  onUpdate:     (payload: Partial<PackageItem>) => Promise<void>;
  onActorsChange: (organizations: PackageItem["organizations"]) => void;
  onAddLoc:     (code: string) => Promise<void>;
  onRemoveLoc:  (code: string) => Promise<void>;
}) {
  const [codeVal, setCodeVal]       = useState(pkg.package_code);
  const [nameVal, setNameVal]       = useState(pkg.name);
  const [descVal, setDescVal]       = useState(pkg.description ?? "");
  const [addingOrg, setAddingOrg]   = useState("");
  const [addingRole, setAddingRole] = useState(actorRoles[0]?.key ?? "");
  const [actorWorking, setActorWorking] = useState(false);
  const [saving, setSaving]         = useState(false);
  const [dirty, setDirty]           = useState(false);

  const organizations = pkg.organizations ?? [];

  React.useEffect(() => {
    setCodeVal(pkg.package_code);
    setNameVal(pkg.name);
    setDescVal(pkg.description ?? "");
    setDirty(false);
  }, [pkg.package_id, pkg.package_code, pkg.name, pkg.description]);

  React.useEffect(() => {
    if (actorRoles.length && !actorRoles.some((r) => r.key === addingRole)) {
      setAddingRole(actorRoles[0].key);
    }
  }, [actorRoles, addingRole]);

  async function handleSave() {
    const codeErr = validateEntityCode(codeVal, "Package code");
    if (codeErr) return;
    setSaving(true);
    await onUpdate({
      package_code: normalizeEntityCodeInput(codeVal),
      name: nameVal.trim(),
      description: descVal.trim() || null,
    });
    setDirty(false);
    setSaving(false);
  }

  async function handleAddActor() {
    if (!addingOrg || !addingRole) return;
    setActorWorking(true);
    try {
      const item = await addPackageOrg(projectId, pkg.package_id, addingOrg, addingRole);
      onActorsChange([...organizations, item]);
      setAddingOrg("");
    } catch { /* */ }
    setActorWorking(false);
  }

  async function handleRemoveActor(organizationId: string, orgRole: string) {
    setActorWorking(true);
    try {
      await removePackageOrg(projectId, pkg.package_id, organizationId, orgRole);
      onActorsChange(organizations.filter(
        (o) => !(o.organization_id === organizationId && o.org_role === orgRole),
      ));
    } catch { /* */ }
    setActorWorking(false);
  }

  const actorSummary = organizations.length === 0
    ? <em className="text-gray-500">No actors</em>
    : organizations.map((po) => {
        const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
        const roleLabel = actorRoles.find((r) => r.key === po.org_role)?.label ?? po.org_role;
        return `${orgName} (${roleLabel})`;
      }).join(", ");

  return (
    <div className="border border-gray-200 rounded-lg">
      {/* Note: no overflow-hidden — LocationSearch uses a dropdown that must paint outside this card */}
      {/* Collapsed header — always visible; click to expand/collapse edit form */}
      <button
        onClick={onToggle}
        className={`group w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors cursor-pointer ${
          expanded ? "rounded-t-lg" : "rounded-lg"
        }`}
        title={expanded ? "Collapse" : "Click to edit"}
      >
        {/* Rotating chevron — right when collapsed, down when expanded */}
        <span
          className={`inline-block text-sm shrink-0 transition-transform duration-200 ${
            expanded ? "rotate-90 text-blue-500" : "text-gray-400"
          }`}
        >▶</span>
        <span className="font-mono text-xs text-gray-500 shrink-0">{pkg.package_code}</span>
        <span className={`font-medium text-sm flex-1 min-w-0 truncate ${expanded ? "text-blue-700" : "text-gray-800"}`}>
          {pkg.name}
        </span>
        <span className="text-xs text-gray-600 shrink-0 max-w-[40%] truncate" title={typeof actorSummary === "string" ? actorSummary : undefined}>
          {actorSummary}
        </span>
        {pkg.location_codes.length > 0 && (
          <div className="flex gap-1 shrink-0">
            {pkg.location_codes.map((c) => (
              <span key={c} className="text-xs font-mono bg-blue-100 text-blue-800 border border-blue-300 px-1.5 py-0.5 rounded">
                {c}
              </span>
            ))}
          </div>
        )}
        {!pkg.is_active && <span className="text-xs text-gray-500 shrink-0">(inactive)</span>}
        {/* Edit hint — visible on hover when collapsed */}
        {!expanded && (
          <span className="text-xs italic text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-1">
            edit
          </span>
        )}
      </button>

      {/* Expanded edit form */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-4 bg-gray-50 space-y-4 rounded-b-lg">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Package code</label>
              <input
                value={codeVal}
                onChange={(e) => { setCodeVal(normalizeEntityCodeInput(e.target.value)); setDirty(true); }}
                maxLength={ENTITY_CODE_MAX_LEN}
                className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Name</label>
              <input
                value={nameVal}
                onChange={(e) => { setNameVal(e.target.value); setDirty(true); }}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Description <span className="font-normal text-gray-400">(km range, scope)</span></label>
              <input
                value={descVal}
                onChange={(e) => { setDescVal(e.target.value); setDirty(true); }}
                placeholder="e.g. Km 0+000 to Km 45+000"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-2">Package actors</label>
              <p className="text-xs text-gray-400 mb-2">Overrides project-wide actor with the same role on this lot only.</p>
              {organizations.length === 0 ? (
                <p className="text-xs text-gray-400 italic mb-2">No package actors yet</p>
              ) : (
                <div className="border border-gray-200 rounded-lg overflow-hidden mb-2 max-w-xl bg-white">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left border-b border-gray-200">
                        <th className="px-3 py-2 text-xs font-medium text-gray-500">Organization</th>
                        <th className="px-3 py-2 text-xs font-medium text-gray-500">Role</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody>
                      {organizations.map((po) => {
                        const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
                        const roleLabel = actorRoles.find((r) => r.key === po.org_role)?.label ?? po.org_role;
                        return (
                          <tr key={`${po.organization_id}-${po.org_role}`} className="border-t border-gray-100">
                            <td className="px-3 py-2 font-medium text-gray-800">{orgName}</td>
                            <td className="px-3 py-2 text-xs text-gray-600">{roleLabel}</td>
                            <td className="px-3 py-2 text-right">
                              <button type="button" disabled={actorWorking}
                                onClick={() => void handleRemoveActor(po.organization_id, po.org_role)}
                                className="text-gray-300 hover:text-red-500 text-lg leading-none disabled:opacity-40">×</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2">
                <select value={addingOrg} onChange={(e) => setAddingOrg(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-2 py-1.5">
                  <option value="">— organization —</option>
                  {orgs.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
                </select>
                <select value={addingRole} onChange={(e) => setAddingRole(e.target.value)}
                  className="text-sm border border-gray-300 rounded px-2 py-1.5">
                  {actorRoles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
                </select>
                <button type="button" onClick={() => void handleAddActor()}
                  disabled={!addingOrg || !addingRole || actorWorking}
                  className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50">
                  Add
                </button>
              </div>
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pkg.is_active}
                  onChange={(e) => onUpdate({ is_active: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-gray-700">Active</span>
              </label>
            </div>
          </div>

          {/* Locations */}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Districts / locations covered</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {pkg.location_codes.length === 0 && (
                <span className="text-xs text-gray-400 italic">No locations linked</span>
              )}
              {pkg.location_codes.map((c) => (
                <span key={c} className="flex items-center gap-1 text-xs font-mono bg-blue-100 text-blue-800 border border-blue-300 px-2 py-0.5 rounded-full">
                  {c}
                  <button onClick={() => onRemoveLoc(c)} className="text-blue-600 hover:text-red-600 leading-none">×</button>
                </span>
              ))}
            </div>
            <LocationSearch
              country="NP"
              placeholder="Search district or municipality…"
              excludeCodes={pkg.location_codes}
              onSelect={(code) => onAddLoc(code)}
            />
          </div>

          {dirty && (
            <div className="flex justify-end pt-1">
              <button
                onClick={handleSave}
                disabled={saving || !nameVal.trim()}
                className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
              >
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
