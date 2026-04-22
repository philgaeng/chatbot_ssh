"use client";

import React, { useState, useEffect, useCallback } from "react";
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
  type WorkflowDefinition,
  type WorkflowStep,
  type WorkflowAssignmentItem,
  type StepPayload,
  type OfficerScope,
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

type Tab = "officers" | "roles" | "workflows" | "organizations" | "report_schedule";

const TABS: { id: Tab; label: string }[] = [
  { id: "officers",        label: "Officers"                  },
  { id: "roles",           label: "Roles & Permissions"       },
  { id: "workflows",       label: "Workflows"                 },
  { id: "organizations",   label: "Organizations & Locations" },
  { id: "report_schedule", label: "Report Schedule"           },
];

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
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("officers");

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <div className="text-3xl mb-3">🔒</div>
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">System configuration — admin access only</p>
      </div>

      {/* Horizontal tabs */}
      <div className="flex gap-0 border-b border-gray-200 mb-6">
        {TABS.map((tab) => (
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
      {activeTab === "organizations"   && <ComingSoon label="Organizations & Locations" />}
      {activeTab === "report_schedule" && <ComingSoon label="Report Schedule" />}
    </div>
  );
}
