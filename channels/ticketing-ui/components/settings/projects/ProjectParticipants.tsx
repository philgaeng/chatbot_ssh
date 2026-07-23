"use client";

/**
 * <ProjectParticipants> — the doc-13 / DECISION 2026-07-10 project-participant surface
 * (replaces the retired actor-role catalog on the Projects frame, wireframe 05):
 *
 *   • Implementing agency — a single defaulted government / local-government org (the
 *     routing + reporting anchor). Rejects a donor/contractor (server-validated).
 *   • Donors — optional 0..n funder orgs (category `donor`). Adding a donor auto-populates
 *     the final standard step's "Kept informed" cast (backend), so the go-live donor
 *     guardrail (A5) becomes satisfiable; SEAH-suppressed at runtime.
 *
 * The A5 (donor informed) + C5 (all levels staffed) go-live blocks are surfaced inline so
 * the admin sees why activation is gated.
 */
import { useCallback, useEffect, useState } from "react";
import { Building2, HandCoins, Plus, X } from "lucide-react";

import {
  addProjectDonor,
  getProjectGoLive,
  listOrganizations,
  listProjectDonors,
  removeProjectDonor,
  updateProject,
  type GoLiveCheck,
  type OrganizationItem,
  type ProjectDonorItem,
  type ProjectItem,
} from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { SeverityBadge, type Severity } from "@/components/shared/SeverityBadge";
import { ProvenanceHint } from "@/components/shared/ProvenanceHint";
import { Bilingual } from "@/components/shared/Bilingual";

const IA_CATEGORIES = new Set(["government", "local_government"]);

function severityOf(check: GoLiveCheck): Severity {
  if (check.status === "pass") return "pass";
  if (check.severity === "block") return "block";
  if (check.severity === "warn") return "warn";
  return "info";
}

export function ProjectParticipants({
  project,
  canEdit,
  onUpdated,
}: {
  project: ProjectItem;
  canEdit: boolean;
  onUpdated?: () => void;
}) {
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [donors, setDonors] = useState<ProjectDonorItem[]>([]);
  const [ia, setIa] = useState<string>(project.implementing_agency_org_id ?? "");
  const [addingDonor, setAddingDonor] = useState<string>("");
  const [checks, setChecks] = useState<GoLiveCheck[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [orgList, donorList, report] = await Promise.all([
        listOrganizations(),
        listProjectDonors(project.project_id),
        getProjectGoLive(project.project_id),
      ]);
      setOrgs(orgList);
      setDonors(donorList);
      setChecks(report.checks.filter((c) => c.id === "A5" || c.id === "C5"));
      setErr(null);
    } catch (e) {
      setErr(e);
    }
  }, [project.project_id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const iaOptions = orgs.filter((o) => IA_CATEGORIES.has(o.org_category ?? ""));
  const donorOrgIds = new Set(donors.map((d) => d.organization_id));
  const donorOptions = orgs.filter(
    (o) => (o.org_category ?? "") === "donor" && !donorOrgIds.has(o.organization_id),
  );
  const orgName = (id: string) => orgs.find((o) => o.organization_id === id)?.name ?? id;

  async function saveIa(next: string) {
    if (!canEdit) return;
    setBusy(true);
    setErr(null);
    try {
      await updateProject(project.project_id, { implementing_agency_org_id: next || null });
      setIa(next);
      onUpdated?.();
      await refresh();
    } catch (e) {
      setErr(e);
      setIa(project.implementing_agency_org_id ?? "");
    } finally {
      setBusy(false);
    }
  }

  async function doAddDonor() {
    if (!canEdit || !addingDonor) return;
    setBusy(true);
    setErr(null);
    try {
      await addProjectDonor(project.project_id, addingDonor);
      setAddingDonor("");
      onUpdated?.();
      await refresh();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  async function doRemoveDonor(orgId: string) {
    if (!canEdit) return;
    setBusy(true);
    setErr(null);
    try {
      await removeProjectDonor(project.project_id, orgId);
      onUpdated?.();
      await refresh();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <ErrorNotice error={err} />

      {/* Implementing agency */}
      <section>
        <div className={`flex items-center gap-1.5 text-sm font-medium ${textTokens.heading} mb-1`}>
          <Building2 size={15} aria-hidden /> Implementing agency
        </div>
        <select
          value={ia}
          disabled={!canEdit || busy}
          onChange={(e) => void saveIa(e.target.value)}
          className="w-full max-w-md border border-gray-300 rounded px-2 py-1.5 text-sm disabled:opacity-60"
        >
          <option value="">— Select the accountable agency —</option>
          {iaOptions.map((o) => (
            <option key={o.organization_id} value={o.organization_id}>
              {o.name}
            </option>
          ))}
        </select>
        <ProvenanceHint className="mt-1">
          The signing government agency — routing &amp; reporting anchor. Only government /
          local-government organisations are eligible.
        </ProvenanceHint>
      </section>

      {/* Donors */}
      <section>
        <div className={`flex items-center gap-1.5 text-sm font-medium ${textTokens.heading} mb-1`}>
          <HandCoins size={15} aria-hidden /> Donors <span className={textTokens.muted}>(optional)</span>
        </div>
        {donors.length === 0 ? (
          <p className={`text-xs ${textTokens.secondary} mb-2`}>No donors on this project.</p>
        ) : (
          <ul className="mb-2 space-y-1">
            {donors.map((d) => (
              <li
                key={d.organization_id}
                className="flex items-center justify-between max-w-md rounded border border-gray-200 px-2.5 py-1.5 text-sm"
              >
                <Bilingual en={d.name ?? orgName(d.organization_id)} ne={null} mode="active" />
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => void doRemoveDonor(d.organization_id)}
                    disabled={busy}
                    className="text-gray-400 hover:text-red-600 disabled:opacity-50"
                    aria-label={`Remove donor ${d.name ?? d.organization_id}`}
                  >
                    <X size={15} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
        {canEdit && (
          <div className="flex items-center gap-2">
            <select
              value={addingDonor}
              onChange={(e) => setAddingDonor(e.target.value)}
              disabled={busy || donorOptions.length === 0}
              className="border border-gray-300 rounded px-2 py-1.5 text-sm disabled:opacity-60"
            >
              <option value="">
                {donorOptions.length === 0 ? "No donor organisations available" : "— Add a donor —"}
              </option>
              {donorOptions.map((o) => (
                <option key={o.organization_id} value={o.organization_id}>
                  {o.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void doAddDonor()}
              disabled={busy || !addingDonor}
              className="inline-flex items-center gap-1 text-sm bg-blue-600 text-white px-2.5 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              <Plus size={14} /> Add
            </button>
          </div>
        )}
        <ProvenanceHint className="mt-1">
          A donor&apos;s staff are kept informed on final escalation of standard cases (never
          on SEAH cases). Adding a donor pre-fills the final step&apos;s notified roles.
        </ProvenanceHint>
      </section>

      {/* Go-live gates that these settings drive */}
      {checks.length > 0 && (
        <section className="rounded border border-gray-200 bg-gray-50 px-3 py-2.5">
          <div className={`text-xs font-medium ${textTokens.secondary} mb-1.5`}>Go-live gates</div>
          <ul className="space-y-1.5">
            {checks.map((c) => (
              <li key={c.id} className="flex items-start gap-2 text-sm">
                <SeverityBadge severity={severityOf(c)} />
                <span className={textTokens.body}>{c.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
