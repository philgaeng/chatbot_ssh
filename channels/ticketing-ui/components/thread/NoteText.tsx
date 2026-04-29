"use client";

/** Renders note text with @mention tokens highlighted in blue. */
export function NoteText({ text }: { text: string }) {
  const parts = text.split(/(@[\w][\w.-]*)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("@")
          ? <span key={i} className="font-semibold text-blue-600">{part}</span>
          : <span key={i}>{part}</span>
      )}
    </>
  );
}
