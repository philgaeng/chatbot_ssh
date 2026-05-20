import type { AuthTokens } from "./token-storage";

export interface ApiErrorDetail {
  code?: string;
  message?: string;
}

export class AuthApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function parseAuthError(resp: Response): Promise<AuthApiError> {
  try {
    const body = (await resp.json()) as { detail?: ApiErrorDetail | string };
    const detail = body.detail;
    if (detail && typeof detail === "object") {
      return new AuthApiError(
        detail.code ?? "login_failed",
        detail.message ?? "Sign-in failed.",
        resp.status,
      );
    }
    if (typeof detail === "string") {
      return new AuthApiError("login_failed", detail, resp.status);
    }
  } catch {
    /* ignore */
  }
  return new AuthApiError("login_failed", "Sign-in failed.", resp.status);
}

export async function loginWithPasswordApi(email: string, password: string): Promise<AuthTokens> {
  const resp = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) throw await parseAuthError(resp);
  return resp.json() as Promise<AuthTokens>;
}

export async function requestPasswordResetApi(email: string): Promise<string> {
  const resp = await fetch("/api/v1/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      redirect_base: window.location.origin,
    }),
  });
  if (!resp.ok) throw await parseAuthError(resp);
  const data = (await resp.json()) as { message: string };
  return data.message;
}

export async function resetPasswordApi(token: string, password: string): Promise<string> {
  const resp = await fetch("/api/v1/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
  if (!resp.ok) throw await parseAuthError(resp);
  const data = (await resp.json()) as { message: string };
  return data.message;
}
