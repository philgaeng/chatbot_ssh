"use client";

import { use, useEffect, useState } from "react";
import { fetchPublicReport } from "@/lib/api";

export default function PublicReportPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchPublicReport>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPublicReport(token)
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
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h1 className="text-lg font-semibold text-gray-800">{data.name}</h1>
        <p className="text-xs text-gray-500 mt-1">Public GRM report — limited fields, no officer PII.</p>
        <div className="overflow-x-auto mt-4">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr className="bg-gray-100">
                {data.columns.map((col) => (
                  <th key={col} className="border border-gray-200 px-2 py-1 text-left font-medium">{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i} className="odd:bg-white even:bg-gray-50">
                  {data.columns.map((col) => (
                    <td key={col} className="border border-gray-200 px-2 py-1">{String(row[col] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
