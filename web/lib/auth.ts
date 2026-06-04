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
};

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
      const j = await res.json();
      msg = j?.detail ?? msg;
    } catch {
      /* ignore */
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
      const j = await res.json();
      msg = j?.detail ?? msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const data = await res.json();
  return data.url as string;
}
