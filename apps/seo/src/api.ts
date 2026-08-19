/**
 * API client for the SEO dashboard.
 *
 * Same shape as `apps/process/src/api.ts`: a bare `fetch` against the main
 * API with `credentials: "include"`, so the dashboard rides the same staff
 * session cookie every other admin surface uses. There is no separate
 * authentication for this app -- "password protected" means a real staff
 * account with the `seo.manage` permission, checked server-side on every
 * request, not a shared secret held by this Worker.
 */

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

export type UserStatus = "invited" | "active" | "disabled";

export interface AdminUser {
  id: string;
  displayName: string;
  email: string;
  status: UserStatus;
  roles: string[];
  roleIds?: string[];
  lastSignInAt: string | null;
}

export interface AdminRole {
  id: string;
  key: string;
  name: string;
  description: string;
  isSystem: boolean;
  locked: boolean;
  permissionIds: string[];
  permissionKeys: string[];
}

export type RunStatus = "queued" | "running" | "completed" | "failed";

export interface CrawlRun {
  id: string;
  status: RunStatus;
  trigger: "cron" | "manual";
  baseUrl: string;
  queuedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  pagesDiscovered: number;
  pagesCrawled: number;
  pagesFailed: number;
  findingsOpened: number;
  findingsClosed: number;
  error: string | null;
}

export type FindingCategory = "schema" | "eeat" | "links" | "indexing" | "content";
export type FindingStatus = "open" | "fixed" | "ignored";

export interface Finding {
  id: string;
  rule: string;
  category: FindingCategory;
  severity: "critical" | "high" | "medium" | "low";
  path: string;
  pageType: string;
  summary: string;
  detail: string;
  fixHint: string;
  status: FindingStatus;
  firstSeenAt: string;
  lastSeenAt: string;
}

/** A phrase competitors invest more in than we do. `gapScore` reflects
 *  editorial placement (titles, headings) observed by the crawl -- never a
 *  ranking or a search volume, since neither is visible from outside a site
 *  we do not own. */
export interface KeywordGap {
  term: string;
  termWords: number;
  ownPages: number;
  ownTitleHits: number;
  competitorPages: number;
  competitorTitleHits: number;
  competitorCount: number;
  gapScore: number;
}

export interface ContentGap {
  pageType: string;
  heading: string;
  headingKey: string;
  competitorCount: number;
  occurrences: number;
}

export interface Competitor {
  id: string;
  label: string;
  origin: string;
  status: "active" | "paused";
  robotsBlocked: boolean;
  lastCrawledAt: string | null;
  lastError: string | null;
  notes: string | null;
}

export type ProposalField = "seo_title" | "seo_description" | "seo_keywords" | "indexing_policy";
export type ProposalStatus = "pending" | "applied" | "rejected" | "superseded" | "reverted";

export interface Proposal {
  id: string;
  entityType: "product" | "article" | "recipe" | "category" | "page" | "route";
  entityId: string;
  entityLabel: string;
  path: string;
  field: ProposalField;
  currentValue: string;
  proposedValue: string;
  rationale: string;
  source: "gap" | "finding";
  sourceRef: string;
  confidence: number;
  status: ProposalStatus;
  createdAt: string;
  appliedAt: string | null;
}

export interface Summary {
  settings: { enabled: boolean; maxPages: number; competitorMaxPages: number };
  counts: {
    openBySeverity: Record<string, number>;
    openByCategory: Record<string, number>;
    pendingProposals: number;
    appliedProposals: number;
  };
  runs: CrawlRun[];
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const seoApi = {
  me: () => request<StaffUser>("/v1/admin/me"),
  login: (email: string, password: string) =>
    request<{ ok: boolean }>("/v1/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/v1/admin/auth/logout", { method: "POST" }),

  users: ({
    limit = 50,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}) => {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (search) query.set("search", search);
    return request<{ items: AdminUser[] }>(`/v1/admin/users?${query}`).then((body) => body.items);
  },
  roles: () => request<{ items: AdminRole[] }>("/v1/admin/roles").then((body) => body.items),
  setUserStatus: (id: string, status: UserStatus) =>
    request<{ id: string; status: UserStatus }>(`/v1/admin/users/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  setUserRoles: (id: string, roleIds: string[]) =>
    request<{ id: string }>(`/v1/admin/users/${id}/roles`, {
      method: "PATCH",
      body: JSON.stringify({ roleIds }),
    }),
  sendUserPasswordReset: (id: string) =>
    request<{ id: string; email: string; emailSent: boolean; emailTransport: string }>(
      `/v1/admin/users/${id}/password-reset-email`,
      { method: "POST" },
    ),

  summary: () => request<Summary>("/v1/admin/seo/summary"),
  setEnabled: (enabled: boolean) =>
    request<{ enabled: boolean }>("/v1/admin/seo/settings", {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),

  runs: (limit = 20) => request<CrawlRun[]>(`/v1/admin/seo/runs?limit=${limit}`),
  queueRun: () => request<{ id: string; status: string }>("/v1/admin/seo/runs", { method: "POST" }),

  findings: (
    params: { status?: FindingStatus; category?: FindingCategory; limit?: number } = {},
  ) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.category) query.set("category", params.category);
    query.set("limit", String(params.limit ?? 100));
    return request<{ total: number; items: Finding[] }>(`/v1/admin/seo/findings?${query}`);
  },
  setFindingStatus: (id: string, status: FindingStatus) =>
    request<{ id: string; status: FindingStatus }>(`/v1/admin/seo/findings/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  keywords: (limit = 100) => request<KeywordGap[]>(`/v1/admin/seo/keywords?limit=${limit}`),
  contentGaps: (limit = 60) => request<ContentGap[]>(`/v1/admin/seo/content-gaps?limit=${limit}`),

  competitors: () => request<Competitor[]>("/v1/admin/seo/competitors"),
  addCompetitor: (label: string, origin: string) =>
    request<Competitor>("/v1/admin/seo/competitors", {
      method: "POST",
      body: JSON.stringify({ label, origin }),
    }),
  removeCompetitor: (id: string) =>
    request<{ id: string }>(`/v1/admin/seo/competitors/${id}`, { method: "DELETE" }),

  proposals: (status: ProposalStatus = "pending", limit = 200) =>
    request<{ total: number; items: Proposal[] }>(
      `/v1/admin/seo/proposals?status=${status}&limit=${limit}`,
    ),
  applyProposal: (id: string) =>
    request<{ id: string; status: string }>(`/v1/admin/seo/proposals/${id}/apply`, {
      method: "POST",
    }),
  rejectProposal: (id: string) =>
    request<{ id: string; status: string }>(`/v1/admin/seo/proposals/${id}/reject`, {
      method: "POST",
    }),
  revertProposal: (id: string) =>
    request<{ id: string; status: string }>(`/v1/admin/seo/proposals/${id}/revert`, {
      method: "POST",
    }),
  applyAll: (proposalIds?: string[]) =>
    request<{ attempted: number; applied: number; failed: Array<{ id: string; reason: string }> }>(
      "/v1/admin/seo/proposals/apply",
      { method: "POST", body: JSON.stringify({ proposalIds: proposalIds ?? null }) },
    ),
};
