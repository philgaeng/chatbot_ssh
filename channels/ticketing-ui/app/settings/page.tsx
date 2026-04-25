"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/app/providers/AuthProvider";
import {
  listWorkflows,
  listTemplates,
  createWorkflow,
  updateWorkflow,
  publishWorkflow,
  archiveWorkflow,
  addStep,
  updateStep,
  deleteStep,
  reorderSteps,
  addAssignment,
  removeAssignment,
  listScopes,
  addScope,
  deleteScope,
  listOrganizations,
  listCountries,
  listLocations,
  listProjects,
  createProject,
  updateProject,
  addProjectOrg,
  removeProjectOrg,
  addProjectLocation,
  removeProjectLocation,
  importLocations,
  getLocationTemplateCsvUrl,
  getLocationTemplateJsonUrl,
  updateProjectOrgRole,
  getOrgRoles,
  setOrgRoles,
  createOrganization,
  updateOrganization,
  listProjectsForOrg,
  listPackages,
  createPackage,
  updatePackage,
  addPackageLocation,
  removePackageLocation,
  type WorkflowDefinition,
  type WorkflowStep,
  type WorkflowAssignmentItem,
  type StepPayload,
  type OfficerScope,
  type OrganizationItem,
  type OrganizationCreate,
  type CountryItem,
  type LocationNode,
  type ProjectItem,
  type ProjectOrgItem,
  type OrgRole,
  type PackageItem,
  type PackageCreate,
} from "@/lib/api";

// ── Role edit modal ───────────────────────────────────────────────────────────

type RoleEntry = {
  key: string;
  label: string;
  workflow: string;
  description: string;
  permissions: string[];
};

function RoleEditModal({ role, onSave, onClose }: {
  role: RoleEntry;
  onSave: (updated: RoleEntry) => void;
  onClose: () => void;
}) {
  const [label, setLabel] = useState(role.label);
  const [description, setDescription] = useState(role.description);
  const [permissions, setPermissions] = useState<string[]>(role.permissions);
  const [newPerm, setNewPerm] = useState("");
  const [saved, setSaved] = useState(false);

  function removePerm(p: string) {
    setPermissions(permissions.filter((x) => x !== p));
  }

  function addPerm() {
    const trimmed = newPerm.trim();
    if (!trimmed || permissions.includes(trimmed)) return;
    setPermissions([...permissions, trimmed]);
    setNewPerm("");
  }

  function handleSave() {
    onSave({ ...role, label, description, permissions });
    setSaved(true);
    setTimeout(() => { setSaved(false); onClose(); }, 800);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div>
            <div className="font-semibold">Edit Role</div>
            <div className="text-xs text-slate-300 font-mono mt-0.5">{role.key}</div>
          </div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Display name</label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Permissions</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {permissions.map((p) => (
                <span key={p} className="flex items-center gap-1 text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                  {p}
                  <button onClick={() => removePerm(p)} className="text-gray-400 hover:text-red-500 ml-0.5 leading-none">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={newPerm}
                onChange={(e) => setNewPerm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addPerm()}
                placeholder="Add permission…"
                className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                onClick={addPerm}
                disabled={!newPerm.trim()}
                className="text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition"
              >
                Add
              </button>
            </div>
          </div>

          <div className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            ⚠️ Permissions listed here are informational for the demo. API-level enforcement is defined in the backend code.
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className={`text-sm px-4 py-1.5 rounded font-medium transition ${
              saved ? "bg-green-600 text-white" : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {saved ? "✓ Saved" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

type Tab = "officers" | "roles" | "workflows" | "organizations" | "report_schedule" | "system_config";

const TABS: { id: Tab; label: string; superAdminOnly?: boolean }[] = [
  { id: "officers",        label: "Officers"                  },
  { id: "roles",           label: "Roles & Permissions"       },
  { id: "workflows",       label: "Workflows"                 },
  { id: "organizations",   label: "Organizations & Locations" },
  { id: "report_schedule", label: "Report Schedule"           },
  { id: "system_config",   label: "⚙ System Config",          superAdminOnly: true },
];

// Color classes for org role badges (keyed by role.key prefix)
const ORG_ROLE_COLORS: Record<string, string> = {
  donor:                   "bg-blue-100 text-blue-700 border-blue-200",
  executing_agency:        "bg-purple-100 text-purple-700 border-purple-200",
  implementing_agency:     "bg-indigo-100 text-indigo-700 border-indigo-200",
  main_contractor:         "bg-orange-100 text-orange-700 border-orange-200",
  subcontractor_t1:        "bg-amber-100 text-amber-700 border-amber-200",
  subcontractor_t2:        "bg-amber-100 text-amber-600 border-amber-200",
  supervision_consultant:  "bg-teal-100 text-teal-700 border-teal-200",
  specialized_consultant:  "bg-green-100 text-green-700 border-green-200",
};

// ── Location search autocomplete ─────────────────────────────────────────────

const LOC_LEVEL_LABELS: Record<number, string> = {
  1: "Province",
  2: "District",
  3: "Municipality",
};
const LOC_LEVEL_COLORS: Record<number, string> = {
  1: "bg-purple-100 text-purple-700",
  2: "bg-blue-100 text-blue-700",
  3: "bg-green-100 text-green-700",
};

/**
 * Autocomplete that searches the location tree (province / district / municipality).
 * Calls GET /api/v1/locations?q=<text> with a 220 ms debounce.
 * Also matches on location_code so admins can type "NP_D004" and still find the result.
 */
function LocationSearch({
  country = "NP",
  placeholder,
  excludeCodes = [],
  onSelect,
}: {
  country?: string;
  placeholder?: string;
  excludeCodes?: string[];
  onSelect: (code: string, name: string) => void;
}) {
  const [q, setQ]           = useState("");
  const [hits, setHits]     = useState<LocationNode[]>([]);
  const [open, setOpen]     = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef            = useRef<ReturnType<typeof setTimeout> | null>(null);
  // stable string for excludeCodes dep
  const excludeKey = excludeCodes.join(",");

  function getName(node: LocationNode) {
    return node.translations.find((t) => t.lang_code === "en")?.name ?? node.location_code;
  }

  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); setOpen(false); return; }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await listLocations({ country, q: q.trim(), limit: 8, active_only: true });
        setHits(res.filter((n) => !excludeCodes.includes(n.location_code)));
        setOpen(true);
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, country, excludeKey]);

  function handleSelect(node: LocationNode) {
    onSelect(node.location_code, getName(node));
    setQ(""); setHits([]); setOpen(false);
  }

  return (
    <div className="relative">
      {/* Input */}
      <div className="flex items-center gap-1.5 border border-gray-300 rounded px-2.5 py-1.5 focus-within:ring-1 focus-within:ring-blue-400 bg-white">
        <span className="text-gray-400 text-xs shrink-0 select-none">⌕</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onBlur={() => setTimeout(() => setOpen(false), 180)}
          onFocus={() => hits.length > 0 && setOpen(true)}
          placeholder={placeholder ?? "Search province, district or municipality…"}
          className="flex-1 text-sm bg-transparent outline-none min-w-0"
        />
        {loading && <span className="text-xs text-gray-300 animate-pulse shrink-0">…</span>}
        {q && (
          <button
            onClick={() => { setQ(""); setHits([]); setOpen(false); }}
            className="text-gray-300 hover:text-gray-500 text-base leading-none shrink-0"
          >×</button>
        )}
      </div>

      {/* Dropdown */}
      {open && hits.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {hits.map((node) => (
            <button
              key={node.location_code}
              onMouseDown={() => handleSelect(node)}
              className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-2 border-t border-gray-50 first:border-t-0 transition-colors"
            >
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${LOC_LEVEL_COLORS[node.level_number] ?? "bg-gray-100 text-gray-600"}`}>
                {LOC_LEVEL_LABELS[node.level_number] ?? `L${node.level_number}`}
              </span>
              <span className="text-sm text-gray-800 flex-1 min-w-0 truncate">{getName(node)}</span>
              <span className="text-xs font-mono text-gray-400 shrink-0">{node.location_code}</span>
            </button>
          ))}
        </div>
      )}

      {/* No results */}
      {open && q.trim().length >= 2 && !loading && hits.length === 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2.5">
          <span className="text-sm text-gray-400 italic">No locations match &ldquo;{q}&rdquo;</span>
        </div>
      )}
    </div>
  );
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const MOCK_OFFICERS = [
  { name: "Mock Site L1",       email: "mock-officer-site-l1@grm.local",       role: "site_safeguards_focal_person", org: "DOR", location: "JHAPA"  },
  { name: "Mock PIU L2",        email: "mock-officer-piu-l2@grm.local",        role: "pd_piu_safeguards_focal",      org: "DOR", location: "MORANG" },
  { name: "Mock GRC Chair",     email: "mock-officer-grc-chair@grm.local",     role: "grc_chair",                   org: "DOR", location: null     },
  { name: "Mock GRC Member",    email: "mock-officer-grc-member@grm.local",    role: "grc_member",                  org: "DOR", location: null     },
  { name: "Mock SEAH National", email: "mock-officer-seah-national@grm.local", role: "seah_national_officer",        org: "ADB", location: null     },
  { name: "Mock SEAH HQ",       email: "mock-officer-seah-hq@grm.local",       role: "seah_hq_officer",             org: "ADB", location: null     },
  { name: "GRM Admin (mock)",   email: "admin@grm.local",                      role: "super_admin",                 org: null,  location: null     },
];

