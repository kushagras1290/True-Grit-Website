/** Shared frontend test helpers. */

/** Deterministic ISO timestamp used across fixtures and assertions. */
export const FIXED_NOW = "2026-07-11T00:00:00Z";

/** Build a fetch stub that returns the given JSON body once. */
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
