/**
 * Community discussions client. Reads (list/detail) work for anyone; starting
 * a thread or commenting requires a signed-in customer session.
 *
 * Requires `VITE_API_URL` — like submissions, there is no fixture/demo mode
 * here since this is live, user-generated content rather than catalogue data.
 */

import { apiRequest as request, AuthError } from "./api-client";

export interface DiscussionSummary {
  id: string;
  title: string;
  excerpt: string;
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
  authorName: string;
  commentCount: number;
  lastActivityAt: string;
  createdAt: string;
  comments: DiscussionComment[];
}

export interface CommunitySettings {
  minAccountAgeMonths: number;
}


export function communitySettings(): Promise<CommunitySettings> {
  return request<CommunitySettings>("/v1/public/community/settings");
}

export function listDiscussions(limit = 30, offset = 0): Promise<DiscussionSummary[]> {
  return request<{ items: DiscussionSummary[] }>(
    `/v1/public/community/discussions?limit=${limit}&offset=${offset}`,
  ).then((body) => body.items);
}

export function getDiscussion(id: string): Promise<DiscussionDetail> {
  return request<DiscussionDetail>(`/v1/public/community/discussions/${encodeURIComponent(id)}`);
}

export function createDiscussion(input: { title: string; body: string }): Promise<{ id: string }> {
  return request("/v1/public/community/discussions", { method: "POST", body: JSON.stringify(input) });
}

export function createComment(discussionId: string, body: string): Promise<{ id: string }> {
  return request(`/v1/public/community/discussions/${encodeURIComponent(discussionId)}/comments`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}
