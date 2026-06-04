/** CB-08: lightweight EXIF extraction for image uploads (browser). */

const EXIF_CONSENT_KEY = "grm_photo_exif_consent";

export function hasExifConsent() {
  return sessionStorage.getItem(EXIF_CONSENT_KEY) === "granted";
}

export function setExifConsent(granted) {
  sessionStorage.setItem(EXIF_CONSENT_KEY, granted ? "granted" : "denied");
}

export async function ensureExifConsent(promptFn) {
  if (sessionStorage.getItem(EXIF_CONSENT_KEY)) {
    return hasExifConsent();
  }
  return promptFn();
}

export async function extractImageMetadata(file) {
  if (!hasExifConsent() || !file || !file.type?.startsWith("image/")) {
    return null;
  }
  const exifr = globalThis.exifr;
  if (!exifr?.gps) {
    return null;
  }
  try {
    const gps = await exifr.gps(file);
    const date = await exifr.parse(file, { pick: ["DateTimeOriginal", "CreateDate"] });
    const captured =
      date?.DateTimeOriginal || date?.CreateDate || null;
    if (!gps && !captured) return null;
    const meta = { file_name: file.name };
    if (gps?.latitude != null) meta.lat = gps.latitude;
    if (gps?.longitude != null) meta.lng = gps.longitude;
    if (gps?.altitude != null) meta.altitude = gps.altitude;
    if (captured) {
      meta.captured_at =
        captured instanceof Date ? captured.toISOString() : String(captured);
    }
    return meta;
  } catch {
    return null;
  }
}

export async function buildFileMetadataList(files, consentPrompt) {
  const imageFiles = Array.from(files).filter((f) =>
    f.type?.startsWith("image/")
  );
  if (!imageFiles.length) return [];
  const allowed = await ensureExifConsent(consentPrompt);
  if (!allowed) return [];
  const out = [];
  for (const file of imageFiles) {
    const meta = await extractImageMetadata(file);
    if (meta) out.push(meta);
  }
  return out;
}
