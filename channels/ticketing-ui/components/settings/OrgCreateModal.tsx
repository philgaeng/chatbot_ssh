"use client";

import { useState } from "react";
import { createOrganization, type CountryItem, type OrganizationCreate, type OrganizationItem } from "@/lib/api";
import { generateOrgId } from "@/lib/orgId";

export function OrgCreateModal({
  countries,
  existingOrganizationIds,
  defaultCountry = "NP",
  onCreated,
  onClose,
}: {
  countries: CountryItem[];
  existingOrganizationIds: Set<string>;
  defaultCountry?: string;
  onCreated: (org: OrganizationItem) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [country, setCountry] = useState(defaultCountry);
  const [isActive, setIsActive] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const generatedId = generateOrgId(name, country, existingOrganizationIds);

  async function handleCreate() {
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const org = await createOrganization({
        name: name.trim(),
        country_code: country || null,
        is_active: isActive,
      } as OrganizationCreate);
      onCreated(org);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
      setCreating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="bg-slate-700 text-white px-6 py-4 flex items-center justify-between">
          <div className="font-semibold">New organization</div>
          <button type="button" onClick={onClose} className="text-slate-300 hover:text-white text-xl leading-none">
            ×
          </button>
        </div>

        <div className="p-6 space-y-4">
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}

          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Full name *</label>
            <input
              autoFocus
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
                {countries.map((c) => (
                  <option key={c.country_code} value={c.country_code}>
                    {c.name} ({c.country_code})
                  </option>
                ))}
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

          {generatedId ? (
            <p className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded px-3 py-2">
              Will be created as: <span className="font-mono font-semibold text-gray-700">{generatedId}</span>
            </p>
          ) : (
            name.trim() && <p className="text-xs text-amber-600">Enter a valid name to generate the ID.</p>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleCreate()}
            disabled={creating || !name.trim() || !generatedId}
            className="text-sm bg-blue-600 text-white hover:bg-blue-700 px-4 py-1.5 rounded font-medium disabled:opacity-50 transition"
          >
            {creating ? "Creating…" : "Create organization"}
          </button>
        </div>
      </div>
    </div>
  );
}
