"use client";

import { useState } from "react";
import { exportReport } from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";

export default function ReportsPage() {
  const { isAdmin } = useAuth();
  const today = new Date().toISOString().split("T")[0];
  const quarterStart = (() => {
    const d = new Date();
    const q = Math.floor(d.getMonth() / 3);
    return new Date(d.getFullYear(), q * 3, 1).toISOString().split("T")[0];
  })();

  const [dateFrom, setDateFrom] = useState(quarterStart);
  const [dateTo, setDateTo] = useState(today);
  const [orgId, setOrgId] = useState("");
  const [downloading, setDownloading] = useState(false);

  function handleExport() {
    setDownloading(true);
    const url = exportReport({ date_from: dateFrom, date_to: dateTo, organization_id: orgId || undefined });
    const a = document.createElement("a");
    a.href = url;
    a.download = `grm-report-${dateFrom}-to-${dateTo}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => setDownloading(false), 2000);
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">Reports</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Export GRM grievance data as XLSX for quarterly review and ADB reporting.
        </p>
      </div>

      {/* Export card */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">📊 Export Report</h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500 block mb-1">Organization (optional)</label>
            <input
              type="text"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="e.g. DOR"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <button
          onClick={handleExport}
          disabled={downloading || !dateFrom || !dateTo}
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition disabled:opacity-50 flex items-center gap-2"
        >
          {downloading ? (
            <>⏳ Preparing…</>
          ) : (
            <>📥 Download XLSX</>
          )}
        </button>
      </div>

      {/* Report columns info */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Report columns</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs text-gray-600">
          {[
            "Reference number",
            "Date submitted",
            "Nature / categories",
            "Grievance AI summary",
            "Location (district/municipality)",
            "Organization",
            "Level reached before resolution",
            "Current status",
            "Days at each level",
            "SLA breached? (Y/N per level)",
            "Instance (Standard / SEAH)",
          ].map((col) => (
            <div key={col} className="flex items-start gap-1.5">
              <span className="text-gray-300 mt-0.5">▸</span>
              <span>{col}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scheduled reports — admin only */}
      {isAdmin && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Automatic quarterly reports</h2>
          <p className="text-xs text-gray-500 mb-4">
            Reports are emailed automatically on the 5th of January, April, July, and October
            to: ADB National Project Director, ADB HQ Safeguards, MoPIT representative, DOR representative.
          </p>
          <div className="bg-gray-50 rounded border border-gray-200 px-4 py-3 text-xs text-gray-500">
            ⚙️ Report schedule and recipients are configured in{" "}
            <a href="/settings" className="text-blue-500 hover:underline">Settings → Report Schedule</a>.
          </div>
        </div>
      )}
    </div>
  );
}
