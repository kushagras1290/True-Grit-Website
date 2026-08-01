/**
 * Farm partnership applications client.
 *
 * Unlike submissions and community, this one is deliberately **unauthenticated**
 * — a grower applying to supply the market is not yet a customer. The fetch
 * still sends credentials, because a visitor who happens to be signed in should
 * have their application attributed to their account; the API treats the
 * session as optional context, never as a requirement.
 */

import { getPublicApiUrl } from "./public-env";

export interface FarmPartnershipInput {
  contactName: string;
  contactEmail: string;
  contactPhone: string;
  farmName: string;
  region: string;
  state?: string;
  city?: string;
  pincode?: string;
  establishedYear?: number;
  landAreaAcres?: string;
  certification?: string;
  primaryProduce?: string;
  farmingPractices?: string;
  websiteUrl?: string;
  message: string;
}

export interface FarmPartnershipResult {
  id: string;
  status: string;
}

/** Carries the API's own message through to the form.
 *
 * The API validates every field with a message written for the applicant
 * ("Enter a valid 10-digit Indian mobile number…"), and that is far more use
 * than a generic failure. `code` lets the form tell a closed intake (403) and a
 * duplicate flood (429) apart from a bad field. */
export class FarmPartnershipError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "FarmPartnershipError";
  }
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new FarmPartnershipError(
      "Farm applications need the live API (set VITE_API_URL).",
      503,
      "demo_mode",
    );
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
    throw new FarmPartnershipError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

export function submitFarmPartnership(input: FarmPartnershipInput): Promise<FarmPartnershipResult> {
  return request("/v1/public/farm-partnerships", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Whether the storefront should render the form at all.
 *
 * Resolves to `true` when the API cannot be reached, matching how every other
 * storefront switch degrades: an unreachable settings endpoint must not present
 * "we are closed" to a grower when we are, in fact, open.
 */
export function farmPartnershipsEnabled(): Promise<boolean> {
  return request<{ enabled: boolean }>("/v1/public/farm-partnerships/settings")
    .then((body) => body.enabled !== false)
    .catch(() => true);
}
