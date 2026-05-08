/**
 * GRM Icon system — all Lucide icons used in the app, re-exported from one place.
 *
 * Import from here rather than directly from lucide-react so the icon set stays
 * auditable and consistent.  Size defaults: w-4 h-4 (16 px).
 */

export {
  // ── Navigation ──────────────────────────────────────────────────────────────
  Inbox          as IconQueue,
  LayoutList     as IconAllTickets,
  AlertTriangle  as IconEscalated,
  BarChart2      as IconReports,
  QrCode         as IconQrCodes,
  Settings       as IconSettings,
  HelpCircle     as IconHelp,

  // ── Mobile tabs ─────────────────────────────────────────────────────────────
  Home           as IconMobileQueue,
  Search         as IconMobileSearch,
  ClipboardList  as IconMobileTasks,

  // ── Header / global ─────────────────────────────────────────────────────────
  Bell           as IconBell,
  LogOut         as IconSignOut,
  Lock           as IconLock,           // SEAH badge

  // ── Ticket actions ───────────────────────────────────────────────────────────
  CheckCircle2   as IconAcknowledge,
  ArrowUpCircle  as IconEscalateAction,
  Flag           as IconResolve,
  Landmark       as IconGrcConvene,
  Scale          as IconGrcDecide,

  // ── Thread toolbar ──────────────────────────────────────────────────────────
  Reply          as IconReply,
  ClipboardList  as IconTask,
  UserPlus       as IconAssign,
  Globe          as IconTranslations,

  // ── Complainant / PII ────────────────────────────────────────────────────────
  Pencil         as IconEdit,
  CheckCircle    as IconActiveSession,  // green — session active
  XCircle        as IconExpiredSession, // red — session expired / closed
  FileText       as IconRevealStatement,
  Phone          as IconPhone,
  Eye            as IconReveal,         // Reveal contact

  // ── Files / attachments ──────────────────────────────────────────────────────
  Image          as IconFileImage,
  FileText       as IconFilePdf,
  Paperclip      as IconFileOther,
  Upload         as IconUpload,
  Download       as IconDownload,

  // ── Thread components ────────────────────────────────────────────────────────
  Eye            as IconViewers,
  User           as IconUser,
  UserCheck      as IconCaseOwner,
  CheckSquare    as IconTasksDone,
  Check          as IconCheck,          // inline ✓ marks

  // ── Findings / AI ────────────────────────────────────────────────────────────
  Lightbulb      as IconFindings,
  RefreshCw      as IconRegenerate,

  // ── SLA / time ───────────────────────────────────────────────────────────────
  Clock          as IconClock,

  // ── Navigation / layout ──────────────────────────────────────────────────────
  ChevronRight   as IconChevronRight,
  ChevronDown    as IconChevronDown,

  // ── State / feedback ────────────────────────────────────────────────────────
  AlertTriangle  as IconWarning,
  X              as IconClose,
  Info           as IconInfo,

  // ── Settings / admin ────────────────────────────────────────────────────────
  Cpu            as IconSystemConfig,
  Construction   as IconComingSoon,
  Rocket         as IconGettingStarted,
  LifeBuoy       as IconSupport,
} from "lucide-react";

// ── TaskTypeIcon component ────────────────────────────────────────────────────
// Renders the icon for a TASK_TYPES entry using the Lucide icon name stored in
// the `icon` field (e.g. "MapPin", "Phone", "FileText", "Camera").

import {
  MapPin, Phone, FileText, Camera, ClipboardList,
  type LucideProps,
} from "lucide-react";

const TASK_ICON_MAP: Record<string, React.ComponentType<LucideProps>> = {
  MapPin, Phone, FileText, Camera,
};

export function TaskTypeIcon({ name, ...props }: { name: string } & LucideProps) {
  const Icon = TASK_ICON_MAP[name] ?? ClipboardList;
  return <Icon {...props} />;
}

// ── UrgencyDot component ──────────────────────────────────────────────────────
// Replaces the old emoji-based urgencyDot() — a proper CSS circle.

import { urgencyDotCls, type SlaUrgency } from "./mobile-constants";

export function UrgencyDot({ urgency, className = "" }: { urgency: SlaUrgency; className?: string }) {
  return (
    <span
      className={`w-2 h-2 rounded-full inline-block flex-shrink-0 ${urgencyDotCls(urgency)} ${className}`}
    />
  );
}

// ── SeahBadge component ───────────────────────────────────────────────────────

import { Lock } from "lucide-react";

export function SeahBadge({ size = "sm" }: { size?: "xs" | "sm" }) {
  const cls = size === "xs"
    ? "inline-flex items-center gap-0.5 text-[10px] font-bold text-red-600 bg-red-50 px-1 py-0.5 rounded"
    : "inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded";
  const iconSize = size === "xs" ? 8 : 10;
  return (
    <span className={cls}>
      <Lock size={iconSize} strokeWidth={2.5} />
      SEAH
    </span>
  );
}
