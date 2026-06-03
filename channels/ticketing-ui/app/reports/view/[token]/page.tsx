"use client";

import { use, useEffect, useState } from "react";
import { fetchInternalReportShare } from "@/lib/api";

export default function InternalReportViewPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchInternalReportShare>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchInternalReportShare(token)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Report not found"));
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!data) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-400">Loading report…</div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold text-gray-800">{data.name}</h1>
      <p className="text-sm text-gray-500 mt-0.5">Officer report — extended ticket fields (auth required).</p>
      <div className="overflow-x-auto mt-4 border border-gray-200 rounded-lg">
        <table className="text-xs w-full border-collapse">
          <thead>
            <tr className="bg-gray-100">
              {data.columns.map((col) => (
                <th key={col} className="border border-gray-200 px-2 py-1 text-left font-medium whitespace-nowrap">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, i) => (
              <tr key={i} className="odd:bg-white even:bg-gray-50">
                {data.columns.map((col) => (
                  <td key={col} className="border border-gray-200 px-2 py-1 max-w-xs truncate">{String(row[col] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
