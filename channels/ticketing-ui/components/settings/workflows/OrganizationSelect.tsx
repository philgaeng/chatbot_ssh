// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <OrganizationSelect> — "Belongs to": pick one organization the admin manages (GRM-122).
 *
 * The list comes from `GET /organizations?manageable=true`, so a scoped admin only ever sees
 * organizations it may assign — the server refuses anything else anyway. A search box narrows long
 * lists without leaving the native select, which keeps it usable on a phone.
 */
import React, { useEffect, useMemo, useState } from "react";
import { listOrganizations, type OrganizationItem } from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

export function OrganizationSelect({
  id,
  value,
  onChange,
  onLoaded,
  disabled,
}: {
  id: string;
  value: string;
  onChange: (organizationId: string, organization: OrganizationItem | undefined) => void;
  /** Called once with everything the admin manages — lets a caller pick a default. */
  onLoaded?: (orgs: OrganizationItem[]) => void;
  disabled?: boolean;
}) {
  const [orgs, setOrgs] = useState<OrganizationItem[] | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let alive = true;
    listOrganizations(undefined, { manageable: true })
      .then((rows) => {
        if (!alive) return;
        const active = rows.filter((o) => o.is_active);
        setOrgs(active);
        onLoaded?.(active);
      })
      .catch((e: unknown) => alive && setError(friendlyError(e)));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once; onLoaded is a one-shot hook
  }, []);

  const shown = useMemo(() => {
    if (!orgs) return [];
    const q = search.trim().toLowerCase();
    const matches = q ? orgs.filter((o) => o.name.toLowerCase().includes(q)) : orgs;
    // Keep the current choice visible even when the search hides it.
    const current = orgs.find((o) => o.organization_id === value);
    return current && !matches.includes(current) ? [current, ...matches] : matches;
  }, [orgs, search, value]);

  if (error) return <p className="text-xs text-red-600">{error}</p>;
  if (!orgs) return <p className="text-xs text-gray-400">Loading organizations…</p>;
  if (orgs.length === 0) return <p className="text-xs text-gray-500">You do not manage any organization.</p>;

  return (
    <div className="space-y-1.5">
      {orgs.length > 8 && (
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search organizations…"
          aria-label="Search organizations"
          disabled={disabled}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      )}
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value, orgs.find((o) => o.organization_id === e.target.value))}
        className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
      >
        <option value="">— Choose an organization —</option>
        {shown.map((o) => (
          <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
        ))}
      </select>
      <p className="text-xs text-gray-400">Only organizations you manage are listed.</p>
    </div>
  );
}
