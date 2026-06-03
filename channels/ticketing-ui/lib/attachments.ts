import type { OfficerAttachment, TicketFile } from "@/lib/api";

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"]);
const AUDIO_EXTENSIONS = new Set([".m4a", ".mp3", ".wav", ".aac", ".webm", ".ogg", ".opus", ".amr"]);

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export function isImageFile(file: { file_type?: string | null; file_name?: string }): boolean {
  const t = (file.file_type ?? "").toLowerCase();
  if (t === "image" || t.startsWith("image/")) return true;
  const ext = extOf(file.file_name ?? "");
  return IMAGE_EXTENSIONS.has(ext);
}

export function isAudioFile(file: { file_type?: string | null; file_name?: string }): boolean {
  const t = (file.file_type ?? "").toLowerCase();
  if (t === "audio" || t.startsWith("audio/")) return true;
  const ext = extOf(file.file_name ?? "");
  return AUDIO_EXTENSIONS.has(ext);
}

export function hasImageAttachment(
  complainantFiles: TicketFile[],
  officerFiles: OfficerAttachment[],
): boolean {
  return (
    complainantFiles.some(isImageFile) ||
    officerFiles.some(isImageFile)
  );
}

export type AttachmentLike = TicketFile | OfficerAttachment;

export function mergeAttachments(
  complainantFiles: TicketFile[],
  officerFiles: OfficerAttachment[],
): { source: "complainant" | "officer"; file: AttachmentLike }[] {
  return [
    ...complainantFiles.map((file) => ({ source: "complainant" as const, file })),
    ...officerFiles.map((file) => ({ source: "officer" as const, file })),
  ];
}

export function filterAudioAttachments(
  complainantFiles: TicketFile[],
  officerFiles: OfficerAttachment[],
): { source: "complainant" | "officer"; file: AttachmentLike }[] {
  return mergeAttachments(complainantFiles, officerFiles).filter(({ file }) => isAudioFile(file));
}
