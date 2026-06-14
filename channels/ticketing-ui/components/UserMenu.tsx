"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/app/providers/AuthProvider";
import { IconSignOut } from "@/lib/icons";

export function UserMenu({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const label = user?.name?.trim() || user?.email || "Account";
  const email = user?.email ?? "";
  const initial = (label.charAt(0) || "?").toUpperCase();

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const mobile = variant === "mobile";

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1.5 rounded-lg hover:bg-gray-100 transition text-left touch-manipulation ${
          mobile ? "px-1 py-1 max-w-[9rem]" : "px-2 py-1.5 max-w-[14rem]"
        }`}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="w-8 h-8 rounded-full bg-slate-200 text-slate-700 text-sm font-semibold flex items-center justify-center shrink-0">
          {initial}
        </span>
        <span
          className={`text-sm text-gray-700 font-medium truncate ${
            mobile ? "max-w-[5.5rem] text-xs" : "hidden sm:block"
          }`}
        >
          {mobile ? (email || label).split("@")[0] : label}
        </span>
        {!mobile && (
          <svg className="w-3.5 h-3.5 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </button>

      {open && (
        <div
          className={`absolute bg-white border border-gray-200 rounded-xl shadow-lg z-50 py-1 ${
            mobile ? "right-0 top-full mt-1 w-64" : "right-0 top-full mt-1 w-56"
          }`}
          role="menu"
        >
          <div className="px-3 py-2 border-b border-gray-100">
            <div className="text-sm font-medium text-gray-800 truncate">{label}</div>
            {email && <div className="text-xs text-gray-500 truncate">{email}</div>}
          </div>
          <Link
            href="/account"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
            role="menuitem"
          >
            Account settings
          </Link>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              signOut();
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 text-left"
            role="menuitem"
          >
            <IconSignOut size={14} strokeWidth={1.75} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
