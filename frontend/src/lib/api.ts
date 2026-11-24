export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const KEY = { token: "gymos.token", refresh: "gymos.refresh", org: "gymos.org" };

function store(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export const auth = {
  get token() { return store()?.getItem(KEY.token) ?? null; },
  get orgId() { return store()?.getItem(KEY.org) ?? null; },
  set(tokens: { access_token: string; refresh_token: string }) {
    store()?.setItem(KEY.token, tokens.access_token);
    store()?.setItem(KEY.refresh, tokens.refresh_token);
  },
  setOrg(id: number | string) { store()?.setItem(KEY.org, String(id)); },
  clear() { Object.values(KEY).forEach((k) => store()?.removeItem(k)); },
};

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(ApiError.message(detail));
  }
  get code(): string | undefined {
    return typeof this.detail === "object" && this.detail ? (this.detail as { code?: string }).code : undefined;
  }
  static message(detail: unknown): string {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(", ");
    if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: string }).message);
    return "Something went wrong";
  }
}

async function refreshToken(): Promise<boolean> {
  const rt = store()?.getItem(KEY.refresh);
  if (!rt) return false;
  const r = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }),
  });
  if (!r.ok) return false;
  auth.set(await r.json());
  return true;
}

type Opts = { method?: string; body?: unknown; org?: boolean; raw?: boolean; params?: Record<string, unknown> };

export async function api<T = any>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  if (opts.org !== false && auth.orgId) headers["X-Org-Id"] = auth.orgId;
  const qs = opts.params
    ? "?" + new URLSearchParams(Object.entries(opts.params).filter(([, v]) => v !== undefined && v !== "" && v !== null)
        .map(([k, v]) => [k, String(v)])).toString()
    : "";
  const r = await fetch(`${API_URL}${path}${qs}`, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (r.status === 401 && !retried && (await refreshToken())) return api<T>(path, opts, true);
  if (!r.ok) {
    let detail: unknown = r.statusText;
    try { detail = (await r.json()).detail; } catch { /* non-json */ }
    throw new ApiError(r.status, detail);
  }
  if (opts.raw) return (await r.blob()) as T;
  return r.status === 204 ? (undefined as T) : r.json();
}

export const inr = (n: number | string | null | undefined) =>
  "₹" + Number(n ?? 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

export const fmtDate = (d?: string | null) =>
  d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const fmtTime = (d?: string | null) =>
  d ? new Date(d).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "—";

/** Open an authenticated HTML/PNG endpoint (receipt, QR poster) in a new tab. */
export async function openAuthed(path: string, download?: string) {
  const blob = await api<Blob>(path, { raw: true });
  const url = URL.createObjectURL(blob);
  if (download) {
    const a = document.createElement("a");
    a.href = url; a.download = download; a.click();
  } else {
    window.open(url, "_blank", "noopener");
  }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
