"use client";

interface AudioPlayerProps {
  src: string;
  fileName: string;
  className?: string;
}

/** Inline audio playback for ticket attachments (TP-01). */
export function AudioPlayer({ src, fileName, className = "" }: AudioPlayerProps) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 ${className}`}>
      <div className="text-xs text-gray-600 truncate mb-1.5" title={fileName}>
        {fileName}
      </div>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <audio controls preload="metadata" className="w-full h-9" src={src}>
        Your browser does not support audio playback.
      </audio>
    </div>
  );
}
