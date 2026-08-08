"use client";

/**
 * <ProjectCreateModal> — new project: **type → name it**. Nothing else.
 *
 * **The "Organization in charge" picker was removed 2026-08-08** (Philippe: organizations are
 * allocated after). It was already not an organization *of* the project — creation stopped
 * filling any slot on 2026-08-04, after writing the chosen organization into the type's first
 * required role and dropping a government department into a "Donor" slot whenever a type
 * happened to list Donor first. What survived was a required field that narrowed the type
 * dropdown and was then thrown away: never sent to `POST /projects`, recorded nowhere.
 *
 * It did not even narrow usefully. `GET /project-types` already returns the global types plus
 * the caller's own subtree (doc 13 §3.1), so asking for the organization made the author do by
 * hand what authority scoping does anyway — and made it a blocking first step.
 *
 * Organizations are named by role on the project screen, where the type says which ones the
 * project needs and go-live blocks until the required ones are filled. Workflows and category
 * routing come from the type; what is left after that is packages and officers — the work that
 * needs local knowledge.
 */
import React, { useState, useEffect } from "react";
import {
  createProject,
  listProjects,
  listProjectTypes,
  type ProjectItem,
  type ProjectTypeItem,
} from "@/lib/api";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { friendlyError } from "@/components/settings/lib/friendlyError";


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
  const [typeKey, setTypeKey]   = useState("");
  const [types, setTypes]       = useState<ProjectTypeItem[]>([]);
  const [typesLoading, setTypesLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");
  const [resumeProject, setResumeProject] = useState<ProjectItem | null>(null);

  // Every type the caller may use — the endpoint already scopes to the global ones plus the
  // caller's own subtree (doc 13 §3.1), which is exactly the list an "organization in charge"
  // picker used to narrow by hand.
  useEffect(() => {
    setTypesLoading(true);
    listProjectTypes(true)
      .then((rows) => {
        setTypes(rows);
        setTypeKey((prev) => (rows.some((t) => t.type_key === prev) ? prev : rows[0]?.type_key ?? ""));
      })
      .catch(() => setTypes([]))
      .finally(() => setTypesLoading(false));
  }, []);

  const selectedType = types.find((t) => t.type_key === typeKey) ?? null;
  const requiredRoles = selectedType?.actor_roles.filter((r) => r.required) ?? [];

  async function handleCreate() {
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
              <label className="text-xs font-medium text-gray-500 block mb-1" htmlFor="new-project-type">
                Project type *
              </label>
              <select
                id="new-project-type"
                value={typeKey}
                disabled={typesLoading}
                onChange={(e) => setTypeKey(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:bg-gray-50"
              >
                {typesLoading ? (
                  <option value="">Loading…</option>
                ) : types.length === 0 ? (
                  <option value="">No project types yet — add one under Workflows</option>
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
                  {requiredRoles.length
                    ? ` · you will name: ${requiredRoles.map((r) => r.label).join(", ")}`
                    : ""}
                </p>
              )}
              {!typesLoading && types.length === 0 && (
                <p className="text-xs text-amber-700 mt-1">
                  Create one under Workflows → Project types first.
                </p>
              )}
              <p className="text-xs text-gray-400 mt-1">
                Workflows come from the type. You name its organizations on the project screen —
                it stays inactive until the go-live checks pass.
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
          <button onClick={handleCreate} disabled={creating || !typeKey || !name.trim() || !shortCode.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}
