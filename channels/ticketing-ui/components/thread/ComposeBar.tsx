"use client";

import { useCallback, useRef, useState } from "react";
import { Paperclip, Mic, Send } from "lucide-react";
import { HASH_COMMANDS, type HashCommand } from "@/lib/mobile-constants";
import { TaskTypeIcon } from "@/lib/icons";

export interface MentionParticipant {
  user_id: string;
  label: string;
}

export interface ComposeBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  /** Called when the paperclip button is tapped */
  onAttach?: () => void;
  /** Called when a # command is selected from the palette */
  onHashCommand?: (cmd: HashCommand) => void;
  /** True when compose bar is in field-report mode (amber styling) */
  reportMode?: boolean;
  /** Called to exit report mode (Escape or ✕ chip) */
  onExitReportMode?: () => void;
  disabled?: boolean;
  participants?: MentionParticipant[];
  placeholder?: string;
  className?: string;
}

// Inline SVG for the two action icons not in TaskTypeIcon
function HashCmdIcon({ name, size = 16, strokeWidth = 2, className = "" }: {
  name: string; size?: number; strokeWidth?: number; className?: string;
}) {
  if (name === "ArrowUpCircle") return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
      stroke="currentColor" strokeWidth={strokeWidth} width={size} height={size} className={className}>
      <circle cx="12" cy="12" r="10"/>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16 12-4-4-4 4M12 16V8"/>
    </svg>
  );
  if (name === "UserCheck") return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
      stroke="currentColor" strokeWidth={strokeWidth} width={size} height={size} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
      <circle cx="9" cy="7" r="4"/>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16 11 2 2 4-4"/>
    </svg>
  );
  return <TaskTypeIcon name={name} size={size} strokeWidth={strokeWidth} className={className} />;
}

