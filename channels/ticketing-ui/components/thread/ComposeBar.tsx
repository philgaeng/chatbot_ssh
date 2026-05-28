"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Paperclip, Mic, Send } from "lucide-react";
import { HASH_COMMANDS, type HashCommand } from "@/lib/mobile-constants";
import { FIELD_WORK_AMBER, INSPECT_SELF_MENTION } from "@/lib/field-visit";
import { TaskTypeIcon } from "@/lib/icons";

const MENTION_QUERY_REGEX = /@([A-Za-z0-9._@-]*)$/;
const MENTION_REPLACE_REGEX = /@[A-Za-z0-9._@-]*$/;
const HASH_QUERY_REGEX = /#([\w]*)$/;

export interface MentionParticipant {
  user_id: string;
  label: string;
}

export interface ComposeBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onAttach?: () => void;
  onFileSelected?: (file: File) => void;
  attachUploading?: boolean;
  onHashCommand?: (cmd: HashCommand) => void;
  fieldReportOpen?: boolean;
  disabled?: boolean;
  participants?: MentionParticipant[];
  placeholder?: string;
  className?: string;
}

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

function hashCmdRowClass(cmd: HashCommand): string {
  if (cmd.kind === "report" || cmd.kind === "task_assign") {
    return FIELD_WORK_AMBER.paletteRow;
  }
  if (cmd.kind === "action") return "text-amber-700 hover:bg-amber-50";
  return "text-gray-700 hover:bg-blue-50";
}

function hashCmdIconClass(cmd: HashCommand): string {
  if (cmd.kind === "report" || cmd.kind === "task_assign") {
    return `${FIELD_WORK_AMBER.paletteIcon} shrink-0`;
  }
  if (cmd.kind === "task") return "text-blue-400 shrink-0";
  return "shrink-0 opacity-80";
}