const ROLES = [
  {
    key: "super_admin",
    label: "Super Admin",
    workflow: "Both",
    description: "Full system access. Can manage all settings, users, and tickets.",
    permissions: ["View all tickets", "Manage users & roles", "Manage workflows", "Export reports", "SEAH access"],
  },
  {
    key: "local_admin",
    label: "Local Admin",
    workflow: "Standard",
    description: "Administrative access scoped to their organization and location.",
    permissions: ["View all tickets (own org)", "Manage officers (own org)", "Export reports"],
  },
  {
    key: "site_safeguards_focal_person",
    label: "Site Safeguards Focal Person",
    workflow: "Standard",
    description: "Level 1 officer — first point of contact for standard grievances.",
    permissions: ["View assigned tickets", "Acknowledge", "Escalate to L2", "Resolve", "Add notes", "Reply to complainant"],
  },
  {
    key: "pd_piu_safeguards_focal",
    label: "PD / PIU Safeguards Focal",
    workflow: "Standard",
    description: "Level 2 officer — receives escalations from L1.",
    permissions: ["View assigned tickets", "Acknowledge", "Escalate to L3 (GRC)", "Resolve", "Add notes", "Reply to complainant"],
  },
  {
    key: "grc_chair",
    label: "GRC Chair",
    workflow: "Standard",
    description: "Level 3 — convenes GRC hearing and records the committee decision.",
    permissions: ["View GRC tickets", "Convene GRC hearing", "Record GRC decision", "Escalate to L4", "Resolve", "Add notes"],
  },
  {
    key: "grc_member",
    label: "GRC Member",
    workflow: "Standard",
    description: "Level 3 — participates in GRC hearing. Receives hearing notifications.",
    permissions: ["View GRC tickets (read)", "Add notes"],
  },
  {
    key: "adb_national_project_director",
    label: "ADB National Project Director",
    workflow: "Standard",
    description: "Observer role — read-only oversight of standard GRM cases.",
    permissions: ["View all standard tickets (read-only)", "Export reports"],
  },
  {
    key: "adb_hq_safeguards",
    label: "ADB HQ Safeguards",
    workflow: "Standard",
    description: "Observer role — read-only oversight of standard GRM cases.",
    permissions: ["View all standard tickets (read-only)", "Export reports"],
  },
  {
    key: "seah_national_officer",
    label: "SEAH National Officer",
    workflow: "SEAH",
    description: "Level 1 SEAH officer — handles SEAH cases. Invisible to standard officers.",
    permissions: ["View SEAH tickets", "Acknowledge", "Escalate to SEAH L2", "Resolve", "Add notes", "Reply to complainant"],
  },
  {
    key: "seah_hq_officer",
    label: "SEAH HQ Officer",
    workflow: "SEAH",
    description: "Level 2 SEAH officer — receives SEAH escalations.",
    permissions: ["View SEAH tickets", "Acknowledge", "Resolve", "Close", "Add notes", "Reply to complainant"],
  },
  {
    key: "adb_hq_exec",
    label: "ADB HQ Executive",
    workflow: "Both",
    description: "Senior oversight — read-only access to both standard and SEAH cases.",
    permissions: ["View all tickets (read-only)", "SEAH access (read-only)", "Export reports"],
  },
];

// ── Tab components ────────────────────────────────────────────────────────────

// ── OfficerScopePanel — expandable jurisdictions editor ──────────────────────

