/**
 * icons.ts — single import point for all Lucide icons used in the GRM UI.
 *
 * Rule: never import lucide-react directly from page/component files.
 * Always import from here so global icon swaps are a one-line change.
 *
 * Icon sizing convention:
 *   Nav sidebar     : size={18}
 *   Inline / button : size={15}  (pairs cleanly with text-sm)
 *   Tiny / badge    : size={12}
 */

export {
  // ── Navigation ────────────────────────────────────────────────────────────
  Inbox          as IconQueue,           // My Queue
  List           as IconAllTickets,      // All Tickets
  TriangleAlert  as IconEscalated,       // Escalated tab / nav
  ChartBar       as IconReports,         // Reports
  Settings       as IconSettings,        // Settings (admin)
  CircleQuestionMark as IconHelp,        // Help

  // ── Shell chrome ──────────────────────────────────────────────────────────
  Bell           as IconBell,            // Notification badge
  LogOut         as IconSignOut,         // Sign out
  Lock           as IconLock,            // SEAH badge, internal note marker
  User           as IconUser,            // Assigned officer / user identity

  // ── Navigation / UI controls ──────────────────────────────────────────────
  ArrowLeft      as IconBack,            // ← Back
  ChevronRight   as IconChevronRight,    // List row arrow
  X              as IconClose,           // Close / dismiss / ×
  RefreshCw      as IconRefresh,         // ↻ Regenerate / refresh

  // ── Ticket status actions ─────────────────────────────────────────────────
  CircleCheck    as IconAcknowledge,     // ✅ Acknowledge
  CircleArrowUp  as IconEscalateAction,  // ↑ Escalate (action button)
  Flag           as IconResolve,         // 🏁 Resolve
  CircleX        as IconClose2,          // ✕ Close ticket

  // ── GRC-specific ──────────────────────────────────────────────────────────
  Landmark       as IconGrcConvene,      // 🏛️ Convene GRC hearing
  Scale          as IconGrcDecide,       // ⚖️ Record GRC decision

  // ── Event timeline ────────────────────────────────────────────────────────
  Plus           as IconCreated,         // Ticket created
  StickyNote     as IconNote,            // Internal note (officer-only)
  MessageSquare  as IconReply,           // Reply sent to complainant
  Smartphone     as IconComplainantNotified, // Complainant notified (SMS/chat)
  Globe          as IconTranslation,     // Translation / bilingual
  FileText       as IconReveal,          // Reveal original statement / doc file
  Sparkles       as IconFindings,        // AI Findings / summary
  Brain          as IconAi,              // AI brain (secondary AI icon)

  // ── Files & attachments ───────────────────────────────────────────────────
  Paperclip      as IconAttachment,      // Attachment row
  Image          as IconImageFile,       // Image file type
  Upload         as IconUpload,          // Upload action

} from "lucide-react";

// ── Re-export type for icon props ─────────────────────────────────────────────
export type { LucideProps } from "lucide-react";
