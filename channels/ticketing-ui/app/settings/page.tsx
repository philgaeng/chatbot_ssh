"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { AlertTriangle, X, Lock, Construction } from "lucide-react";
import { useAuth } from "@/app/providers/AuthProvider";
import { QuarterlyReportSettings } from "@/components/settings/QuarterlyReportSettings";
import {
  listScopes,
  addScope,
  deleteScope,
  setProjectActorRoles,
  updateOrganization,
  deleteOrganization,
  listProjectsForOrg,
  type WorkflowAssignmentItem,
  type OfficerScope,
  type ProjectOrgItem,
  type PackageCreate,
  listRoles,
} from "@/lib/api";
import { ProjectTypesTab } from "@/components/settings/ProjectTypesTab";
// RB-2/RB-4: the god-file's flat OrgsSection + actor-role editor are replaced by the
// decomposed org-chart surfaces (tree + CSV + position types) and the doc-13 participant model.
import { OrganisationTab } from "@/components/settings/org/OrganisationTab";
import { OfficersTabV2 } from "@/components/settings/officers-v2/OfficersTabV2";
import { AdminAccessTab } from "@/components/settings/platform/AdminAccessTab";
import { LocationsSection } from "@/components/settings/platform/LocationsSection";
import { SystemConfigTab } from "@/components/settings/platform/SystemConfigTab";
import { type RoleEntry, mapGrmRoleToEntry } from "@/components/settings/roles/roleEntry";
import { WorkflowsTab } from "@/components/settings/workflows/WorkflowsTab";
import { ProjectsSection } from "@/components/settings/projects/ProjectsSection";

type MainTab = "org_officers" | "workflows_roles" | "projects" | "platform";
type OrgOfficersSub = "organizations" | "officers";
/** A project type is mostly a bundle of workflows, so it is authored beside them, not under
 *  platform data (moved 2026-08-04 — it sat under Settings → Project types, where nobody
 *  looking at a workflow would find it). */
type WorkflowsSub = "workflows" | "project_types";
type PlatformSub = "locations" | "reports" | "system_config" | "admin_access";

/**
 * "Setup & go-live" was removed as a top-level tab (2026-08-07, Philippe). It listed every
 * project's go-live checks a second time, in a second layout, one click from the project
 * console that owns them — so it could only ever agree with the console by accident, and it
 * asked you to pick a project before it could say anything the console does not say better.
 * Go-live lives on the project, next to the panes that fix it.
 */
const MAIN_TABS: { id: MainTab; label: string }[] = [
  { id: "org_officers",      label: "Organizations & officers" },
  { id: "workflows_roles",   label: "Workflows" },
  { id: "projects",          label: "Projects & packages" },
  { id: "platform",          label: "Settings" },
];

// Org-role badge colors now live in lib/design-tokens.ts (orgRoleBadge) — the banned-hue
// map that used to be here (purple/indigo/orange/teal) is gone (RB-2 §7.C, F24).