export function ComposeBar({
  value,
  onChange,
  onSubmit,
  onAttach,
  onFileSelected,
  attachUploading = false,
  onHashCommand,
  fieldReportOpen = false,
  disabled,
  participants = [],
  placeholder,
  className = "",
}: ComposeBarProps) {
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [hashQuery, setHashQuery] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAttachClick = useCallback(() => {
    if (onFileSelected) {
      fileInputRef.current?.click();
      return;
    }
    onAttach?.();
  }, [onAttach, onFileSelected]);

  const resolvedPlaceholder = placeholder ?? "Add a note… (@ to mention · # for commands)";

  const handleChange = useCallback((v: string) => {
    onChange(v);
    const mentionMatch = v.match(MENTION_QUERY_REGEX);
    const hashMatch = v.match(HASH_QUERY_REGEX);
    setMentionQuery(mentionMatch ? mentionMatch[1] : null);
    setHashQuery(hashMatch ? hashMatch[1] : null);
  }, [onChange]);

  useEffect(() => {
    const mentionMatch = value.match(MENTION_QUERY_REGEX);
    const hashMatch = value.match(HASH_QUERY_REGEX);
    setMentionQuery(mentionMatch ? mentionMatch[1] : null);
    setHashQuery(hashMatch ? hashMatch[1] : null);
  }, [value]);

  const insertMention = useCallback((userId: string) => {
    onChange(value.replace(MENTION_REPLACE_REGEX, `@${userId} `));
    setMentionQuery(null);
    textareaRef.current?.focus();
  }, [value, onChange]);

  const selectHashCmd = useCallback((cmd: HashCommand) => {
    setHashQuery(null);
    if (cmd.kind === "assign") {
      onChange("#assign @");
      setMentionQuery("");
      textareaRef.current?.focus();
      onHashCommand?.(cmd);
      return;
    }
    if (cmd.kind === "task_assign") {
      onChange(`#${cmd.hash} ${INSPECT_SELF_MENTION}`);
      setMentionQuery(null);
      textareaRef.current?.focus();
      onHashCommand?.(cmd);
      return;
    }
    onChange("");
    onHashCommand?.(cmd);
  }, [onChange, onHashCommand]);

  const filteredMentions = mentionQuery !== null
    ? participants.filter((p) => !mentionQuery || p.user_id.toLowerCase().includes(mentionQuery.toLowerCase())).slice(0, 6)
    : [];

  const filteredHash = hashQuery !== null
    ? HASH_COMMANDS.filter((c) => !hashQuery || c.hash.startsWith(hashQuery.toLowerCase()))
    : [];

  const fieldWorkCmds = filteredHash.filter((c) => c.kind === "report" || c.kind === "task_assign");
  const taskCmds = filteredHash.filter((c) => c.kind === "task");
  const actionCmds = filteredHash.filter((c) => c.kind === "action" || c.kind === "assign");
  const hasText = value.trim().length > 0;

  const renderHashRow = (cmd: HashCommand) => (
    <button
      key={cmd.hash}
      type="button"
      onMouseDown={(e) => { e.preventDefault(); selectHashCmd(cmd); }}
      className={`w-full flex items-center gap-3 px-3 py-2 text-sm ${hashCmdRowClass(cmd)}`}
    >
      <HashCmdIcon name={cmd.icon} size={15} strokeWidth={2} className={hashCmdIconClass(cmd)} />
      <span className="flex-1 text-left">{cmd.label}</span>
      <span className="text-[11px] text-gray-300 font-mono">#{cmd.hash}</span>
    </button>
  );

  return (
    <div className={`flex items-end gap-2 px-3 py-2 ${className}`}>
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file && onFileSelected) onFileSelected(file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={handleAttachClick}
        disabled={attachUploading || (!onFileSelected && !onAttach)}
        tabIndex={-1}
        className="w-9 h-9 flex items-center justify-center text-gray-400 active:text-blue-500 hover:text-blue-500 rounded-full active:bg-gray-100 hover:bg-gray-100 flex-shrink-0 mb-0.5 disabled:opacity-40"
        aria-label="Attach file"
      >
        <Paperclip size={20} strokeWidth={2} />
      </button>

      <div className="relative flex-1">
        {mentionQuery !== null && (
          <div className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20">
            {filteredMentions.length > 0
              ? filteredMentions.map((p) => (
                  <button
                    key={p.user_id}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); insertMention(p.user_id); }}
                    className="w-full text-left px-4 py-2.5 text-sm text-gray-700 hover:bg-blue-50 border-b border-gray-100 last:border-0"
                  >
                    <span className="font-medium text-blue-600">{p.label}</span>
                  </button>
                ))
              : <div className="px-4 py-2.5 text-xs text-gray-400">No participants match</div>}
          </div>
        )}

        {filteredHash.length > 0 && (
          <div className="absolute bottom-full mb-1 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20">
            {fieldWorkCmds.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-amber-700/90 uppercase tracking-wide">
                  Field & inspection
                </div>
                {fieldWorkCmds.map(renderHashRow)}
              </>
            )}
            {fieldWorkCmds.length > 0 && taskCmds.length > 0 && (
              <div className="border-t border-gray-100" />
            )}
            {taskCmds.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                  Assign task to yourself
                </div>
                {taskCmds.map(renderHashRow)}
              </>
            )}
            {(fieldWorkCmds.length > 0 || taskCmds.length > 0) && actionCmds.length > 0 && (
              <div className="border-t border-gray-100" />
            )}
            {actionCmds.length > 0 && (
              <>
                <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                  Actions
                </div>
                {actionCmds.map(renderHashRow)}
              </>
            )}
          </div>
        )}

        <div className={`rounded-2xl px-4 py-2.5 min-h-[44px] flex items-center transition-colors bg-gray-100 ${
          fieldReportOpen ? "opacity-60" : ""
        }`}>
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={resolvedPlaceholder}
            rows={1}
            className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none"
            style={{ maxHeight: "120px" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setMentionQuery(null);
                setHashQuery(null);
                return;
              }
              if (e.key === "Enter" && !e.shiftKey) {
                if (mentionQuery !== null && filteredMentions.length > 0) {
                  e.preventDefault();
                  insertMention(filteredMentions[0].user_id);
                  return;
                }
                if (hashQuery !== null && filteredHash.length > 0) {
                  e.preventDefault();
                  selectHashCmd(filteredHash[0]);
                  return;
                }
                e.preventDefault();
                onSubmit();
              }
            }}
          />
        </div>
      </div>

      {hasText ? (
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled}
          className="w-10 h-10 rounded-full flex items-center justify-center text-white flex-shrink-0 transition-colors bg-blue-600 active:bg-blue-700"
          aria-label="Send"
        >
          <Send size={18} strokeWidth={2} />
        </button>
      ) : (
        <button
          type="button"
          disabled
          tabIndex={-1}
          className="w-10 h-10 rounded-full flex items-center justify-center text-gray-400 flex-shrink-0"
          aria-label="Voice note (coming soon)"
        >
          <Mic size={20} strokeWidth={2} />
        </button>
      )}
    </div>
  );
}
