"use client";

import { useCallback, useRef, useState } from "react";

export interface MentionParticipant {
  user_id: string;
  label: string;
}

interface ComposeBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  participants?: MentionParticipant[];
  placeholder?: string;
  /** Extra classes on the outer wrapper — use for padding/border overrides */
  className?: string;
}

export function ComposeBar({
  value,
  onChange,
  onSubmit,
  disabled,
  participants = [],
  placeholder = "Add a note… (type @ to mention)",
  className = "",
}: ComposeBarProps) {
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleChange = useCallback((newValue: string) => {
    onChange(newValue);
    const match = newValue.match(/@([\w.-]*)$/);
    setMentionQuery(match ? match[1] : null);
  }, [onChange]);

  const insertMention = useCallback((userId: string) => {
    const next = value.replace(/@[\w.-]*$/, `@${userId} `);
    onChange(next);
    setMentionQuery(null);
    textareaRef.current?.focus();
  }, [value, onChange]);

  const filteredParticipants = mentionQuery !== null
    ? participants
        .filter((p) => !mentionQuery || p.user_id.toLowerCase().includes(mentionQuery.toLowerCase()))
        .slice(0, 6)
    : [];

  return (
    <div className={`flex items-end gap-2 px-3 py-2 ${className}`}>
      <div className="relative flex-1">
        {/* @mention autocomplete popup — floats above the textarea */}
        {mentionQuery !== null && (
          <div className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-10">
            {filteredParticipants.length > 0
              ? filteredParticipants.map((p) => (
                <button
                  key={p.user_id}
                  onMouseDown={(e) => { e.preventDefault(); insertMention(p.user_id); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-blue-50 active:bg-blue-100 border-b border-gray-100 last:border-0"
                >
                  <span className="font-medium text-blue-600">{p.label}</span>
                </button>
              ))
              : <div className="px-4 py-2.5 text-xs text-gray-400">No participants match</div>
            }
          </div>
        )}

        <div className="bg-gray-100 rounded-2xl px-4 py-2.5 min-h-[44px] flex items-center">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={placeholder}
            rows={1}
            className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none"
            style={{ maxHeight: "96px" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") { setMentionQuery(null); return; }
              if (e.key === "Enter" && !e.shiftKey && mentionQuery === null) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />
        </div>
      </div>

      <button
        onClick={onSubmit}
        disabled={!value.trim() || disabled}
        className={`w-10 h-10 rounded-full flex items-center justify-center text-white transition-colors flex-shrink-0 ${
          value.trim() && !disabled ? "bg-blue-600 hover:bg-blue-700 active:bg-blue-800" : "bg-gray-300"
        }`}
      >
        ↑
      </button>
    </div>
  );
}
