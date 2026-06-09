"use client";

import { useEffect, useState } from "react";
import {
  filedPresetLabel,
  listPackages,
  listProjects,
  ticketListFiltersActive,
  type FiledDatePreset,
  type PackageItem,
  type ProjectItem,
  type TicketListFilterValues,
} from "@/lib/api";

const PRIORITIES = ["NORMAL", "HIGH", "CRITICAL"] as const;

const selectCls =
  "border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-0";

const FILED_PRESET_CHIPS: { value: Exclude<FiledDatePreset, "" | "custom">; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "2d", label: "2d" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "month", label: "This month" },
];

function FiledPresetChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-xs font-medium px-2.5 py-1 rounded-full border transition-colors ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-gray-600 border-gray-300 hover:border-gray-400 hover:text-gray-800"
      }`}
    >
      {label}
    </button>
  );
}

export function TicketListFiltersBar({
  values,
  onChange,
  onClear,
}: {
  values: TicketListFilterValues;
  onChange: (next: TicketListFilterValues) => void;
  onClear: () => void;
}) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packages, setPackages] = useState<PackageItem[]>([]);
  const active = ticketListFiltersActive(values);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!values.projectCode) {
      setPackages([]);
      return;
    }
    const project = projects.find((p) => p.short_code === values.projectCode);
    if (!project) {
      setPackages([]);
      return;
    }
    listPackages(project.project_id)
      .then(setPackages)
      .catch(() => setPackages([]));
  }, [values.projectCode, projects]);

  function patch(partial: Partial<TicketListFilterValues>) {
    const next = { ...values, ...partial };
    if (partial.projectCode !== undefined && partial.projectCode !== values.projectCode) {
      next.packageId = "";
    }
    if (partial.filedPreset !== undefined && partial.filedPreset !== "custom") {
      next.createdFrom = "";
      next.createdTo = "";
    }
    onChange(next);
  }

  function toggleFiledPreset(preset: FiledDatePreset) {
    if (values.filedPreset === preset) {
      patch({ filedPreset: "", createdFrom: "", createdTo: "" });
    } else {
      patch({ filedPreset: preset });
    }
  }

  const summaryChips: string[] = [];
  if (values.q.trim()) summaryChips.push(`"${values.q.trim()}"`);
  if (values.priority) summaryChips.push(values.priority);
  if (values.sla === "overdue") summaryChips.push("Overdue");
  if (values.sla === "not_overdue") summaryChips.push("On track");
  const filed = filedPresetLabel(values.filedPreset, values.createdFrom, values.createdTo);
  if (filed) summaryChips.push(filed);
  if (values.projectCode) summaryChips.push(values.projectCode);
  if (values.packageId) {
    const pkg = packages.find((p) => p.package_id === values.packageId);
    summaryChips.push(pkg?.package_code ?? values.packageId);
  }

  return (
    <div className="mb-4 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          placeholder="Search ID, summary, assignee…"
          value={values.q}
          onChange={(e) => patch({ q: e.target.value })}
          aria-label="Search tickets"
          className="flex-1 min-w-[160px] border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        <select
          value={values.priority}
          onChange={(e) => patch({ priority: e.target.value })}
          aria-label="Priority"
          className={selectCls}
        >
          <option value="">Priority</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>

        <select
          value={values.sla}
          onChange={(e) => patch({ sla: e.target.value })}
          aria-label="SLA status"
          className={selectCls}
        >
          <option value="">SLA</option>
          <option value="overdue">Overdue</option>
          <option value="not_overdue">On track</option>
        </select>

        <select
          value={values.projectCode}
          onChange={(e) => patch({ projectCode: e.target.value })}
          aria-label="Project"
          className={selectCls}
        >
          <option value="">Project</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.short_code}>
              {p.short_code}
            </option>
          ))}
        </select>

        <select
          value={values.packageId}
          onChange={(e) => patch({ packageId: e.target.value })}
          disabled={!values.projectCode}
          aria-label="Package"
          className={`${selectCls} max-w-[140px] disabled:bg-gray-100 disabled:text-gray-400`}
        >
          <option value="">{values.projectCode ? "Package" : "Package…"}</option>
          {packages.map((p) => (
            <option key={p.package_id} value={p.package_id}>
              {p.package_code}
            </option>
          ))}
        </select>

        {active && (
          <button
            type="button"
            onClick={onClear}
            className="text-sm text-gray-600 hover:text-gray-900 px-2 py-1.5 whitespace-nowrap"
          >
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500 shrink-0">Created</span>
        {FILED_PRESET_CHIPS.map((chip) => (
          <FiledPresetChip
            key={chip.value}
            label={chip.label}
            active={values.filedPreset === chip.value}
            onClick={() => toggleFiledPreset(chip.value)}
          />
        ))}
        <FiledPresetChip
          label="Custom…"
          active={values.filedPreset === "custom"}
          onClick={() => toggleFiledPreset("custom")}
        />
      </div>

      {values.filedPreset === "custom" && (
        <div className="flex flex-wrap items-center gap-2 pl-0.5">
          <input
            type="date"
            value={values.createdFrom}
            onChange={(e) => patch({ createdFrom: e.target.value })}
            aria-label="Created from"
            className={selectCls}
          />
          <span className="text-xs text-gray-400">to</span>
          <input
            type="date"
            value={values.createdTo}
            onChange={(e) => patch({ createdTo: e.target.value })}
            aria-label="Created to"
            className={selectCls}
          />
        </div>
      )}

      {active && summaryChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {summaryChips.map((chip) => (
            <span
              key={chip}
              className="inline-flex text-xs text-blue-800 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-full"
            >
              {chip}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
