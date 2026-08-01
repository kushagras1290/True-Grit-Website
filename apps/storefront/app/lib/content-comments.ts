/**
 * Reader comments on blog posts and recipes.
 *
 * Reads are public; posting needs a signed-in customer. Fetched from the
 * browser rather than in the route loader on purpose: a comment thread is
 * live, per-visitor state that changes far faster than the article around it,
 * and loading it server-side would tie the article's cacheability to it.
 */

import { AuthError } from "./customer-auth";
import { getPublicApiUrl } from "./public-env";

export type CommentContentType = "article" | "recipe";

export interface ContentComment {
  id: string;
  body: string;
  authorName: string;
  createdAt: string;
}

export interface ContentCommentThread {
  items: ContentComment[];
  total: number;
  /** False when the owner has closed commenting. The existing thread is still
   *  returned — closing stops new comments, it does not erase the old ones. */
  enabled: boolean;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new AuthError("Comments need the live API (set VITE_API_URL).", 503, "demo_mode");
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

function threadPath(contentType: CommentContentType, slug: string): string {
  return `/v1/public/content/${contentType}/${encodeURIComponent(slug)}/comments`;
}

export function listContentComments(
  contentType: CommentContentType,
  slug: string,
): Promise<ContentCommentThread> {
  return request<ContentCommentThread>(threadPath(contentType, slug));
}

export function postContentComment(
  contentType: CommentContentType,
  slug: string,
  body: string,
): Promise<{ id: string }> {
  return request(threadPath(contentType, slug), {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}
