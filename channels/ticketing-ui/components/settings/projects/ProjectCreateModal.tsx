"use client";

/**
 * <ProjectCreateModal> — new project: **organization → type → name it**.
 *
 * The order is the decision (DECISION-author-defined-slots §5): the organization comes first
 * because it decides which templates are on offer, and it fills the type's first required
 * organization role, so nobody has to name it again on the project screen. Everything else
 * (workflows, category routing, the other organizations a project must name) comes from the
 * type. What is left afterwards is locations and officers, which is the work that actually
 * needs local knowledge.
 */
import React, { useState, useEffect } from "react";
import {
  createProject,
  listOrganizations,
  listProjects,
  listProjectTypes,
  type OrganizationItem,
  type ProjectItem,
  type ProjectTypeItem,
} from "@/lib/api";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { friendlyError } from "@/components/settings/lib/friendlyError";

const GOVERNMENT_CATEGORIES = new Set(["government", "local_government"]);

export function ProjectCreateModal({
  onCreated,
  onClose,
}: {
  onCreated: (p: ProjectItem) => void;
  onClose: () => void;
}) {
  const [name, setName]         = useState("");
  const [shortCode, setShortCode] = useState("");
  const [country, setCountry]   = useState("NP");
  const [desc, setDesc]         = useState("");
  const [orgId, setOrgId]       = useState("");
  const [orgs, setOrgs]         = useState<OrganizationItem[]>([]);
  const [typeKey, setTypeKey]   = useState("");
  const [types, setTypes]       = useState<ProjectTypeItem[]>([]);
  const [typesLoading, setTypesLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");
  const [resumeProject, setResumeProject] = useState<ProjectItem | null>(null);

  // The bodies that run projects: a ministry or a local body, at the top of its tree.
  // Contractors and consultants are named later, in the type's other slots.
  useEffect(() => {
    listOrganizations()
      .then((rows) =>
        setOrgs(
          rows.filter(
            (o) =>
              o.is_active
              && !o.parent_organization_id
              && GOVERNMENT_CATEGORIES.has((o.org_category ?? "").toLowerCase()),
          ),
        ),
      )
      .catch(() => {});
  }, []);

  // The organization decides what is on offer: its own templates plus the shared ones.
  useEffect(() => {
    if (!orgId) { setTypes([]); setTypeKey(""); return; }
    setTypesLoading(true);
    listProjectTypes(true, orgId)
      .then((rows) => {
        setTypes(rows);
        setTypeKey((prev) => (rows.some((t) => t.type_key === prev) ? prev : rows[0]?.type_key ?? ""));
      })
      .catch(() => setTypes([]))
      .finally(() => setTypesLoading(false));
  }, [orgId]);

  const selectedType = types.find((t) => t.type_key === typeKey) ?? null;
  /** The organization in charge fills the type's first required role, so the creator does not
   *  re-enter it on the project screen. (It filled the `routing_org_role` anchor until
   *  2026-08-04 — that concept is retired; see DECISION-organization-membership.) */
  const leadRoleLabel = selectedType?.actor_roles.find((r) => r.required)?.label ?? null;

  async function handleCreate() {
    if (!orgId) { setError("Choose the organization in charge of this project."); return; }
    if (!typeKey) { setError("Choose a project type."); return; }
    if (!name.trim()) { setError("Project name is required."); return; }
    const codeErr = validateEntityCode(shortCode, "Project code");
    if (codeErr) { setError(codeErr); return; }
    setCreating(true);
    setError("");
    setResumeProject(null);
    const code = normalizeEntityCodeInput(shortCode);
    try {
      const p = await createProject({
        name: name.trim(),
        short_code: code,
        country_code: country,
        description: desc.trim() || null,
        project_type_key: typeKey,
        organization_id: orgId,
        is_active: false,
      });
      onCreated(p);
    } catch (e: unknown) {
      const msg = friendlyError(e);
      if (msg.includes("already exists")) {
        try {
          const existing = (await listProjects(undefined, false)).find((p) => p.short_code === code) ?? null;
          setResumeProject(existing);
          if (existing) {
            setError(
              `Project code “${code}” is already in use (${existing.is_active ? "active" : "inactive, awaiting setup"}).`,
            );
          } else {
            setError(`${msg} Refresh the project list or contact an administrator.`);
          }
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
      setCreating(false);
    }
  }

  function handleResumeSetup() {
    if (resumeProject) onCreated(resumeProject);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New project</div>
          <button onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-6 space-y-4">
          {error && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2 space-y-2">
              <p>{error}</p>
              {resumeProject && (
                <button
                  type="button"
                  onClick={handleResumeSetup}
                  className="text-sm font-medium text-blue-700 hover:text-blue-900 underline"
                >
                  Resume setup — {resumeProject.short_code}
                  {!resumeProject.is_active ? " (inactive)" : ""}
                </button>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1" htmlFor="new-project-org">
                Organization in charge *
              </label>
              <select
                id="new-project-org"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— choose an organization —</option>
                {orgs.map((o) => (
                  <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
                ))}
              </select>
              <p className="text-xs text-gray-400 mt-1">
                It decides which project types you can use.
              </p>
            </div>

            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1" htmlFor="new-project-type">
                Project type *
              </label>
              <select
                id="new-project-type"
                value={typeKey}
                disabled={!orgId || typesLoading}
                onChange={(e) => setTypeKey(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
              >
                {!orgId ? (
                  <option value="">— choose an organization first —</option>
                ) : typesLoading ? (
                  <option value="">Loading…</option>
                ) : types.length === 0 ? (
                  <option value="">No project types for this organization</option>
                ) : (
                  types.map((t) => (
                    <option key={t.type_key} value={t.type_key}>{t.label}</option>
                  ))
                )}
              </select>
              {selectedType && (
                <p className="text-xs text-gray-500 mt-1">
                  {selectedType.description ? `${selectedType.description} ` : ""}
                  {selectedType.workflow_bindings.length}{" "}
                  {selectedType.workflow_bindings.length === 1 ? "workflow" : "workflows"}
                  {leadRoleLabel ? ` · this organization becomes the ${leadRoleLabel}` : ""}
                </p>
              )}
              {orgId && !typesLoading && types.length === 0 && (
                <p className="text-xs text-amber-700 mt-1">
                  Create one under Settings → Project types first.
                </p>
              )}
              <p className="text-xs text-gray-400 mt-1">
                Workflows and the organizations a project must name come from the type. The project
                starts inactive until the go-live checks pass.
              </p>
            </div>

            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project name *</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Kakarbhitta-Laukahi Road"
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Project code * <span className="font-normal text-gray-400">(unique, max {ENTITY_CODE_MAX_LEN})</span></label>
              <input value={shortCode} onChange={(e) => {
                setShortCode(normalizeEntityCodeInput(e.target.value));
                setResumeProject(null);
                setError("");
              }}
                placeholder="KL_ROAD"
                maxLength={ENTITY_CODE_MAX_LEN}
                className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 font-mono focus:outline-none focus:ring-1 focus:ring-blue-400" />
              <p className="text-xs text-gray-400 mt-1">A–Z, 0–9, underscore only.</p>
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
          <button onClick={handleCreate} disabled={creating || !orgId || !typeKey || !name.trim() || !shortCode.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}
