"use client";

import { useEffect, useState } from "react";
import { Download, Loader2, X } from "lucide-react";
import { AuthenticatedAudioPlayer } from "@/components/AudioPlayer";
import {
  filterAudioAttachments,
  isAudioFile,
  isImageFile,
  type AttachmentLike,
} from "@/lib/attachments";
import type { OfficerAttachment, TicketFile } from "@/lib/api";
import {
  fetchAuthenticatedBlobUrl,
  openAuthenticatedAttachment,
} from "@/lib/api";
import { IconFileImage, IconFileOther, IconFilePdf } from "@/lib/icons";

function FileIcon({ file }: { file: AttachmentLike }) {
  if (isImageFile(file)) return <IconFileImage size={13} strokeWidth={2} className="shrink-0" />;
  if ((file.file_type ?? "").toLowerCase() === "pdf") return <IconFilePdf size={13} strokeWidth={2} className="shrink-0" />;
  return <IconFileOther size={13} strokeWidth={2} className="shrink-0" />;
}

function fmt(bytes: number) {
  return bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function AttachmentListSection({
  complainantFiles,
  officerFiles,
  complainantFilePath,
  officerFilePath,
  onBeforeDownload,
  compact = false,
}: {
  complainantFiles: TicketFile[];
  officerFiles: OfficerAttachment[];
  complainantFilePath: (fileId: string) => string;
  officerFilePath: (fileId: string) => string;
  onOpenComplainantFile?: (fileId: string, fileName: string) => Promise<void>;
  onOpenOfficerFile?: (fileId: string, fileName: string) => Promise<void>;
  onBeforeDownload?: () => Promise<void>;
  compact?: boolean;
}) {
  const audioItems = filterAudioAttachments(complainantFiles, officerFiles);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ src: string; name: string } | null>(null);

  useEffect(() => {
    return () => {
      if (preview?.src) URL.revokeObjectURL(preview.src);
    };
  }, [preview]);

  async function handleOpen(file: AttachmentLike, source: "complainant" | "officer") {
    const path =
      source === "complainant"
        ? complainantFilePath(file.file_id)
        : officerFilePath(file.file_id);

    setFileError(null);
    setLoadingId(file.file_id);

    const previewWindow =
      /\.pdf$/i.test(file.file_name) ? window.open("about:blank", "_blank") : null;

    try {
      await onBeforeDownload?.();
      if (isImageFile(file)) {
        const blobUrl = await fetchAuthenticatedBlobUrl(path);
        previewWindow?.close();
        setPreview({ src: blobUrl, name: file.file_name });
        return;
      }
      await openAuthenticatedAttachment(path, file.file_name, { previewWindow });
    } catch (err: unknown) {
      previewWindow?.close();
      const message = err instanceof Error ? err.message : "Could not open file";
      setFileError(message);
    } finally {
      setLoadingId(null);
    }
  }

  function closePreview() {
    setPreview((current) => {
      if (current?.src) URL.revokeObjectURL(current.src);
      return null;
    });
  }

  const renderFileRow = (
    file: AttachmentLike,
    source: "complainant" | "officer",
  ) => {
    const path =
      source === "complainant"
        ? complainantFilePath(file.file_id)
        : officerFilePath(file.file_id);
    const isLoading = loadingId === file.file_id;

    if (isAudioFile(file)) {
      return (
        <AuthenticatedAudioPlayer
          key={file.file_id}
          path={path}
          fileName={file.file_name}
          className={compact ? "mb-2" : "mb-2"}
        />
      );
    }
    return (
      <button
        key={file.file_id}
        type="button"
        disabled={isLoading}
        onClick={() => handleOpen(file, source)}
        className={`flex items-center gap-2 text-xs text-blue-600 hover:text-blue-800 disabled:opacity-60 group w-full text-left ${compact ? "mb-2 px-1" : "mb-1"}`}
      >
        <FileIcon file={file} />
        <span className="flex-1 truncate group-hover:underline">{file.file_name}</span>
        <span className="text-gray-400 shrink-0">{fmt(file.file_size)}</span>
        {isLoading ? (
          <Loader2 size={12} className="text-gray-400 shrink-0 animate-spin" />
        ) : (
          <Download size={12} className="text-gray-300 shrink-0 opacity-0 group-hover:opacity-100" />
        )}
      </button>
    );
  };

  if (complainantFiles.length === 0 && officerFiles.length === 0 && audioItems.length === 0) {
    return null;
  }

  return (
    <>
      {fileError && (
        <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {fileError}
        </div>
      )}

      <div className={compact ? "space-y-3" : "space-y-4"}>
        {audioItems.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-600 mb-1.5">Voice notes</div>
            {audioItems.map(({ file, source }) => renderFileRow(file, source))}
          </div>
        )}

        {complainantFiles.filter((f) => !isAudioFile(f)).length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-600 mb-1.5">From complainant</div>
            {complainantFiles.filter((f) => !isAudioFile(f)).map((f) =>
              renderFileRow(f, "complainant"),
            )}
          </div>
        )}

        {officerFiles.filter((f) => !isAudioFile(f)).length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-600 mb-1.5">Officer attachments</div>
            {officerFiles.filter((f) => !isAudioFile(f)).map((f) =>
              renderFileRow(f, "officer"),
            )}
          </div>
        )}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={preview.name}
          onClick={closePreview}
        >
          <button
            type="button"
            onClick={closePreview}
            className="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
            aria-label="Close preview"
          >
            <X size={20} />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview.src}
            alt={preview.name}
            className="max-h-[90vh] max-w-full rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}
