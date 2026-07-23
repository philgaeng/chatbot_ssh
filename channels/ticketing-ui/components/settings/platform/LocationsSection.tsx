"use client";

/**
 * <LocationsSection> — Settings → Platform → Locations (super_admin only).
 *
 * Browses the country location tree (level / parent / free-text search) and drives the
 * CSV+JSON location import, including the dry-run preview and the downloadable templates.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import {
  listCountries,
  listLocations,
  importLocations,
  getLocationTemplateCsvUrl,
  getLocationTemplateJsonUrl,
  type CountryItem,
  type LocationNode,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

export function LocationsSection() {
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
      setImportError(friendlyError(e));
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
              placeholder="e.g. P1"
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
