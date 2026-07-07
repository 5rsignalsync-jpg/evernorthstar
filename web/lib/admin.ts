// Admin-only fetchers. All hit /admin/* endpoints that require is_admin=True on
// the current session. If a non-admin user's browser inspector triggers these,
// the backend returns 403; we surface it as a thrown Error so the UI can show
// the message.

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type CompTier = "pro" | "founder_lifetime";

export type CompResult = {
  email: string;
  tier: string;
  action: "promoted" | "already_pro" | "not_found" | "created_placeholder";
  note?: string | null;
};

export type AdminUserSummary = {
  id: number;
  email: string;
  subscription_tier: string;
  subscription_expires_at: string | null;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const j = await res.json();
      msg = typeof j?.detail === "string" ? j.detail : JSON.stringify(j);
    } catch { /* keep status */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function compUser(
  email: string,
  tier: CompTier = "pro",
  note?: string,
): Promise<CompResult> {
  return post<CompResult>("/admin/comp", { email, tier, note });
}

export async function uncompUser(email: string): Promise<CompResult> {
  return post<CompResult>("/admin/uncomp", { email });
}

export async function listAdminUsers(
  limit = 25,
): Promise<AdminUserSummary[]> {
  const res = await fetch(`${BASE}/admin/users?limit=${limit}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Admin users ${res.status}`);
  return res.json();
}
