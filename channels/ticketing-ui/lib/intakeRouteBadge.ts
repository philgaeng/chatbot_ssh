/** Intake route (chatbot story_main) → queue/detail badge styling. */

export type IntakeRouteKey =
  | "seah_intake"
  | "road_hazard_grievance"
  | "new_grievance";

export interface IntakeRouteBadgeSpec {
  key: IntakeRouteKey;
  label: string;
  /** Tailwind classes for solid badge (desktop). */
  className: string;
  /** Tailwind classes for light badge (mobile xs). */
  classNameXs: string;
  showLock: boolean;
}

const SPECS: Record<IntakeRouteKey, IntakeRouteBadgeSpec> = {
  seah_intake: {
    key: "seah_intake",
    label: "SEAH",
    className: "bg-red-600 text-white",
    classNameXs: "text-red-600 bg-red-50",
    showLock: true,
  },
  road_hazard_grievance: {
    key: "road_hazard_grievance",
    label: "Road Hazard",
    className: "bg-orange-500 text-white",
    classNameXs: "text-orange-700 bg-orange-50",
    showLock: false,
  },
  new_grievance: {
    key: "new_grievance",
    label: "Safeguards",
    className: "bg-blue-600 text-white",
    classNameXs: "text-blue-700 bg-blue-50",
    showLock: false,
  },
};

const LEGACY_ALIASES: Record<string, IntakeRouteKey> = {
  grievance_new: "new_grievance",
  standard_grievance: "new_grievance",
  grievance_submission: "new_grievance",
  seah: "seah_intake",
  dust: "road_hazard_grievance",
  dust_grievance: "road_hazard_grievance",
  fast_track: "road_hazard_grievance",
  road_hazard: "road_hazard_grievance",
};

/** Map stored intake_route to badge spec, or null if unknown / missing. */
export function intakeRouteBadgeSpec(
  intakeRoute: string | null | undefined,
): IntakeRouteBadgeSpec | null {
  if (!intakeRoute?.trim()) return null;
  const raw = intakeRoute.trim().toLowerCase();
  const key =
    (raw in SPECS ? raw : LEGACY_ALIASES[raw]) as IntakeRouteKey | undefined;
  if (!key || !(key in SPECS)) return null;
  return SPECS[key];
}
