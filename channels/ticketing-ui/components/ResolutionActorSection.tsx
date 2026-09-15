// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * *Who took the action?* — inside the resolve form (GRM-117, DESIGN §3.2 and §4).
 *
 * Three answers and **nothing typed**: the officer's own office, another office from the directory,
 * or an outside body from a fixed list. The manager's Excel gets a *Resolved by* column from this,
 * and a free-text answer is exactly where a person's name would be written.
 *
 * The office search is limited to the case's country: once several ministries share the platform the
 * directory holds all their offices, and a road engineer in Jhapa should not be offered a customs
 * office in another country. Across ministries in one country it is deliberately not limited.
 */
import React, { useEffect, useState } from "react";
import {
  listOrganizations,
  type ExternalActor,
  type OrganizationChoice,
} from "@/lib/api";
import type { ResolutionActorChoice, ResolutionActorState } from "@/lib/resolution";

const SEARCH_DEBOUNCE_MS = 250;
const MAX_RESULTS = 20;

function Radio({
  name,
  checked,
  onChange,
  children,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer py-1">
      <input type="radio" name={name} checked={checked} onChange={onChange} className="mt-1 shrink-0" />
      <span className="min-w-0">{children}</span>
    </label>
  );
}

export function ResolutionActorSection({
  selfOffices,
  officeSuggestions,
  externalActors,
  countryCode,
  choice,
  state,
  onChange,
}: {
  selfOffices: OrganizationChoice[];
  officeSuggestions: OrganizationChoice[];
  externalActors: ExternalActor[];
  countryCode: string | null;
  choice: ResolutionActorChoice;
  state: ResolutionActorState;
  onChange: (choice: ResolutionActorChoice) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<OrganizationChoice[] | null>(null);
  const [searchFailed, setSearchFailed] = useState(false);

  // Server-side search, debounced. Only runs once the officer types — the project's offices are
  // shown before that, because the office that acted is almost always one of them.
  useEffect(() => {
    const q = query.trim();
    if (choice.kind !== "organization" || q.length < 2) return;
    let alive = true;
    const timer = setTimeout(() => {
      listOrganizations(countryCode ?? undefined, { q, activeOnly: true })
        .then((rows) => {
          if (!alive) return;
          setSearchFailed(false);
          setResults(rows.slice(0, MAX_RESULTS).map((o) => ({ organization_id: o.organization_id, name: o.name })));
        })
        .catch(() => alive && setSearchFailed(true));
    }, SEARCH_DEBOUNCE_MS);
    return () => { alive = false; clearTimeout(timer); };
  }, [query, choice.kind, countryCode]);

  if (state.hidden) return null;

  const searching = query.trim().length >= 2;
  const offices = searching ? (results ?? []) : officeSuggestions;
  const pick = (organizationId: string) => onChange({ ...choice, kind: "organization", organizationId });

  return (
    <fieldset className="mb-4">
      <legend className="block text-xs font-medium text-gray-600 mb-1">Who took the action?</legend>

      <Radio name="resolution-actor" checked={choice.kind === "self"}
        onChange={() => onChange({ kind: "self", organizationId: null, external: null })}>
        {state.selfOffice ? <>I did — <strong>{state.selfOffice.name}</strong></> : "I did"}
      </Radio>
      {choice.kind === "self" && !state.selfOffice && (
        <select
          aria-label="Which of your offices"
          value={choice.organizationId ?? ""}
          onChange={(e) => onChange({ ...choice, organizationId: e.target.value || null })}
          className="ml-6 w-[calc(100%-1.5rem)] border border-gray-300 rounded-lg px-3 py-2 text-sm mb-1"
        >
          <option value="">— Choose your office —</option>
          {selfOffices.map((o) => <option key={o.organization_id} value={o.organization_id}>{o.name}</option>)}
        </select>
      )}

      <Radio name="resolution-actor" checked={choice.kind === "organization"}
        onChange={() => onChange({ kind: "organization", organizationId: null, external: null })}>
        Another office
      </Radio>
      {choice.kind === "organization" && (
        <div className="ml-6 mb-1 space-y-1">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search offices…"
            aria-label="Search offices"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
          {!searching && offices.length > 0 && <p className="text-xs text-gray-500">Offices on this project:</p>}
          {searchFailed && <p className="text-xs text-red-600">The search failed. Try again.</p>}
          {searching && results !== null && offices.length === 0 && !searchFailed && (
            <p className="text-xs text-gray-500">
              No office found. If it is not in the directory, choose &ldquo;An outside body&rdquo; or ask an admin to add it.
            </p>
          )}
          {offices.map((o) => (
            <Radio key={o.organization_id} name="resolution-actor-office"
              checked={choice.organizationId === o.organization_id} onChange={() => pick(o.organization_id)}>
              {o.name}
            </Radio>
          ))}
        </div>
      )}

      <Radio name="resolution-actor" checked={choice.kind === "external"}
        onChange={() => onChange({ kind: "external", organizationId: null, external: null })}>
        An outside body
      </Radio>
      {choice.kind === "external" && (
        <select
          aria-label="Which outside body"
          value={choice.external ?? ""}
          onChange={(e) => onChange({ ...choice, external: e.target.value || null })}
          className="ml-6 w-[calc(100%-1.5rem)] border border-gray-300 rounded-lg px-3 py-2 text-sm mb-1"
        >
          <option value="">— Choose —</option>
          {externalActors.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
        </select>
      )}

      {state.missing && <p className="text-xs text-gray-500 mt-1">{state.missing}</p>}
    </fieldset>
  );
}
