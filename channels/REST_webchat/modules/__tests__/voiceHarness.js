/**
 * Shared fakes for the voice-note upload tests (T3-03).
 *
 * `makeFakeServer` mirrors the real contract of `POST /upload-voice-chunk`
 * (backend/api/routers/files.py:390-482 → backend/services/file_server_core.py:302-333)
 * closely enough that a client bug shows up here the way it shows up in production:
 *
 *   - no upload_id + chunk_index !== 0  -> 400 "upload_id required for chunk_index > 0"
 *   - no upload_id + chunk_index === 0  -> mints and returns a new upload_id
 *   - chunk_index < next                -> 200 {duplicate: true}   (retry-safe)
 *   - chunk_index > next                -> 409 "Chunk received out of order"
 *
 * Tests drive latency and injected failures through `hooks.beforeChunk`; they never
 * reach for wall-clock time, so the ordering assertions are deterministic.
 */

export function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

export function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (name) => (name.toLowerCase() === "content-type" ? "application/json" : null),
    },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

export function makeFakeServer() {
  const sessions = new Map();
  const requests = [];
  const completed = [];
  const hooks = { beforeChunk: null };
  let idCounter = 0;
  let inFlight = 0;
  let maxConcurrent = 0;

  async function routeChunk(record, formData) {
    if (hooks.beforeChunk) {
      const injected = await hooks.beforeChunk(record, formData);
      if (injected) return injected;
    }

    let uploadId = record.uploadId;
    if (!uploadId) {
      if (record.chunkIndex !== 0) {
        return { status: 400, body: { error: "upload_id required for chunk_index > 0" } };
      }
      idCounter += 1;
      uploadId = `upload-${idCounter}`;
      sessions.set(uploadId, { next: 0 });
    }

    const session = sessions.get(uploadId);
    if (!session) {
      return { status: 404, body: { error: "Upload session expired or not found" } };
    }
    if (record.chunkIndex < session.next) {
      return {
        status: 200,
        body: { status: "success", upload_id: uploadId, duplicate: true, chunks_received: session.next },
      };
    }
    if (record.chunkIndex > session.next) {
      return { status: 409, body: { error: "Chunk received out of order" } };
    }

    session.next += 1;
    return {
      status: 200,
      body: { status: "success", upload_id: uploadId, duplicate: false, chunks_received: session.next },
    };
  }

  async function handleChunk(formData) {
    const record = {
      chunkIndex: Number(formData.get("chunk_index")),
      uploadId: formData.get("upload_id") ?? null,
      status: null,
    };
    requests.push(record);
    const result = await routeChunk(record, formData);
    record.status = result.status;
    return result;
  }

  async function handleComplete(formData) {
    const uploadId = formData.get("upload_id");
    const session = sessions.get(uploadId);
    if (!session) {
      return { status: 404, body: { error: "Upload session expired or not found" } };
    }
    completed.push({ uploadId, chunks: session.next });
    return {
      status: 200,
      body: { status: "success", file_id: "file-1", chunks_received: session.next },
    };
  }

  async function fetchImpl(url, init) {
    inFlight += 1;
    maxConcurrent = Math.max(maxConcurrent, inFlight);
    try {
      let result;
      if (url === "/upload-voice-chunk") {
        result = await handleChunk(init.body);
      } else if (url === "/upload-voice-complete") {
        result = await handleComplete(init.body);
      } else {
        throw new Error(`unexpected url in test: ${url}`);
      }
      return jsonResponse(result.status, result.body);
    } finally {
      inFlight -= 1;
    }
  }

  return {
    fetchImpl,
    hooks,
    requests,
    completed,
    get maxConcurrent() {
      return maxConcurrent;
    },
  };
}

export class FakeMediaRecorder {
  static instances = [];

  static isTypeSupported() {
    return true;
  }

  static reset() {
    FakeMediaRecorder.instances = [];
  }

  constructor(stream, options) {
    this.stream = stream;
    this.mimeType = options?.mimeType;
    this.state = "inactive";
    this.ondataavailable = null;
    this.onstop = null;
    /** Real MediaRecorder flushes a final dataavailable when stopped; opt in per test. */
    this.finalChunkOnStop = false;
    this._listeners = new Map();
    FakeMediaRecorder.instances.push(this);
  }

  start() {
    this.state = "recording";
  }

  stop() {
    if (this.finalChunkOnStop) this.emitChunk();
    this.state = "inactive";
    this.onstop?.();
    for (const fn of this._listeners.get("stop") ?? []) fn();
  }

  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }

  emitChunk(bytes = 1024) {
    this.ondataavailable?.({ data: new Blob([new Uint8Array(bytes)]) });
  }
}

export function makeButton() {
  const handlers = new Map();
  return {
    disabled: false,
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {},
    addEventListener(type, fn) {
      handlers.set(type, fn);
    },
    async click() {
      await handlers.get("click")?.({ preventDefault() {} });
    },
  };
}

export function makeMediaDevices() {
  return {
    getUserMedia: async () => ({
      getTracks: () => [{ stop() {} }],
    }),
  };
}