// ─────────────────────────────────────────────────────────────────────────────

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Construction size={40} strokeWidth={1.25} className="mb-4 text-gray-300" />
      <h3 className="text-base font-semibold text-gray-700 mb-1">{label}</h3>
      <p className="text-sm text-gray-400 max-w-xs">
        This section is coming in Week 3. Contact your administrator to make changes directly.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SettingsSubTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  active: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="flex gap-0 border-b border-gray-200 mb-6">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            active === tab.id
              ? "border-blue-500 text-blue-600"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export default function SettingsPage() {
  const {
    isAdmin,
    isSuperAdmin,
    isCountryAdmin,
    isProjectAdmin,
    canAccessPlatformSettings,
    canCreateProject,
    canManageStructure,
    canCreateOperationalRoles,
    adminWorkflowTracks,
  } = useAuth();
  const canManageProjectCatalog = isSuperAdmin || isCountryAdmin;
  const mainTabs = useMemo(() => {
    if (isSuperAdmin) return MAIN_TABS;
    if (isCountryAdmin) {
      const tabs = MAIN_TABS.filter((t) => t.id !== "platform");
      if (!adminWorkflowTracks.includes("standard")) {
        return tabs.filter((t) => t.id !== "projects" || adminWorkflowTracks.includes("seah"));
      }
      return tabs;
    }
    if (isProjectAdmin) {
      return MAIN_TABS.filter((t) => t.id === "org_officers" || t.id === "workflows_roles" || t.id === "projects");
    }
    if (isAdmin) return MAIN_TABS.filter((t) => t.id === "projects");
    return MAIN_TABS.filter((t) => t.id === "projects");
  }, [isSuperAdmin, isCountryAdmin, isProjectAdmin, isAdmin, adminWorkflowTracks]);
  // Projects is the landing: it is where setup actually happens now that the go-live tab is gone.
  const [activeMain, setActiveMain] = useState<MainTab>("projects");
  const [orgSub, setOrgSub] = useState<OrgOfficersSub>("organizations");
  const [workflowsSub, setWorkflowsSub] = useState<WorkflowsSub>("workflows");
  const [platformSub, setPlatformSub] = useState<PlatformSub>("locations");
  const [jumpProjectId, setJumpProjectId] = useState<string | null>(null);
  const [roleCatalog, setRoleCatalog]     = useState<RoleEntry[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);

  const grmRoleChoices = useMemo(
    () => roleCatalog.map((r) => ({ key: r.key, label: r.label })),
    [roleCatalog],
  );

  const loadRoleCatalog = useCallback(async () => {
    setRolesLoading(true);
    try {
      const raw = await listRoles({ kind: "operational" });
      setRoleCatalog(raw.map(mapGrmRoleToEntry));
    } catch {
      setRoleCatalog([]);
    } finally {
      setRolesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoleCatalog();
  }, [loadRoleCatalog]);

  useEffect(() => {
    if (!mainTabs.some((t) => t.id === activeMain)) {
      setActiveMain(mainTabs[0]?.id ?? "projects");
    }
  }, [mainTabs, activeMain]);

  function navigateToProject(projectId: string) {
    setJumpProjectId(projectId);
    setActiveMain("projects");
  }

  // Authoring a type is the same gate as authoring a workflow (DECISION-author-defined-slots
  // §3.1): super_admin anywhere, org_admin in its own subtree. A project_admin sees the
  // Workflows tab but not this sub-tab.
  const canAuthorProjectTypes = isSuperAdmin || isCountryAdmin;
  const workflowsTabs: { id: WorkflowsSub; label: string }[] = useMemo(
    () =>
      canAuthorProjectTypes
        ? [
            { id: "workflows", label: "Workflows" },
            { id: "project_types", label: "Project types" },
          ]
        : [],
    [canAuthorProjectTypes],
  );

  useEffect(() => {
    if (!canAuthorProjectTypes && workflowsSub !== "workflows") setWorkflowsSub("workflows");
  }, [canAuthorProjectTypes, workflowsSub]);

  const platformTabs: { id: PlatformSub; label: string }[] = useMemo(() => {
    if (canAccessPlatformSettings) {
      return [
        { id: "locations", label: "Locations" },
        { id: "reports", label: "Quarterly reports" },
        { id: "system_config", label: "Advanced (JSON)" },
        { id: "admin_access", label: "Admin access" },
      ];
    }
    return [];
  }, [canAccessPlatformSettings]);

  useEffect(() => {
    if (!canAccessPlatformSettings && platformSub !== "reports") {
      setPlatformSub("locations");
    }
  }, [canAccessPlatformSettings, platformSub]);

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <Lock size={32} strokeWidth={1.5} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm text-gray-500">Settings are only accessible to administrators.</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-gray-800">{canManageProjectCatalog ? "Settings" : "Project setup"}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {canManageProjectCatalog
            ? "Admin configuration — organizations, projects, workflows, and platform data"
            : "Add partner organizations, invite officers, link locations, and complete go-live checks."}
        </p>
      </div>

      {mainTabs.length > 1 && (
      <div className="flex gap-0 border-b border-gray-200 mb-4 overflow-x-auto">
        {mainTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveMain(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeMain === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      )}

      {activeMain === "org_officers" && (
        <>
          <SettingsSubTabs
            tabs={[
              { id: "organizations", label: "Organizations" },
              { id: "officers", label: "Officers" },
            ]}
            active={orgSub}
            onChange={setOrgSub}
          />
          {orgSub === "organizations" && (
            <OrganisationTab canEdit={canManageStructure} canCreateRoot={isSuperAdmin} />
          )}
          {orgSub === "officers" && (
            <OfficersTabV2
              // R10 (BUILD-REVIEW MO1): managing officers is an officer-admin capability, not
              // org-structure — decouple from canManageStructure so a project_admin who can
              // invite can also manage/deactivate. (Backend already enforces the real scope.)
              canInvite={isSuperAdmin || isCountryAdmin || isProjectAdmin}
              canManage={isSuperAdmin || isCountryAdmin || isProjectAdmin}
            />
          )}
        </>
      )}

      {activeMain === "workflows_roles" && (
        // Operational Roles tab removed (DESIGN-cast-model §7 Phase 3): tiers live on the step
        // editor, who + jurisdiction on per-package staffing, Standard/SEAH on the workflow track.
        // Project types sit here, beside the workflows they bundle.
        <>
          {workflowsTabs.length > 1 && (
            <SettingsSubTabs tabs={workflowsTabs} active={workflowsSub} onChange={setWorkflowsSub} />
          )}
          {workflowsSub === "project_types" && canAuthorProjectTypes ? (
            <ProjectTypesTab />
          ) : (
            <WorkflowsTab
              roleCatalog={roleCatalog}
              canCreateRole={canCreateOperationalRoles}
              onRoleCatalogRefresh={loadRoleCatalog}
            />
          )}
        </>
      )}

      {activeMain === "projects" && (
        <ProjectsSection
          initialEditId={jumpProjectId}
          grmRoleChoices={grmRoleChoices}
          isSuperAdmin={isSuperAdmin}
          isCountryAdmin={isCountryAdmin}
          adminWorkflowTracks={adminWorkflowTracks}
          canCreateProject={canCreateProject}
          canManageStructure={canManageStructure}
          onOpenProjectTypes={() => { setActiveMain("workflows_roles"); setWorkflowsSub("project_types"); }}
        />
      )}

      {activeMain === "platform" && (
        <>
          <SettingsSubTabs tabs={platformTabs} active={platformSub} onChange={setPlatformSub} />
          {platformSub === "locations" && <LocationsSection />}
          {platformSub === "reports" && <QuarterlyReportSettings />}
          {platformSub === "system_config" && isSuperAdmin && <SystemConfigTab />}
          {platformSub === "admin_access" && isSuperAdmin && <AdminAccessTab />}
        </>
      )}
    </div>
  );
}
