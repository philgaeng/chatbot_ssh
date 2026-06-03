"use client";

import { Download } from "lucide-react";
import { AudioPlayer } from "@/components/AudioPlayer";
import {
  filterAudioAttachments,
  isAudioFile,
  isImageFile,
  type AttachmentLike,
} from "@/lib/attachments";
import type { OfficerAttachment, TicketFile } from "@/lib/api";
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
  getComplainantUrl,
  getOfficerUrl,
  onBeforeDownload,
  compact = false,
}: {
  complainantFiles: TicketFile[];
  officerFiles: OfficerAttachment[];
  getComplainantUrl: (fileId: string) => string;
  getOfficerUrl: (fileId: string) => string;
  onBeforeDownload?: () => Promise<void>;
  compact?: boolean;
}) {
  const audioItems = filterAudioAttachments(complainantFiles, officerFiles);

  const renderFileRow = (
    file: AttachmentLike,
    source: "complainant" | "officer",
    url: string,
  ) => {
    if (isAudioFile(file)) {
      return (
        <AudioPlayer
          key={file.file_id}
          src={url}
          fileName={file.file_name}
          className={compact ? "mb-2" : "mb-2"}
        />
      );
    }
    return (
      <button
        key={file.file_id}
        type="button"
        onClick={async () => {
          await onBeforeDownload?.();
          window.open(url, "_blank", "noopener,noreferrer");
        }}
        className={`flex items-center gap-2 text-xs text-blue-600 hover:text-blue-800 group w-full text-left ${compact ? "mb-2 px-1" : "mb-1"}`}
      >
        <FileIcon file={file} />
        <span className="flex-1 truncate group-hover:underline">{file.file_name}</span>
        <span className="text-gray-400 shrink-0">{fmt(file.file_size)}</span>
        <Download size={12} className="text-gray-300 shrink-0 opacity-0 group-hover:opacity-100" />
      </button>
    );
  };

  if (complainantFiles.length === 0 && officerFiles.length === 0 && audioItems.length === 0) {
    return null;
  }

  return (
    <div className={compact ? "space-y-3" : "space-y-4"}>
      {audioItems.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-1.5">Voice notes</div>
          {audioItems.map(({ file, source }) =>
            renderFileRow(
              file,
              source,
              source === "complainant"
                ? getComplainantUrl(file.file_id)
                : getOfficerUrl(file.file_id),
            ),
          )}
        </div>
      )}

      {complainantFiles.filter((f) => !isAudioFile(f)).length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-1.5">From complainant</div>
          {complainantFiles.filter((f) => !isAudioFile(f)).map((f) =>
            renderFileRow(f, "complainant", getComplainantUrl(f.file_id)),
          )}
        </div>
      )}

      {officerFiles.filter((f) => !isAudioFile(f)).length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-1.5">Officer attachments</div>
          {officerFiles.filter((f) => !isAudioFile(f)).map((f) =>
            renderFileRow(f, "officer", getOfficerUrl(f.file_id)),
          )}
        </div>
      )}
    </div>
  );
}
