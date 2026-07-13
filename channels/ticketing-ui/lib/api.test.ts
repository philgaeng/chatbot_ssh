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
  isSessionExpiredResponse: () => false,
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
