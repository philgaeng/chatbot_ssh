"use client";

/**
 * <SystemConfigTab> — Settings → Platform → Advanced (super_admin only).
 *
 * Raw-JSON editors for the three platform-wide config documents: report limits,
 * archiving policy, and the grievance categories catalog. Each editor validates the
 * JSON locally before PUTting it, and can reset to the DEFAULT_*_JSON shapes below.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import {
  getReportLimits,
  setReportLimits,
  getArchivingPolicy,
  setArchivingPolicy,
  getGrievanceCategoriesCatalog,
  setGrievanceCategoriesCatalog,
  getOrgRoles,
  setOrgRoles,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

const DEFAULT_REPORT_LIMITS_JSON = {
  max_export_rows: 100,
  max_exports_per_user_per_hour: 10,
  max_reports_per_role_per_quarter: 3,
  quarterly_email_enabled: true,
  allowed_recipient_roles: [
    "adb_national_project_director",
    "adb_hq_safeguards",
    "adb_hq_project",
    "mopit_rep",
    "dor_rep",
  ],
};

const DEFAULT_ARCHIVING_POLICY_JSON = {
  enabled: true,
  years_before_archiving: 1,
  archive_run_month: 1,
  archive_run_day: 2,
  timezone: "Asia/Kathmandu",
  attachment_tier_on_archive: "none",
  allow_complainant_download_when_archived: false,
  seah_years_before_archiving: null,
};

const DEFAULT_GRIEVANCE_CATEGORIES_JSON = { categories: [] };

export function SystemConfigTab() {
  const [jsonText, setJsonText] = useState("");
  const [limitsJson, setLimitsJson] = useState("");
  const [archivingJson, setArchivingJson] = useState("");
  const [categoriesJson, setCategoriesJson] = useState("");
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [savingLimits, setSavingLimits] = useState(false);
  const [savingArchiving, setSavingArchiving] = useState(false);
  const [savingCategories, setSavingCategories] = useState(false);
  const [error, setError]       = useState("");
  const [limitsError, setLimitsError] = useState("");
  const [archivingError, setArchivingError] = useState("");
  const [categoriesError, setCategoriesError] = useState("");
  const [saved, setSaved]       = useState(false);
  const [limitsSaved, setLimitsSaved] = useState(false);
  const [archivingSaved, setArchivingSaved] = useState(false);
  const [categoriesSaved, setCategoriesSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      getOrgRoles().catch(() => null),
      getReportLimits().catch(() => null),
      getArchivingPolicy().catch(() => null),
      getGrievanceCategoriesCatalog().catch(() => null),
    ])
      .then(([roles, limits, archiving, categories]) => {
        if (roles) {
          setJsonText(JSON.stringify(roles, null, 2));
        } else {
          setJsonText(
            JSON.stringify(
              [
                { key: "donor", label: "Donor", description: "Financing institution (e.g. ADB, World Bank)" },
                { key: "executing_agency", label: "Executing Agency", description: "Government project owner" },
                { key: "implementing_agency", label: "Implementing Agency", description: "Government implementation arm" },
                { key: "main_contractor", label: "Main Contractor", description: "Primary civil-works contractor" },
                { key: "subcontractor_t1", label: "Subcontractor (Tier 1)", description: "First-tier subcontractor" },
                { key: "subcontractor_t2", label: "Subcontractor (Tier 2)", description: "Second-tier subcontractor" },
                { key: "supervision_consultant", label: "Supervision Consultant", description: "Engineer's Representative" },
                { key: "specialized_consultant", label: "Specialized Consultant", description: "Safeguards, resettlement, etc." },
              ],
              null,
              2,
            ),
          );
        }
        setLimitsJson(JSON.stringify(limits ?? DEFAULT_REPORT_LIMITS_JSON, null, 2));
        setArchivingJson(JSON.stringify(archiving ?? DEFAULT_ARCHIVING_POLICY_JSON, null, 2));
        setCategoriesJson(
          JSON.stringify(categories ?? DEFAULT_GRIEVANCE_CATEGORIES_JSON, null, 2),
        );
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
      setError(friendlyError(e));
    }
    setSaving(false);
  }

  async function handleSaveLimits() {
    setSavingLimits(true);
    setLimitsError("");
    setLimitsSaved(false);
    try {
      const parsed = JSON.parse(limitsJson);
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Must be a JSON object");
      }
      await setReportLimits(parsed);
      setLimitsSaved(true);
      setTimeout(() => setLimitsSaved(false), 2500);
    } catch (e: unknown) {
      setLimitsError(friendlyError(e));
    }
    setSavingLimits(false);
  }

  async function handleSaveArchiving() {
    setSavingArchiving(true);
    setArchivingError("");
    setArchivingSaved(false);
    try {
      const parsed = JSON.parse(archivingJson);
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Must be a JSON object");
      }
      await setArchivingPolicy(parsed);
      setArchivingSaved(true);
      setTimeout(() => setArchivingSaved(false), 2500);
    } catch (e: unknown) {
      setArchivingError(friendlyError(e));
    }
    setSavingArchiving(false);
  }

  async function handleSaveCategories() {
    setSavingCategories(true);
    setCategoriesError("");
    setCategoriesSaved(false);
    try {
      const parsed = JSON.parse(categoriesJson);
      if (typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Must be a JSON object with a categories array");
      }
      if (!Array.isArray(parsed.categories) || parsed.categories.length === 0) {
        throw new Error("categories must be a non-empty array");
      }
      for (const item of parsed.categories) {
        if (!item.classification || !item.generic_grievance_name) {
          throw new Error(
            'Each category needs "classification" and "generic_grievance_name"',
          );
        }
      }
      await setGrievanceCategoriesCatalog(parsed);
      setCategoriesSaved(true);
      setTimeout(() => setCategoriesSaved(false), 2500);
    } catch (e: unknown) {
      setCategoriesError(friendlyError(e));
    }
    setSavingCategories(false);
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

      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5 mt-6">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Report dispatch limits</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Caps exports and quarterly emails for all projects. Local admins configure templates
            within these limits. Keys:{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_export_rows</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_exports_per_user_per_hour</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">max_reports_per_role_per_quarter</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">quarterly_email_enabled</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">allowed_recipient_roles</code>.
          </p>
        </div>
        <textarea
          value={limitsJson}
          onChange={(e) => setLimitsJson(e.target.value)}
          rows={16}
          spellCheck={false}
          disabled={loading}
          className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
        />
        {limitsError && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {limitsError}
          </p>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSaveLimits}
            disabled={savingLimits || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {savingLimits ? "Saving…" : "Save report limits"}
          </button>
          {limitsSaved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
        </div>
      </section>

      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5 mt-6">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Archiving and retention</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Resolved cases archive after{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">years_before_archiving</code> full
            calendar years (eligible from 2 January). Daily Celery job at 03:00 Asia/Kathmandu.
            Keys:{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">enabled</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">years_before_archiving</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">attachment_tier_on_archive</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">seah_years_before_archiving</code>.
          </p>
        </div>
        <textarea
          value={archivingJson}
          onChange={(e) => setArchivingJson(e.target.value)}
          rows={14}
          spellCheck={false}
          disabled={loading}
          className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
        />
        {archivingError && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {archivingError}
          </p>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSaveArchiving}
            disabled={savingArchiving || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {savingArchiving ? "Saving…" : "Save archiving policy"}
          </button>
          {archivingSaved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
        </div>
      </section>

      <section className="bg-gray-50 border border-gray-200 rounded-lg p-5 mt-6">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-gray-700 mb-0.5">Grievance classification catalog</h3>
          <p className="text-xs text-gray-500 leading-relaxed">
            Complaint categories for LLM classification and officer validation. Saving syncs to{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">public.grievance_classification_taxonomy</code>.
            Each entry in <code className="bg-gray-200 px-1 rounded text-xs">categories</code> supports:{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">category_key</code> (optional — derived from
            classification + generic name),{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">generic_grievance_name</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">generic_grievance_name_ne</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">short_description</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">short_description_ne</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">classification</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">classification_ne</code>,{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">description</code> (LLM prompt text),{" "}
            <code className="bg-gray-200 px-1 rounded text-xs">description_ne</code>, follow-up question
            fields, and <code className="bg-gray-200 px-1 rounded text-xs">high_priority</code>.
          </p>
        </div>
        <textarea
          value={categoriesJson}
          onChange={(e) => setCategoriesJson(e.target.value)}
          rows={28}
          spellCheck={false}
          disabled={loading}
          className="w-full font-mono text-xs bg-white border border-gray-300 rounded px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-400 resize-y"
        />
        {categoriesError && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {categoriesError}
          </p>
        )}
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            onClick={handleSaveCategories}
            disabled={savingCategories || loading}
            className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded font-medium hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {savingCategories ? "Saving…" : "Save classification catalog"}
          </button>
          {categoriesSaved && <span className="text-xs text-green-600 font-medium">✓ Saved</span>}
        </div>
      </section>
    </div>
  );
}
