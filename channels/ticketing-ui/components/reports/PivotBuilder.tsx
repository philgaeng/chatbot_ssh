"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";

export type PivotValueSpec = { field: string; agg: "count" | "sum" | "avg" | "max" | "min" };

export type PivotConfig = {
  rows: string[];
  columns: string[];
  values: PivotValueSpec[];
  filters: Record<string, string[]>;
};

type FieldItem = { key: string; label: string };

const AGG_OPTIONS: { value: PivotValueSpec["agg"]; label: string }[] = [
  { value: "count", label: "Count" },
  { value: "sum", label: "Sum" },
  { value: "avg", label: "Average" },
  { value: "max", label: "Max" },
  { value: "min", label: "Min" },
];

function Zone({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="border border-dashed border-gray-300 rounded-lg p-3 bg-gray-50/80 min-h-[72px]">
      <div className="text-xs font-semibold text-gray-600 mb-0.5">{title}</div>
      {hint && <div className="text-[10px] text-gray-400 mb-2">{hint}</div>}
      {children}
    </div>
  );
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 bg-white border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-800 mr-1 mb-1">
      {label}
      <button type="button" onClick={onRemove} className="text-gray-400 hover:text-red-600" aria-label="Remove">
        <X size={12} />
      </button>
    </span>
  );
}

export function PivotBuilder({
  dimensions,
  measures,
  config,
  onChange,
}: {
  dimensions: FieldItem[];
  measures: FieldItem[];
  config: PivotConfig;
  onChange: (next: PivotConfig) => void;
}) {
  const dimLabel = (key: string) => dimensions.find((d) => d.key === key)?.label ?? key;
  const measureLabel = (key: string) =>
    key === "ticket_id" ? "Complaints" : measures.find((m) => m.key === key)?.label ?? key;

  function addTo(zone: "rows" | "columns" | "filters", field: string) {
    if (zone === "filters") {
      onChange({
        ...config,
        filters: { ...config.filters, [field]: config.filters[field] ?? [] },
      });
      return;
    }
    const list = config[zone];
    if (list.includes(field)) return;
    onChange({ ...config, [zone]: [...list, field] });
  }

  function removeFrom(zone: "rows" | "columns", field: string) {
    onChange({ ...config, [zone]: config[zone].filter((f) => f !== field) });
  }

  function removeFilter(field: string) {
    const next = { ...config.filters };
    delete next[field];
    onChange({ ...config, filters: next });
  }

  function setFilterValues(field: string, raw: string) {
    const values = raw.split(",").map((s) => s.trim()).filter(Boolean);
    onChange({ ...config, filters: { ...config.filters, [field]: values } });
  }

  function addValue(field: string, agg: PivotValueSpec["agg"]) {
    onChange({ ...config, values: [...config.values, { field, agg }] });
  }

  function removeValue(index: number) {
    onChange({ ...config, values: config.values.filter((_, i) => i !== index) });
  }

  const unusedDims = dimensions.filter(
    (d) =>
      !config.rows.includes(d.key) &&
      !config.columns.includes(d.key) &&
      !(d.key in config.filters),
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-8 space-y-3">
        <Zone title="Filters" hint="Limit data before pivoting (comma-separated values)">
          {Object.keys(config.filters).length === 0 && (
            <span className="text-xs text-gray-400">Add a dimension to Filters</span>
          )}
          {Object.entries(config.filters).map(([field, vals]) => (
            <div key={field} className="mb-2">
              <div className="flex items-center gap-2 mb-1">
                <Chip label={dimLabel(field)} onRemove={() => removeFilter(field)} />
              </div>
              <input
                type="text"
                placeholder="Values, e.g. OPEN, ESCALATED (empty = no filter)"
                value={vals.join(", ")}
                onChange={(e) => setFilterValues(field, e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
              />
            </div>
          ))}
          {unusedDims.length > 0 && (
            <select
              className="text-xs border border-gray-300 rounded px-2 py-1 mt-1"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) addTo("filters", e.target.value);
                e.target.value = "";
              }}
            >
              <option value="">+ Add filter field</option>
              {unusedDims.map((d) => (
                <option key={d.key} value={d.key}>{d.label}</option>
              ))}
            </select>
          )}
        </Zone>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Zone title="Rows" hint="Categories down the left">
            {config.rows.map((f) => (
              <Chip key={f} label={dimLabel(f)} onRemove={() => removeFrom("rows", f)} />
            ))}
            <select
              className="text-xs border border-gray-300 rounded px-2 py-1"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) addTo("rows", e.target.value);
                e.target.value = "";
              }}
            >
              <option value="">+ Add</option>
              {dimensions.filter((d) => !config.rows.includes(d.key)).map((d) => (
                <option key={d.key} value={d.key}>{d.label}</option>
              ))}
            </select>
          </Zone>

          <Zone title="Columns" hint="Categories across the top">
            {config.columns.map((f) => (
              <Chip key={f} label={dimLabel(f)} onRemove={() => removeFrom("columns", f)} />
            ))}
            <select
              className="text-xs border border-gray-300 rounded px-2 py-1"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) addTo("columns", e.target.value);
                e.target.value = "";
              }}
            >
              <option value="">+ Add</option>
              {dimensions.filter((d) => !config.columns.includes(d.key)).map((d) => (
                <option key={d.key} value={d.key}>{d.label}</option>
              ))}
            </select>
          </Zone>
        </div>

        <Zone title="Values" hint="Numbers to aggregate in each cell">
          {config.values.map((v, i) => (
            <Chip
              key={`${v.field}-${v.agg}-${i}`}
              label={`${AGG_OPTIONS.find((a) => a.value === v.agg)?.label ?? v.agg} of ${measureLabel(v.field)}`}
              onRemove={() => removeValue(i)}
            />
          ))}
          <div className="flex flex-wrap gap-2 items-center mt-1">
            <select
              id="pivot-value-field"
              className="text-xs border border-gray-300 rounded px-2 py-1"
              defaultValue="ticket_id"
            >
              <option value="ticket_id">Complaints (count)</option>
              {measures.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
            <select
              id="pivot-value-agg"
              className="text-xs border border-gray-300 rounded px-2 py-1"
              defaultValue="count"
            >
              {AGG_OPTIONS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
            <button
              type="button"
              className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700"
              onClick={() => {
                const field = (document.getElementById("pivot-value-field") as HTMLSelectElement).value;
                const agg = (document.getElementById("pivot-value-agg") as HTMLSelectElement)
                  .value as PivotValueSpec["agg"];
                addValue(field, agg);
              }}
            >
              Add value
            </button>
          </div>
        </Zone>
      </div>

      <div className="lg:col-span-4 border border-gray-200 rounded-lg p-3 bg-white">
        <div className="text-xs font-semibold text-gray-600 mb-2">Fields</div>
        <div className="text-[10px] uppercase text-gray-400 mb-1">Dimensions</div>
        <ul className="text-xs text-gray-700 space-y-0.5 mb-3 max-h-40 overflow-y-auto">
          {dimensions.map((d) => (
            <li key={d.key}>{d.label}</li>
          ))}
        </ul>
        <div className="text-[10px] uppercase text-gray-400 mb-1">Measures</div>
        <ul className="text-xs text-gray-700 space-y-0.5">
          <li>Complaints (count)</li>
          {measures.map((m) => (
            <li key={m.key}>{m.label}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
