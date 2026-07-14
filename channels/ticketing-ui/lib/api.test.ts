import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the auth seams so we can drive apiFetch's 401 → refresh → retry path
// without a real Keycloak or token. isAccessTokenExpiringSoon=false disables the
// proactive branch; handleSessionExpired throws (mirrors the real `never`).
const refreshTokens = vi.fn<() => Promise<string | null>>();
const handleSessionExpired = vi.fn(() => {
  throw new Error("REDIRECT_LOGIN");
});

vi.mock("./auth/oidc-auth", () => ({ refreshTokens }));
vi.mock("./auth/session-expired", () => ({
  handleSessionExpired,
  isAccessTokenExpiringSoon: () => false,
}));

function ok(json: unknown) {
  return { ok: true, status: 200, json: async () => json, text: async () => JSON.stringify(json) };
}
function unauthorized() {
  return { ok: false, status: 401, json: async () => ({}), text: async () => "not authenticated" };
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  const ls = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
  vi.stubGlobal("window", { localStorage: ls });
  vi.stubGlobal("localStorage", ls);
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch 401 handling (H2-01)", () => {
  it("401 → silent refresh → retries once → succeeds (no logout)", async () => {
    const queue = [unauthorized(), ok([{ code: "dust", label: "Dust" }])];
    fetchMock.mockImplementation(async () => queue.shift());
    refreshTokens.mockResolvedValue("fresh-access-token");

    const { listGrievanceCategories } = await import("./api");
    const result = await listGrievanceCategories();

    expect(result).toEqual([{ code: "dust", label: "Dust" }]);
    expect(refreshTokens).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2); // original + one retry
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });

  it("401 → refresh fails → handleSessionExpired exactly once (no retry)", async () => {
    fetchMock.mockResolvedValue(unauthorized());
    refreshTokens.mockResolvedValue(null);

    const { listGrievanceCategories } = await import("./api");
    await expect(listGrievanceCategories()).rejects.toThrow("REDIRECT_LOGIN");

    expect(refreshTokens).toHaveBeenCalledTimes(1);
    expect(handleSessionExpired).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1); // no retry when refresh yields nothing
  });
});

describe("authedFetch — blob/multipart 401 handling (apifetch-refresh followup)", () => {
  const A_FILE = new File(["x"], "evidence.jpg", { type: "image/jpeg" });

  it("multipart upload: 401 → refresh → retry-once → succeeds, parts re-sent", async () => {
    const bodies: unknown[] = [];
    const queue = [unauthorized(), ok({ file_id: "F1" })];
    fetchMock.mockImplementation(async (_url: string, init: RequestInit) => {
      bodies.push(init.body);
      return queue.shift();
    });
    refreshTokens.mockResolvedValue("fresh-access-token");

    const { uploadOfficerAttachment } = await import("./api");
    const result = await uploadOfficerAttachment("T-1", A_FILE, "at the site");

    expect(result).toEqual({ file_id: "F1" });
    expect(refreshTokens).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2); // original + one retry
    expect(handleSessionExpired).not.toHaveBeenCalled();
    // The retry rebuilt + re-sent a FormData body (not a dropped/consumed one).
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toBeInstanceOf(FormData);
  });

  it("multipart upload: 401 → refresh fails → handleSessionExpired once, no retry", async () => {
    fetchMock.mockResolvedValue(unauthorized());
    refreshTokens.mockResolvedValue(null);

    const { uploadOfficerAttachment } = await import("./api");
    await expect(uploadOfficerAttachment("T-1", A_FILE, "x")).rejects.toThrow("REDIRECT_LOGIN");

    expect(refreshTokens).toHaveBeenCalledTimes(1);
    expect(handleSessionExpired).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1); // no retry when refresh yields nothing
  });

  it("blob GET: 401 → refresh → retry-once → succeeds", async () => {
    const blob = new Blob(["file-bytes"]);
    const queue = [
      unauthorized(),
      { ok: true, status: 200, blob: async () => blob },
    ];
    fetchMock.mockImplementation(async () => queue.shift());
    refreshTokens.mockResolvedValue("fresh-access-token");
    vi.stubGlobal("URL", { createObjectURL: () => "blob:mock-url" });

    const { fetchAuthenticatedBlobUrl } = await import("./api");
    const url = await fetchAuthenticatedBlobUrl("/api/v1/files/1");

    expect(url).toBe("blob:mock-url");
    expect(refreshTokens).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(handleSessionExpired).not.toHaveBeenCalled();
  });
});
