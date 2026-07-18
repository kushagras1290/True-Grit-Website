/**
 * Community blog/recipe submissions client: signed-in customers pitch a post
 * or recipe and track its review status.
 *
 * Requires `VITE_API_URL` (there is no fixture/demo mode for submissions —
 * this is account-scoped, customer-authored content, not public catalogue
 * data, matching how order history and returns are only ever live-fetched).
 */

import { apiRequest as request, AuthError } from "./api-client";

export type SubmissionContentType = "article" | "recipe";

export type SubmissionStatus =
  | "submitted"
  | "under_review"
  | "changes_requested"
  | "approved"
  | "rejected";

export interface SubmissionIngredientInput {
  label: string;
  quantityText: string;
}

export interface SubmissionInput {
  contentType: SubmissionContentType;
  contactName: string;
  contactEmail: string;
  contactPhone?: string;
  title: string;
  excerpt?: string;
  body: string;
  prepMinutes?: number;
  cookMinutes?: number;
  servings?: number;
  dietaryTags?: string[];
  ingredients?: SubmissionIngredientInput[];
  steps?: string[];
}

export interface SubmissionDetail extends SubmissionInput {
  id: string;
  status: SubmissionStatus;
  reviewerNotes: string | null;
  createdAt: string;
  updatedAt: string;
  publishedArticleId: string | null;
  publishedRecipeId: string | null;
}

export function createSubmission(input: SubmissionInput): Promise<{ id: string; status: string }> {
  return request("/v1/public/submissions", { method: "POST", body: JSON.stringify(input) });
}

export function listMySubmissions(): Promise<SubmissionDetail[]> {
  return request<{ items: SubmissionDetail[] }>("/v1/public/submissions").then((body) => body.items);
}

export function getMySubmission(id: string): Promise<SubmissionDetail> {
  return request<SubmissionDetail>(`/v1/public/submissions/${encodeURIComponent(id)}`);
}

export function updateSubmission(
  id: string,
  input: SubmissionInput,
): Promise<{ id: string; status: string }> {
  return request(`/v1/public/submissions/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
