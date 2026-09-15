// SPDX-License-Identifier: Apache-2.0

/**
 * Read the text cells of a downloaded .xlsx — enough to assert a workbook's headers without adding a
 * spreadsheet library to the portal's dependencies for one test (GRM-118).
 *
 * An .xlsx is a ZIP archive. Cell text lives in one of two places: `xl/sharedStrings.xml`, or inline in
 * each worksheet (`<is><t>…</t></is>`). ⚠ Measured 2026-09-15: this export has **no** sharedStrings
 * part at all — the writer puts every string inline — so reading only shared strings found nothing.
 * This walks the archive's central directory (not the local headers, whose sizes a streaming writer
 * may leave as zero) and inflates both kinds of part.
 */
import { inflateRawSync } from "node:zlib";

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;

function entries(buf: Buffer, wanted: (name: string) => boolean): Buffer[] {
  const out: Buffer[] = [];
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 0xffff); i--) {
    if (buf.readUInt32LE(i) === EOCD_SIGNATURE) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a ZIP archive: no end-of-central-directory record");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(p) !== CENTRAL_SIGNATURE) throw new Error("corrupt central directory");
    const method = buf.readUInt16LE(p + 10);
    const compressed = buf.readUInt32LE(p + 20);
    const nameLen = buf.readUInt16LE(p + 28);
    const extraLen = buf.readUInt16LE(p + 30);
    const commentLen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf8", p + 46, p + 46 + nameLen);
    if (wanted(name)) {
      const dataStart = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
      const data = buf.subarray(dataStart, dataStart + compressed);
      out.push(method === 0 ? data : inflateRawSync(data));
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  return out;
}

/** Every text cell in the workbook — shared or inline, all sheets — XML entities decoded. */
export function workbookStrings(xlsx: Buffer): string[] {
  const parts = entries(xlsx, (n) => n === "xl/sharedStrings.xml" || /^xl\/worksheets\/[^/]+\.xml$/.test(n));
  const xml = parts.map((b) => b.toString("utf8")).join("\n");
  return [...xml.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((m) =>
    m[1].replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&"),
  );
}
