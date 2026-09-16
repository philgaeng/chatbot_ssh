// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <RoleLabel> — render a role by its plain-language name, never a bare slug
 * (DESIGN §7.C). Prefers the server `display_name`; falls back to a humanized key.
 * Pass `showKey` to append the mono `role_key` for admin/debug surfaces.
 */
import { roleLabel } from "@/lib/labels";
import { text as textTokens } from "@/lib/design-tokens";

export function RoleLabel({
  roleKey,
  displayName,
  showKey = false,
  className = "",
}: {
  roleKey: string | null | undefined;
  displayName?: string | null;
  showKey?: boolean;
  className?: string;
}) {
  const label = roleLabel(roleKey, displayName);
  return (
    <span className={className}>
      {label}
      {showKey && roleKey ? (
        <span className={`ml-1.5 font-mono text-xs ${textTokens.muted}`}>{roleKey}</span>
      ) : null}
    </span>
  );
}
