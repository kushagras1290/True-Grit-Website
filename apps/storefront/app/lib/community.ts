/**
 * Community discussions client. Reads (list/detail) work for anyone; starting
 * a thread or commenting requires a signed-in customer session.
 *
 * Requires `VITE_API_URL` — like submissions, there is no fixture/demo mode
 * here since this is live, user-generated content rather than catalogue data.
 */

import { AuthError } from "./customer-auth";
import { getPublicApiUrl } from "./public-env";

export interface DiscussionSummary {
  id: string;
  title: string;
  excerpt: string;
  imageUrl: string | null;
  imageAlt: string | null;
  authorName: string;
  commentCount: number;
  lastActivityAt: string;
  createdAt: string;
}

export interface DiscussionComment {
  id: string;
  body: string;
  authorName: string;
  createdAt: string;
}

export interface DiscussionDetail {
  id: string;
  title: string;
  body: string;
  imageUrl: string | null;
  imageAlt: string | null;
  authorName: string;
  commentCount: number;
  lastActivityAt: string;
  createdAt: string;
  comments: DiscussionComment[];
}

export interface CommunitySettings {
  minAccountAgeMonths: number;
}

export interface DiscussionPage {
  items: DiscussionSummary[];
  total: number;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new AuthError("Community needs the live API (set VITE_API_URL).", 503, "demo_mode");
  }
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body
      ? { "content-type": "application/json", ...(init?.headers ?? {}) }
      : init?.headers,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new AuthError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

export function communitySettings(): Promise<CommunitySettings> {
  return request<CommunitySettings>("/v1/public/community/settings");
}

export function listDiscussions(locale: string, limit = 12, offset = 0): Promise<DiscussionPage> {
  return request<DiscussionPage>(
    `/v1/public/community/discussions?limit=${limit}&offset=${offset}&locale=${encodeURIComponent(locale)}`,
  );
}

export function getDiscussion(id: string, locale: string): Promise<DiscussionDetail> {
  return request<DiscussionDetail>(
    `/v1/public/community/discussions/${encodeURIComponent(id)}?locale=${encodeURIComponent(locale)}`,
  );
}

export function createDiscussion(input: { title: string; body: string }): Promise<{ id: string }> {
  return request("/v1/public/community/discussions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createComment(discussionId: string, body: string): Promise<{ id: string }> {
  return request(`/v1/public/community/discussions/${encodeURIComponent(discussionId)}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}
