const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

export interface StaffUser {
  displayName: string;
  email: string;
  isSuperAdmin: boolean;
  permissions: string[];
}

export interface ReleaseUser {
  id: string;
  displayName: string;
  email: string;
  status: string;
  lastSignInAt: string | null;
}

export interface ReleaseCheck {
  name: string;
  status: string;
  conclusion: string | null;
  url: string | null;
}

export interface ReleaseCommit {
  sha: string;
  message: string;
  author: string;
  authoredAt: string;
  url: string;
}

export interface ReleaseBranch {
  name: "testing" | "staging" | "main";
  environmentUrl: string | null;
  headSha: string;
  ciState: "pending" | "failure" | "success";
  checks: ReleaseCheck[];
  gate: {
    context: string | null;
    state: string;
    description: string | null;
    actor: string | null;
    createdAt?: string | null;
  };
  canPromote: boolean;
  blockedReason: string | null;
  commits: ReleaseCommit[];
}

export interface ReleaseDashboard {
  repository: string;
  canWrite: boolean;
  generatedAt: string;
  branches: ReleaseBranch[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) throw new ApiError("VITE_API_URL is not configured.", 503, "not_configured");
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { ...(init?.body ? { "content-type": "application/json" } : {}), ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string; code?: string };
    } | null;
    throw new ApiError(
      body?.error?.message ?? `Request failed (${response.status}).`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

export const releaseApi = {
  me: () => request<StaffUser>("/v1/admin/me"),
  login: (email: string, password: string) =>
    request<{ ok: boolean }>("/v1/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/v1/admin/auth/logout", { method: "POST" }),
  dashboard: () => request<ReleaseDashboard>("/v1/admin/deployments"),
  verifyStaging: (sha: string, notes: string) =>
    request<{ verified: boolean }>("/v1/admin/deployments/verify-staging", {
      method: "POST",
      body: JSON.stringify({ sha, notes }),
    }),
  promote: (source: "testing" | "staging", target: "staging" | "main", sha: string) =>
    request<{ targetSha: string | null; alreadyCurrent: boolean }>(
      "/v1/admin/deployments/promote",
      { method: "POST", body: JSON.stringify({ source, target, sha }) },
    ),
  users: () => request<{ items: ReleaseUser[] }>("/v1/admin/deployments/users"),
  addUser: (email: string, displayName: string, password: string) =>
    request<{ id: string; email: string }>("/v1/admin/deployments/users", {
      method: "POST",
      body: JSON.stringify({ email, display_name: displayName, password }),
    }),
  deleteUser: (id: string) =>
    request<{ ok: boolean }>(`/v1/admin/deployments/users/${id}`, {
      method: "DELETE",
    }),
  setUserStatus: (id: string, status: string) =>
    request<{ ok: boolean }>(`/v1/admin/deployments/users/${id}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    }),
  resetUserPassword: (id: string, password: string) =>
    request<{ ok: boolean }>(`/v1/admin/deployments/users/${id}/password`, {
      method: "PUT",
      body: JSON.stringify({ password }),
    }),
};
