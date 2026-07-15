"use client";

/**
 * <ProjectCreateModal> — creates a project (code + name + type), with entity-code
 * normalisation/validation shared via lib/entityCodes.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import { createProject, listProjects, listProjectTypes, type ProjectItem } from "@/lib/api";
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
  const [typeKey, setTypeKey]   = useState("construction_road");
  const [types, setTypes]       = useState<{ type_key: string; label: string }[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState("");
  const [resumeProject, setResumeProject] = useState<ProjectItem | null>(null);

  useEffect(() => {
    listProjectTypes(true)
      .then((rows) => {
        setTypes(rows.map((t) => ({ type_key: t.type_key, label: t.label })));
        if (rows.length && !rows.some((t) => t.type_key === "construction_road")) {
          setTypeKey(rows[0].type_key);
        }
      })
      .catch(() => {});
  }, []);

  async function handleCreate() {
    if (!name.trim()) { setError("Project name is required."); return; }
    const codeErr = validateEntityCode(shortCode, "Project code");
    if (codeErr) { setError(codeErr); return; }
    if (!typeKey) { setError("Select a project type."); return; }
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
              <label className="text-xs font-medium text-gray-500 block mb-1">Project type *</label>
              <select
                value={typeKey}
                onChange={(e) => setTypeKey(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {types.length === 0 ? (
                  <option value="construction_road">Construction (road)</option>
                ) : (
                  types.map((t) => (
                    <option key={t.type_key} value={t.type_key}>{t.label}</option>
                  ))
                )}
              </select>
              <p className="text-xs text-gray-400 mb-2">
                Workflows and actor roles come from the type. Project starts inactive until go-live checks pass.
                Clicking Create saves the project immediately — use Set up to finish configuration before activating.
              </p>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-gray-500 block mb-1">Project name *</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)}
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
          <button onClick={handleCreate} disabled={creating || !name.trim() || !shortCode.trim()}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition">
            {creating ? "Creating…" : "Create project"}
          </button>
        </div>
      </div>
    </div>
  );
}
