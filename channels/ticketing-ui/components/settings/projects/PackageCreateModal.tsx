"use client";

/**
 * <PackageCreateModal> — creates a package under a project, suggesting the next
 * package code from the existing set.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState } from "react";
import { createPackage, type PackageItem } from "@/lib/api";
import {
  normalizeEntityCodeInput,
  suggestNextPackageCode,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { friendlyError } from "@/components/settings/lib/friendlyError";

export function PackageCreateModal({
  projectId, existingCodes, onCreated, onClose,
}: {
  projectId: string;
  existingCodes: string[];
  onCreated: (pkg: PackageItem) => void;
  onClose: () => void;
}) {
  const [code, setCode]       = useState(() => suggestNextPackageCode(existingCodes));
  const [name, setName]       = useState("");
  const [desc, setDesc]       = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError]     = useState("");

  async function handleCreate() {
    if (!name.trim()) { setError("Package name is required."); return; }
    const codeErr = validateEntityCode(code, "Package code");
    if (codeErr) { setError(codeErr); return; }
    setCreating(true); setError("");
    try {
      const pkg = await createPackage(projectId, {
        package_code: normalizeEntityCodeInput(code),
        name: name.trim(),
        description: desc.trim() || null,
      });
      onCreated(pkg);
    } catch (e: unknown) {
      const msg = friendlyError(e);
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
            <label className="text-xs font-medium text-gray-500 block mb-1">Package code * <span className="font-normal text-gray-400">(unique within project)</span></label>
            <input autoFocus value={code} onChange={(e) => setCode(normalizeEntityCodeInput(e.target.value))}
              placeholder="01"
              maxLength={ENTITY_CODE_MAX_LEN}
              className="w-full text-sm font-mono border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
            <p className="text-xs text-gray-400 mt-1">Default is next package number. A–Z, 0–9, underscore, max {ENTITY_CODE_MAX_LEN}.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Name *</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Package 1 — Kakarbhitta to Sitapur"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Description</label>
            <input value={desc} onChange={(e) => setDesc(e.target.value)}
              placeholder="e.g. Km 0+000 to Km 45+000"
              className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          </div>
          <p className="text-xs text-gray-500">
            Say which districts it covers next. Organizations and officers come after that, under
            Organizations and Staffing.
          </p>
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
