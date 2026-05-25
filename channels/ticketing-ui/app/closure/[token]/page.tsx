"use client";

import { use, useEffect, useState } from "react";

interface PublicClosure {
  grievance_id: string;
  primary_language: string;
  generated_at: string | null;
  summary_public_json: {
    project_name?: string;
    original_complaint?: string;
    resolution_category_label?: string;
    resolution_text_public?: string;
    findings_summary_public?: string;
    resolved_at?: string;
  };
}

export default function PublicClosurePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<PublicClosure | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/v1/public/closure/${token}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [token]);

  const pub = data?.summary_public_json;

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 p-6 max-w-lg mx-auto">
        <p className="text-gray-600">Loading your case outcome…</p>
      </main>
    );
  }

  if (error || !data || !pub) {
    return (
      <main className="min-h-screen bg-gray-50 p-6 max-w-lg mx-auto">
        <p className="text-red-700">This closure link is invalid or not ready yet.</p>
      </main>
    );
  }

  const pdfUrl = `/api/v1/public/closure/${token}/pdf`;

  return (
    <main className="min-h-screen bg-gray-50 p-6 max-w-lg mx-auto print:bg-white">
      <meta name="robots" content="noindex" />
      <header className="mb-6">
        <p className="text-xs text-gray-500 uppercase tracking-wide">GRM case closure</p>
        <h1 className="text-xl font-bold text-gray-900 mt-1">{pub.project_name ?? "Project"}</h1>
        <p className="text-sm text-gray-600 mt-1">Reference: {data.grievance_id}</p>
        {pub.resolved_at && (
          <p className="text-sm text-gray-500">Resolved {pub.resolved_at.slice(0, 10)}</p>
        )}
      </header>

      <section className="bg-white rounded-xl p-4 shadow-sm mb-4">
        <h2 className="font-semibold text-gray-900 mb-2">Your complaint</h2>
        <p className="text-sm text-gray-800 whitespace-pre-wrap">{pub.original_complaint}</p>
      </section>

      <section className="bg-white rounded-xl p-4 shadow-sm mb-4 border-l-4 border-green-600">
        <h2 className="font-semibold text-gray-900 mb-2">Outcome</h2>
        <p className="text-sm font-medium text-green-800">{pub.resolution_category_label}</p>
        <p className="text-sm text-gray-800 mt-2 whitespace-pre-wrap">{pub.resolution_text_public}</p>
      </section>

      {pub.findings_summary_public && (
        <section className="bg-white rounded-xl p-4 shadow-sm mb-6">
          <h2 className="font-semibold text-gray-900 mb-2">Summary</h2>
          <p className="text-sm text-gray-800 whitespace-pre-wrap">{pub.findings_summary_public}</p>
        </section>
      )}

      <a
        href={pdfUrl}
        className="block w-full text-center bg-green-600 text-white font-semibold py-3 rounded-xl mb-3 print:hidden"
      >
        Download PDF
      </a>
      <button
        type="button"
        onClick={() => window.print()}
        className="block w-full text-center border border-gray-300 text-gray-700 py-3 rounded-xl text-sm print:hidden"
      >
        Print
      </button>

      {data.generated_at && (
        <p className="text-xs text-gray-400 mt-6 text-center">
          Generated {new Date(data.generated_at).toLocaleString()}
        </p>
      )}
    </main>
  );
}
