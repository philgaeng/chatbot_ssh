"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getResolvedSummary, type ResolvedSummaryResponse } from "@/lib/api";

export default function OfficerClosurePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<ResolvedSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getResolvedSummary(id)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [id]);

  const pub = data?.summary_public_json as Record<string, string> | null | undefined;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <Link href={`/tickets/${id}`} className="text-sm text-blue-600 hover:underline">← Back to case</Link>
      <h1 className="text-xl font-bold mt-4 mb-2">Case closure summary</h1>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!data && !error && <p className="text-gray-500">Loading…</p>}
      {data && (
        <>
          <p className="text-sm text-gray-500 mb-4">
            Status: {data.generation_status}
            {data.closure_public_url && (
              <> · <a href={data.closure_public_url} className="text-blue-600 underline" target="_blank" rel="noreferrer">Complainant link</a></>
            )}
          </p>
          {pub && (
            <div className="space-y-4 text-sm">
              <section className="bg-white border rounded-lg p-4">
                <h2 className="font-semibold mb-2">Public view (complainant)</h2>
                <p><strong>Outcome:</strong> {pub.resolution_category_label}</p>
                <p className="mt-2 whitespace-pre-wrap">{pub.resolution_text_public}</p>
                {pub.findings_summary_public && (
                  <p className="mt-2 whitespace-pre-wrap text-gray-700">{pub.findings_summary_public}</p>
                )}
              </section>
            </div>
          )}
          {data.generation_status !== "complete" && (
            <p className="text-amber-700 text-sm mt-4">Summary is still generating. Refresh in a moment.</p>
          )}
        </>
      )}
    </div>
  );
}
