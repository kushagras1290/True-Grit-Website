/**
 * Shared browser-side fetch client for the customer-facing API.
 *
 * Every caller here runs from a browser event handler (form submit, button
 * click) — this app has no server `action`/`clientAction` that mutates data
 * through the API (checkout, submissions, and community all post directly
 * from the browser; see customer-auth.tsx's module docstring). That is what
 * makes the module-scoped CSRF token below safe: a Workers isolate serving
 * SSR requests for many different browsers never touches it, so there is no
 * cross-user leakage risk in holding it as plain module state.
 *
 * The session cookie is HttpOnly and issued cross-site (the storefront and
 * API are on different registrable domains), so it carries no CSRF
 * protection on its own — see the API's `auth/dependencies.py`
 * `_enforce_csrf`. The API hands back a CSRF token in the body of every
 * session-creating response (login/register/etc.) and via
 * `GET /v1/public/auth/csrf` for an already-authenticated session (e.g.
 * after a page reload, when this in-memory value is lost).
 */

import { getPublicApiUrl } from "./public-env";

export class AuthError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

let csrfToken: string | null = null;
let csrfTokenPromise: Promise<string | null> | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

async function ensureCsrfToken(apiUrl: string): Promise<string | null> {
  if (csrfToken) return csrfToken;
  if (!csrfTokenPromise) {
    csrfTokenPromise = fetch(`${apiUrl}/v1/public/auth/csrf`, { credentials: "include" })
      .then((response) => (response.ok ? (response.json() as Promise<{ csrfToken?: string }>) : null))
      .then((body) => {
        csrfToken = body?.csrfToken ?? null;
        return csrfToken;
      })
      .catch(() => null)
      .finally(() => {
        csrfTokenPromise = null;
      });
  }
  return csrfTokenPromise;
}

const SAFE_METHODS = new Set(["GET", "HEAD"]);

async function parseErrorBody(response: Response): Promise<ApiErrorBody | null> {
  return (await response.json().catch(() => null)) as ApiErrorBody | null;
}

/**
 * Fetch `path` on the configured API, attaching credentials and — for any
 * non-GET/HEAD request — a CSRF header. On a stale/missing token (the API
 * replies 403 `csrf_invalid`) it fetches a fresh one and retries exactly
 * once before giving up, so an aged in-memory token from a long-lived tab
 * self-heals instead of dead-ending the user's action.
 */
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new AuthError("This action needs the live API.", 503, "demo_mode");
  }
  const method = (init?.method ?? "GET").toUpperCase();
  const isMutating = !SAFE_METHODS.has(method);

  const send = (token: string | null) =>
    fetch(`${apiUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        ...(init?.body ? { "content-type": "application/json" } : {}),
        ...(isMutating && token ? { "x-csrf-token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });

  const token = isMutating ? await ensureCsrfToken(apiUrl) : null;
  let response = await send(token);

  if (isMutating && response.status === 403) {
    const body = await parseErrorBody(response.clone());
    if (body?.error?.code === "csrf_invalid") {
      setCsrfToken(null);
      response = await send(await ensureCsrfToken(apiUrl));
    }
  }

  if (!response.ok) {
    const body = await parseErrorBody(response);
    throw new AuthError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}
