/**
 * T3-03 — voice-chunk upload ordering.
 *
 * Guards two bugs that only appear when the network is slower than the 1 s
 * MediaRecorder timeslice (docs/sprints/2026-08_tier3_structural/02-webchat-voice-spec.md):
 *
 *   1. Chunks fired concurrently => chunk 1 is built before chunk 0's response has
 *      minted the upload_id => 400 => the whole recording is aborted and discarded.
 *   2. A mid-recording 409 was swallowed as "late chunk" => the chunk is lost, every
 *      later chunk 409s, and completion still succeeds => a silently truncated note.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  FakeMediaRecorder,
  deferred,
  makeButton,
  makeFakeServer,
  makeMediaDevices,
} from "./voiceHarness.js";

/** Long enough to burn every retry (800 ms + 1600 ms backoff) and settle the chain. */
const SETTLE_MS = 10_000;

let server;
let button;
let statuses;
let uploadErrors;
let uploadCompletions;

async function startRecording() {
  const { initVoiceNote } = await import("../voiceNote.js");
  initVoiceNote({
    button,
    onStatus: (status) => statuses.push(status),
    onTick: () => {},
    onUploadComplete: (result) => uploadCompletions.push(result),
    onUploadError: (error) => uploadErrors.push(error),
    getUploadContext: () => ({ grievanceId: "GRV-1", complainantId: "CMP-1" }),
  });
  await button.click();
  return FakeMediaRecorder.instances.at(-1);
}

/** Advance fake timers and flush the promise chain they unblock. */
async function settle(ms = SETTLE_MS) {
  await vi.advanceTimersByTimeAsync(ms);
}

/**
 * Stop, then settle. The click must not be awaited before the timers advance:
 * stopRecording joins the pending uploads, whose retry backoff is a fake timer, so
 * awaiting it first would deadlock the test rather than the code.
 */
async function stopAndSettle() {
  const stopped = button.click();
  await settle();
  await stopped;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetModules();
  FakeMediaRecorder.reset();

  server = makeFakeServer();
  button = makeButton();
  statuses = [];
  uploadErrors = [];
  uploadCompletions = [];

  vi.stubGlobal("fetch", (url, init) => server.fetchImpl(url, init));
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  vi.stubGlobal("navigator", { mediaDevices: makeMediaDevices() });
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("the slow-network race", () => {
  it("carries an upload_id on every chunk after 0 even when chunk 0's response is slow", async () => {
    // Chunk 0's response is held open past the point where chunks 1 and 2 are produced —
    // i.e. RTT > CHUNK_TIMESLICE_MS. This is the exact production condition on 2G/3G.
    const chunkZeroResponse = deferred();
    server.hooks.beforeChunk = async (record) => {
      if (record.chunkIndex === 0) await chunkZeroResponse.promise;
      return null;
    };

    const recorder = await startRecording();
    recorder.emitChunk(); // t=1s
    recorder.emitChunk(); // t=2s — pre-fix this is already in flight, id-less
    recorder.emitChunk(); // t=3s
    await settle();

    chunkZeroResponse.resolve();
    await settle();

    const laterChunks = server.requests.filter((r) => r.chunkIndex > 0);
    expect(laterChunks.length).toBeGreaterThan(0);
    expect(laterChunks.every((r) => r.uploadId !== null)).toBe(true);
    expect(server.requests.filter((r) => r.status === 400)).toEqual([]);
    expect(statuses).not.toContain("upload_error");
  });

  it("uploads one chunk at a time, in index order", async () => {
    server.hooks.beforeChunk = async (record) => {
      // Hold every chunk briefly so overlapping uploads would be observable.
      if (record.chunkIndex >= 0) await new Promise((resolve) => setTimeout(resolve, 50));
      return null;
    };

    const recorder = await startRecording();
    recorder.emitChunk();
    recorder.emitChunk();
    recorder.emitChunk();
    await settle();

    expect(server.requests.map((r) => r.chunkIndex)).toEqual([0, 1, 2]);
    expect(server.maxConcurrent).toBe(1);
  });
});

describe("the silent-truncation guard", () => {
  it("surfaces a mid-recording 409 instead of swallowing it", async () => {
    // A 409 that exhausts its retries mid-recording means the server's .part file is
    // permanently behind: the note would complete, shorter than the user recorded.
    server.hooks.beforeChunk = async (record) =>
      record.chunkIndex === 1 ? { status: 409, body: { error: "Chunk received out of order" } } : null;

    const recorder = await startRecording();
    recorder.emitChunk(); // 0 — ok
    await settle(100);
    recorder.emitChunk(); // 1 — 409 x3
    await settle();

    expect(statuses).toContain("upload_error");
    expect(server.completed).toEqual([]);
  });

  it("still ignores a late 409 after stop", async () => {
    // The legitimate case the swallow exists for: MediaRecorder flushes a final chunk
    // as it stops, and that one racing the finalize is not worth an error.
    const recorder = await startRecording();
    recorder.finalChunkOnStop = true;
    recorder.emitChunk(); // 0 — ok
    await settle(100);

    server.hooks.beforeChunk = async () => ({
      status: 409,
      body: { error: "Chunk received out of order" },
    });

    await stopAndSettle();

    expect(statuses).not.toContain("upload_error");
    expect(uploadErrors).toEqual([]);
    expect(uploadCompletions).toHaveLength(1);
  });
});

describe("fast network (no regression)", () => {
  it("uploads and completes a 3-chunk recording unchanged", async () => {
    const recorder = await startRecording();
    recorder.emitChunk();
    await settle(10);
    recorder.emitChunk();
    await settle(10);
    recorder.emitChunk();
    await settle(10);

    await stopAndSettle();

    expect(server.requests.map((r) => r.chunkIndex)).toEqual([0, 1, 2]);
    expect(server.requests.every((r) => r.status === 200)).toBe(true);
    expect(server.completed).toEqual([{ uploadId: "upload-1", chunks: 3 }]);
    expect(uploadCompletions).toHaveLength(1);
    expect(statuses).toContain("stopped");
    expect(statuses).not.toContain("upload_error");
  });
});
