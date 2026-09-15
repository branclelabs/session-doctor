export type RestoreMode = "safe" | "best-effort";
export type ActivityKind = "backup" | "fix" | "restore" | string;

export interface SessionRow {
  id: string;
  title: string | null;
  pinned: number;
  archived: number;
  hidden: number;
  model: string | null;
  message_count: number | null;
  last_activity_at: number | null;
  parent_session_id: string | null;
  seals_active: number;
  seals_total: number;
  needs_fix: boolean;
  source?: string | null;
  [k: string]: unknown;
}

export interface SessionDetail extends SessionRow {
  active_msgs: number;
  kept_items: number;
  lease: boolean;
  source: string | null;
}

export interface Bundle {
  dir: string;
  session_id: string;
  utc: string;
  seals_total: number;
  active_msgs: number;
  snapshot_bytes: number;
  verified: boolean;
}

export interface ActivityEvent {
  ts: string;
  kind: ActivityKind;
  session: string;
  detail: string;
}

export type Backend = "hermes" | "opencode";

export interface OcSettingsResponse {
  backup_root: string;
  self_session: string;
}

export interface SessionsResponse {
  rows: SessionRow[];
  count: number;
  home: string;
  backup_root: string;
  db_mb: string;
  last_backup: string;
  self_session?: string;
}
export interface BundlesResponse {
  bundles: Bundle[];
}
export interface ActivityResponse {
  events: ActivityEvent[];
}
export interface BackupResponse {
  dir: string;
}
export type FixResponse =
  | { cleared: number; backup: string }
  | { cleared: 0; backup: null; note: "nothing to fix" };
export interface RestoreResponse {
  seals_after: number;
  msgs_after: number;
  stash: string;
  bundle: string;
  mode: RestoreMode;
  warnings: string[];
  skipped_columns: { sessions: string[]; messages: string[] };
}
export interface SettingsResponse {
  backup_root: string;
  requested?: string;
  fallback?: boolean;
}
export interface ApiError {
  error: string;
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8765";

async function api<T>(p: string, init?: { method?: string; body?: unknown }): Promise<T> {
  const r = await fetch(`${API_BASE}${p}`, {
    method: init?.method ?? "GET",
    headers: { "Content-Type": "application/json" },
    body: init?.body ? JSON.stringify(init.body) : undefined,
  });
  const j = (await r.json().catch(() => ({ error: "bad response" }))) as T & ApiError;
  if (!r.ok) throw new Error((j as ApiError).error || `HTTP ${r.status}`);
  return j as T;
}

export const getSessions = () => api<SessionsResponse>("/api/sessions");
export const getSession = (id: string) =>
  api<SessionDetail>(`/api/session?id=${encodeURIComponent(id)}`);
export const getBundles = (session?: string) =>
  api<BundlesResponse>(session ? `/api/bundles?session=${encodeURIComponent(session)}` : "/api/bundles");
export const getActivity = () => api<ActivityResponse>("/api/activity");
export const getHealth = () => api<{ ok: boolean; count: number }>("/api/health");
export const postBackup = (id: string, verify = true) =>
  api<BackupResponse>("/api/backup", { method: "POST", body: { id, verify } });
export const postFix = (id: string, verify = true) =>
  api<FixResponse>("/api/fix", { method: "POST", body: { id, verify } });
export const postRestore = (id: string, dir: string, mode: RestoreMode = "safe") =>
  api<RestoreResponse>("/api/restore", { method: "POST", body: { id, dir, mode } });
export const postSettings = (backup_root: string) =>
  api<SettingsResponse>("/api/settings", { method: "POST", body: { backup_root } });

// ---- OpenCode backend (same contracts, /api/oc/* prefix) ----
const oc = (p: string) => `/api/oc${p}`;
export const ocGetSessions = () => api<SessionsResponse>(oc("/sessions"));
export const ocGetSession = (id: string) =>
  api<SessionDetail>(oc(`/session?id=${encodeURIComponent(id)}`));
export const ocGetBundles = (session?: string) =>
  api<BundlesResponse>(session ? oc(`/bundles?session=${encodeURIComponent(session)}`) : oc("/bundles"));
export const ocPostBackup = (id: string, verify = true) =>
  api<BackupResponse>(oc("/backup"), { method: "POST", body: { id, verify } });
export const ocPostFix = (id: string, verify = true) =>
  api<FixResponse>(oc("/fix"), { method: "POST", body: { id, verify } });
export const ocPostRestore = (id: string, dir: string, mode: RestoreMode = "safe") =>
  api<RestoreResponse>(oc("/restore"), { method: "POST", body: { id, dir, mode } });
export const ocPostSettings = (body: { oc_backup_root?: string; current_session_id?: string }) =>
  api<OcSettingsResponse>(oc("/settings"), { method: "POST", body });

// ---- backend-switched helpers (one call site per feature) ----
export const beGetSessions = (be: Backend) => (be === "opencode" ? ocGetSessions() : getSessions());
export const beGetSession = (be: Backend, id: string) =>
  be === "opencode" ? ocGetSession(id) : getSession(id);
export const beGetBundles = (be: Backend, session?: string) =>
  be === "opencode" ? ocGetBundles(session) : getBundles(session);
export const bePostBackup = (be: Backend, id: string, verify = true) =>
  be === "opencode" ? ocPostBackup(id, verify) : postBackup(id, verify);
export const bePostFix = (be: Backend, id: string, verify = true) =>
  be === "opencode" ? ocPostFix(id, verify) : postFix(id, verify);
export const bePostRestore = (be: Backend, id: string, dir: string, mode: RestoreMode = "safe") =>
  be === "opencode" ? ocPostRestore(id, dir, mode) : postRestore(id, dir, mode);
