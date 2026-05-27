"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Copy, Download, Info, Loader2 } from "lucide-react";
import {
  downloadSummaryReportXlsx,
  fetchReportSummary,
  listPackages,
  saveToQuarterlyLibrary,
  type PackageItem,
  type ProjectItem,
  type ReportSummaryResponse,
  type LocationNode,
} from "@/lib/api";
import {
  CHART_COLORS,
  copyBarChart,
  copyPieChart,
  type PieSlice,
} from "@/lib/chart-clipboard";

function recentQuarterOptions(count = 8): { key: string; label: string }[] {
  const out: { key: string; label: string }[] = [];
  const d = new Date();
  let y = d.getFullYear();
  let q = Math.floor(d.getMonth() / 3) + 1;
  for (let i = 0; i < count; i++) {
    out.push({ key: `${y}-Q${q}`, label: `${y} Q${q}` });
    q -= 1;
    if (q < 1) {
      q = 4;
      y -= 1;
    }
  }
  return out;
}

function CopyChartButton({
  onCopy,
  disabled,
}: {
  onCopy: () => Promise<void>;
  disabled?: boolean;
}) {
  const [status, setStatus] = useState<"idle" | "copying" | "copied" | "error">("idle");
  const [hint, setHint] = useState<string | null>(null);

  const handleClick = async () => {
    if (disabled || status === "copying") return;
    setStatus("copying");
    setHint(null);
    try {
      await onCopy();
      setStatus("copied");
      setHint("Copied");
      window.setTimeout(() => {
        setStatus("idle");
        setHint(null);
      }, 2000);
    } catch (err) {
      setStatus("error");
      setHint(err instanceof Error ? err.message : "Copy failed");
      window.setTimeout(() => {
        setStatus("idle");
        setHint(null);
      }, 3500);
    }
  };

  return (
    <div className="flex items-center gap-1 shrink-0">
      {hint ? (
        <span
          className={`text-[10px] max-w-[120px] truncate ${status === "error" ? "text-red-600" : "text-gray-500"}`}
        >
          {hint}
        </span>
      ) : null}
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={disabled || status === "copying"}
        title="Copy chart as image (paste into Word, PowerPoint, etc.)"
        className="p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-40"
        aria-label="Copy chart as image"
      >
        {status === "copied" ? (
          <Check className="w-3.5 h-3.5 text-green-600" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
}

function PieBlock({ title, slices }: { title: string; slices: PieSlice[] }) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  const hasData = slices.some((s) => s.value > 0);
  let acc = 0;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-xs font-semibold text-gray-700">{title}</h4>
        <CopyChartButton
          disabled={!hasData}
          onCopy={() => copyPieChart(title, slices)}
        />
      </div>
      <div className="flex items-center gap-3">
        <div
          className="w-28 h-28 rounded-full shrink-0"
          style={{
            background: `conic-gradient(${slices
              .map((sl, i) => {
                const start = (acc / total) * 100;
                acc += sl.value;
                const end = (acc / total) * 100;
                return `${CHART_COLORS[i % CHART_COLORS.length]} ${start}% ${end}%`;
              })
              .join(", ")})`,
          }}
          title={slices.map((s) => `${s.label}: ${s.value} (${s.percent}%)`).join("\n")}
        />
        <ul className="text-xs space-y-1 min-w-0">
          {slices.map((s, i) => (
            <li key={s.label} className="flex gap-2 truncate">
              <span
                className="w-2 h-2 rounded-full shrink-0 mt-1"
                style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
              />
              <span>
                {s.label}: <strong>{s.value}</strong>
                <span className="text-gray-400"> ({s.percent}%)</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

type Props = {
  projects: ProjectItem[];
  locations: LocationNode[];
  canSeeSeah: boolean;
  onError: (msg: string | null) => void;
};

export function SummaryTab({ projects, locations, canSeeSeah, onError }: Props) {
  const [packages, setPackages] = useState<PackageItem[]>([]);
  const quarterOptions = useMemo(() => recentQuarterOptions(), []);
  const [projectId, setProjectId] = useState("");
  const [provinceCode, setProvinceCode] = useState("");
  const [selectedQuarters, setSelectedQuarters] = useState<string[]>([
    quarterOptions[0]?.key ?? "",
  ]);
  const [chartPackageIds, setChartPackageIds] = useState<string[]>([]);
  const [includeSeah, setIncludeSeah] = useState(false);
  const [data, setData] = useState<ReportSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingLibrary, setSavingLibrary] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const provinces = useMemo(
    () => locations.filter((l) => l.level_number === 1),
    [locations],
  );

  useEffect(() => {
    if (!projectId && projects.length) {
      setProjectId(projects[0].project_id);
    }
  }, [projects, projectId]);

  useEffect(() => {
    if (!projectId) {
      setPackages([]);
      return;
    }
    listPackages(projectId).then(setPackages).catch(() => setPackages([]));
  }, [projectId]);

  const load = useCallback(async () => {
    if (!projectId || selectedQuarters.length === 0) return;
    setLoading(true);
    onError(null);
    try {
      const res = await fetchReportSummary({
        project_id: projectId,
        province_code: provinceCode || undefined,
        quarter_keys: selectedQuarters,
        chart_package_ids: chartPackageIds.length ? chartPackageIds : undefined,
        include_seah: includeSeah,
      });
      setData(res);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to load summary");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [
    projectId,
    provinceCode,
    selectedQuarters,
    chartPackageIds,
    includeSeah,
    onError,
  ]);

  useEffect(() => {
    const t = setTimeout(load, 400);
    return () => clearTimeout(t);
  }, [load]);

  function toggleQuarter(key: string) {
    setSelectedQuarters((prev) => {
      if (prev.includes(key)) {
        return prev.length > 1 ? prev.filter((x) => x !== key) : prev;
      }
      if (prev.length >= 4) return prev;
      return [...prev, key];
    });
  }

  async function handleExportXlsx() {
    if (!projectId || selectedQuarters.length === 0) return;
    setDownloading(true);
    onError(null);
    try {
      const projectName = projects.find((p) => p.project_id === projectId)?.name;
      await downloadSummaryReportXlsx({
        project_id: projectId,
        province_code: provinceCode || undefined,
        quarter_keys: selectedQuarters,
        chart_package_ids: chartPackageIds.length ? chartPackageIds : undefined,
        include_seah: includeSeah,
        project_name: projectName,
      });
    } catch (e) {
      onError(e instanceof Error ? e.message : "Summary export failed");
    } finally {
      setDownloading(false);
    }
  }

  async function saveToLibrary() {
    setSavingLibrary(true);
    onError(null);
    try {
      await saveToQuarterlyLibrary({
        name: `Summary ${selectedQuarters.join(", ")}`,
        template: {
          name: `Summary ${selectedQuarters.join(", ")}`,
          kind: "summary",
          include_seah: includeSeah,
          project_ids: [projectId],
          package_ids: chartPackageIds,
          location_codes: provinceCode ? [provinceCode] : [],
          pivot: null,
          summary_quarter_keys: selectedQuarters,
          summary_province_code: provinceCode || null,
        },
      });
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSavingLibrary(false);
    }
  }

  // Build two-row header: group row + leaf row (short labels)
  const { headerGroups, columnLeaves } = useMemo(() => {
    if (!data) return { headerGroups: [], columnLeaves: [] };
    const leaves: { key: string; label: string; groupId: string }[] = [];
    const groups: { id: string; label: string; span: number }[] = [];
    for (const g of data.matrix.column_groups) {
      const children = g.children ?? [];
      // Short group label: strip long Q-key prefix for readability
      const shortGroup = g.label
        .replace(/Closed (\d{4}-Q\d) — /, "Q$1 ")
        .replace(/Open overdue end /, "Open ");
      groups.push({ id: g.id, label: shortGroup, span: children.length });
      for (const c of children) {
        leaves.push({ key: c.key, label: c.label, groupId: g.id });
      }
    }
    return { headerGroups: groups, columnLeaves: leaves };
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Project</span>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 min-w-[180px]"
          >
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Province</span>
          <select
            value={provinceCode}
            onChange={(e) => setProvinceCode(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1 min-w-[160px]"
          >
            <option value="">All provinces</option>
            {provinces.map((l) => (
              <option key={l.location_code} value={l.location_code}>
                {l.translations?.find((t) => t.lang_code === "en")?.name ||
                  l.location_code}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Quarters (max 4)</span>
          <div className="flex flex-wrap gap-2">
            {quarterOptions.map((q) => (
              <label key={q.key} className="inline-flex items-center gap-1 text-xs">
                <input
                  type="checkbox"
                  checked={selectedQuarters.includes(q.key)}
                  onChange={() => toggleQuarter(q.key)}
                />
                {q.label}
              </label>
            ))}
          </div>
        </div>
        <label className="flex flex-col gap-1 min-w-[200px]">
          <span className="text-xs font-medium text-gray-600">Chart packages (optional)</span>
          <select
            multiple
            value={chartPackageIds}
            onChange={(e) =>
              setChartPackageIds(
                Array.from(e.target.selectedOptions).map((o) => o.value),
              )
            }
            className="border border-gray-300 rounded px-2 py-1 h-20"
          >
            {packages.map((p) => (
              <option key={p.package_id} value={p.package_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        {canSeeSeah && (
          <label className="flex items-center gap-2 self-end pb-1">
            <input
              type="checkbox"
              checked={includeSeah}
              onChange={(e) => setIncludeSeah(e.target.checked)}
            />
            <span className="text-xs">Include SEAH</span>
          </label>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
        <Info size={14} className="shrink-0" />
        <span title={data?.definitions?.closed_on_time}>
          On time = no overdue episode during the case. Category breakdown is in pies only.
        </span>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleExportXlsx}
            disabled={downloading || !projectId || selectedQuarters.length === 0}
            className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-3 py-1.5 rounded-lg text-xs disabled:opacity-50"
          >
            {downloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Export summary (XLSX)
          </button>
          <button
            type="button"
            onClick={saveToLibrary}
            disabled={savingLibrary || !projectId}
            className="text-blue-600 hover:underline disabled:opacity-50"
          >
            {savingLibrary ? "Saving…" : "Save to report library"}
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex justify-center py-12 text-gray-500">
          <Loader2 className="animate-spin mr-2" size={20} />
          Loading summary…
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          {/* ── Matrix table — full width, horizontally scrollable ── */}
          <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
            <table className="text-xs text-left border-collapse" style={{ minWidth: "100%" }}>
              <thead className="bg-gray-100">
                {/* Row 1: group headers */}
                <tr>
                  <th
                    rowSpan={2}
                    className="p-2 border-b border-r border-gray-300 font-semibold sticky left-0 bg-gray-100 z-10 min-w-[140px]"
                  >
                    Package
                  </th>
                  {headerGroups.map((g) => (
                    <th
                      key={g.id}
                      colSpan={g.span}
                      className="px-2 py-1 border-b border-r border-gray-300 text-center font-semibold whitespace-nowrap bg-gray-100"
                    >
                      {g.label}
                    </th>
                  ))}
                </tr>
                {/* Row 2: leaf column headers — short, rotated for narrow columns */}
                <tr>
                  {columnLeaves.map((c) => (
                    <th
                      key={c.key}
                      className="px-1 py-1 border-b border-r border-gray-200 text-center font-medium text-gray-600"
                      style={{ minWidth: 44, maxWidth: 60 }}
                    >
                      <div
                        style={{
                          writingMode: "vertical-rl",
                          transform: "rotate(180deg)",
                          whiteSpace: "nowrap",
                          fontSize: "10px",
                          lineHeight: 1.2,
                          maxHeight: 70,
                        }}
                      >
                        {c.label}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.matrix.rows.map((row) => (
                  <tr key={`${row.package_id ?? "none"}-${row.package_name}`} className="border-t hover:bg-gray-50">
                    <td className="p-2 font-medium border-r border-gray-200 sticky left-0 bg-white z-10 whitespace-nowrap">
                      {row.package_name}
                    </td>
                    {columnLeaves.map((c) => {
                      const v = row.cells[c.key] ?? 0;
                      return (
                        <td
                          key={c.key}
                          className={`px-1 py-2 text-center tabular-nums border-r border-gray-100 ${v > 0 ? "font-semibold text-gray-900" : "text-gray-300"}`}
                        >
                          {v || "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Charts: bar + 2×2 pie grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Bar chart */}
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h4 className="text-xs font-semibold text-gray-700">Resolved by month (12 mo)</h4>
                <CopyChartButton
                  disabled={data.charts.resolved_by_month.length === 0}
                  onCopy={() =>
                    copyBarChart("Resolved by month (12 mo)", data.charts.resolved_by_month)
                  }
                />
              </div>
              {data.charts.resolved_by_month.length === 0 ? (
                <p className="text-xs text-gray-400 py-4 text-center">No resolved tickets in window</p>
              ) : (
                (() => {
                  const totals = data.charts.resolved_by_month.map((m) =>
                    m.packages.reduce((s, p) => s + (p.count ?? 0), 0),
                  );
                  const maxTotal = Math.max(1, ...totals);
                  const chartHeightPx = 120;
                  return (
                    <div className="overflow-x-auto px-1">
                      <div className="h-[160px] flex items-end gap-2">
                        {data.charts.resolved_by_month.map((m) => {
                          const total = m.packages.reduce((s, p) => s + (p.count ?? 0), 0);
                          const h = Math.max(2, Math.round((total / maxTotal) * chartHeightPx));
                          const label = m.month.slice(5); // MM
                          return (
                            <div key={m.month} className="flex flex-col items-center min-w-[42px]">
                              <div
                                className="h-[120px] flex items-end justify-center w-full"
                                title={`${m.month} — ${total} resolved`}
                              >
                                <div
                                  className={`w-5 rounded-t ${total ? "bg-blue-500" : "bg-gray-200"}`}
                                  style={{ height: `${h}px` }}
                                />
                              </div>
                              <div className="mt-1 text-[10px] text-gray-500 text-center whitespace-nowrap">
                                {label}
                              </div>
                              <div className="text-[10px] text-gray-400">{total}</div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()
              )}
            </div>

            {/* 2×2 pie grid */}
            <div className="lg:col-span-2 grid grid-cols-2 gap-3">
              <PieBlock title="On time vs closed overdue" slices={data.charts.pies.overdue_vs_ontime} />
              <PieBlock title="Escalated" slices={data.charts.pies.escalated} />
              <PieBlock title="Max level at resolve" slices={data.charts.pies.max_level} />
              <PieBlock title="Resolution category" slices={data.charts.pies.resolution_category} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