export function ComposeBar({
  value,
  onChange,
  onSubmit,
  onAttach,
  onHashCommand,
  reportMode = false,
  onExitReportMode,
  disabled,
  participants = [],
  placeholder,
  className = "",
}: ComposeBarProps) {
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [hashQuery,    setHashQuery]    = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const resolvedPlaceholder = placeholder ?? (
    reportMode
      ? "Describe your site findings… (Enter to submit)"
      : "Add a note… (@ to mention · # for commands)"
  );

  // Detect @ and # triggers on every keystroke
  const handleChange = useCallback((v: string) => {
    onChange(v);
    setMentionQuery(v.match(/@([\w.-]*)$/) ? v.match(/@([\w.-]*)$/)![1] : null);
    setHashQuery(   v.match(/#([\w]*)$/)   ? v.match(/#([\w]*)$/)![1]   : null);
  }, [onChange]);

  const insertMention = useCallback((userId: string) => {
    onChange(value.replace(/@[\w.-]*$/, `@${userId} `));
    setMentionQuery(null);
    textareaRef.current?.focus();
  }, [value, onChange]);

  const selectHashCmd = useCallback((cmd: HashCommand) => {
    setHashQuery(null);
    if (cmd.kind === "assign") {
      onChange("#assign @");
      setMentionQuery("");           // open mention popup immediately
      textareaRef.current?.focus();
      onHashCommand?.(cmd);
      return;
    }
    onChange("");
    onHashCommand?.(cmd);           // report / task / action — parent handles
  }, [onChange, onHashCommand]);

  const filteredMentions = mentionQuery !== null
    ? participants.filter((p) => !mentionQuery || p.user_id.toLowerCase().includes(mentionQuery.toLowerCase())).slice(0, 6)
    : [];

  const filteredHash = hashQuery !== null
    ? HASH_COMMANDS.filter((c) => !hashQuery || c.hash.startsWith(hashQuery.toLowerCase()))
    : [];

  const taskCmds   = filteredHash.filter((c) => c.kind === "task");
  const actionCmds = filteredHash.filter((c) => c.kind !== "task");
  const hasText    = value.trim().length > 0;

  return (
    <div className={`flex items-end gap-2 px-3 py-2 ${className}`}>

      {/* Paperclip */}
      <button onClick={onAttach} tabIndex={-1}
        className="w-9 h-9 flex items-center justify-center text-gray-400 active:text-blue-500 rounded-full active:bg-gray-100 flex-shrink-0 mb-0.5"
        aria-label="Attach file">
        <Paperclip size={20} strokeWidth={2} />
      </button>

      {/* Input area */}
      <div className="relative flex-1">

        {/* @mention popup */}
        {mentionQuery !== null && (
          <div className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20">
            {filteredMentions.length > 0
              ? filteredMentions.map((p) => (
                  <button key={p.user_id}
                    onMouseDown={(e) => { e.preventDefault(); insertMention(p.user_id); }}
                    className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-blue-50 border-b border-gray-100 last:border-0">
                    <span className="font-medium text-blue-600">{p.label}</span>
                  </button>
                ))
              : <div className="px-4 py-2.5 text-xs text-gray-400">No participants match</div>
            }
          </div>
        )}

        {/* # command palette */}
        {filteredHash.length > 0 && (
          <div className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20">
            {taskCmds.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                  Assign task to yourself
                </div>
                {taskCmds.map((cmd) => (
                  <button key={cmd.hash}
                    onMouseDown={(e) => { e.preventDefault(); selectHashCmd(cmd); }}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-blue-50">
                    <TaskTypeIcon name={cmd.icon} size={15} strokeWidth={2} className="text-blue-400 shrink-0" />
                    <span className="flex-1 text-left">{cmd.label}</span>
                    <span className="text-[11px] text-gray-300 font-mono">#{cmd.hash}</span>
                  </button>
                ))}
              </>
            )}
            {taskCmds.length > 0 && actionCmds.length > 0 && (
              <div className="border-t border-gray-100" />
            )}
            {actionCmds.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                  Actions
                </div>
                {actionCmds.map((cmd) => (
                  <button key={cmd.hash}
                    onMouseDown={(e) => { e.preventDefault(); selectHashCmd(cmd); }}
                    className={`w-full flex items-center gap-3 px-3 py-2 text-sm ${
                      cmd.kind === "action" ? "text-amber-700 hover:bg-amber-50" :
                      cmd.kind === "report" ? "text-green-700 hover:bg-green-50" :
                                              "text-blue-700 hover:bg-blue-50"
                    }`}>
                    <HashCmdIcon name={cmd.icon} size={15} strokeWidth={2} className="shrink-0 opacity-80" />
                    <span className="flex-1 text-left">{cmd.label}</span>
                    <span className="text-[11px] text-gray-300 font-mono">#{cmd.hash}</span>
                  </button>
                ))}
              </>
            )}
          </div>
        )}

        {/* Report mode badge */}
        {reportMode && (
          <div className="absolute -top-7 left-0 flex items-center gap-1.5">
            <span className="text-[11px] font-semibold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
              📋 Field Report
            </span>
            {onExitReportMode && (
              <button onClick={onExitReportMode} className="text-[11px] text-gray-400 hover:text-gray-600" aria-label="Exit report mode">
                ✕
              </button>
            )}
          </div>
        )}

        {/* Textarea bubble */}
        <div className={`rounded-2xl px-4 py-2.5 min-h-[44px] flex items-center transition-colors ${
          reportMode ? "bg-amber-50 border border-amber-200" : "bg-gray-100"
        }`}>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={resolvedPlaceholder}
            rows={1}
            className={`w-full bg-transparent text-sm placeholder-gray-400 resize-none focus:outline-none ${
              reportMode ? "text-amber-900" : "text-gray-800"
            }`}
            style={{ maxHeight: "120px" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setMentionQuery(null); setHashQuery(null);
                if (reportMode) onExitReportMode?.();
                return;
              }
              if (e.key === "Enter" && !e.shiftKey && mentionQuery === null && hashQuery === null) {
                e.preventDefault(); onSubmit();
              }
            }}
          />
        </div>
      </div>

      {/* Mic / Send toggle */}
      {hasText ? (
        <button onClick={onSubmit} disabled={disabled}
          className={`w-10 h-10 rounded-full flex items-center justify-center text-white flex-shrink-0 transition-colors ${
            reportMode ? "bg-amber-500 active:bg-amber-600" : "bg-blue-600 active:bg-blue-700"
          }`}
          aria-label={reportMode ? "Submit report" : "Send"}>
          <Send size={18} strokeWidth={2} />
        </button>
      ) : (
        <button disabled tabIndex={-1}
          className="w-10 h-10 rounded-full flex items-center justify-center text-gray-400 flex-shrink-0"
          aria-label="Voice note (coming soon)">
          <Mic size={20} strokeWidth={2} />
        </button>
      )}
    </div>
  );
}
