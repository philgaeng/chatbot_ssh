"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  BarChart2,
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
  Plus,
  Settings,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import {
  downloadBuildReportXlsx,
  buildReportJson,
  downloadExportReportXlsx,
  fetchReportFields,
  queryReport,
  saveToQuarterlyLibrary,
  type PivotConfig,
  type ReportBucket,
  type ReportBuildResult,
  type ReportQueryResponse,
  type ReportRow,
} from "@/lib/api";
import { PivotBuilder } from "@/components/reports/PivotBuilder";
import { PivotPreviewTable } from "@/components/reports/PivotPreviewTable";
import { QuarterlyPlanTab } from "@/components/reports/QuarterlyPlanTab";
import { SummaryTab } from "@/components/reports/SummaryTab";
import {
  listLocations,
  listProjects,
  listPackages,
  type LocationNode,
  type ProjectItem,
  type PackageItem,
} from "@/lib/api";

const TEMPLATE_STORAGE_KEY = "grm_report_templates";

type PeriodPreset = "this_month" | "last_month" | "this_quarter" | "last_quarter" | "ytd" | "custom";

type ReportTemplate = {
  id: string;
  name: string;
  pivot: PivotConfig;
};

const DEFAULT_PIVOT: PivotConfig = {
  rows: ["project_name"],
  columns: ["complaint_category"],
  values: [{ field: "ticket_id", agg: "count" }],
  filters: {},
};

function quarterStart(d = new Date()): string {
  const q = Math.floor(d.getMonth() / 3);
  return new Date(d.getFullYear(), q * 3, 1).toISOString().split("T")[0];
}

function periodRange(preset: PeriodPreset): { from: string; to: string } {
  const today = new Date();
  const to = today.toISOString().split("T")[0];
  const y = today.getFullYear();
  const m = today.getMonth();
  switch (preset) {
    case "this_month":
      return { from: new Date(y, m, 1).toISOString().split("T")[0], to };
    case "last_month":
      return { from: new Date(y, m - 1, 1).toISOString().split("T")[0], to: new Date(y, m, 0).toISOString().split("T")[0] };
    case "this_quarter":
      return { from: quarterStart(today), to };
    case "last_quarter": {
      const q = Math.floor(m / 3);
      const start = new Date(y, (q - 1) * 3, 1);
      const end = new Date(y, q * 3, 0);
      return { from: start.toISOString().split("T")[0], to: end.toISOString().split("T")[0] };
    }
    case "ytd":
      return { from: `${y}-01-01`, to };
    default:
      return { from: quarterStart(today), to };
  }
}

const SECTION_META: { key: ReportBucket; title: string; hint: string; accent: string }[] = [
  { key: "resolved", title: "Resolved", hint: "Created in period and closed", accent: "border-green-300 bg-green-50" },
  { key: "high", title: "High", hint: "High/Critical priority, SEAH, or overdue (may overlap Overdue)", accent: "border-amber-300 bg-amber-50" },
  { key: "overdue", title: "Overdue", hint: "Past SLA deadline — active cases", accent: "border-red-300 bg-red-50" },
  { key: "other", title: "Others", hint: "Active cases not in High or Overdue", accent: "border-gray-200 bg-gray-50" },
];

function loadTemplates(): ReportTemplate[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(TEMPLATE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Array<ReportTemplate & { columns?: string[] }>;
    return parsed.map((t) =>
      t.pivot ? t : { id: t.id, name: t.name, pivot: DEFAULT_PIVOT },
    );
  } catch {
    return [];
  }
}

function saveTemplates(templates: ReportTemplate[]) {
  localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
}

// ── Shared filters ────────────────────────────────────────────────────────────

