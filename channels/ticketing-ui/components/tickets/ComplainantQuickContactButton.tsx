"use client";

import { MessageSquare, Phone } from "lucide-react";

const STYLES = {
  sms: "bg-blue-600 active:bg-blue-700 hover:bg-blue-700",
  call: "bg-green-600 active:bg-green-700 hover:bg-green-700",
} as const;

interface ComplainantQuickContactButtonProps {
  kind: "sms" | "call";
  href: string | null;
  loading?: boolean;
  onUnavailable?: () => void;
  className?: string;
}

export function ComplainantQuickContactButton({
  kind,
  href,
  loading = false,
  onUnavailable,
  className = "",
}: ComplainantQuickContactButtonProps) {
  if (loading) return null;

  const compactCls = `flex-shrink-0 min-w-[3rem] h-12 px-3 flex items-center justify-center text-white rounded-xl transition-colors ${STYLES[kind]}`;
  const Icon = kind === "sms" ? MessageSquare : Phone;
  const label = kind === "sms" ? "Text complainant" : "Call complainant";
  const title = kind === "sms" ? "Text complainant" : "Call complainant";

  if (!href) {
    if (!onUnavailable) return null;
    return (
      <button
        type="button"
        onClick={onUnavailable}
        className={`${compactCls} opacity-40 cursor-not-allowed ${className}`}
        aria-label={`${label} — no phone on file`}
        title="No phone number on file"
      >
        <Icon size={20} strokeWidth={2} />
      </button>
    );
  }

  return (
    <a
      href={href}
      className={`${compactCls} ${className}`}
      aria-label={label}
      title={title}
    >
      <Icon size={20} strokeWidth={2} />
    </a>
  );
}
