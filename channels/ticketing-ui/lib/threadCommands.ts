/**
 * H2-06 — pure parsing for the two compose-bar hash commands (`#assign` / `#inspect`).
 *
 * Extracted verbatim from the desktop (`app/tickets/[id]`) and mobile
 * (`app/m/tickets/[id]`) `handleNoteOrReport` bodies, which each carried their own
 * ~40-line copy of this parse. Two copies of one command parser is a bug farm (the
 * ticket's words) — this is the single source of truth both pages now share.
 *
 * Pure: no React, no I/O. Unit-tested in `threadCommands.test.ts`.
 */
import { parseInspectAssignCommand } from "@/lib/field-visit";

/**
 * `#assign @name …` — anchored at the start, captures the assignee mention.
 * Intentionally a *prefix* match (no `$`): any trailing free text after the
 * mention is allowed and surfaced as `rest` (the original handler ignored it, but
 * keeping it keeps the parse lossless). Matches the regex the two pages used
 * inline: `/^#assign\s+@([A-Za-z0-9][A-Za-z0-9._@-]*)/`.
 */
export const ASSIGN_COMMAND_REGEX = /^#assign\s+@([A-Za-z0-9][A-Za-z0-9._@-]*)/;

/**
 * Result of {@link parseThreadCommand}. One discriminated member per branch of the
 * original `if (inspect) … else if (assign) … else note` ladder, so the consumer
 * switches on `kind` instead of re-deriving matches.
 */
export type ThreadCommand =
  /** `#inspect` (self) or `#inspect @officer`. `assignee === null` ⇒ assign to self. */
  | { kind: "inspect"; args: { assignee: string | null }; rest: string }
  /** `#assign @officer …` — reassign the ticket to `assignee`. */
  | { kind: "assign"; args: { assignee: string }; rest: string }
  /** Anything else — a plain thread note; `rest` is the trimmed note body. */
  | { kind: "note"; args: Record<string, never>; rest: string };

/**
 * Parse a compose-bar submission into its command intent.
 *
 * Precedence mirrors the original handlers exactly: **`#inspect` is tested before
 * `#assign`** (the inspect branch came first in both pages). `#inspect` requires the
 * *whole* line to be the command (`parseInspectAssignCommand` is `$`-anchored), so
 * `#inspect look into this` is a NOTE, not an inspect command — preserved here.
 */
export function parseThreadCommand(input: string): ThreadCommand {
  const text = input.trim();

  // `#inspect` / `#inspect @me` / `#inspect @officer` — undefined ⇒ not an inspect
  // command; null ⇒ self; string ⇒ that officer. Reuses the existing shared parser.
  const inspectAssignee = parseInspectAssignCommand(text);
  if (inspectAssignee !== undefined) {
    return { kind: "inspect", args: { assignee: inspectAssignee }, rest: "" };
  }

  const assignMatch = text.match(ASSIGN_COMMAND_REGEX);
  if (assignMatch) {
    return {
      kind: "assign",
      args: { assignee: assignMatch[1] },
      rest: text.slice(assignMatch[0].length).trim(),
    };
  }

  return { kind: "note", args: {}, rest: text };
}