function ReportFilters({
  periodPreset,
  setPeriodPreset,
  dateFrom,
  setDateFrom,
  dateTo,
  setDateTo,
  projects,
  selectedProjectIds,
  setSelectedProjectIds,
  packages,
  selectedPackageIds,
  setSelectedPackageIds,
  locations,
  selectedLocationCodes,
  setSelectedLocationCodes,
  includeSeah,
  setIncludeSeah,
  showSeahToggle,
}: {
  periodPreset: PeriodPreset;
  setPeriodPreset: (p: PeriodPreset) => void;
  dateFrom: string;
  setDateFrom: (v: string) => void;
  dateTo: string;
  setDateTo: (v: string) => void;
  projects: ProjectItem[];
  selectedProjectIds: string[];
  setSelectedProjectIds: (ids: string[]) => void;
  packages: PackageItem[];
  selectedPackageIds: string[];
  setSelectedPackageIds: (ids: string[]) => void;
  locations: LocationNode[];
  selectedLocationCodes: string[];
  setSelectedLocationCodes: (codes: string[]) => void;
  includeSeah: boolean;
  setIncludeSeah: (v: boolean) => void;
  showSeahToggle: boolean;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Period</label>
          <select
            value={periodPreset}
            onChange={(e) => {
              const p = e.target.value as PeriodPreset;
              setPeriodPreset(p);
              if (p !== "custom") {
                const { from, to } = periodRange(p);
                setDateFrom(from);
                setDateTo(to);
              }
            }}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          >
            <option value="this_quarter">This quarter</option>
            <option value="last_quarter">Last quarter</option>
            <option value="this_month">This month</option>
            <option value="last_month">Last month</option>
            <option value="ytd">Year to date</option>
            <option value="custom">Custom range</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPeriodPreset("custom"); }}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPeriodPreset("custom"); }}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>
        {showSeahToggle && (
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-gray-700 pb-2">
              <input
                type="checkbox"
                checked={includeSeah}
                onChange={(e) => setIncludeSeah(e.target.checked)}
              />
              Include SEAH cases
            </label>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Projects (empty = all)</label>
          <select
            multiple
            value={selectedProjectIds}
            onChange={(e) => {
              const ids = Array.from(e.target.selectedOptions, (o) => o.value);
              setSelectedProjectIds(ids);
            }}
            className="w-full border border-gray-300 rounded px-2 py-2 text-sm h-24"
          >
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Packages</label>
          <select
            multiple
            value={selectedPackageIds}
            onChange={(e) => setSelectedPackageIds(Array.from(e.target.selectedOptions, (o) => o.value))}
            className="w-full border border-gray-300 rounded px-2 py-2 text-sm h-24"
            disabled={packages.length === 0}
          >
            {packages.map((pkg) => (
              <option key={pkg.package_id} value={pkg.package_id}>{pkg.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Locations (includes children)</label>
          <select
            multiple
            value={selectedLocationCodes}
            onChange={(e) => setSelectedLocationCodes(Array.from(e.target.selectedOptions, (o) => o.value))}
            className="w-full border border-gray-300 rounded px-2 py-2 text-sm h-24"
          >
            {locations.map((loc) => (
              <option key={loc.location_code} value={loc.location_code}>
                {loc.translations.find((t) => t.lang_code === "en")?.name
                  ?? loc.translations[0]?.name
                  ?? loc.location_code}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

function isResolvedRow(row: ReportRow, bucket: ReportBucket): boolean {
  const status = String(row.status_code ?? "").toUpperCase();
  const bucketValue = String(row.report_bucket ?? "").toLowerCase();
  return (
    bucket === "resolved" ||
    bucketValue.includes("resolved") ||
    status === "RESOLVED" ||
    status === "CLOSED"
  );
}

function hasResolutionRecordHint(row: ReportRow): boolean {
  const category = String(row.resolution_category ?? "").trim();
  return category.length > 0;
}

function reportRowHref(row: ReportRow, bucket: ReportBucket): string | null {
  if (!row.ticket_id) return null;
  if (isResolvedRow(row, bucket) && hasResolutionRecordHint(row)) {
    return `/tickets/${row.ticket_id}/closure`;
  }
  return `/tickets/${row.ticket_id}`;
}

function ReportTable({
  columns,
  labels,
  rows,
  bucket,
}: {
  columns: string[];
  labels: Record<string, string>;
  rows: ReportRow[];
  bucket: ReportBucket;
}) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-500 py-4">No complaints in this section.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs text-left">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            {columns.map((c) => (
              <th key={c} className="py-2 pr-3 font-medium whitespace-nowrap">
                {labels[c] ?? c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const href = reportRowHref(row, bucket);
            return (
            <tr key={row.ticket_id ?? row.grievance_id} className="border-b border-gray-100 hover:bg-gray-50">
              {columns.map((c) => (
                <td key={c} className="py-2 pr-3 text-gray-800 max-w-[200px] truncate">
                  {c === "grievance_id" && href ? (
                    <Link href={href} className="text-blue-600 hover:underline">
                      {row.grievance_id}
                    </Link>
                  ) : (
                    String(row[c] ?? "")
                  )}
                </td>
              ))}
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { isAdmin, canSeeSeah } = useAuth();
  const [tab, setTab] = useState<"overview" | "summary" | "builder" | "quarterly">("overview");
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("this_quarter");
  const [dateFrom, setDateFrom] = useState(quarterStart());
  const [dateTo, setDateTo] = useState(new Date().toISOString().split("T")[0]);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [selectedPackageIds, setSelectedPackageIds] = useState<string[]>([]);
  const [selectedLocationCodes, setSelectedLocationCodes] = useState<string[]>([]);
  const [includeSeah, setIncludeSeah] = useState(false);

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packages, setPackages] = useState<PackageItem[]>([]);
  const [locations, setLocations] = useState<LocationNode[]>([]);

  const [data, setData] = useState<ReportQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadingPivot, setDownloadingPivot] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<ReportBucket, boolean>>({
    resolved: false,
    high: false,
    overdue: false,
    other: false,
  });

  // Builder / pivot state
  const [dimensions, setDimensions] = useState<{ key: string; label: string }[]>([]);
  const [measures, setMeasures] = useState<{ key: string; label: string }[]>([]);
  const [pivotConfig, setPivotConfig] = useState<PivotConfig>(DEFAULT_PIVOT);
  const [builderResult, setBuilderResult] = useState<ReportBuildResult | null>(null);
  const [builderLoading, setBuilderLoading] = useState(false);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [savingLibrary, setSavingLibrary] = useState(false);
  const [librarySaved, setLibrarySaved] = useState(false);

  const filterParams = useMemo(
    () => ({
      date_from: dateFrom,
      date_to: dateTo,
      project_ids: selectedProjectIds.length ? selectedProjectIds : undefined,
      package_ids: selectedPackageIds.length ? selectedPackageIds : undefined,
      location_codes: selectedLocationCodes.length ? selectedLocationCodes : undefined,
      include_seah: includeSeah,
    }),
    [dateFrom, dateTo, selectedProjectIds, selectedPackageIds, selectedLocationCodes, includeSeah],
  );

  useEffect(() => {
    listProjects().then(setProjects).catch(() => {});
    listLocations({ country: "NP", limit: 500 }).then(setLocations).catch(() => {});
    fetchReportFields().then((f) => {
      setDimensions(f.dimensions ?? []);
      setMeasures(f.measures ?? []);
      if (f.default_pivot) setPivotConfig(f.default_pivot);
    }).catch(() => {});
    setTemplates(loadTemplates());

  }, []);

  useEffect(() => {
    if (selectedProjectIds.length === 0) {
      setPackages([]);
      return;
    }
    Promise.all(selectedProjectIds.map((id) => listPackages(id)))
      .then((lists) => setPackages(lists.flat()))
      .catch(() => setPackages([]));
  }, [selectedProjectIds]);

  const loadOverview = useCallback(async () => {
    if (!dateFrom || !dateTo) return;
    setLoading(true);
    setError(null);
    try {
      const res = await queryReport({ ...filterParams, page_size: 100 });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load report");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [filterParams, dateFrom, dateTo]);

  const loadBuilder = useCallback(async () => {
    if (!dateFrom || !dateTo) return;
    if (pivotConfig.values.length === 0) return;
    setBuilderLoading(true);
    setError(null);
    try {
      const res = await buildReportJson({
        ...filterParams,
        pivot: pivotConfig,
        page_size: 500,
      });
      setBuilderResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to build pivot");
      setBuilderResult(null);
    } finally {
      setBuilderLoading(false);
    }
  }, [filterParams, dateFrom, dateTo, pivotConfig]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (tab === "overview") loadOverview();
      else if (tab === "builder") loadBuilder();
    }, 400);
    return () => clearTimeout(t);
  }, [tab, loadOverview, loadBuilder, dateFrom, dateTo, selectedProjectIds, selectedPackageIds, selectedLocationCodes, includeSeah, pivotConfig]);

  async function handleExportAll() {
    setDownloading(true);
    setError(null);
    try {
      await downloadExportReportXlsx(filterParams);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setDownloading(false);
    }
  }

  async function handleExportPivot() {
    setDownloadingPivot(true);
    setError(null);
    try {
      await downloadBuildReportXlsx({ ...filterParams, pivot: pivotConfig });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pivot export failed");
    } finally {
      setDownloadingPivot(false);
    }
  }

  function saveCurrentTemplate() {
    const name = templateName.trim() || `Report ${new Date().toLocaleDateString()}`;
    const t: ReportTemplate = {
      id: crypto.randomUUID(),
      name,
      pivot: { ...pivotConfig, values: [...pivotConfig.values] },
    };
    const next = [...templates, t];
    setTemplates(next);
    saveTemplates(next);
    setTemplateName("");
  }

  function applyTemplate(t: ReportTemplate) {
    setPivotConfig(t.pivot);
  }

  function deleteTemplate(id: string) {
    const next = templates.filter((x) => x.id !== id);
    setTemplates(next);
    saveTemplates(next);
  }

  function buildQuarterlyTemplate(kind: "overview" | "pivot") {
    return {
      name: templateName.trim() || (kind === "pivot" ? "Quarterly pivot" : "GRM quarterly overview"),
      kind,
      include_seah: includeSeah,
      project_ids: selectedProjectIds,
      package_ids: selectedPackageIds,
      location_codes: selectedLocationCodes,
      pivot: kind === "pivot" ? pivotConfig : null,
    };
  }

  async function saveReportToLibrary(kind: "overview" | "pivot") {
    if (kind === "pivot" && pivotConfig.values.length === 0) {
      setError("Add at least one value to the pivot before saving.");
      return;
    }
    setSavingLibrary(true);
    setError(null);
    setLibrarySaved(false);
    try {
      await saveToQuarterlyLibrary({
        name: buildQuarterlyTemplate(kind).name,
        template: buildQuarterlyTemplate(kind),
      });
      setLibrarySaved(true);
      setTimeout(() => setLibrarySaved(false), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save report");
    } finally {
      setSavingLibrary(false);
    }
  }

  const sharedFilters = (
    <ReportFilters
      periodPreset={periodPreset}
      setPeriodPreset={setPeriodPreset}
      dateFrom={dateFrom}
      setDateFrom={setDateFrom}
      dateTo={dateTo}
      setDateTo={setDateTo}
      projects={projects}
      selectedProjectIds={selectedProjectIds}
      setSelectedProjectIds={setSelectedProjectIds}
      packages={packages}
      selectedPackageIds={selectedPackageIds}
      setSelectedPackageIds={setSelectedPackageIds}
      locations={locations}
      selectedLocationCodes={selectedLocationCodes}
      setSelectedLocationCodes={setSelectedLocationCodes}
      includeSeah={includeSeah}
      setIncludeSeah={setIncludeSeah}
      showSeahToggle={canSeeSeah}
    />
  );

  return (
    <div className="p-6 max-w-7xl">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Reports</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Operational grievance lists and custom exports (Nepal time, max 100 rows per export).
          </p>
        </div>
        <div className="flex gap-2">
          {tab !== "quarterly" && tab !== "summary" && (
            <button
              type="button"
              onClick={handleExportAll}
              disabled={downloading || !dateFrom || !dateTo}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2 disabled:opacity-50"
            >
              {downloading ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
              Export all (XLSX)
            </button>
          )}
        </div>
      </div>

      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {(
          [
            { id: "overview" as const, label: "Overview" },
            { id: "summary" as const, label: "Summary" },
            { id: "builder" as const, label: "Pivot table" },
            ...(isAdmin ? [{ id: "quarterly" as const, label: "Quarterly email" }] : []),
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t.id ? "border-blue-600 text-blue-700" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab !== "quarterly" && tab !== "summary" && sharedFilters}

      {error && (
        <div className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</div>
      )}

      {tab === "summary" && (
        <SummaryTab
          projects={projects}
          locations={locations}
          canSeeSeah={canSeeSeah}
          onError={setError}
        />
      )}

      {tab === "overview" && (
        <>
          {isAdmin && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={savingLibrary}
                onClick={() => saveReportToLibrary("overview")}
                className="text-sm border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50"
              >
                {savingLibrary ? "Saving…" : "Save overview to report library"}
              </button>
              {librarySaved && (
                <span className="text-xs text-green-600">✓ Saved — assign roles in Quarterly email tab</span>
              )}
            </div>
          )}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-500 mt-4">
              <Loader2 size={16} className="animate-spin" /> Loading…
            </div>
          )}
          {data && (
            <div className="mt-4 flex flex-wrap gap-3 text-sm">
              <span className="font-medium text-gray-700">Total: {data.summary.total}</span>
              <span className="text-green-700">Resolved: {data.summary.resolved}</span>
              <span className="text-amber-700">High: {data.summary.high}</span>
              <span className="text-red-700">Overdue: {data.summary.overdue}</span>
              <span className="text-gray-600">Others: {data.summary.other}</span>
            </div>
          )}
          <div className="mt-4 space-y-4">
            {SECTION_META.map(({ key, title, hint, accent }) => {
              const block = data?.sections[key];
              const open = !collapsed[key];
              return (
                <div key={key} className={`rounded-lg border ${accent}`}>
                  <button
                    type="button"
                    className="w-full flex items-center gap-2 px-4 py-3 text-left"
                    onClick={() => setCollapsed((c) => ({ ...c, [key]: !c[key] }))}
                  >
                    {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <span className="font-semibold text-gray-800">{title}</span>
                    <span className="text-xs bg-white/80 border border-gray-200 rounded-full px-2 py-0.5">
                      {block?.total ?? 0}
                    </span>
                    <span className="text-xs text-gray-500 ml-1">{hint}</span>
                  </button>
                  {open && data && (
                    <div className="px-4 pb-4 bg-white rounded-b-lg border-t border-gray-100">
                      <ReportTable
                        columns={data.columns}
                        labels={data.column_labels}
                        rows={block?.items ?? []}
                        bucket={key}
                      />
                      {(block?.total ?? 0) > (block?.items?.length ?? 0) && (
                        <p className="text-xs text-gray-500 mt-2">
                          Showing first {block?.items.length} of {block?.total}. Narrow filters or export for full list (cap 100).
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {tab === "quarterly" && isAdmin && <QuarterlyPlanTab onError={setError} />}

      {tab === "builder" && (
        <div className="mt-4 space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1">
              <SlidersHorizontal size={14} /> Pivot table editor
            </h2>
            <p className="text-xs text-gray-500 mb-4">
              Like Excel or Google Sheets: put categories in Rows and Columns, then add Values with Sum, Average, Max, Min, or Count.
            </p>
            <PivotBuilder
              dimensions={dimensions}
              measures={measures}
              config={pivotConfig}
              onChange={setPivotConfig}
            />
          </div>

          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex gap-2 flex-1 min-w-[200px]">
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Save template as…"
                className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm"
              />
              <button
                type="button"
                onClick={saveCurrentTemplate}
                className="px-3 py-1.5 bg-gray-100 rounded text-sm hover:bg-gray-200 flex items-center gap-1"
              >
                <Plus size={14} /> Save
              </button>
            </div>
            {templates.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {templates.map((t) => (
                  <span key={t.id} className="inline-flex items-center gap-1 text-xs bg-gray-100 rounded px-2 py-1">
                    <button type="button" className="text-blue-600 hover:underline" onClick={() => applyTemplate(t)}>
                      {t.name}
                    </button>
                    <button type="button" onClick={() => deleteTemplate(t.id)} className="text-gray-400 hover:text-red-600">
                      <Trash2 size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <button
              type="button"
              disabled={builderLoading || downloadingPivot || pivotConfig.values.length === 0}
              onClick={handleExportPivot}
              className="bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg flex items-center gap-2 disabled:opacity-50"
            >
              {(builderLoading || downloadingPivot) ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
              Export pivot XLSX
            </button>
            {isAdmin && (
              <>
                <button
                  type="button"
                  disabled={savingLibrary || pivotConfig.values.length === 0}
                  onClick={() => saveReportToLibrary("pivot")}
                  className="border border-gray-400 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50 hover:bg-gray-50"
                >
                  {savingLibrary ? "Saving…" : "Save to report library"}
                </button>
                {librarySaved && (
                  <span className="text-xs text-green-600 font-medium self-center">
                    ✓ Saved — assign roles in Quarterly email tab
                  </span>
                )}
              </>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1">
              <BarChart2 size={14} className="text-blue-500" /> Pivot preview
            </h2>
            {builderLoading ? (
              <div className="text-sm text-gray-500 flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" /> Calculating…
              </div>
            ) : !builderResult || builderResult.rows.length === 0 ? (
              <p className="text-sm text-gray-500">No data for this pivot. Adjust filters or add row/column fields.</p>
            ) : (
              <PivotPreviewTable
                columns={builderResult.columns}
                column_labels={builderResult.column_labels}
                rows={builderResult.rows}
                header_rows={builderResult.header_rows}
                row_dims={builderResult.row_dims}
              />
            )}
          </div>
        </div>
      )}

    </div>
  );
}
