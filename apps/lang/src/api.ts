const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) throw new ApiError("VITE_API_URL is not configured.", 503, "not_configured");
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...init?.headers,
    },
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

export interface StaffUser {
  id: string;
  displayName: string;
  email: string;
  permissions: string[];
  isSuperAdmin: boolean;
}

export interface TranslationResourceRow {
  id: string;
  type: string;
  title: string;
  status: string;
  updatedAt: string;
  fieldCount: number;
  translatedCount: number;
  staleCount: number;
}

export interface TranslationField {
  key: string;
  source: string;
  translation: string;
  status: "missing" | "machine" | "reviewed";
  stale: boolean;
  updatedAt: string | null;
}

export interface TranslationResourceDetail {
  id: string;
  type: string;
  title: string;
  status: string;
  updatedAt: string;
  locale: string;
  fields: TranslationField[];
}

export interface CustomLocale {
  code: string;
  nativeName: string;
  englishName: string;
  direction: "ltr" | "rtl";
  groupName: "indian" | "world";
  active: boolean;
  updatedAt: string;
}

export interface TranslationBatch {
  id: string;
  mode: "content" | "interface";
  resourceType: string | null;
  target: "storefront" | "admin" | null;
  overwriteExisting: boolean;
  status: "queued" | "running" | "completed" | "partial" | "failed";
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  pendingTasks: number;
  translatedStrings: number;
  failures: Array<{ locale: string; message: string }>;
  createdAt: string;
  updatedAt: string;
}

export const languageApi = {
  me: () => request<StaffUser>("/v1/admin/me"),
  login: (email: string, password: string) =>
    request<{ ok: boolean }>("/v1/admin/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: boolean }>("/v1/admin/auth/logout", { method: "POST" }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ ok: boolean }>("/v1/admin/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ currentPassword, newPassword }),
    }),
  resources: (type: string, locale: string, search: string, offset = 0) =>
    request<{ items: TranslationResourceRow[]; total: number; limit: number; offset: number }>(
      `/v1/admin/translation-hub/resources?type=${encodeURIComponent(type)}&locale=${encodeURIComponent(locale)}&search=${encodeURIComponent(search)}&limit=25&offset=${offset}`,
    ),
  resource: (type: string, id: string, locale: string) =>
    request<TranslationResourceDetail>(
      `/v1/admin/translation-hub/resources/${encodeURIComponent(type)}/${encodeURIComponent(id)}?locale=${encodeURIComponent(locale)}`,
    ),
  saveResource: (type: string, id: string, locale: string, translations: Record<string, string>) =>
    request<TranslationResourceDetail>(
      `/v1/admin/translation-hub/resources/${encodeURIComponent(type)}/${encodeURIComponent(id)}?locale=${encodeURIComponent(locale)}`,
      { method: "PUT", body: JSON.stringify({ translations }) },
    ),
  autoTranslateResource: (type: string, id: string, locale: string) =>
    request<TranslationResourceDetail>(
      `/v1/admin/translation-hub/resources/${encodeURIComponent(type)}/${encodeURIComponent(id)}/auto-translate?locale=${encodeURIComponent(locale)}`,
      { method: "POST" },
    ),
  deleteResource: (type: string, id: string, locale: string) =>
    request<{ deleted: boolean }>(
      `/v1/admin/translation-hub/resources/${encodeURIComponent(type)}/${encodeURIComponent(id)}?locale=${encodeURIComponent(locale)}`,
      { method: "DELETE" },
    ),
  interfaceMessages: (locale: string, target: "storefront" | "admin") =>
    request<{ messages: Record<string, string> }>(
      `/v1/admin/translation-hub/interface?locale=${encodeURIComponent(locale)}&target=${target}`,
    ),
  saveInterface: (
    locale: string,
    target: "storefront" | "admin",
    entries: Record<string, { source: string; translation: string }>,
  ) =>
    request<{ messages: Record<string, string> }>(
      `/v1/admin/translation-hub/interface?locale=${encodeURIComponent(locale)}&target=${target}`,
      { method: "PUT", body: JSON.stringify({ entries }) },
    ),
  autoTranslateInterface: (
    locale: string,
    target: "storefront" | "admin",
    entries: Record<string, { source: string; translation: string }>,
  ) =>
    request<{ messages: Record<string, string> }>(
      `/v1/admin/translation-hub/interface/auto-translate?locale=${encodeURIComponent(locale)}&target=${target}`,
      { method: "POST", body: JSON.stringify({ entries }) },
    ),
  createContentBatch: (
    resourceType: string,
    resources: Array<{ resourceId: string; fieldKeys?: string[] }>,
    locales: string[],
    overwriteExisting: boolean,
  ) =>
    request<TranslationBatch>("/v1/admin/translation-hub/batches/content", {
      method: "POST",
      body: JSON.stringify({ resourceType, resources, locales, overwriteExisting }),
    }),
  createInterfaceBatch: (
    target: "storefront" | "admin",
    entries: Record<string, { source: string; translation: string }>,
    locales: string[],
    overwriteExisting: boolean,
  ) =>
    request<TranslationBatch>("/v1/admin/translation-hub/batches/interface", {
      method: "POST",
      body: JSON.stringify({ target, entries, locales, overwriteExisting }),
    }),
  batch: (id: string) => request<TranslationBatch>(`/v1/admin/translation-hub/batches/${id}`),
  locales: () => request<{ items: CustomLocale[] }>("/v1/admin/translation-hub/locales"),
  saveLocale: (locale: Omit<CustomLocale, "updatedAt">) =>
    request<CustomLocale>(`/v1/admin/translation-hub/locales/${encodeURIComponent(locale.code)}`, {
      method: "PUT",
      body: JSON.stringify(locale),
    }),
  deleteLocale: (code: string) =>
    request<{ deleted: boolean }>(`/v1/admin/translation-hub/locales/${encodeURIComponent(code)}`, {
      method: "DELETE",
    }),
};
