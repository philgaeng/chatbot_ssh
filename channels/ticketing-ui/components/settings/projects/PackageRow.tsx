// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <PackageRow> — one package inside <ProjectEditor>: what it is called, and where it works.
 *
 * **Four attributes, and that is all** (Philippe, 2026-08-08): code, name, description,
 * locations. Two things used to live here and no longer do:
 *
 *  • **Organizations** moved to the Organizations section. Naming a contractor per package is
 *    an *override* of the project-wide one, needed only when a package differs — but the panel
 *    that edited it was always open on every package, with an empty state reading like a
 *    to-do, so a rare exception looked like a required step on every row. The whole picture
 *    (project-level slots, then the packages that differ) reads better in one place.
 *  • **Staffing** moved out 2026-08-04, for the same reason.
 *
 * **Every package is an ordinary package** (2026-08-09). The auto-created first one used to
 * carry an `is_unnamed` flag: it took the *project's* name and the card hid its code, name and
 * description, showing "Everywhere this project works". That read as a mistake beside "Package
 * 2" — and the package most likely to want a chainage description was the one that could not
 * have one. It is called "Package 1" now, and is renamed and described like any other.
 */
import React, { useState } from "react";
import { type PackageItem } from "@/lib/api";
import {
  normalizeEntityCodeInput,
  validateEntityCode,
  ENTITY_CODE_MAX_LEN,
} from "@/lib/entityCodes";
import { LocationSearch } from "@/components/LocationSearch";
import { IconWarning } from "@/lib/icons";
import { warning } from "@/lib/design-tokens";

export function PackageRow({
  pkg,
  expanded,
  onToggle,
  onUpdate,
  onAddLoc,
  onRemoveLoc,
}: {
  pkg:          PackageItem;
  expanded:     boolean;
  onToggle:     () => void;
  onUpdate:     (payload: Partial<PackageItem>) => Promise<void>;
  onAddLoc:     (code: string) => Promise<void>;
  onRemoveLoc:  (code: string) => Promise<void>;
}) {
  const [codeVal, setCodeVal] = useState(pkg.package_code);
  const [nameVal, setNameVal] = useState(pkg.name);
  const [descVal, setDescVal] = useState(pkg.description ?? "");
  const [saving, setSaving]   = useState(false);
  const [dirty, setDirty]     = useState(false);

  React.useEffect(() => {
    setCodeVal(pkg.package_code);
    setNameVal(pkg.name);
    setDescVal(pkg.description ?? "");
    setDirty(false);
  }, [pkg.package_id, pkg.package_code, pkg.name, pkg.description]);

  async function handleSave() {
    if (validateEntityCode(codeVal, "Package code")) return;
    setSaving(true);
    await onUpdate({
      package_code: normalizeEntityCodeInput(codeVal),
      name: nameVal.trim(),
      description: descVal.trim() || null,
    });
    setDirty(false);
    setSaving(false);
  }

  /** The one thing that can be wrong here: a package nobody can route a grievance to (B2). */
  const noCoverage = pkg.location_codes.length === 0;

  return (
    <div className="border border-gray-200 rounded-lg">
      {/* Note: no overflow-hidden — LocationSearch uses a dropdown that must paint outside this card */}
      <button
        onClick={onToggle}
        className={`group w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors cursor-pointer ${
          expanded ? "rounded-t-lg" : "rounded-lg"
        }`}
        title={expanded ? "Collapse" : "Click to edit"}
      >
        <span
          className={`inline-block text-sm shrink-0 transition-transform duration-200 ${
            expanded ? "rotate-90 text-blue-500" : "text-gray-400"
          }`}
        >▶</span>
        <span className="font-mono text-xs text-gray-500 shrink-0">{pkg.package_code}</span>
        <span className={`font-medium text-sm flex-1 min-w-0 truncate ${expanded ? "text-blue-700" : "text-gray-800"}`}>
          {pkg.name}
        </span>
        {noCoverage && (
          // The project's standard warning element (02_design_system §2/§4 amber tokens,
          // §8 Lucide not emoji), saying the severity in words — never colour alone.
          <span
            className={`inline-flex items-center gap-1 shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${warning.borderLight} ${warning.bgLight} ${warning.textStrong}`}
            title="No districts yet — grievances cannot reach this package"
          >
            <IconWarning size={12} className="shrink-0" />
            <span className="truncate">No districts yet</span>
          </span>
        )}
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
        {!expanded && (
          <span className="text-xs italic text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-1">
            edit
          </span>
        )}
      </button>

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
                <label className="text-xs font-medium text-gray-500 block mb-1">
                  Description <span className="font-normal text-gray-400">(km range, scope)</span>
                </label>
                <input
                  value={descVal}
                  onChange={(e) => { setDescVal(e.target.value); setDirty(true); }}
                  placeholder="e.g. Km 0+000 to Km 45+000"
                  className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
              </div>
            </div>

          {/* Locations — the reason this card exists. */}
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-2">Districts covered</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {pkg.location_codes.length === 0 && (
                <span className="text-xs text-gray-400 italic">
                  None yet — grievances cannot reach this package until you add one.
                </span>
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

          <div className="flex flex-wrap items-center gap-5 pt-1">
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
