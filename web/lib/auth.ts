/**
 * Auth client. All requests must use `credentials: "include"` so the
 * httpOnly session cookie travels with cross-origin requests in dev
 * (Next.js on :3000 → FastAPI on :8000). The backend's CORS config
 * sets `allow_credentials=true` to match.
 */

export type AuthUser = {
  id: number;
  email: string;
  subscription_tier: "free" | "pro" | "founder_lifetime";
  subscription_expires_at: string | null;
  is_pro: boolean;
  is_admin: boolean;
  daily_digest_opt_in: boolean;
};

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/**
 * Extract a human-readable error message from a FastAPI error response.
 *
 * FastAPI returns two shapes for `detail`:
 *   - `detail: "Email already registered"` (HTTPException) — plain string
 *   - `detail: [{loc, msg, type, input}, ...]` (422 Pydantic validation)  — array
 *
 * Falling back to `JSON.stringify(detail)` for an array gave us literal
 * "[object Object]" rendered in the UI. Now we extract the field + message
 * from each entry so users see "email: value is not a valid email address".
 */
function extractErrorMessage(body: unknown, status: number): string {
  if (!body || typeof body !== "object") return `${status}`;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: { msg?: string; loc?: (string | number)[] }) => {
        const field = e.loc && e.loc.length > 0 ? String(e.loc[e.loc.length - 1]) : "field";
        return `${field}: ${e.msg ?? "invalid"}`;
      })
      .join("; ");
  }
  return `${status}`;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      msg = extractErrorMessage(await res.json(), res.status);
    } catch {
      /* ignore — keep status code as fallback */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function register(email: string, password: string): Promise<AuthUser> {
  return postJSON<AuthUser>("/auth/register", { email, password });
}

export async function login(email: string, password: string): Promise<AuthUser> {
  return postJSON<AuthUser>("/auth/login", { email, password });
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
}

export async function fetchMe(): Promise<AuthUser | null> {
  const res = await fetch(`${BASE}/auth/me`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data ?? null;
}

/**
 * Update user preferences (currently just the daily-digest opt-in).
 * Returns the refreshed user. Throws on auth failure or server error so
 * the caller can revert the optimistic toggle.
 */
export async function updatePrefs(
  patch: { daily_digest_opt_in?: boolean },
): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/me/prefs`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      msg = extractErrorMessage(await res.json(), res.status);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

/** Opens the Stripe Customer Portal for self-service subscription management. */
export async function openBillingPortal(): Promise<string> {
  const res = await fetch(`${BASE}/billing/portal-session`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      msg = extractErrorMessage(await res.json(), res.status);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const data = await res.json();
  return data.url as string;
}