function OfficerScopePanel({ userId, roleKey }: { userId: string; roleKey: string }) {
  const [scopes, setScopes] = useState<OfficerScope[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newOrg, setNewOrg] = useState("");
  const [newLoc, setNewLoc] = useState("");
  const [newProj, setNewProj] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listScopes(userId)
      .then(setScopes)
      .catch(() => setScopes([]))
      .finally(() => setLoading(false));
  }, [userId]);

  async function handleAdd() {
    if (!newOrg.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const created = await addScope(userId, {
        role_key: roleKey,
        organization_id: newOrg.trim(),
        location_code: newLoc.trim() || null,
        project_code: newProj.trim() || null,
      });
      setScopes((s) => [...s, created]);
      setNewOrg(""); setNewLoc(""); setNewProj("");
      setAdding(false);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg.includes("409") ? "Scope already exists" : "Failed to add scope");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(scopeId: string) {
    try {
      await deleteScope(userId, scopeId);
      setScopes((s) => s.filter((x) => x.scope_id !== scopeId));
    } catch {
      setError("Failed to remove scope");
    }
  }

  return (
    <div className="bg-slate-50 border-t border-gray-200 px-6 py-3">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
        Jurisdiction scopes
        <span className="ml-1 text-slate-400 font-normal normal-case">(tickets this officer can see)</span>
      </p>

      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : (
        <>
          {scopes.length === 0 && !adding && (
            <p className="text-xs text-amber-600 mb-2">
              No scopes — officer only sees tickets assigned directly to them.
            </p>
          )}

          {scopes.length > 0 && (
            <table className="w-full text-xs mb-2">
              <thead>
                <tr className="text-left text-slate-400">
                  <th className="pr-4 pb-1 font-medium">Organization</th>
                  <th className="pr-4 pb-1 font-medium">Location</th>
                  <th className="pr-4 pb-1 font-medium">Project</th>
                  <th className="pb-1" />
                </tr>
              </thead>
              <tbody>
                {scopes.map((s) => (
                  <tr key={s.scope_id} className="border-t border-gray-100">
                    <td className="pr-4 py-1 text-gray-700">{s.organization_id}</td>
                    <td className="pr-4 py-1 text-gray-500">{s.location_code ?? <span className="text-gray-300">all</span>}</td>
                    <td className="pr-4 py-1 text-gray-500">{s.project_code ?? <span className="text-gray-300">all</span>}</td>
                    <td className="py-1 text-right">
                      <button
                        onClick={() => handleDelete(s.scope_id)}
                        className="text-red-400 hover:text-red-600 font-medium"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {adding ? (
            <div className="flex items-center gap-2 mt-1">
              <input
                type="text"
                placeholder="Org *"
                value={newOrg}
                onChange={(e) => setNewOrg(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-xs w-28 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <input
                type="text"
                placeholder="Location"
                value={newLoc}
                onChange={(e) => setNewLoc(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-xs w-28 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <input
                type="text"
                placeholder="Project"
                value={newProj}
                onChange={(e) => setNewProj(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-xs w-28 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                onClick={handleAdd}
                disabled={saving || !newOrg.trim()}
                className="bg-blue-600 text-white text-xs px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Add"}
              </button>
              <button
                onClick={() => { setAdding(false); setError(null); }}
                className="text-gray-400 hover:text-gray-600 text-xs"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAdding(true)}
              className="text-blue-600 hover:underline text-xs mt-1"
            >
              + Add scope
            </button>
          )}

          {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </>
      )}
    </div>
  );
}

function OfficersTab() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search officers…"
            className="text-sm border border-gray-300 rounded px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <select className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option>All roles</option>
            {ROLES.map((r) => <option key={r.key}>{r.key}</option>)}
          </select>
        </div>
        <button className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium">
          + Invite Officer
        </button>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-4 py-2.5 font-medium w-6" />
              <th className="px-4 py-2.5 font-medium">Name</th>
              <th className="px-4 py-2.5 font-medium">Email</th>
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Organization</th>
              <th className="px-4 py-2.5 font-medium">Location</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_OFFICERS.map((o, i) => {
              const rowId = `mock-${i}`;
              const isOpen = expandedId === rowId;
              return (
                <React.Fragment key={rowId}>
                  <tr className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-2 py-2.5 text-center">
                      <button
                        onClick={() => setExpandedId(isOpen ? null : rowId)}
                        title="Manage jurisdiction scopes"
                        className="text-slate-400 hover:text-slate-600 text-xs leading-none"
                      >
                        {isOpen ? "▼" : "▶"}
                      </button>
                    </td>
                    <td className="px-4 py-2.5 font-medium text-gray-800">{o.name}</td>
                    <td className="px-4 py-2.5 text-gray-500">{o.email}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                        {o.role}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-500">{o.org ?? "—"}</td>
                    <td className="px-4 py-2.5 text-gray-500">{o.location ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs text-green-600 font-medium">Active</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-3">
                        <button className="text-blue-600 hover:underline text-xs">Edit</button>
                        <button className="text-red-500 hover:underline text-xs">Remove</button>
                      </div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr key={`${rowId}-scopes`}>
                      <td colSpan={8} className="p-0">
                        <OfficerScopePanel userId={o.email} roleKey={o.role} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-3">
        Full invite flow (Cognito email) — coming in Week 3. Jurisdictions managed via ▶ expand.
      </p>
    </div>
  );
}

function RolesTab() {
  const [roles, setRoles] = useState<RoleEntry[]>(ROLES.map((r) => ({ ...r })));
  const [editing, setEditing] = useState<RoleEntry | null>(null);

  const workflowBadge = (w: string) =>
    w === "SEAH"
      ? "bg-red-100 text-red-700"
      : w === "Both"
      ? "bg-purple-100 text-purple-700"
      : "bg-blue-100 text-blue-700";

  function handleSave(updated: RoleEntry) {
    setRoles(roles.map((r) => r.key === updated.key ? updated : r));
  }

  return (
    <div>
      {editing && (
        <RoleEditModal
          role={editing}
          onSave={handleSave}
          onClose={() => setEditing(null)}
        />
      )}

      <div className="flex items-center justify-between mb-5">
        <p className="text-sm text-gray-500">
          {roles.length} roles defined · permissions are enforced at the API level
        </p>
        <button
          disabled
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded font-medium opacity-40 cursor-not-allowed"
        >
          + Add Role
        </button>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-slate-100 text-left">
              <th className="px-4 py-2.5 font-medium">Role</th>
              <th className="px-4 py-2.5 font-medium">Workflow</th>
              <th className="px-4 py-2.5 font-medium">Description</th>
              <th className="px-4 py-2.5 font-medium">Permissions</th>
              <th className="px-4 py-2.5 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.key} className="border-t border-gray-100 hover:bg-gray-50 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{r.label}</div>
                  <div className="text-xs font-mono text-gray-400 mt-0.5">{r.key}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${workflowBadge(r.workflow)}`}>
                    {r.workflow}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs max-w-xs">{r.description}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {r.permissions.map((p) => (
                      <span key={p} className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                        {p}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => setEditing(r)}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-400 mt-3">
        Changes here update the display only. API-level enforcement requires a backend deploy.
      </p>
    </div>
  );
}

// ── Workflow helpers ──────────────────────────────────────────────────────────

const ROLE_OPTIONS = [
  { key: "site_safeguards_focal_person", label: "Site Safeguards Focal Person" },
  { key: "pd_piu_safeguards_focal",      label: "PD / PIU Safeguards Focal" },
  { key: "grc_chair",                    label: "GRC Chair" },
  { key: "grc_member",                   label: "GRC Member" },
  { key: "adb_national_project_director",label: "ADB National Project Director" },
  { key: "adb_hq_safeguards",            label: "ADB HQ Safeguards" },
  { key: "adb_hq_project",              label: "ADB HQ Project" },
  { key: "seah_national_officer",        label: "SEAH National Officer" },
  { key: "seah_hq_officer",             label: "SEAH HQ Officer" },
  { key: "super_admin",                  label: "Super Admin" },
  { key: "local_admin",                  label: "Local Admin" },
];

function statusBadge(status: string) {
  const map: Record<string, string> = {
    published: "bg-green-100 text-green-700",
    draft:     "bg-yellow-100 text-yellow-700",
    archived:  "bg-gray-100 text-gray-500",
    template:  "bg-blue-100 text-blue-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}

function typeBadge(t: string) {
  return t === "seah" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600";
}

// ── Step form (inline accordion) ─────────────────────────────────────────────

function StepForm({
  step,
  workflowId,
  onSaved,
  onCancel,
}: {
  step: WorkflowStep;
  workflowId: string;
  onSaved: (s: WorkflowStep) => void;
  onCancel: () => void;
}) {
  const [displayName, setDisplayName]       = useState(step.display_name);
  const [stepKey, setStepKey]               = useState(step.step_key);
  const [roleKey, setRoleKey]               = useState(step.assigned_role_key);
  const [responseH, setResponseH]           = useState<string>(step.response_time_hours?.toString() ?? "");
  const [resolutionD, setResolutionD]       = useState<string>(step.resolution_time_days?.toString() ?? "");
  const [stakeholders, setStakeholders]     = useState<string[]>(step.stakeholders ?? []);
  const [newStakeholder, setNewStakeholder] = useState("");
  const [actions, setActions]               = useState<string[]>(step.expected_actions ?? []);
  const [newAction, setNewAction]           = useState("");
  const [saving, setSaving]                 = useState(false);
  const [error, setError]                   = useState("");

  async function handleSave() {
    if (!displayName.trim() || !roleKey) { setError("Name and role are required."); return; }
    setSaving(true); setError("");
    try {
      const payload: Partial<StepPayload> = {
        display_name: displayName.trim(),
        step_key: stepKey.trim() || undefined,
        assigned_role_key: roleKey,
        response_time_hours: responseH ? parseInt(responseH) : null,
        resolution_time_days: resolutionD ? parseInt(resolutionD) : null,
        stakeholders: stakeholders.length ? stakeholders : null,
        expected_actions: actions.length ? actions : null,
      };
      const updated = await updateStep(workflowId, step.step_id, payload);
      onSaved(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally { setSaving(false); }
  }

  function addTag(list: string[], setList: (v: string[]) => void, val: string, setVal: (v: string) => void) {
    const t = val.trim();
    if (t && !list.includes(t)) setList([...list, t]);
    setVal("");
  }

  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 mt-2 space-y-3">
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</p>}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Display name *</label>
          <input value={displayName} onChange={e => setDisplayName(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Step key</label>
          <input value={stepKey} onChange={e => setStepKey(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Assigned role *</label>
        <select value={roleKey} onChange={e => setRoleKey(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
          <option value="">— select role —</option>
          {ROLE_OPTIONS.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Response time (hours)</label>
          <input type="number" min="0" value={responseH} onChange={e => setResponseH(e.target.value)} placeholder="e.g. 48"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Resolution time (days)</label>
          <input type="number" min="0" value={resolutionD} onChange={e => setResolutionD(e.target.value)} placeholder="e.g. 7"
            className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
        </div>
      </div>

      {/* Stakeholders */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Stakeholders notified</label>
        <div className="flex flex-wrap gap-1 mb-1">
          {stakeholders.map(s => (
            <span key={s} className="flex items-center gap-1 text-xs bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
              {s}
              <button onClick={() => setStakeholders(stakeholders.filter(x => x !== s))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <select value={newStakeholder} onChange={e => setNewStakeholder(e.target.value)}
            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="">+ Add stakeholder role</option>
            {ROLE_OPTIONS.filter(r => !stakeholders.includes(r.key)).map(r =>
              <option key={r.key} value={r.key}>{r.label}</option>
            )}
          </select>
          <button onClick={() => addTag(stakeholders, setStakeholders, newStakeholder, setNewStakeholder)}
            disabled={!newStakeholder}
            className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
        </div>
      </div>

      {/* Expected actions */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Expected actions</label>
        <div className="flex flex-wrap gap-1 mb-1">
          {actions.map(a => (
            <span key={a} className="flex items-center gap-1 text-xs bg-white border border-gray-200 text-gray-700 px-2 py-0.5 rounded">
              {a}
              <button onClick={() => setActions(actions.filter(x => x !== a))} className="text-gray-400 hover:text-red-500 leading-none">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={newAction} onChange={e => setNewAction(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addTag(actions, setActions, newAction, setNewAction)}
            placeholder="e.g. Investigate root cause"
            className="flex-1 text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <button onClick={() => addTag(actions, setActions, newAction, setNewAction)}
            disabled={!newAction.trim()}
            className="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded disabled:opacity-40 transition">Add</button>
        </div>
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded transition">Cancel</button>
        <button onClick={handleSave} disabled={saving}
          className="text-xs bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
          {saving ? "Saving…" : "Save step"}
        </button>
      </div>
    </div>
  );
}

// ── Assignment panel ──────────────────────────────────────────────────────────

function AssignmentPanel({
  workflowId,
  assignments,
  onChange,
}: {
  workflowId: string;
  assignments: WorkflowAssignmentItem[];
  onChange: (updated: WorkflowAssignmentItem[]) => void;
}) {
  const [org, setOrg]       = useState("");
  const [loc, setLoc]       = useState("");
  const [proj, setProj]     = useState("");
  const [priority, setPri]  = useState("");
  const [adding, setAdding] = useState(false);
  const [err, setErr]       = useState("");

  async function handleAdd() {
    if (!org.trim()) { setErr("Organization ID is required."); return; }
    setAdding(true); setErr("");
    try {
      const row = await addAssignment(workflowId, {
        organization_id: org.trim(),
        location_code:   loc.trim()  || null,
        project_code:    proj.trim() || null,
        priority:        priority.trim() || null,
      });
      onChange([...assignments, row]);
      setOrg(""); setLoc(""); setProj(""); setPri("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to add");
    } finally { setAdding(false); }
  }

  async function handleRemove(assignmentId: string) {
    try {
      await removeAssignment(workflowId, assignmentId);
      onChange(assignments.filter(a => a.assignment_id !== assignmentId));
    } catch { /* ignore */ }
  }

  function fmt(a: WorkflowAssignmentItem) {
    const parts = [a.organization_id, a.location_code, a.project_code, a.priority ?? "(all priorities)"].filter(Boolean);
    return parts.join(" · ");
  }

  return (
    <div className="mt-6 border-t border-gray-200 pt-5">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Assigned to</h3>
      {assignments.length === 0 && (
        <p className="text-xs text-gray-400 mb-3 italic">No assignments — workflow won&apos;t be used for new tickets until assigned.</p>
      )}
      <div className="space-y-1.5 mb-3">
        {assignments.map(a => (
          <div key={a.assignment_id} className="flex items-center justify-between text-xs bg-gray-50 border border-gray-200 rounded px-3 py-1.5">
            <span className="text-gray-700 font-mono">{fmt(a)}</span>
            <button onClick={() => handleRemove(a.assignment_id)} className="text-gray-400 hover:text-red-500 ml-3 leading-none text-sm">×</button>
          </div>
        ))}
      </div>

      {/* Add form */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2">
        <p className="text-xs font-medium text-gray-500">+ Add assignment</p>
        {err && <p className="text-xs text-red-600">{err}</p>}
        <div className="grid grid-cols-4 gap-2">
          <div>
            <label className="text-xs text-gray-400 block mb-0.5">Org ID *</label>
            <input value={org} onChange={e => setOrg(e.target.value)} placeholder="DOR"
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-0.5">Location</label>
            <input value={loc} onChange={e => setLoc(e.target.value)} placeholder="JHAPA"
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-0.5">Project</label>
            <input value={proj} onChange={e => setProj(e.target.value)} placeholder="KL_ROAD"
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-0.5">Priority</label>
            <select value={priority} onChange={e => setPri(e.target.value)}
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">All</option>
              <option value="LOW">LOW</option>
              <option value="NORMAL">NORMAL</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end">
          <button onClick={handleAdd} disabled={adding || !org.trim()}
            className="text-xs bg-blue-600 text-white hover:bg-blue-700 px-3 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {adding ? "Adding…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Workflow editor ───────────────────────────────────────────────────────────

function WorkflowEditor({
  workflow: initial,
  onBack,
  onUpdated,
}: {
  workflow: WorkflowDefinition;
  onBack: () => void;
  onUpdated: (w: WorkflowDefinition) => void;
}) {
  const [wf, setWf]               = useState<WorkflowDefinition>(initial);
  const [expandedStep, setExpanded] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal]       = useState(wf.display_name);
  const [publishing, setPublishing] = useState(false);
  const [archiving, setArchiving]   = useState(false);
  const [addingStep, setAddingStep] = useState(false);
  const [msg, setMsg]               = useState("");

  const steps = wf.steps.filter(s => !s.is_deleted).sort((a, b) => a.step_order - b.step_order);

  function flash(text: string) { setMsg(text); setTimeout(() => setMsg(""), 2500); }

  async function handlePublish() {
    setPublishing(true);
    try { const updated = await publishWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Published ✓"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Publish failed"); }
    finally { setPublishing(false); }
  }

  async function handleArchive() {
    if (!confirm("Archive this workflow? It won't be used for new tickets.")) return;
    setArchiving(true);
    try { const updated = await archiveWorkflow(wf.workflow_id); setWf(updated); onUpdated(updated); flash("Archived"); }
    catch (e: unknown) { flash(e instanceof Error ? e.message : "Archive failed"); }
    finally { setArchiving(false); }
  }

  async function handleRename() {
    if (!nameVal.trim() || nameVal === wf.display_name) { setEditingName(false); return; }
    try {
      const updated = await updateWorkflow(wf.workflow_id, { display_name: nameVal.trim() });
      setWf(updated); onUpdated(updated); flash("Renamed ✓");
    } catch { /* ignore */ }
    setEditingName(false);
  }

  async function handleMoveUp(idx: number) {
    if (idx === 0) return;
    const newOrder = [...steps];
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleMoveDown(idx: number) {
    if (idx === steps.length - 1) return;
    const newOrder = [...steps];
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    const ids = newOrder.map(s => s.step_id);
    const updated = await reorderSteps(wf.workflow_id, ids);
    setWf(prev => ({ ...prev, steps: updated }));
  }

  async function handleDeleteStep(step: WorkflowStep) {
    if (!confirm(`Remove step "${step.display_name}"? This cannot be undone if tickets are active on it.`)) return;
    try {
      await deleteStep(wf.workflow_id, step.step_id);
      setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === step.step_id ? { ...s, is_deleted: true } : s) }));
      flash("Step removed");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Cannot delete step");
    }
  }

  async function handleAddStep() {
    setAddingStep(true);
    try {
      const newStep = await addStep(wf.workflow_id, {
        display_name: `Step ${steps.length + 1}`,
        assigned_role_key: "site_safeguards_focal_person",
      });
      setWf(prev => ({ ...prev, steps: [...prev.steps, newStep] }));
      setExpanded(newStep.step_id);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to add step");
    } finally { setAddingStep(false); }
  }

  function handleStepSaved(updated: WorkflowStep) {
    setWf(prev => ({ ...prev, steps: prev.steps.map(s => s.step_id === updated.step_id ? updated : s) }));
    setExpanded(null);
    flash("Step saved ✓");
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">
            ← <span>Workflows</span>
          </button>
          <span className="text-gray-300">/</span>
          {editingName ? (
            <input autoFocus value={nameVal} onChange={e => setNameVal(e.target.value)}
              onBlur={handleRename} onKeyDown={e => e.key === "Enter" && handleRename()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          ) : (
            <h2 className="text-lg font-semibold text-gray-800 cursor-pointer hover:text-blue-600" onClick={() => setEditingName(true)} title="Click to rename">
              {wf.display_name}
            </h2>
          )}
          {wf.workflow_type === "seah" && <span className="text-xs text-red-600">🔒 SEAH</span>}
        </div>
        <div className="flex items-center gap-3">
          {msg && <span className="text-xs text-green-600 font-medium">{msg}</span>}
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${statusBadge(wf.status)}`}>{wf.status}</span>
          <span className="text-xs text-gray-400">v{wf.version}</span>
          {wf.status !== "archived" && (
            <button onClick={handlePublish} disabled={publishing}
              className="text-sm bg-green-600 text-white hover:bg-green-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
              {publishing ? "Publishing…" : wf.status === "published" ? "Re-publish" : "Publish"}
            </button>
          )}
          {wf.status === "published" && (
            <button onClick={handleArchive} disabled={archiving}
              className="text-sm text-gray-500 hover:text-gray-700 border border-gray-300 px-3 py-1.5 rounded transition">
              {archiving ? "Archiving…" : "Archive"}
            </button>
          )}
        </div>
      </div>

      {/* Meta info */}
      <div className="flex items-center gap-4 mb-6 text-xs text-gray-500">
        <span>Type: <span className={`font-medium px-1.5 py-0.5 rounded ${typeBadge(wf.workflow_type)}`}>{wf.workflow_type.toUpperCase()}</span></span>
        <span>Key: <code className="text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{wf.workflow_key}</code></span>
        {wf.description && <span className="text-gray-400 italic">{wf.description}</span>}
      </div>

      {/* Steps */}
      <div className="space-y-2 mb-4">
        {steps.map((step, idx) => (
          <div key={step.step_id} className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Step row */}
            <div className="flex items-center gap-3 px-4 py-3 bg-white hover:bg-gray-50">
              {/* Reorder */}
              <div className="flex flex-col gap-0.5 shrink-0">
                <button onClick={() => handleMoveUp(idx)} disabled={idx === 0}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▲</button>
                <button onClick={() => handleMoveDown(idx)} disabled={idx === steps.length - 1}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▼</button>
              </div>

              {/* Step number */}
              <span className="w-6 h-6 rounded-full bg-slate-700 text-white text-xs flex items-center justify-center font-medium shrink-0">
                {idx + 1}
              </span>

              {/* Step info */}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-800 text-sm">{step.display_name}</div>
                <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                  <span>Role: <code>{step.assigned_role_key}</code></span>
                  {step.response_time_hours != null && <span>Response: {step.response_time_hours}h</span>}
                  {step.resolution_time_days != null && <span>Resolution: {step.resolution_time_days}d</span>}
                  {step.response_time_hours == null && step.resolution_time_days == null && <span className="italic">No SLA</span>}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setExpanded(expandedStep === step.step_id ? null : step.step_id)}
                  className="text-xs text-blue-600 hover:underline px-2 py-1">
                  {expandedStep === step.step_id ? "Collapse" : "Edit"}
                </button>
                <button onClick={() => handleDeleteStep(step)}
                  className="text-xs text-gray-400 hover:text-red-500 px-1 py-1 leading-none">✕</button>
              </div>
            </div>

            {/* Accordion */}
            {expandedStep === step.step_id && (
              <div className="px-4 pb-4">
                <StepForm
                  step={step}
                  workflowId={wf.workflow_id}
                  onSaved={handleStepSaved}
                  onCancel={() => setExpanded(null)}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add step */}
      <button onClick={handleAddStep} disabled={addingStep}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 border border-dashed border-blue-300 hover:border-blue-500 rounded-lg px-4 py-2.5 w-full justify-center transition disabled:opacity-50">
        {addingStep ? "Adding…" : "+ Add step"}
      </button>

      {/* Assignments */}
      <AssignmentPanel
        workflowId={wf.workflow_id}
        assignments={wf.assignments}
        onChange={updated => setWf(prev => ({ ...prev, assignments: updated }))}
      />
    </div>
  );
}

// ── New workflow modal ────────────────────────────────────────────────────────

function NewWorkflowModal({
  templates,
  canSeeSeah,
  onCreated,
  onClose,
}: {
  templates: WorkflowDefinition[];
  canSeeSeah: boolean;
  onCreated: (w: WorkflowDefinition) => void;
  onClose: () => void;
}) {
  const [name, setName]             = useState("");
  const [wfType, setWfType]         = useState("standard");
  const [cloneFrom, setCloneFrom]   = useState("__builtin_default_grm");
  const [creating, setCreating]     = useState(false);
  const [error, setError]           = useState("");

  const builtIns = [
    { id: "__builtin_default_grm",  label: "Default GRM (4 steps)",  type: "standard" },
    ...(canSeeSeah ? [{ id: "__builtin_default_seah", label: "Default SEAH (2 steps)", type: "seah" }] : []),
    { id: "",  label: "Blank (0 steps)",  type: "any" },
  ];

  const adminTemplates = templates.filter(t => canSeeSeah || t.workflow_type !== "seah");

  async function handleCreate() {
    if (!name.trim()) { setError("Workflow name is required."); return; }
    setCreating(true); setError("");
    try {
      const created = await createWorkflow({
        display_name: name.trim(),
        workflow_type: wfType,
        clone_from_id: cloneFrom || undefined,
      });
      onCreated(created);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New workflow</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Workflow name *</label>
            <input autoFocus value={name} onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreate()}
              placeholder="e.g. KL Road Standard GRM"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Type</label>
            <div className="flex gap-3">
              {["standard", ...(canSeeSeah ? ["seah"] : [])].map(t => (
                <label key={t} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" value={t} checked={wfType === t} onChange={() => { setWfType(t); if (t === "seah") setCloneFrom("__builtin_default_seah"); else setCloneFrom("__builtin_default_grm"); }} />
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeBadge(t)}`}>{t.toUpperCase()}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Start from template</label>
            <div className="space-y-1.5">
              {builtIns.filter(b => b.type === "any" || b.type === wfType || b.type === "standard").map(b => (
                <label key={b.id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === b.id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={b.id} checked={cloneFrom === b.id} onChange={() => setCloneFrom(b.id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{b.label}</span>
                </label>
              ))}
              {adminTemplates.map(t => (
                <label key={t.workflow_id} className={`flex items-center gap-3 border rounded-lg px-3 py-2 cursor-pointer transition ${cloneFrom === t.workflow_id ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
                  <input type="radio" value={t.workflow_id} checked={cloneFrom === t.workflow_id} onChange={() => setCloneFrom(t.workflow_id)} className="shrink-0" />
                  <span className="text-sm text-gray-700">{t.display_name} <span className="text-xs text-gray-400">({t.steps.length} steps)</span></span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded transition">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !name.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create workflow"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Workflows tab ─────────────────────────────────────────────────────────────

function WorkflowsTab() {
  const { canSeeSeah } = useAuth();
  const [workflows, setWorkflows]     = useState<WorkflowDefinition[]>([]);
  const [templates, setTemplates]     = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState("");
  const [editing, setEditing]         = useState<WorkflowDefinition | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);
  const [search, setSearch]           = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [wfRes, tplRes] = await Promise.all([listWorkflows(), listTemplates()]);
      setWorkflows(wfRes.items);
      setTemplates(tplRes.items.filter(t => t.is_template));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load workflows");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Editor view
  if (editing) {
    return (
      <WorkflowEditor
        workflow={editing}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={updated => setEditing(updated)}
      />
    );
  }

  const visible = workflows.filter(w => {
    if (!canSeeSeah && w.workflow_type === "seah") return false;
    if (search && !w.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  // Templates come entirely from the API (built-ins included)
  const allTemplates = templates.filter(t => canSeeSeah || t.workflow_type !== "seah");

  return (
    <div>
      {showNewModal && (
        <NewWorkflowModal
          templates={templates}
          canSeeSeah={!!canSeeSeah}
          onCreated={w => { setShowNewModal(false); setWorkflows(prev => [...prev, w]); setEditing(w); }}
          onClose={() => setShowNewModal(false)}
        />
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search workflows…"
            className="text-sm border border-gray-300 rounded px-3 py-1.5 w-56 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {loading && <span className="text-xs text-gray-400 animate-pulse">Loading…</span>}
          {error && <span className="text-xs text-red-500">{error}</span>}
        </div>
        <button onClick={() => setShowNewModal(true)}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium">
          + New workflow
        </button>
      </div>

      {/* Workflow list */}
      {!loading && visible.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <div className="text-3xl mb-3">📋</div>
          <p className="text-sm">No workflows yet. Create one to get started.</p>
        </div>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
        {visible.map(wf => (
          <div key={wf.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-800 text-sm">{wf.display_name}</span>
                {wf.workflow_type === "seah" && <span className="text-xs text-red-500">🔒</span>}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {wf.steps.filter(s => s && !s.is_deleted).length} steps
                {wf.assignments.length > 0 && ` · assigned to ${wf.assignments.map(a => [a.organization_id, a.location_code, a.project_code].filter(Boolean).join("/")).join(", ")}`}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(wf.workflow_type)}`}>
                {wf.workflow_type.toUpperCase()}
              </span>
              <span className="text-xs text-gray-400">v{wf.version}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${statusBadge(wf.status)}`}>
                {wf.status.charAt(0).toUpperCase() + wf.status.slice(1)}
              </span>
              <button onClick={() => setEditing(wf)}
                className="text-sm text-blue-600 hover:underline ml-2">Edit</button>
            </div>
          </div>
        ))}
      </div>

      {/* Templates section */}
      {allTemplates.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Templates</h3>
          <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
            {allTemplates.map(tpl => (
              <div key={tpl.workflow_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 text-sm">{tpl.display_name}</span>
                    {tpl.workflow_type === "seah" && <span className="text-xs text-red-500">🔒</span>}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {tpl.steps.filter(s => s && !s.is_deleted).length} steps · {tpl.workflow_id.startsWith("__builtin_") ? "built-in" : "admin template"}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${typeBadge(tpl.workflow_type)}`}>
                    {tpl.workflow_type.toUpperCase()}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded font-medium bg-blue-100 text-blue-700">Template</span>
                  <button onClick={() => setShowNewModal(true)}
                    className="text-sm text-blue-600 hover:underline ml-2">Clone</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Organizations & Locations Tab ─────────────────────────────────────────────

type OrgLocSubTab = "organizations" | "locations" | "projects";

function OrganizationsTab() {
  const [sub, setSub] = useState<OrgLocSubTab>("organizations");
  // When set, ProjectsSection will auto-open this project on mount
  const [jumpProjectId, setJumpProjectId] = useState<string | null>(null);

  function handleSubChange(id: OrgLocSubTab) {
    if (id !== "projects") setJumpProjectId(null); // clear jump when leaving projects
    setSub(id);
  }

  function navigateToProject(projectId: string) {
    setJumpProjectId(projectId);
    setSub("projects");
  }

  return (
    <div>
      {/* Sub-tabs */}
      <div className="flex gap-0 border-b border-gray-200 mb-6">
        {(["organizations", "locations", "projects"] as OrgLocSubTab[]).map((id) => (
          <button
            key={id}
            onClick={() => handleSubChange(id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              sub === id ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {id.charAt(0).toUpperCase() + id.slice(1)}
          </button>
        ))}
      </div>
      {sub === "organizations" && <OrgsSection onNavigateToProject={navigateToProject} />}
      {sub === "locations"     && <LocationsSection />}
      {sub === "projects"      && <ProjectsSection initialEditId={jumpProjectId} />}
    </div>
  );
}

// ── Organizations section ─────────────────────────────────────────────────────

function OrgsSection({ onNavigateToProject }: { onNavigateToProject: (id: string) => void }) {
  const [orgs, setOrgs]           = useState<OrganizationItem[]>([]);
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing]     = useState<OrganizationItem | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [o, c] = await Promise.all([listOrganizations(), listCountries()]);
      setOrgs(o);
      setCountries(c);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (editing) {
    return (
      <OrgEditor
        org={editing}
        countries={countries}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={(updated) => setEditing(updated)}
        onNavigateToProject={onNavigateToProject}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">{orgs.length} organization{orgs.length !== 1 ? "s" : ""}</p>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded font-medium hover:bg-blue-700 transition"
        >
          + Add Organization
        </button>
      </div>

      {showCreate && (
        <OrgCreateModal
          countries={countries}
          onCreated={(org) => { setShowCreate(false); setOrgs((prev) => [...prev, org]); setEditing(org); }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}
      {error   && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-700 text-slate-100 text-left">
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Country</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium w-16" />
              </tr>
            </thead>
            <tbody>
              {orgs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">No organizations yet.</td></tr>
              )}
              {orgs.map((o) => (
                <tr key={o.organization_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{o.organization_id}</td>
                  <td className="px-4 py-2.5 font-medium text-gray-800">{o.name}</td>
                  <td className="px-4 py-2.5 text-gray-500">{o.country_code ?? <span className="text-gray-300">—</span>}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium ${o.is_active ? "text-green-600" : "text-gray-400"}`}>
                      {o.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => setEditing(o)} className="text-xs text-blue-600 hover:underline">
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Create org modal ──────────────────────────────────────────────────────────

function OrgCreateModal({
  countries,
  onCreated,
  onClose,
}: {
  countries: CountryItem[];
  onCreated: (org: OrganizationItem) => void;
  onClose: () => void;
}) {
  const [orgId, setOrgId]       = useState("");
  const [name, setName]         = useState("");
  const [country, setCountry]   = useState("NP");
  const [isActive, setIsActive] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");

  async function handleCreate() {
    const id = orgId.trim().toUpperCase();
    if (!id || !name.trim()) { setError("ID and name are required."); return; }
    if (!/^[A-Z0-9_]+$/.test(id)) { setError("ID must be uppercase letters, digits, or underscores only (e.g. DOR, ABC_CONST)."); return; }
    setCreating(true); setError("");
    try {
      const org = await createOrganization({
        organization_id: id,
        name: name.trim(),
        country_code: country || null,
        is_active: isActive,
      } as OrganizationCreate);
      onCreated(org);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Create failed";
      setError(msg.includes("409") ? `ID "${id}" is already taken.` : msg);
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New organization</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">
              Organization ID <span className="text-gray-400 font-normal">(short code, permanent)</span>
            </label>
            <input
              autoFocus
              value={orgId}
              onChange={(e) => setOrgId(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
              placeholder="e.g. DOR, ADB, ABC_CONST"
              className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <p className="text-xs text-gray-400 mt-1">Uppercase letters, numbers, underscores only. Cannot be changed later.</p>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Full name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Department of Roads"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Country</label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— none (multi-country) —</option>
                {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name} ({c.country_code})</option>)}
              </select>
            </div>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                <span className="text-sm text-gray-700">Active</span>
              </label>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">Cancel</button>
          <button
            onClick={handleCreate}
            disabled={creating || !orgId.trim() || !name.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition"
          >
            {creating ? "Creating…" : "Create organization"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Org editor ────────────────────────────────────────────────────────────────

function OrgEditor({
  org: initial,
  countries,
  onBack,
  onUpdated,
  onNavigateToProject,
}: {
  org: OrganizationItem;
  countries: CountryItem[];
  onBack: () => void;
  onUpdated: (o: OrganizationItem) => void;
  onNavigateToProject: (id: string) => void;
}) {
  const [org, setOrg]       = useState<OrganizationItem>(initial);
  const [nameVal, setNameVal] = useState(org.name);
  const [countryVal, setCountryVal] = useState(org.country_code ?? "");
  const [activeVal, setActiveVal]   = useState(org.is_active);
  const [msg, setMsg]       = useState("");
  const [dirty, setDirty]   = useState(false);
  const [saving, setSaving] = useState(false);

  // Project-linking state
  const [allProjects, setAllProjects] = useState<ProjectItem[]>([]);
  const [orgRoles, setOrgRoles]       = useState<OrgRole[]>([]);
  const [linkedProjects, setLinkedProjects] = useState<ProjectItem[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  // Packages where this org is the contractor, keyed by project_id (read-only context)
  const [packagesByProject, setPackagesByProject] = useState<Record<string, PackageItem[]>>({});

  function flash(t: string) { setMsg(t); setTimeout(() => setMsg(""), 2500); }

  useEffect(() => {
    Promise.all([listProjects(), getOrgRoles().catch(() => [] as OrgRole[])])
      .then(([all, roles]) => {
        setAllProjects(all);
        setOrgRoles(roles);
        setLinkedProjects(all.filter((p) => p.organizations.some((o) => o.organization_id === org.organization_id)));
      })
      .finally(() => setProjectsLoading(false));
  }, [org.organization_id]);

  // Load packages for each linked project — show read-only contractor context
  useEffect(() => {
    if (linkedProjects.length === 0) { setPackagesByProject({}); return; }
    Promise.all(
      linkedProjects.map((proj) =>
        listPackages(proj.project_id)
          .then((pkgs) => [
            proj.project_id,
            pkgs.filter((pkg) => pkg.contractor_org_id === org.organization_id),
          ] as [string, PackageItem[]])
          .catch(() => [proj.project_id, []] as [string, PackageItem[]])
      )
    ).then((entries) => setPackagesByProject(Object.fromEntries(entries)));
  }, [linkedProjects, org.organization_id]);

  async function handleSaveMeta() {
    if (!nameVal.trim()) return;
    setSaving(true);
    try {
      const updated = await updateOrganization(org.organization_id, {
        name: nameVal.trim(),
        country_code: countryVal || null,
        is_active: activeVal,
      });
      setOrg(updated); onUpdated(updated); setDirty(false); flash("Saved ✓");
    } catch { flash("Save failed"); }
    setSaving(false);
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">← Organizations</button>
        <span className="text-gray-300">/</span>
        <h2 className="text-lg font-semibold text-gray-800">{org.name}</h2>
        <span className="font-mono text-sm text-gray-400">{org.organization_id}</span>
        {msg && <span className="text-xs text-green-600 font-medium ml-2">{msg}</span>}
      </div>

      {/* Meta fields */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 mb-6 max-w-lg space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Full name</label>
          <input
            value={nameVal}
            onChange={(e) => { setNameVal(e.target.value); setDirty(true); }}
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Country</label>
            <select
              value={countryVal}
              onChange={(e) => { setCountryVal(e.target.value); setDirty(true); }}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">— none (multi-country) —</option>
              {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name} ({c.country_code})</option>)}
            </select>
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={activeVal}
                onChange={(e) => { setActiveVal(e.target.checked); setDirty(true); }}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm text-gray-700">Active</span>
            </label>
          </div>
        </div>
        {dirty && (
          <div className="flex justify-end">
            <button
              onClick={handleSaveMeta}
              disabled={saving || !nameVal.trim()}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        )}
      </div>

      {/* Projects — read-only list; click to open in Projects tab */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Projects</h3>
        <p className="text-xs text-gray-400 mb-3">
          Projects this organization is involved in. Click a project to open it and manage assignments.
        </p>

        {projectsLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : linkedProjects.length === 0 ? (
          <p className="text-xs text-gray-400 italic">
            Not linked to any projects yet.{" "}
            <button
              onClick={() => onNavigateToProject("")}
              className="text-blue-500 hover:underline"
            >
              Go to Projects tab →
            </button>
          </p>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden max-w-xl">
            <table className="w-full text-sm">
              <tbody>
                {linkedProjects.map((proj) => {
                  const link = proj.organizations.find((o) => o.organization_id === org.organization_id);
                  const roleDef = orgRoles.find((r) => r.key === link?.org_role);
                  const roleColor = link?.org_role
                    ? (ORG_ROLE_COLORS[link.org_role] ?? "bg-gray-100 text-gray-600 border-gray-200")
                    : "";
                  const contractorPkgs = packagesByProject[proj.project_id] ?? [];
                  return (
                    <React.Fragment key={proj.project_id}>
                      {/* Clickable project row → navigates to Projects tab with this project open */}
                      <tr
                        className="border-t border-gray-100 first:border-t-0 hover:bg-blue-50 cursor-pointer group transition-colors"
                        onClick={() => onNavigateToProject(proj.project_id)}
                      >
                        <td className="px-3 py-2.5">
                          <div className="font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                            {proj.name}
                          </div>
                          <div className="font-mono text-xs text-gray-400">{proj.short_code}</div>
                        </td>
                        <td className="px-3 py-2.5">
                          {roleDef ? (
                            <span className={`text-xs px-2 py-0.5 rounded border font-medium ${roleColor}`}>
                              {roleDef.label}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <span className="text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity">
                            Open →
                          </span>
                        </td>
                      </tr>
                      {/* Package contractor context (read-only) */}
                      {contractorPkgs.length > 0 && (
                        <tr
                          className="bg-orange-50/60 cursor-pointer"
                          onClick={() => onNavigateToProject(proj.project_id)}
                        >
                          <td colSpan={3} className="px-4 pb-2.5 pt-1">
                            <div className="flex flex-wrap gap-1.5 items-center">
                              <span className="text-xs text-gray-400 mr-0.5">Contractor on:</span>
                              {contractorPkgs.map((pkg) => (
                                <span
                                  key={pkg.package_id}
                                  title={pkg.name}
                                  className="text-xs font-mono bg-orange-100 text-orange-700 border border-orange-200 px-1.5 py-0.5 rounded"
                                >
                                  {pkg.package_code}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Locations section ─────────────────────────────────────────────────────────

function LocationsSection() {
  const [countries, setCountries] = useState<CountryItem[]>([]);
  const [country, setCountry]     = useState("NP");
  const [level, setLevel]         = useState<number | "">("");
  const [parent, setParent]       = useState("");
  const [q, setQ]                 = useState("");
  const [nodes, setNodes]         = useState<LocationNode[]>([]);
  const [loadingNodes, setLoadingNodes] = useState(false);
  const [searched, setSearched]   = useState(false);

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [dryRun, setDryRun]         = useState(true);
  const [importing, setImporting]   = useState(false);
  const [importResult, setImportResult] = useState<{ locations_upserted: number; translations_upserted: number; dry_run: boolean } | null>(null);
  const [importError, setImportError] = useState("");

  useEffect(() => {
    listCountries().then(setCountries).catch(() => {});
  }, []);

  const selectedCountry = countries.find((c) => c.country_code === country);

  async function handleSearch() {
    setLoadingNodes(true);
    setSearched(true);
    try {
      const res = await listLocations({
        country,
        level: level !== "" ? (level as number) : undefined,
        parent: parent.trim() || undefined,
        q: q.trim() || undefined,
        limit: 200,
      });
      setNodes(res);
    } catch {
      setNodes([]);
    } finally {
      setLoadingNodes(false);
    }
  }

  function getName(node: LocationNode, lang = "en") {
    return node.translations.find((t) => t.lang_code === lang)?.name
      ?? node.translations[0]?.name
      ?? node.location_code;
  }

  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    try {
      const result = await importLocations(importFile, { country, dry_run: dryRun });
      setImportResult(result);
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const levelLabel = (n: number) =>
    selectedCountry?.level_defs.find((d) => d.level_number === n)?.level_name_en ?? `Level ${n}`;

  return (
    <div className="space-y-8">
      {/* ── Tree browser ── */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Browse location tree</h3>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Country</label>
            <select
              value={country}
              onChange={(e) => { setCountry(e.target.value); setLevel(""); setParent(""); }}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Level</label>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">All levels</option>
              {(selectedCountry?.level_defs ?? []).map((d) => (
                <option key={d.level_number} value={d.level_number}>{d.level_name_en}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Parent code</label>
            <input
              value={parent}
              onChange={(e) => setParent(e.target.value)}
              placeholder="e.g. NP_P1"
              className="text-sm border border-gray-300 rounded px-2 py-1.5 w-32 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Search name</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="e.g. Jhapa"
              className="text-sm border border-gray-300 rounded px-2 py-1.5 w-40 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loadingNodes}
            className="bg-slate-700 text-white text-sm px-4 py-1.5 rounded hover:bg-slate-800 disabled:opacity-50 transition"
          >
            {loadingNodes ? "Searching…" : "Search"}
          </button>
        </div>

        {searched && (
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            {nodes.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">No locations found.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-700 text-slate-100 text-left">
                    <th className="px-4 py-2.5 font-medium">Code</th>
                    <th className="px-4 py-2.5 font-medium">English name</th>
                    <th className="px-4 py-2.5 font-medium">Local name</th>
                    <th className="px-4 py-2.5 font-medium">Level</th>
                    <th className="px-4 py-2.5 font-medium">Parent</th>
                  </tr>
                </thead>
                <tbody>
                  {nodes.slice(0, 100).map((n) => (
                    <tr key={n.location_code} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs text-gray-600">{n.location_code}</td>
                      <td className="px-4 py-2 text-gray-800">{getName(n, "en")}</td>
                      <td className="px-4 py-2 text-gray-500">{getName(n, "ne") ?? "—"}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">{levelLabel(n.level_number)}</td>
                      <td className="px-4 py-2 font-mono text-xs text-gray-400">{n.parent_location_code ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {nodes.length > 100 && (
              <p className="text-xs text-gray-400 text-center py-2 border-t border-gray-100">
                Showing first 100 of {nodes.length} results. Refine your search to see more.
              </p>
            )}
          </div>
        )}
      </section>

      {/* ── Import ── */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Import location data</h3>
        <p className="text-xs text-gray-500 mb-4">
          Upload a CSV or nested JSON file to add or update locations. Operation is idempotent — safe to re-run.
          Super admin only.
        </p>

        {/* Template downloads */}
        <div className="flex gap-3 mb-5">
          <a
            href={getLocationTemplateCsvUrl()}
            download="location_template.csv"
            className="flex items-center gap-1.5 text-xs bg-white border border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50 px-3 py-1.5 rounded transition"
          >
            ⬇ Download CSV template
          </a>
          <a
            href={getLocationTemplateJsonUrl()}
            download="location_template.json"
            className="flex items-center gap-1.5 text-xs bg-white border border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50 px-3 py-1.5 rounded transition"
          >
            ⬇ Download JSON template
          </a>
        </div>

        {/* Upload form */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3 max-w-xl">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-1">Country</label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {countries.map((c) => <option key={c.country_code} value={c.country_code}>{c.name}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                type="checkbox"
                id="dry-run-check"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="w-3.5 h-3.5"
              />
              <label htmlFor="dry-run-check" className="text-xs text-gray-600 cursor-pointer">
                Preview only (dry run)
              </label>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 block mb-1">File (CSV or JSON)</label>
            <input
              type="file"
              accept=".csv,.json"
              onChange={(e) => { setImportFile(e.target.files?.[0] ?? null); setImportResult(null); setImportError(""); }}
              className="w-full text-xs text-gray-600 file:mr-3 file:text-xs file:py-1.5 file:px-3 file:rounded file:border file:border-gray-300 file:bg-white file:text-gray-700 hover:file:bg-gray-50"
            />
          </div>

          <button
            onClick={handleImport}
            disabled={!importFile || importing}
            className="bg-blue-600 text-white text-sm px-5 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-40 transition"
          >
            {importing ? "Importing…" : dryRun ? "Preview import" : "Import"}
          </button>

          {importError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {importError}
            </p>
          )}

          {importResult && (
            <div className={`text-xs rounded px-3 py-2 border ${importResult.dry_run ? "bg-amber-50 border-amber-200 text-amber-800" : "bg-green-50 border-green-200 text-green-800"}`}>
              {importResult.dry_run ? "Preview: " : "✓ Imported: "}
              <strong>{importResult.locations_upserted}</strong> locations,{" "}
              <strong>{importResult.translations_upserted}</strong> translations
              {importResult.dry_run && " — uncheck 'Preview only' and re-upload to commit."}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ── Projects section ──────────────────────────────────────────────────────────

function ProjectsSection({ initialEditId = null }: { initialEditId?: string | null }) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [orgs, setOrgs]         = useState<OrganizationItem[]>([]);
  const [orgRoles, setOrgRoles] = useState<OrgRole[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [editing, setEditing]   = useState<ProjectItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [p, o] = await Promise.all([listProjects(), listOrganizations()]);
      const r = await getOrgRoles().catch(() => [] as OrgRole[]);
      setProjects(p);
      setOrgs(o);
      setOrgRoles(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Auto-open a project when navigated here from the Org tab
  useEffect(() => {
    if (!initialEditId || projects.length === 0) return;
    const target = projects.find((p) => p.project_id === initialEditId);
    if (target) setEditing(target);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialEditId, projects]);

  if (editing) {
    return (
      <ProjectEditor
        project={editing}
        orgs={orgs}
        orgRoles={orgRoles}
        onBack={() => { setEditing(null); load(); }}
        onUpdated={(p) => setEditing(p)}
      />
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">{projects.length} project{projects.length !== 1 ? "s" : ""}</p>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded hover:bg-blue-700 transition font-medium"
        >
          + New Project
        </button>
      </div>

      {showCreate && (
        <ProjectCreateModal
          orgs={orgs}
          onCreated={(p) => { setShowCreate(false); setProjects((prev) => [...prev, p]); setEditing(p); }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {loading && <p className="text-sm text-gray-400 animate-pulse">Loading…</p>}
      {error   && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100">
          {projects.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">No projects yet.</p>
          ) : projects.map((p) => {
            const orgSummary = p.organizations.map((po) => {
              const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
              const roleDef = orgRoles.find((r) => r.key === po.org_role);
              return roleDef ? `${orgName} (${roleDef.label})` : orgName;
            });
            return (
              <div key={p.project_id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 text-sm">{p.name}</span>
                    <span className="font-mono text-xs text-gray-400">{p.short_code}</span>
                    {!p.is_active && <span className="text-xs text-gray-400">(inactive)</span>}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-3">
                    <span>Orgs: {orgSummary.length > 0 ? orgSummary.join(", ") : <em>none</em>}</span>
                    <span>·</span>
                    <span>Locations: {p.location_codes.length > 0 ? `${p.location_codes.length} linked` : <em>none</em>}</span>
                  </div>
                </div>
                <button onClick={() => setEditing(p)} className="text-sm text-blue-600 hover:underline shrink-0">
                  Edit
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProjectCreateModal({
  orgs,
  onCreated,
  onClose,
}: {
  orgs: OrganizationItem[];
  onCreated: (p: ProjectItem) => void;
  onClose: () => void;
}) {
  const [name, setName]         = useState("");
  const [shortCode, setShortCode] = useState("");
  const [country, setCountry]   = useState("NP");
  const [desc, setDesc]         = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");

  async function handleCreate() {
    if (!name.trim() || !shortCode.trim()) { setError("Name and short code are required."); return; }
    setCreating(true); setError("");
    try {
      const p = await createProject({ name: name.trim(), short_code: shortCode.trim().toUpperCase(), country_code: country, description: desc.trim() || null });
      onCreated(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New project</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project name *</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Kakarbhitta-Laukahi Road"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Short code * <span className="font-normal text-gray-400">(unique)</span></label>
              <input value={shortCode} onChange={(e) => setShortCode(e.target.value.toUpperCase())}
                placeholder="KL_ROAD"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Country</label>
              <select value={country} onChange={(e) => setCountry(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
                <option value="NP">Nepal (NP)</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
              <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !name.trim() || !shortCode.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectEditor({
  project: initial,
  orgs,
  orgRoles,
  onBack,
  onUpdated,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  orgRoles: OrgRole[];
  onBack: () => void;
  onUpdated: (p: ProjectItem) => void;
}) {
  const [p, setP]             = useState<ProjectItem>(initial);
  const [editingName, setEditingName] = useState(false);
  const [nameVal, setNameVal] = useState(p.name);
  const [descVal, setDescVal] = useState(p.description ?? "");
  const [msg, setMsg]         = useState("");
  const [addingOrg, setAddingOrg]     = useState("");
  const [addingOrgRole, setAddingOrgRole] = useState("");
  const [working, setWorking] = useState(false);
  const [locError, setLocError] = useState("");

  function flash(t: string) { setMsg(t); setTimeout(() => setMsg(""), 2500); }

  async function saveMeta() {
    try {
      const updated = await updateProject(p.project_id, { name: nameVal.trim(), description: descVal.trim() || null });
      setP(updated); onUpdated(updated); flash("Saved ✓");
    } catch { flash("Save failed"); }
    setEditingName(false);
  }

  async function handleAddOrg() {
    if (!addingOrg) return;
    setWorking(true);
    try {
      const item = await addProjectOrg(p.project_id, addingOrg, addingOrgRole || null);
      setP({ ...p, organizations: [...p.organizations, item] });
      setAddingOrg(""); setAddingOrgRole(""); flash("Organization linked ✓");
    } catch { flash("Failed"); }
    setWorking(false);
  }

  async function handleRemoveOrg(orgId: string) {
    setWorking(true);
    try {
      await removeProjectOrg(p.project_id, orgId);
      setP({ ...p, organizations: p.organizations.filter((o) => o.organization_id !== orgId) });
      flash("Removed ✓");
    } catch { flash("Failed"); }
    setWorking(false);
  }

  async function handleRoleChange(orgId: string, newRole: string | null) {
    try {
      const updated = await updateProjectOrgRole(p.project_id, orgId, newRole);
      setP({ ...p, organizations: p.organizations.map((o) => o.organization_id === orgId ? updated : o) });
      flash("Role updated ✓");
    } catch { flash("Failed"); }
  }

  async function handleAddLoc(code: string) {
    if (!code) return;
    setWorking(true); setLocError("");
    try {
      await addProjectLocation(p.project_id, code);
      setP({ ...p, location_codes: [...p.location_codes, code] });
      flash("Location linked ✓");
    } catch (e: unknown) {
      setLocError(e instanceof Error && e.message.includes("404") ? `Location '${code}' not found` : "Failed");
    }
    setWorking(false);
  }

  async function handleRemoveLoc(code: string) {
    setWorking(true);
    try {
      await removeProjectLocation(p.project_id, code);
      setP({ ...p, location_codes: p.location_codes.filter((x) => x !== code) });
      flash("Removed ✓");
    } catch { flash("Failed"); }
    setWorking(false);
  }

  // ── Packages ──
  const [packages, setPackages]           = useState<PackageItem[]>([]);
  const [pkgLoading, setPkgLoading]       = useState(true);
  const [showCreatePkg, setShowCreatePkg] = useState(false);
  const [expandedPkg, setExpandedPkg]     = useState<string | null>(null);

  useEffect(() => {
    listPackages(p.project_id)
      .then(setPackages)
      .catch(() => {/* non-fatal */})
      .finally(() => setPkgLoading(false));
  }, [p.project_id]);

  async function handleUpdatePkg(packageId: string, payload: Partial<PackageItem>) {
    try {
      const updated = await updatePackage(p.project_id, packageId, payload);
      setPackages((prev) => prev.map((pk) => pk.package_id === packageId ? updated : pk));
      flash("Saved ✓");
    } catch { flash("Failed"); }
  }

  async function handleAddPkgLoc(packageId: string, code: string) {
    const uc = code.trim().toUpperCase();
    if (!uc) return;
    try {
      await addPackageLocation(p.project_id, packageId, uc);
      setPackages((prev) => prev.map((pk) =>
        pk.package_id === packageId
          ? { ...pk, location_codes: [...pk.location_codes, uc] }
          : pk
      ));
      flash("Location added ✓");
    } catch (e: unknown) {
      flash(e instanceof Error && e.message.includes("404") ? `'${uc}' not found` : "Failed");
    }
  }

  async function handleRemovePkgLoc(packageId: string, code: string) {
    try {
      await removePackageLocation(p.project_id, packageId, code);
      setPackages((prev) => prev.map((pk) =>
        pk.package_id === packageId
          ? { ...pk, location_codes: pk.location_codes.filter((c) => c !== code) }
          : pk
      ));
    } catch { flash("Failed"); }
  }

  const linkedOrgIds = new Set(p.organizations.map((o) => o.organization_id));
  const availableOrgs = orgs.filter((o) => !linkedOrgIds.has(o.organization_id));

  return (
    <div>
      {/* Back + header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="text-gray-400 hover:text-gray-600 text-sm flex items-center gap-1">← Projects</button>
        <span className="text-gray-300">/</span>
        {editingName ? (
          <div className="flex items-center gap-2">
            <input autoFocus value={nameVal} onChange={(e) => setNameVal(e.target.value)}
              onBlur={saveMeta} onKeyDown={(e) => e.key === "Enter" && saveMeta()}
              className="text-lg font-semibold text-gray-800 border-b-2 border-blue-400 bg-transparent focus:outline-none" />
          </div>
        ) : (
          <h2 className="text-lg font-semibold text-gray-800 cursor-pointer hover:text-blue-600" onClick={() => setEditingName(true)} title="Click to rename">
            {p.name}
          </h2>
        )}
        <span className="font-mono text-sm text-gray-400">{p.short_code}</span>
        {msg && <span className="text-xs text-green-600 font-medium ml-2">{msg}</span>}
      </div>

      {/* Description */}
      <div className="mb-6">
        <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
        <textarea value={descVal} onChange={(e) => setDescVal(e.target.value)}
          onBlur={saveMeta} rows={2}
          placeholder="Project description…"
          className="w-full max-w-lg text-sm border border-gray-200 rounded px-3 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400" />
      </div>

      {/* Organizations */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Organizations</h3>

        {/* Linked orgs table */}
        {p.organizations.length === 0 ? (
          <p className="text-xs text-gray-400 italic mb-3">No organizations linked</p>
        ) : (
          <div className="border border-gray-200 rounded-lg overflow-hidden mb-3 max-w-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left border-b border-gray-200">
                  <th className="px-3 py-2 text-xs font-medium text-gray-500 w-1/2">Organization</th>
                  <th className="px-3 py-2 text-xs font-medium text-gray-500">Role in this project</th>
                  <th className="px-3 py-2 w-8" />
                </tr>
              </thead>
              <tbody>
                {p.organizations.map((po) => {
                  const orgName = orgs.find((o) => o.organization_id === po.organization_id)?.name ?? po.organization_id;
                  const roleDef = orgRoles.find((r) => r.key === po.org_role);
                  const roleColor = po.org_role ? (ORG_ROLE_COLORS[po.org_role] ?? "bg-gray-100 text-gray-600 border-gray-200") : "";
                  return (
                    <tr key={po.organization_id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-2.5 font-medium text-gray-800">{orgName}</td>
                      <td className="px-3 py-2.5">
                        <select
                          value={po.org_role ?? ""}
                          onChange={(e) => handleRoleChange(po.organization_id, e.target.value || null)}
                          disabled={working}
                          className={`text-xs px-2 py-1 rounded border font-medium focus:outline-none focus:ring-1 focus:ring-blue-300 ${
                            roleDef ? roleColor : "text-gray-400 border-gray-200 bg-white"
                          }`}
                        >
                          <option value="">— no role —</option>
                          {orgRoles.map((r) => (
                            <option key={r.key} value={r.key}>{r.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button onClick={() => handleRemoveOrg(po.organization_id)} disabled={working}
                          className="text-gray-300 hover:text-red-500 text-lg leading-none disabled:opacity-40">×</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Add org row */}
        {availableOrgs.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <select value={addingOrg} onChange={(e) => setAddingOrg(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">— select organization —</option>
              {availableOrgs.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
            </select>
            <select value={addingOrgRole} onChange={(e) => setAddingOrgRole(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">— role (optional) —</option>
              {orgRoles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
            </select>
            <button onClick={handleAddOrg} disabled={!addingOrg || working}
              className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 transition">
              Link
            </button>
          </div>
        )}
      </div>

      {/* Locations */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Linked locations</h3>
        <p className="text-xs text-gray-400 mb-3">
          Search for the provinces, districts or municipalities this project covers.
        </p>
        {locError && <p className="text-xs text-red-500 mb-2">{locError}</p>}
        <div className="flex flex-wrap gap-2 mb-3">
          {p.location_codes.length === 0 && <span className="text-xs text-gray-400 italic">No locations linked</span>}
          {p.location_codes.map((code) => (
            <span key={code} className="flex items-center gap-1.5 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full">
              {code}
              <button onClick={() => handleRemoveLoc(code)} disabled={working}
                className="text-blue-400 hover:text-red-500 leading-none disabled:opacity-50">×</button>
            </span>
          ))}
        </div>
        <div className="max-w-sm">
          <LocationSearch
            country={p.country_code || "NP"}
            placeholder="Search province, district or municipality…"
            excludeCodes={p.location_codes}
            onSelect={(code) => handleAddLoc(code)}
          />
        </div>
      </div>

      {/* Civil-works packages */}
      <div className="mt-8 pt-6 border-t border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-700">Packages</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Lots or contracts within this project. Each package has one contractor and covers specific locations.
              L1 officers are scoped to a package.
            </p>
          </div>
          <button
            onClick={() => setShowCreatePkg(true)}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 transition font-medium shrink-0"
          >
            + New Package
          </button>
        </div>

        {showCreatePkg && (
          <PackageCreateModal
            projectId={p.project_id}
            orgs={orgs}
            onCreated={(pkg) => { setPackages((prev) => [...prev, pkg]); setShowCreatePkg(false); setExpandedPkg(pkg.package_id); }}
            onClose={() => setShowCreatePkg(false)}
          />
        )}

        {pkgLoading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : packages.length === 0 ? (
          <p className="text-xs text-gray-400 italic">No packages defined yet.</p>
        ) : (
          <div className="space-y-2">
            {packages.map((pkg) => {
              const contractor = orgs.find((o) => o.organization_id === pkg.contractor_org_id);
              const expanded = expandedPkg === pkg.package_id;
              return (
                <PackageRow
                  key={pkg.package_id}
                  pkg={pkg}
                  orgs={orgs}
                  contractor={contractor}
                  expanded={expanded}
                  onToggle={() => setExpandedPkg(expanded ? null : pkg.package_id)}
                  onUpdate={(payload) => handleUpdatePkg(pkg.package_id, payload)}
                  onAddLoc={(code) => handleAddPkgLoc(pkg.package_id, code)}
                  onRemoveLoc={(code) => handleRemovePkgLoc(pkg.package_id, code)}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Package row (collapsed + expanded editor) ─────────────────────────────────

function PackageRow({
  pkg, orgs, contractor, expanded, onToggle, onUpdate, onAddLoc, onRemoveLoc,
}: {
  pkg:          PackageItem;
  orgs:         OrganizationItem[];
  contractor:   OrganizationItem | undefined;
  expanded:     boolean;
  onToggle:     () => void;
  onUpdate:     (payload: Partial<PackageItem>) => Promise<void>;
  onAddLoc:     (code: string) => Promise<void>;
  onRemoveLoc:  (code: string) => Promise<void>;
}) {
  const [nameVal, setNameVal]       = useState(pkg.name);
  const [descVal, setDescVal]       = useState(pkg.description ?? "");
  const [contractorVal, setContractorVal] = useState(pkg.contractor_org_id ?? "");
  const [saving, setSaving]         = useState(false);
  const [dirty, setDirty]           = useState(false);

  // Sync local state if pkg prop changes (e.g. after parent reload)
  React.useEffect(() => {
    setNameVal(pkg.name);
    setDescVal(pkg.description ?? "");
    setContractorVal(pkg.contractor_org_id ?? "");
    setDirty(false);
  }, [pkg.package_id, pkg.name, pkg.description, pkg.contractor_org_id]);

  async function handleSave() {
    setSaving(true);
    await onUpdate({ name: nameVal.trim(), description: descVal.trim() || null, contractor_org_id: contractorVal || null });
    setDirty(false);
    setSaving(false);
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* Collapsed header — always visible; click to expand/collapse edit form */}
      <button
        onClick={onToggle}
        className="group w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors cursor-pointer"
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
        <span className="text-xs text-gray-400 shrink-0">
          {contractor ? contractor.name : <em className="text-gray-300">No contractor</em>}
        </span>
        {pkg.location_codes.length > 0 && (
          <div className="flex gap-1 shrink-0">
            {pkg.location_codes.map((c) => (
              <span key={c} className="text-xs font-mono bg-blue-50 text-blue-600 border border-blue-200 px-1.5 py-0.5 rounded">
                {c}
              </span>
            ))}
          </div>
        )}
        {!pkg.is_active && <span className="text-xs text-gray-400 shrink-0">(inactive)</span>}
        {/* Edit hint — visible on hover when collapsed */}
        {!expanded && (
          <span className="text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-1">
            ✏ edit
          </span>
        )}
      </button>

      {/* Expanded edit form */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-4 bg-gray-50 space-y-4">
          <div className="grid grid-cols-2 gap-3">
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
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Contractor</label>
              <select
                value={contractorVal}
                onChange={(e) => { setContractorVal(e.target.value); setDirty(true); }}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— not assigned —</option>
                {orgs.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
              </select>
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
                <span key={c} className="flex items-center gap-1 text-xs font-mono bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                  {c}
                  <button onClick={() => onRemoveLoc(c)} className="text-blue-400 hover:text-red-500 leading-none">×</button>
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

// ── Package create modal ──────────────────────────────────────────────────────

function PackageCreateModal({
  projectId, orgs, onCreated, onClose,
}: {
  projectId: string;
  orgs: OrganizationItem[];
  onCreated: (pkg: PackageItem) => void;
  onClose: () => void;
}) {
  const [code, setCode]       = useState("");
  const [name, setName]       = useState("");
  const [desc, setDesc]       = useState("");
  const [contractor, setContractor] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError]     = useState("");

  async function handleCreate() {
    if (!code.trim() || !name.trim()) { setError("Package code and name are required."); return; }
    setCreating(true); setError("");
    try {
      const pkg = await createPackage(projectId, {
        package_code: code.trim(),
        name: name.trim(),
        description: desc.trim() || null,
        contractor_org_id: contractor || null,
      } as PackageCreate);
      onCreated(pkg);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Create failed";
      setError(msg.includes("409") ? `Code "${code.trim()}" already exists in this project.` : msg);
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New package</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Package / lot code *</label>
            <input autoFocus value={code} onChange={(e) => setCode(e.target.value)}
              placeholder="e.g. SHEP/OCB/KL/01"
              className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Name *</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lot 1 — Kakarbhitta to Sitapur"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <input value={desc} onChange={(e) => setDesc(e.target.value)}
              placeholder="e.g. Km 0+000 to Km 45+000"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Contractor <span className="font-normal text-gray-400">(optional, can assign later)</span></label>
            <select value={contractor} onChange={(e) => setContractor(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
              <option value="">— not assigned —</option>
              {orgs.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
            </select>
          </div>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !code.trim() || !name.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create package"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── System Config tab (super_admin only) ─────────────────────────────────────

function SystemConfigTab() {
  const [jsonText, setJsonText] = useState("");
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");
  const [saved, setSaved]       = useState(false);

  useEffect(() => {
    getOrgRoles()
      .then((roles) => setJsonText(JSON.stringify(roles, null, 2)))
      .catch(() => {
        // Seed not yet run — show the defaults inline
        setJsonText(JSON.stringify([
          { key: "donor",                  label: "Donor",                   description: "Financing institution (e.g. ADB, World Bank)" },
          { key: "executing_agency",       label: "Executing Agency",        description: "Government project owner (maître d'ouvrage)" },
          { key: "implementing_agency",    label: "Implementing Agency",     description: "Government implementation arm (maître d'œuvre)" },
          { key: "main_contractor",        label: "Main Contractor",         description: "Primary civil-works contractor" },
          { key: "subcontractor_t1",       label: "Subcontractor (Tier 1)",  description: "First-tier subcontractor" },
          { key: "subcontractor_t2",       label: "Subcontractor (Tier 2)",  description: "Second-tier or specialist subcontractor" },
          { key: "supervision_consultant", label: "Supervision Consultant",  description: "Engineer's Representative / contract administrator" },
          { key: "specialized_consultant", label: "Specialized Consultant",  description: "Environmental, social safeguards, resettlement, etc." },
        ], null, 2));
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true); setError(""); setSaved(false);
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) throw new Error("Must be a JSON array");
      for (const item of parsed) {
        if (!item.key || !item.label) throw new Error(`Each entry needs "key" and "label". Missing on: ${JSON.stringify(item)}`);
      }
      await setOrgRoles(parsed);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid JSON");
    }
    setSaving(false);
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-gray-800 mb-0.5">System Configuration</h2>
        <p className="text-xs text-gray-500">
          Super-admin only. Settings here rarely need changing. Edit JSON directly — like VS Code settings.
        </p>
      </div>

      {/* Org Roles section */}
      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Organization Role Vocabulary</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Defines the roles organizations can hold within a project (donor, contractor, consultant, etc.).
            Used in the Projects editor. Each entry requires <code className="bg-gray-200 px-1 rounded text-xs">key</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">label</code>, and optionally{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">description</code>.
          </p>
        </div>

        {loading ? (
          <p className="text-sm text-gray-400 animate-pulse">Loading…</p>
        ) : (
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            rows={24}
            spellCheck={false}
            className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
          />
        )}

        {error && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {saved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
          <span className="text-xs text-gray-400 ml-auto">
            Changes take effect on next project editor load
          </span>
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-4xl mb-4">🚧</div>
      <h3 className="text-base font-semibold text-gray-700 mb-1">{label}</h3>
      <p className="text-sm text-gray-400 max-w-xs">
        This section is coming in Week 3. Contact your administrator to make changes directly.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { isAdmin, roleKeys } = useAuth();
  const isSuperAdmin = roleKeys.includes("super_admin");
  const [activeTab, setActiveTab] = useState<Tab>("officers");

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <div className="text-3xl mb-3">🔒</div>
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  const visibleTabs = TABS.filter((t) => !t.superAdminOnly || isSuperAdmin);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">System configuration — admin access only</p>
      </div>

      {/* Horizontal tabs */}
      <div className="flex gap-0 border-b border-gray-200 mb-6">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "officers"        && <OfficersTab />}
      {activeTab === "roles"           && <RolesTab />}
      {activeTab === "workflows"       && <WorkflowsTab />}
      {activeTab === "organizations"   && <OrganizationsTab />}
      {activeTab === "report_schedule" && <ComingSoon label="Report Schedule" />}
      {activeTab === "system_config"   && isSuperAdmin && <SystemConfigTab />}
    </div>
  );
}
