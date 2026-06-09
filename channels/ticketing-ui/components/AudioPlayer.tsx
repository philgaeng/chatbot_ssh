"use client";

import { useEffect, useState } from "react";
import { fetchAuthenticatedBlobUrl } from "@/lib/api";

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

/** Audio player that loads a protected API path with Bearer auth. */
export function AuthenticatedAudioPlayer({
  path,
  fileName,
  className = "",
}: {
  path: string;
  fileName: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let blobUrl: string | null = null;
    let cancelled = false;
    fetchAuthenticatedBlobUrl(path)
      .then((url) => {
        if (!cancelled) {
          blobUrl = url;
          setSrc(url);
        } else {
          URL.revokeObjectURL(url);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load audio");
        }
      });
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [path]);

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 ${className}`}>
        {fileName}: {error}
      </div>
    );
  }
  if (!src) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-500 ${className}`}>
        Loading {fileName}…
      </div>
    );
  }
  return <AudioPlayer src={src} fileName={fileName} className={className} />;
}
