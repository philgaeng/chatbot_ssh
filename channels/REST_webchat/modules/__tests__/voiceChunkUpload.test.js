/**
 * T3-03 — the retry must re-read the upload_id, not resend a frozen body.
 *
 * Precedent: H2-01 / apifetch-refresh-non-json-sites in the portal, where multipart
 * bodies are rebuilt inside the thunk so a retry re-sends them
 * (channels/ticketing-ui/lib/api.ts → authedFetch). Same bug shape: a frozen body
 * re-sent by a retry that cannot pick up state which landed in the meantime.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse } from "./voiceHarness.js";

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetModules();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("uploadVoiceChunk", () => {
  it("re-reads the upload_id on retry rather than resending an id-less body", async () => {
    let uploadId = null;
    const sentIds = [];

    vi.stubGlobal("fetch", async (_url, init) => {
      sentIds.push(init.body.get("upload_id"));
      if (sentIds.length === 1) {
        // The id lands between attempt 1 and attempt 2 — exactly what happens when
        // chunk 0's response returns while chunk 1 is already backing off.
        uploadId = "upload-42";
        return jsonResponse(400, { error: "upload_id required for chunk_index > 0" });
      }
      return jsonResponse(200, { status: "success", upload_id: "upload-42" });
    });

    const { uploadVoiceChunk } = await import("../voiceChunkUpload.js");
    const pending = uploadVoiceChunk({
      getUploadId: () => uploadId,
      chunkIndex: 1,
      blob: new Blob([new Uint8Array(8)]),
    });
    await vi.advanceTimersByTimeAsync(5_000);

    await expect(pending).resolves.toMatchObject({ status: "success" });
    expect(sentIds).toEqual([null, "upload-42"]);
  });

  it("gives up after exhausting retries and surfaces the server status", async () => {
    vi.stubGlobal("fetch", async () =>
      jsonResponse(409, { error: "Chunk received out of order" })
    );

    const { uploadVoiceChunk } = await import("../voiceChunkUpload.js");
    const pending = uploadVoiceChunk({
      getUploadId: () => "upload-1",
      chunkIndex: 2,
      blob: new Blob([new Uint8Array(8)]),
    });
    const assertion = expect(pending).rejects.toMatchObject({ status: 409 });
    await vi.advanceTimersByTimeAsync(5_000);
    await assertion;
  });
});
