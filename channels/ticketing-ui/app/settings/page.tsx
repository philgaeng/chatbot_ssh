"use client";

import { useState } from "react";
import { useAuth } from "@/app/providers/AuthProvider";

type Section = "workflows" | "users" | "organizations" | "report_schedule";

const SECTIONS: { id: Section; label: string; icon: string; description: string }[] = [
  {
    id: "workflows",
    label: "Workflows",
    icon: "🔄",
    description: "Manage GRM workflow definitions, escalation levels, and SLA targets.",
  },
  {
    id: "users",
    label: "Officers & Roles",
    icon: "👥",
    description: "Invite officers, assign roles, manage SEAH access.",
  },
  {
    id: "organizations",
    label: "Organizations & Locations",
    icon: "🏢",
    description: "Manage organizations (DOR, ADB) and project locations.",
  },
  {
    id: "report_schedule",
    label: "Report Schedule",
    icon: "📅",
    description: "Configure quarterly report schedule and distribution list.",
  },
];

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-4">🚧</div>
      <h3 className="text-base font-semibold text-gray-700 mb-1">{label}</h3>
      <p className="text-sm text-gray-400 max-w-xs">
        This section will be available in Week 3. Contact your administrator to make changes directly.
      </p>
    </div>
  );
}

export default function SettingsPage() {
  const { isAdmin } = useAuth();
  const [active, setActive] = useState<Section>("workflows");

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <div className="text-3xl mb-3">🔒</div>
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  const current = SECTIONS.find((s) => s.id === active)!;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">System configuration — admin access only</p>
      </div>

      <div className="flex gap-5">
        {/* Sidebar */}
        <nav className="w-52 shrink-0 space-y-0.5">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              className={`w-full text-left flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active === s.id
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <span>{s.icon}</span>
              <span>{s.label}</span>
            </button>
          ))}
        </nav>

        {/* Content pane */}
        <div className="flex-1 bg-white rounded-lg border border-gray-200 min-h-[400px]">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <span>{current.icon}</span>
              <span>{current.label}</span>
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">{current.description}</p>
          </div>
          <ComingSoon label={current.label} />
        </div>
      </div>
    </div>
  );
}
